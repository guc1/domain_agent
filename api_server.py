import os
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from dotenv import load_dotenv

from agents import PromptSynthesizerAgent, CreatorAgent, CheckerAgent

load_dotenv()

API_KEY = os.getenv("DOMAIN_AGENT_API_KEY")

app = FastAPI(title="Domain Checker AI")

class GenerateRequest(BaseModel):
    brief: str
    answers: Dict[str, str] | None = None

class DomainResponse(BaseModel):
    available: Dict[str, str]
    taken: Dict[str, str]


def verify_api_key(x_api_key: str = Header(...)) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.post("/generate-domains", response_model=DomainResponse)
async def generate_domains(payload: GenerateRequest, _auth: Any = Depends(verify_api_key)):
    synthesizer = PromptSynthesizerAgent()
    creator = CreatorAgent()
    checker = CheckerAgent()

    answers = payload.answers or {}
    final_prompt = synthesizer.synthesize(payload.brief, answers)
    ideas = creator.create(final_prompt, set())
    available, taken = checker.filter_available(ideas)
    return {"available": available, "taken": taken}
