import os
import requests

API_URL = os.getenv("DOMAIN_API_URL", "http://localhost:8000")
API_KEY = os.getenv("DOMAIN_API_KEY")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}


def post(path: str, payload=None):
    resp = requests.post(f"{API_URL}{path}", json=payload, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def run_test_flow(initial_brief: str, answer_map: dict):
    data = post("/sessions", {"initial_brief": initial_brief})
    sid = data["session_id"]
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


if __name__ == "__main__":
    result = run_test_flow("demo business", {})
    print(result)
