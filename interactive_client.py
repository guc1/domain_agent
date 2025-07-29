import os
import requests

API_URL = os.getenv("DOMAIN_API_URL", "http://localhost:8000")
API_KEY = os.getenv("DOMAIN_API_KEY")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}


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
        print("\nPrompt:\n" + prompt)

        gen = post(f"/sessions/{session_id}/generate")
        print("\nAvailable:")
        for d in gen["available"]:
            print(" -", d)
        print("Taken:")
        for d in gen["taken"]:
            print(" -", d)

        liked, disliked = {}, {}
        for d in gen["available"]:
            reason = input(f"Like '{d}'? (optional reason) ")
            if reason:
                liked[d] = reason
        for d in gen["taken"]:
            reason = input(f"Dislike '{d}'? (optional reason) ")
            if reason:
                disliked[d] = reason

        fb = post(
            f"/sessions/{session_id}/feedback",
            {"liked": liked, "disliked": disliked},
        )
        print("\nRefined Brief:\n" + fb["refined_brief"])
        questions = fb["questions"]

        clar = post("/clarify", {"prompt": prompt})
        clar_answers = ask_questions(clar["questions"])
        new_prompt = post(
            "/combine",
            {
                "previous_prompt": prompt,
                "answers": clar_answers,
                "question_map": {q["id"]: q["text"] for q in clar["questions"]},
                "liked_domains": liked,
                "disliked_domains": disliked,
                "taken_domains": gen["taken"],
            },
        )["prompt"]
        prompt = new_prompt
        print("\nNew Prompt:\n" + prompt)

        cont = input("Another loop? (y/N) ").strip().lower()
        if cont != "y":
            break


if __name__ == "__main__":
    main()

