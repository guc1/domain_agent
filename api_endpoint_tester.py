import os
import requests

API_URL = os.getenv("DOMAIN_API_URL", "http://localhost:8000")
API_KEY = os.getenv("DOMAIN_API_KEY")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}


def post(path: str, payload=None):
    resp = requests.post(f"{API_URL}{path}", json=payload, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def run_test_flow(initial_brief: str, answer_map: dict, session_settings: dict):
    data = post("/sessions", {"initial_brief": initial_brief})
    sid = data["session_id"]
    post(f"/sessions/{sid}/settings", session_settings)
    questions = data["questions"]

    # Answer initial questions
    answers = {q["id"]: answer_map.get(q["id"], "") for q in questions}
    prompt = post(f"/sessions/{sid}/answers", {"answers": answers})["prompt"]

    # Generate once
    suggestions = post(f"/sessions/{sid}/generate")

    # Provide empty feedback just for demonstration
    fb = post(f"/sessions/{sid}/feedback", {"liked": {}, "disliked": {}})
    follow_up = {q["id"]: answer_map.get(q["id"], "") for q in fb["questions"]}
    post(f"/sessions/{sid}/answers", {"answers": follow_up})

    return {
        "prompt": prompt,
        "available": suggestions["available"],
        "taken": suggestions["taken"],
    }


def prompt_for_settings() -> dict:
    local_dev = input("Use local dev mode? (y/N) ").strip().lower() == "y"
    creators = input("Creators to use [A,B,C]: ").strip().upper()
    active = [c.strip() for c in creators.split(',') if c.strip()] or ["A", "B", "C"]
    gen_count = int(input("Generation count per creator [1]: ") or "1")
    domain_goal = int(input("Desired available domains [3]: ") or "3")
    show_logs = input("Show logs? (y/N) ").strip().lower() == "y"
    return {
        "local_dev": local_dev,
        "active_creators": active,
        "generation_count": gen_count,
        "domain_goal": domain_goal,
        "show_logs": show_logs,
    }


if __name__ == "__main__":
    cfg = prompt_for_settings()
    brief = input("Describe the business or project: ")
    result = run_test_flow(brief, {}, cfg)
    print(result)
