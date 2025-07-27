"""
Contains all AI Agent implementations for the Domain Generator.
"""
from __future__ import annotations
import os, json, time, re, logging
from typing import List, Dict, Tuple, Optional

import google.generativeai as genai
from openai import OpenAI
import requests
import settings

# --- Initialize APIs & Logger ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
log = logging.getLogger("domain-agent.agents")

def _clean_json_response(text: str) -> str:
    """Helper to strip markdown fences from AI responses."""
    match = re.search(r"```(?:json)?\s*({.*?})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    return text.strip()

class QuestionAgent:
    """Asks the user initial clarifying questions for the first loop."""
    def __init__(self):
        cfg = settings.QUESTION_AGENT_CONFIG
        self.model = genai.GenerativeModel(cfg["model"])
        self.generation_config = genai.types.GenerationConfig(temperature=cfg["temperature"])
        self.system_prompt = "# ROLE\nYou are a clarifier. Your only task is to ask follow-up questions that will let a\nlater agent generate the best possible domain names.\n\n# RULES\n• Output valid JSON only.\n• Keys must be \"q1\", \"q2\", … in order.\n• No markdown fences or prose.\n• Ask 2–10 questions – the fewest that fully clarify the brief.\n\n# GUIDELINES  (topics you may cover)\n• Brand / company match                • Desired TLD(s)\n• Tone or vibe                         • Length limits\n• Keywords to include / avoid          • Real-word vs. abstract\n• Examples the user likes (but are taken)\n• Legal / geographic constraints"

    def ask(self, brief: str) -> List[str]:
        prompt = f"{self.system_prompt}\n\nUSER'S INITIAL BRIEF: \"{brief}\""
        log.debug("--- START QuestionAgent PROMPT ---\n%s\n--- END QuestionAgent PROMPT ---", prompt)
        try:
            response = self.model.generate_content(prompt, generation_config=self.generation_config)
            log.debug("--- START QuestionAgent RAW RESPONSE ---\n%s\n--- END QuestionAgent RAW RESPONSE ---", response.text)
            data = json.loads(_clean_json_response(response.text))
            questions = [data[key] for key in sorted(data.keys())]
            log.info(f"Generated {len(questions)} initial questions.")
            return questions
        except Exception as e:
            log.warning(f"QuestionAgent failed: {e}. Falling back.")
            return ["Primary purpose?", "Target audience?"]

class PromptSynthesizerAgent:
    """Takes a brief and Q&A and synthesizes a high-quality narrative prompt."""
    def __init__(self):
        cfg = settings.PROMPT_SYNTHESIZER_AGENT_CONFIG
        self.model, self.temperature = cfg["model"], cfg["temperature"]
        self.system_prompt = "You are a master prompt engineer. Your task is to synthesize a user's brief and a set of questions and answers into a single, cohesive, and well-written narrative brief. This new brief will be given to a creative AI to generate domain names. Transform the raw Q&A into a descriptive paragraph. Infer the user's core desires from their answers. Only use the information provided; do not add new details."
        self.ignore_answers = {'no', 'none', 'n/a', '', 'no comment'}

    def synthesize(self, brief: str, q_and_a: Dict[str, str]) -> str:
        filtered_qa = {q: a for q, a in q_and_a.items() if a.lower().strip() not in self.ignore_answers}
        if not filtered_qa:
            log.info("No meaningful answers provided, using initial brief only.")
            return brief

        qa_text = "\n".join([f"Q: {q}\nA: {a}" for q, a in filtered_qa.items()])
        prompt = f"{self.system_prompt}\n\n# CORE BRIEF:\n{brief}\n\n# USER'S ANSWERS:\n{qa_text}\n\nSynthesize this into a paragraph."
        log.debug("--- START PromptSynthesizerAgent PROMPT ---\n%s\n--- END PromptSynthesizerAgent PROMPT ---", prompt)
        try:
            response = client.chat.completions.create(model=self.model, temperature=self.temperature, messages=[{"role": "user", "content": prompt}])
            return response.choices[0].message.content.strip()
        except Exception as e:
            log.error(f"PromptSynthesizerAgent failed: {e}.")
            return f"User Brief: {brief}\n\n" + qa_text

class CreatorAgent:
    """Generates domain name ideas from three models, tracking attribution."""
    def _generate_batch(self, prompt: str, config: dict, tag: str, count: int) -> Dict[str, str]:
        if count <= 0: return {}
        system_content = f"You are a creative domain name generator. Based on the user's detailed brief, provide a list of exactly {count} domain name ideas. Your output must be a single, valid JSON object containing one key which is an array of strings, like {{\"domains\": [\"idea1.com\", \"idea2.net\"]}}. Do not add any other text or explanation."
        log.debug("--- START %s PROMPT ---\n[SYSTEM]\n%s\n\n[USER]\n%s\n--- END %s PROMPT ---", tag, system_content, prompt, tag)
        try:
            response = client.chat.completions.create(model=config["model"], temperature=config["temperature"], messages=[{"role": "system", "content": system_content}, {"role": "user", "content": prompt}], response_format={"type": "json_object"})
            content = response.choices[0].message.content
            log.debug("--- START %s RAW RESPONSE ---\n%s\n--- END %s RAW RESPONSE ---", tag, content, tag)
            data = json.loads(content)
            for value in data.values():
                if isinstance(value, list): return {str(item): tag for item in value[:count]}
            return {}
        except Exception as e:
            log.error(f"CreatorAgent ({tag}) failed: {e}")
            return {}
            
    def create(self, prompt: str, previously_seen: set) -> Dict[str, str]:
        # This method no longer splits a passed-in count.
        # It reads the generation count for each creator directly from its configuration.
        count_a = settings.CREATOR_A_CONFIG.get("generation_count", 0)
        count_b = settings.CREATOR_B_CONFIG.get("generation_count", 0)
        count_c = settings.CREATOR_C_CONFIG.get("generation_count", 0)

        ideas_a = self._generate_batch(prompt, settings.CREATOR_A_CONFIG, "CreatorA", count_a)
        ideas_b = self._generate_batch(prompt, settings.CREATOR_B_CONFIG, "CreatorB", count_b)
        ideas_c = self._generate_batch(prompt, settings.CREATOR_C_CONFIG, "CreatorC", count_c)
        
        all_ideas = {**ideas_a, **ideas_b, **ideas_c}
        return {name: source for name, source in all_ideas.items() if name not in previously_seen}

class RDAPBootstrap:
    """Finds and caches the correct RDAP server for a given TLD."""
    def __init__(self):
        self._tld_map: Dict[str, str] = {}
        self._loaded = False
        self.bootstrap_url = "https://data.iana.org/rdap/dns.json"
    def _load_data(self):
        if self._loaded: return
        log.info(f"Loading IANA RDAP bootstrap data...")
        try:
            response = requests.get(self.bootstrap_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            for service in data.get("services", []):
                tlds, server_urls = service[0], service[1]
                if server_urls:
                    base_url = next((url for url in server_urls if url.startswith("https://")), server_urls[0])
                    for tld in tlds: self._tld_map[tld.lower()] = base_url
            self._loaded = True
            log.info(f"Cached {len(self._tld_map)} TLD-to-server mappings.")
        except Exception as e:
            log.critical(f"Failed to load IANA RDAP bootstrap data: {e}")
    def get_server_for_tld(self, tld: str) -> Optional[str]:
        if not self._loaded: self._load_data()
        return self._tld_map.get(tld.lower())

class CheckerAgent:
    """Checks domain availability using one of two modes: LOCAL or MODEL."""
    def __init__(self):
        self.config = settings.CHECKER_AGENT_CONFIG
        self.mode = self.config.get("mode", "LOCAL").upper()
        self.search_model = self.config.get("search_model")
        self.bootstrap = RDAPBootstrap()

    def _filter_with_local_http(self, candidates: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Mode 1: Direct HTTP requests from the local machine."""
        available, taken = {}, {}
        log.info(f"Checking availability for {len(candidates)} domains via LOCAL direct HTTP requests...")
        for name, source in candidates.items():
            try: tld = name.split('.')[-1]
            except IndexError: continue
            
            rdap_base_url = self.bootstrap.get_server_for_tld(tld)
            if not rdap_base_url:
                log.warning(f"No RDAP server for '{name}'. Assuming FREE.")
                available[name] = source; continue
            
            full_query_url = f"{rdap_base_url.rstrip('/')}/domain/{name}"
            try:
                log.debug(f"Querying authoritative server directly: {full_query_url}")
                response = requests.get(full_query_url, timeout=self.config["request_timeout"])
                status_code = response.status_code
            except requests.RequestException as e:
                log.error(f"Request for {name} failed: {e}. Assuming TAKEN as a precaution.")
                taken[name] = source; continue # Assume taken on network error
            
            decision = "TAKEN" if status_code == 200 else "FREE"
            log.info(f"CHECKER: {name:<30} [{source}] -> Status {status_code}, Decision: {decision}")
            (taken if decision == "TAKEN" else available)[name] = source
            time.sleep(self.config["check_sleep"])
        return available, taken

    def _filter_with_llm_search(self, candidates: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Mode 2: Use LLM with web search to check domains INDIVIDUALLY for higher accuracy.
        This is slower but more robust against hallucinations and handles errors safely.
        """
        if not self.search_model:
            log.error("CheckerAgent in MODEL mode, but no 'search_model' is configured. Aborting check.")
            return {}, candidates # Return all as taken if not configured

        log.info(f"Individually checking {len(candidates)} domains via MODEL (LLM Web Search)...")
        available, taken = {}, {}

        instructions = (
            "You are a domain-status checker. "
            "For the single domain listed, use web_search once if needed, decide whether it "
            "is registered, and return a JSON object whose key is the domain and "
            "whose value is either OK (registered) or NOT (available). "
            "Return *only* the JSON, nothing else."
        )

        # Loop and check each domain one by one
        for name, source in candidates.items():
            log.debug(f"--- START CheckerAgent Individual LLM Search for: {name} ---")
            try:
                prompt = f"Domains: {name}"
                response = client.responses.create(
                    model=self.search_model,
                    instructions=instructions,
                    input=prompt,
                    tools=[{"type": "web_search"}],
                )
                raw_output = response.output_text
                log.debug(f"--- RAW RESPONSE for {name} ---\n{raw_output}\n--- END RAW RESPONSE ---")
                
                # Parse the response for the single domain
                try:
                    results = json.loads(_clean_json_response(raw_output))
                except json.JSONDecodeError:
                    log.warning(f"LLM response for {name} was not clean JSON, attempting regex fallback.")
                    pairs = re.findall(r'"([^"]+)":\s*"?(OK|NOT)"?', raw_output, re.I)
                    results = {d: s.upper() for d, s in pairs}

                status = results.get(name, "UNKNOWN").upper()
                
                # Make a decision based on the parsed status
                if status == "OK":
                    decision = "TAKEN"
                    taken[name] = source
                elif status == "NOT":
                    decision = "FREE"
                    available[name] = source
                else:
                    log.warning(f"LLM returned ambiguous status '{status}' for {name}. Assuming TAKEN as a precaution.")
                    decision = "TAKEN"
                    taken[name] = source
                    
                log.info(f"CHECKER: {name:<30} [{source}] -> LLM Decision: {decision}")

            except Exception as e:
                # CRITICAL CHANGE: If any error occurs (network, API, etc.), assume TAKEN.
                # This prevents falsely reporting a domain as available.
                log.error(f"LLM search failed for '{name}': {e}. Assuming TAKEN as a precaution.")
                taken[name] = source

            # Sleep to be kind to the API and avoid rate limits
            time.sleep(self.config.get("check_sleep", 0.5))

        return available, taken

    def filter_available(self, candidates: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Dispatcher method that chooses the check mode from settings."""
        if not candidates:
            return {}, {}
        if self.mode == "MODEL":
            return self._filter_with_llm_search(candidates)
        else:
            return self._filter_with_local_http(candidates)

class RefinementQuestionAgent:
    """Asks contextual follow-up questions."""
    def __init__(self):
        cfg = settings.REFINEMENT_QUESTION_AGENT_CONFIG
        self.model = genai.GenerativeModel(cfg["model"])
        self.generation_config = genai.types.GenerationConfig(temperature=cfg["temperature"])
        self.system_prompt = "# ROLE\nYou are a domain name strategy consultant..."
    def ask(self, refined_brief: str, feedback_summary: str) -> List[str]:
        prompt = (f"{self.system_prompt}\n\n# PREVIOUS FEEDBACK SUMMARY\n{feedback_summary}\n\n# NEW REFINED GOAL\n\"{refined_brief}\"\n\nBased on all the above, ask your two follow-up questions now.")
        log.debug("--- START RefinementQuestionAgent PROMPT ---\n%s\n--- END RefinementQuestionAgent PROMPT ---", prompt)
        try:
            response = self.model.generate_content(prompt, generation_config=self.generation_config)
            log.debug("--- START RefinementQuestionAgent RAW RESPONSE ---\n%s\n--- END RefinementQuestionAgent RAW RESPONSE ---", response.text)
            data = json.loads(_clean_json_response(response.text))
            questions = [data["q1"], data["q2"]]
            log.info(f"Generated {len(questions)} refinement questions.")
            return questions
        except Exception as e:
            log.warning(f"RefinementQuestionAgent failed: {e}. Falling back.")
            return ["What specific element did you like most?", "What was missing?"]

class DirectionistAgent:
    """Refines the brief using all feedback."""
    def __init__(self):
        self.config = settings.DIRECTIONIST_AGENT_CONFIG
        self.model = self.config["model"]
        self.system_prompt = "You are a prompt optimizer..."
    def _build_feedback_summary(self, liked_domains: Dict[str, str], taken_domains: List[str], dislike_reason: Optional[str]) -> str:
        parts = []
        if liked_domains: parts.append(f"POSITIVE FEEDBACK (domains the user liked):\n" + "\n".join([f"- Liked '{d}': {r}" for d, r in liked_domains.items()]))
        if taken_domains: parts.append(f"NEGATIVE FEEDBACK (these were good ideas, but already taken):\n- {', '.join(taken_domains)}")
        if dislike_reason: parts.append(f"CRITICAL FEEDBACK (why the user disliked all previous suggestions):\n- {dislike_reason}")
        return "\n\n".join(parts)
    def refine_brief(self, original_brief: str, liked_domains: Dict[str, str], taken_domains: List[str], dislike_reason: Optional[str] = None) -> Tuple[str, str]:
        feedback_summary = self._build_feedback_summary(liked_domains, taken_domains, dislike_reason)
        if not feedback_summary: return original_brief, ""
        prompt = (f"{self.system_prompt}\n\nORIGINAL BRIEF:\n{original_brief}\n\nUSER FEEDBACK ANALYSIS:\n{feedback_summary}\n\nGenerate the new, refined brief now.")
        log.debug("--- START DirectionistAgent PROMPT ---\n%s\n--- END DirectionistAgent PROMPT ---", prompt)
        try:
            response = client.chat.completions.create(model=self.model, temperature=0.5, messages=[{"role": "user", "content": prompt}])
            new_brief = response.choices[0].message.content.strip()
            log.debug("--- START DirectionistAgent RAW RESPONSE ---\n%s\n--- END DirectionistAgent RAW RESPONSE ---", new_brief)
            log.info("DirectionistAgent refined brief.")
            return new_brief, feedback_summary
        except Exception as e:
            log.error(f"DirectionistAgent failed: {e}")
            return original_brief, feedback_summary
