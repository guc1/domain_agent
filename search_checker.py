# domain_status_combined.py
import os, json, re
from dotenv import load_dotenv
from openai import OpenAI

# pick up API key
load_dotenv("/Users/yer/Desktop/scrappaa/Domain_checker_ai/.env")
client = OpenAI()

def check_domains(domains):
    """
    domains: iterable of bare domain strings  (e.g. ["welcome.ai", "foo.ai"])
    returns: dict {domain: "OK" | "NOT"}
    """

    # 1️⃣ build an instruction that lists all names up-front
    names = ", ".join(domains)
    response = client.responses.create(
        model="o4-mini",
        tools=[{"type": "web_search"}],
        instructions=(
            "You are a domain-status checker. "
            "For EACH domain listed, use web_search once if needed, decide whether it "
            "is registered, and return a JSON object whose keys are the domains and "
            "whose values are either OK (registered) or NOT (available). "
            "Return *only* the JSON, nothing else."
        ),
        input=f"Domains: {names}"
        # optional: max_tokens=20 to hard-cap the reply
    )

    # 2️⃣ parse the tiny JSON object the model sends back
    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError:
        # fall-back: pull "domain: OK" pairs with regex if the model adds stray text
        pairs = re.findall(r'"([^"]+)":\s*"?(OK|NOT)"?', response.output_text, re.I)
        return {d: s.upper() for d, s in pairs}

# quick demo
if __name__ == "__main__":
    names = ["welcome.ai", "welcsdfsdfdfsfome.ai"]
    result = check_domains(names)
    for n in names:
        print(n, "→", result.get(n, "UNKNOWN"))