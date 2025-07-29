import logging
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

log = logging.getLogger("domain-agent.api")

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field

import settings
from store import SessionStore
from agents import (
    QuestionAgent,
    RefinementQuestionAgent,
    PromptSynthesizerAgent,
    CreatorAgent,
    CheckerAgent,
    DirectionistAgent,
)

app = FastAPI()

API_KEY = settings.API_KEY

store = SessionStore()

question_agent = QuestionAgent()
refinement_question_agent = RefinementQuestionAgent()
prompt_synthesizer = PromptSynthesizerAgent()
creator_agent = CreatorAgent()
checker_agent = CheckerAgent()
directionist_agent = DirectionistAgent()

# In-memory session cache
session_state: Dict[str, Dict] = {}


def verify_key(x_api_key: str = Header(...)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


class StartSessionIn(BaseModel):
    initial_brief: str


class Question(BaseModel):
    id: str
    text: str

class StartSessionOut(BaseModel):
    session_id: str
    questions: List[Question]


class AnswerIn(BaseModel):
    answers: Dict[str, str]
    liked_domains: Optional[Dict[str, str]] = None
    disliked_domains: Optional[Dict[str, str]] = None

class AnswerOut(BaseModel):
    available: Dict[str, str]
    taken: Dict[str, str]
    next_questions: Optional[List[Question]] = None


class PromptOut(BaseModel):
    prompt: str


class SuggestionsOut(BaseModel):
    available: List[str]
    taken: List[str]
    history: Dict[str, Dict]


class SessionSettingsIn(BaseModel):
    """Per-session configuration overrides."""
    local_dev: bool = False
    active_creators: List[str] = Field(default_factory=lambda: ["A", "B", "C"])
    generation_count: int = 1
    domain_goal: int = settings.MIN_AVAILABLE_DOMAINS
    show_logs: bool = settings.SHOW_LOGS


class FeedbackIn(BaseModel):
    liked: Optional[Dict[str, str]] = None
    disliked: Optional[Dict[str, str]] = None


class RefinementOut(BaseModel):
    refined_brief: str
    questions: List[Question]




@app.post("/sessions", response_model=StartSessionOut)
def start_session(payload: StartSessionIn, _=Depends(verify_key)):
    sid = store.new()
    questions = question_agent.ask(payload.initial_brief)
    qmap = {q["id"]: q["text"] for q in questions}
    session_state[sid] = {
        "brief": payload.initial_brief,
        "loop": 1,
        "question_map": qmap,
    }
    store.set_question_map(sid, qmap)
    return {"session_id": sid, "questions": questions}


@app.post("/sessions/{sid}/settings")
def configure_session(sid: str, payload: SessionSettingsIn, _=Depends(verify_key)):
    state = session_state.get(sid)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state["settings"] = payload.dict()
    return {"settings": state["settings"]}


@app.post("/sessions/{sid}/answers", response_model=PromptOut)
def submit_answers(sid: str, payload: AnswerIn, _=Depends(verify_key)):
    state = session_state.get(sid)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    qmap = state.get("question_map", {})
    prompt = prompt_synthesizer.synthesize(state["brief"], payload.answers, qmap)
    state["prompt"] = prompt
    state["answers"] = payload.answers
    return {"prompt": prompt}


@app.post("/sessions/{sid}/generate", response_model=SuggestionsOut)
async def generate_suggestions(sid: str, _=Depends(verify_key)):
    state = session_state.get(sid)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    if not state.get("prompt"):
        raise HTTPException(status_code=400, detail="No prompt. Submit answers first")

    cfg = state.get("settings", {})
    desired = cfg.get("domain_goal", settings.MIN_AVAILABLE_DOMAINS)
    max_attempts = settings.MAX_GENERATION_ATTEMPTS
    counts = {}
    active = set(cfg.get("active_creators", ["A", "B", "C"]))
    for tag in ["A", "B", "C"]:
        counts[tag] = cfg.get("generation_count", 1) if tag in active else 0

    available, taken = {}, {}
    attempts = 0

    while len(available) < desired and attempts < max_attempts:
        attempts += 1
        log.info(f"Generation attempt {attempts} for session {sid}")
        ideas = creator_agent.create(state["prompt"], store.seen(sid), counts)
        store.add(sid, list(ideas.keys()))
        avail_batch, taken_batch = checker_agent.filter_available(ideas)
        if taken_batch:
            log.info("Taken domains: %s", ", ".join(taken_batch.keys()))
        available.update(avail_batch)
        taken.update(taken_batch)
        store.record_results(sid, avail_batch, taken_batch)

    state["available"] = available
    state["taken"] = taken
    return {
        "available": list(available.keys()),
        "taken": list(taken.keys()),
        "history": store.history(sid),
    }


@app.post("/sessions/{sid}/feedback", response_model=RefinementOut)
def give_feedback(sid: str, payload: FeedbackIn, _=Depends(verify_key)):
    state = session_state.get(sid)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    liked = payload.liked or {}
    disliked = payload.disliked or {}
    new_brief, summary = directionist_agent.refine_brief(
        state["brief"], liked, list(state.get("taken", {}).keys()), disliked
    )
    state["brief"] = new_brief
    state["loop"] = state.get("loop", 1) + 1
    questions = refinement_question_agent.ask(new_brief, summary)
    qmap = {q["id"]: q["text"] for q in questions}
    state["question_map"] = qmap
    store.set_question_map(sid, qmap)
    # Clear prompt and suggestions for next loop
    state.pop("prompt", None)
    state.pop("available", None)
    state.pop("taken", None)
    return {"refined_brief": new_brief, "questions": questions}


@app.get("/sessions/{sid}/state")
def get_state(sid: str, _=Depends(verify_key)):
    state = session_state.get(sid)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state_copy = dict(state)
    state_copy["history"] = store.history(sid)
    return state_copy


