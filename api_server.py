import logging
import os
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Dict, List, Optional

load_dotenv()

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

session_meta: Dict[str, dict] = {}


def verify_key(x_api_key: str = Header(...)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


class StartRequest(BaseModel):
    brief: str


class StartResponse(BaseModel):
    session_id: str
    questions: List[str]


class AnswerRequest(BaseModel):
    answers: Dict[str, str]
    liked_domains: Optional[Dict[str, str]] = None
    dislike_reason: Optional[str] = None


class AnswerResponse(BaseModel):
    available: Dict[str, str]
    taken: Dict[str, str]
    next_questions: List[str]


@app.post("/session/start", response_model=StartResponse)
def start(req: StartRequest, _=Depends(verify_key)):
    sid = store.new()
    meta = {
        "initial_brief": req.brief,
        "current_brief": req.brief,
        "last_feedback_summary": "",
        "loop_count": 1,
        "last_taken_domains": [],
    }
    questions = question_agent.ask(req.brief)
    meta["last_questions"] = questions
    session_meta[sid] = meta
    return StartResponse(session_id=sid, questions=questions)


@app.post("/session/{session_id}/answer", response_model=AnswerResponse)
def answer(session_id: str, req: AnswerRequest, _=Depends(verify_key)):
    if session_id not in session_meta:
        raise HTTPException(status_code=404, detail="Session not found")

    meta = session_meta[session_id]

    # Refine brief using feedback from previous loop
    liked = req.liked_domains or {}
    dislike = req.dislike_reason
    new_brief, summary = directionist_agent.refine_brief(
        meta["current_brief"], liked, meta["last_taken_domains"], dislike
    )
    meta["current_brief"] = new_brief
    meta["last_feedback_summary"] = summary

    final_prompt = prompt_synthesizer.synthesize(new_brief, req.answers)
    ideas = creator_agent.create(final_prompt, store.seen(session_id))
    store.add(session_id, list(ideas.keys()))

    if ideas:
        available, taken = checker_agent.filter_available(ideas)
    else:
        available, taken = {}, {}

    if not available:
        meta["failures"] = meta.get("failures", 0) + 1
        if meta["failures"] >= settings.MAX_LOOP_FAILURES:
            raise HTTPException(status_code=400, detail="Too many failures")
    else:
        meta["failures"] = 0

    meta["last_taken_domains"] = list(taken.keys())
    meta["loop_count"] += 1

    questions = refinement_question_agent.ask(new_brief, summary)
    meta["last_questions"] = questions

    return AnswerResponse(available=available, taken=taken, next_questions=questions)
