"""
This module contains the function for checking domain availability using
the OpenAI Responses API with the 'o4-mini' model and web_search tool.
This is called by the CheckerAgent when in 'MODEL' mode.
"""
import os, json, re, logging
from openai import OpenAI

log = logging.getLogger("domain-agent.model_checker")

def check_domains_with_model(domains: list[str]) -> dict:
    """
    Checks a list of domains using the OpenAI Responses API.

    Args:
        domains: A list of domain name strings.

    Returns:
        A dictionary mapping each domain to its status ("OK" or "NOT").
    """
    if not domains:
        return {}

    # This client will use the OPENAI_API_KEY from the environment.
    client = OpenAI()
    
    names = ", ".join(domains)
    instructions = (
        "You are a domain-status checker. "
        "For EACH domain listed, use web_search once if needed, decide whether it "
        "is registered, and return a JSON object whose keys are the domains and "
        "whose values are either OK (registered) or NOT (available). "
        "Return *only* the JSON, nothing else."
    )
    prompt_input = f"Domains: {names}"
    
    log.debug("--- START MODEL_CHECKER PROMPT ---\n[INSTRUCTIONS]\n%s\n\n[INPUT]\n%s\n--- END MODEL_CHECKER PROMPT ---", instructions, prompt_input)

    try:
        response = client.responses.create(
            model="o4-mini",
            tools=[{"type": "web_search"}],
            instructions=instructions,
            input=prompt_input
        )
        raw_output = response.output_text
        log.debug("--- START MODEL_CHECKER RAW RESPONSE ---\n%s\n--- END MODEL_CHECKER RAW RESPONSE ---", raw_output)

        # Attempt to parse the JSON directly
        return json.loads(raw_output)
    except json.JSONDecodeError:
        # Fallback: pull "domain: OK" pairs with regex if the model adds stray text
        log.warning("MODEL_CHECKER response was not clean JSON, attempting regex fallback.")
        pairs = re.findall(r'"([^"]+)":\s*"?(OK|NOT)"?', raw_output, re.I)
        return {d: s.upper() for d, s in pairs}
    except Exception as e:
        log.error(f"An unexpected error occurred in MODEL_CHECKER: {e}")
        # In case of any other failure, assume all domains are available to avoid false negatives.
        return {domain: "NOT" for domain in domains}
