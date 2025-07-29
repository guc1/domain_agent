import os
import requests

API_URL = os.getenv("DOMAIN_API_URL", "http://localhost:8000")
API_KEY = os.getenv("DOMAIN_API_KEY")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

# Toggle whether verbose logs (prompt, taken domains, etc.) should be displayed
SHOW_LOGS = os.getenv("SHOW_LOGS", "1") != "0"


def post(path: str, payload=None):
    url = f"{API_URL}{path}"
    resp = requests.post(url, json=payload, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def ask_questions(questions):
    answers = {}
    for q in questions:
        ans = input(f"{q['text']} ") or ""
        answers[q['id']] = ans
    return answers


def main():
    brief = input("Describe the business or project: ")
    data = post("/sessions", {"initial_brief": brief})
    session_id = data["session_id"]
    questions = data["questions"]
    prompt = None

    while True:
        answers = ask_questions(questions)
        ans_out = post(f"/sessions/{session_id}/answers", {"answers": answers})
        prompt = ans_out["prompt"]
        if SHOW_LOGS:
            print("\nPrompt:\n" + prompt)

        gen = post(f"/sessions/{session_id}/generate")
        print("\nAvailable:")
        for d in gen["available"]:
            print(" -", d)
        if SHOW_LOGS:
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

        fb = post(
            f"/sessions/{session_id}/feedback",
            {"liked": liked, "disliked": disliked},
        )
        if SHOW_LOGS:
            print("\nRefined Brief:\n" + fb["refined_brief"])
        questions = fb["questions"]


if __name__ == "__main__":
    main()

