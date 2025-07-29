import os
import requests

API_URL = os.getenv("DOMAIN_API_URL", "http://localhost:8000")
API_KEY = os.getenv("DOMAIN_API_KEY")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}


def post(path: str, payload=None):
    resp = requests.post(f"{API_URL}{path}", json=payload, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def ask_questions(questions):
    answers = {}
    for q in questions:
        ans = input(f"{q['text']} ") or ""
        answers[q['id']] = ans
    return answers


def run_test_flow(initial_brief: str, session_settings: dict):
    data = post("/sessions", {"initial_brief": initial_brief})
    sid = data["session_id"]
    post(f"/sessions/{sid}/settings", session_settings)
    questions = data["questions"]
    show_logs = session_settings.get("show_logs", True)

    while True:
        answers = ask_questions(questions)
        prompt = post(f"/sessions/{sid}/answers", {"answers": answers})["prompt"]
        if show_logs:
            print("\nPrompt:\n" + prompt)

        gen = post(f"/sessions/{sid}/generate")
        print("\nAvailable:")
        for d in gen["available"]:
            print(" -", d)
        if show_logs:
            print("Taken:")
            for d in gen["taken"]:
                print(" -", d)

        cont = input("Continue? (y/N) ").strip().lower()
        if cont != "y":
            break

        liked, disliked = {}, {}
        for d in gen["available"]:
            like = input(f"Do you like '{d}'? (y/N) ").strip().lower()
            reason = input("  Reason? ") or ""
            if like == "y":
                liked[d] = reason
            else:
                disliked[d] = reason

        fb = post(f"/sessions/{sid}/feedback", {"liked": liked, "disliked": disliked})
        if show_logs:
            print("\nRefined Brief:\n" + fb["refined_brief"])
        questions = fb["questions"]



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
    run_test_flow(brief, cfg)
