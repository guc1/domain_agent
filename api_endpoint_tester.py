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


def main():
    # Gather settings first
    dev = input("Use local dev mode? (y/N) ").strip().lower() == "y"
    creators_raw = input("Creators to use [A,B,C]: ").strip() or "A,B,C"
    creators = [c.strip() for c in creators_raw.split(",") if c.strip()]
    gen_count = input("Generation count per creator [1]: ").strip() or "1"
    show_logs = input("Show logs? (y/N) ").strip().lower() == "y"

    brief = input("Describe the business or project: ")

    data = post("/sessions", {"initial_brief": brief})
    sid = data["session_id"]
    post(
        f"/sessions/{sid}/settings",
        {
            "local_dev": dev,
            "creators": creators,
            "generation_count": int(gen_count),
            "show_logs": show_logs,
        },
    )
    questions = data["questions"]

    while True:
        answers = ask_questions(questions)
        ans_out = post(f"/sessions/{sid}/answers", {"answers": answers})
        prompt = ans_out["prompt"]
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

    print("Session complete.")


if __name__ == "__main__":
    main()
