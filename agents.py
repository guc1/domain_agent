"""
Contains all AI Agent implementations for the Domain Generator.
"""
from __future__ import annotations
import os, json, time, re, logging
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv
load_dotenv()

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
        self.system_prompt = """
# ROLE
You are a clarifier that—by asking follow-up questions about the exact type of domain name the user wants—will help the later AI agent fully understand their needs. Keep your language concise but precise.

# RULES
• Output valid JSON only.
• Keys must be "q1", "q2", … in order.
• No markdown fences or prose.
• Ask exactly 10 questions.
• Phrase every question as a full sentence ending with a question mark (e.g., "What is the name of the company?").

# GUIDELINES (always ask these unless already provided)
• Company name (if any)  
• Desired TLD(s) (e.g. .com, .net, .io)  
• Preferred length (short, medium, long)  
• Legal or geographic constraints

# GUIDELINES (choose 3 of these, plus craft any niche-specific creative questions to hit the sweet spot)
• Tone or vibe (e.g. modern, playful)  
• Keywords to include/avoid (e.g. “yoga”, “wellness”)  
• Real-word vs. abstract style  
• Examples you like (even if taken)  
• [Your own unique, niche-driven question]

> **Tip:** For each question, include brief options in parentheses to guide the user (customized when possible).

USER'S INITIAL BRIEF: "{brief}"  
Make each question tailored to this brief so you capture all the information needed for the AI to generate perfect domain ideas.
"""

    def ask(self, brief: str) -> List[Dict[str, str]]:
        prompt = self.system_prompt.format(brief=brief)
        log.debug("--- START QuestionAgent PROMPT ---\n%s\n--- END QuestionAgent PROMPT ---", prompt)
        try:
            response = self.model.generate_content(prompt, generation_config=self.generation_config)
            log.debug("--- START QuestionAgent RAW RESPONSE ---\n%s\n--- END QuestionAgent RAW RESPONSE ---", response.text)
            data = json.loads(_clean_json_response(response.text))
            questions = [
                {"id": key, "text": data[key]} for key in sorted(data.keys())
            ]
            log.info(f"Generated {len(questions)} initial questions.")
            return questions
        except Exception as e:
            log.warning(f"QuestionAgent failed: {e}. Falling back.")
            return [
                {"id": "q1", "text": "What is the primary purpose?"},
                {"id": "q2", "text": "Who is the target audience?"},
            ]

class ClarifyingAgent:
    """Asks exactly two short follow up questions."""

    def __init__(self):
        cfg = settings.REFINEMENT_QUESTION_AGENT_CONFIG
        self.model = genai.GenerativeModel(cfg["model"])
        self.generation_config = genai.types.GenerationConfig(
            temperature=cfg["temperature"]
        )
        self.system_prompt = (
            "# ROLE\nYou are a brief clarifier focused on domain naming. "
            "Ask exactly two concise questions that will help refine the request.\n\n"
            "# RULES\n"
            "• Output valid JSON only.\n"
            "• Keys must be 'q1' and 'q2'.\n"
            "• No markdown fences or extra text."
        )

    def ask(self, brief: str) -> List[Dict[str, str]]:
        prompt = f"{self.system_prompt}\n\nUSER PROMPT:\n{brief}"
        log.debug(
            "--- START ClarifyingAgent PROMPT ---\n%s\n--- END ClarifyingAgent PROMPT ---",
            prompt,
        )
        try:
            response = self.model.generate_content(
                prompt, generation_config=self.generation_config
            )
            log.debug(
                "--- START ClarifyingAgent RAW RESPONSE ---\n%s\n--- END ClarifyingAgent RAW RESPONSE ---",
                response.text,
            )
            data = json.loads(_clean_json_response(response.text))
            return [{"id": "q1", "text": data["q1"]}, {"id": "q2", "text": data["q2"]}]
        except Exception as e:
            log.warning(f"ClarifyingAgent failed: {e}. Using fallback questions.")
            return [
                {"id": "q1", "text": "What detail should we focus on?"},
                {"id": "q2", "text": "Any style preferences?"},
            ]

class PromptSynthesizerAgent:
    """Takes a brief and Q&A and synthesizes a high-quality narrative prompt."""
    def __init__(self):
        cfg = settings.PROMPT_SYNTHESIZER_AGENT_CONFIG
        self.model, self.temperature = cfg["model"], cfg["temperature"]
        self.system_prompt = """
You are a master prompt engineer operating within a multi-agent domain-naming framework. Your goal is to synthesize the user’s original brief plus their answers to clarifying questions into one clear, cohesive narrative brief. This brief will drive the creative AI that actually generates domain names.

• Analyze the user’s inputs carefully to identify their core desires and priorities.  
• Emphasize the elements they care most about, but stay true only to the information provided—do not invent new details.  
• Strive to satisfy all explicit requests (tone, keywords, constraints, etc.), while leaving room for creative interpretation by the next agent.

Transform the raw Q&A into a single descriptive paragraph that captures:
- The user’s overarching objective  
- Any required keywords, styles, or constraints  
- The vibe or nuance they want the AI to preserve  

Only use the answers and brief given. Make it concise, narrative-driven, and ready for a domain-name generator to follow.
"""
        self.ignore_answers = {'no', 'none', 'n/a', '', 'no comment'}

    def synthesize(self, brief: str, answers: Dict[str, str], question_map: Dict[str, str]) -> str:
        ordered_ids = sorted(question_map.keys(), key=lambda k: int(k[1:]))
        pairs = []
        for qid in ordered_ids:
            answer = answers.get(qid, "").strip()
            if answer.lower() in self.ignore_answers:
                continue
            question_text = question_map.get(qid)
            if question_text:
                pairs.append((question_text, answer))

        if not pairs:
            log.info("No meaningful answers provided, using initial brief only.")
            return brief

        qa_text = "\n".join([f"Q: {q}\nA: {a}" for q, a in pairs])
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
        if tag.endswith("A"):
            system_content = f"""
    You are Creator A: the Balanced Domain Name Generator.
    Your task is to deliver a list of straightforward, reliable domain names that honor the user’s brief and preferences. Think of how Apple landed on “iPhone”—simple, elegant, immediately understandable.
    • Produce exactly {count} `.com`-style names (or the TLDs the user specified).
    • Keep each name original yet familiar—safe bets that feel “just right.”
    • Respond with a JSON object {"domains": [names]} and no extra text.
    """
        elif tag.endswith("B"):
            system_content = f"""
    You are Creator B: the Straight-Shooter Domain Name Generator.
    Your job is to follow the user’s instructions with laser focus—even if it means suggesting names that are obvious or likely already taken. Be as literal as Google was when it named “Google Search.”
    • Provide exactly {count} names that align verbatim with the brief’s keywords and constraints.
    • Emphasize clarity over creativity—if it’s descriptive, suggest it.
    • Respond with a JSON object {"domains": [names]} and no extra text.
    """
        else:  # CreatorC
            system_content = f"""
    You are Creator C: the Free-Spirit Domain Name Generator.
    Your mission is to push the boundaries—generate names as inventively as Salvador Dalí painted “The Persistence of Memory.”
    • Produce exactly {count} domain ideas that still respect the user’s core requirements (tone, keywords, TLDs).
    • Dare to combine unusual words or coined terms—edge-of-possibility suggestions.
    • Respond with a JSON object {"domains": [names]} and no extra text.
    """
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
            
    def create(
        self,
        prompt: str,
        previously_seen: set,
        creators: Optional[List[str]] = None,
        generation_count: Optional[int] = None,
    ) -> Dict[str, str]:
        """Generate domain ideas using the selected creator models."""

        creators = creators or ["A", "B", "C"]

        def run(tag: str, cfg: dict) -> Dict[str, str]:
            count = generation_count if generation_count is not None else cfg.get(
                "generation_count", 0
            )
            return self._generate_batch(prompt, cfg, f"Creator{tag}", count)

        ideas = {}
        if "A" in creators:
            ideas.update(run("A", settings.CREATOR_A_CONFIG))
        if "B" in creators:
            ideas.update(run("B", settings.CREATOR_B_CONFIG))
        if "C" in creators:
            ideas.update(run("C", settings.CREATOR_C_CONFIG))

        return {name: src for name, src in ideas.items() if name not in previously_seen}

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
        self.system_prompt = """
# ROLE
You are a domain name strategy consultant. Compare the previous prompt’s generated output feedback to the new refined goal. Identify patterns the user liked or disliked, and craft two targeted questions to confirm positive patterns or rule out negative ones.

# RULES
• Output valid JSON only.
• Keys must be "q1" and "q2".
• No markdown fences or extra text.

# GUIDELINES
• Base each question on the difference between feedback and the refined brief.
• One question should validate a pattern they liked; the other should clarify or discard something they disliked.
• Include brief examples or options in parentheses to guide the user.
"""
    def ask(self, refined_brief: str, feedback_summary: str) -> List[Dict[str, str]]:
        prompt = (f"{self.system_prompt}\n\n# PREVIOUS FEEDBACK SUMMARY\n{feedback_summary}\n\n# NEW REFINED GOAL\n\"{refined_brief}\"\n\nBased on all the above, ask your two follow-up questions now.")
        log.debug("--- START RefinementQuestionAgent PROMPT ---\n%s\n--- END RefinementQuestionAgent PROMPT ---", prompt)
        try:
            response = self.model.generate_content(prompt, generation_config=self.generation_config)
            log.debug("--- START RefinementQuestionAgent RAW RESPONSE ---\n%s\n--- END RefinementQuestionAgent RAW RESPONSE ---", response.text)
            data = json.loads(_clean_json_response(response.text))
            questions = [
                {"id": "q1", "text": data["q1"]},
                {"id": "q2", "text": data["q2"]},
            ]
            log.info(f"Generated {len(questions)} refinement questions.")
            return questions
        except Exception as e:
            log.warning(f"RefinementQuestionAgent failed: {e}. Falling back.")
            return [
                {"id": "q1", "text": "What specific element did you like most?"},
                {"id": "q2", "text": "What was missing?"},
            ]

class DirectionistAgent:
    """Refines the brief using all feedback."""
    def __init__(self):
        self.config = settings.DIRECTIONIST_AGENT_CONFIG
        self.model = self.config["model"]
        self.system_prompt = "You are a prompt optimizer..."
    def _build_feedback_summary(
        self,
        liked_domains: Dict[str, str],
        taken_domains: List[str],
        disliked_domains: Dict[str, str],
    ) -> str:
        parts = []
        if liked_domains:
            parts.append(
                "POSITIVE FEEDBACK (domains the user liked):\n"
                + "\n".join([f"- Liked '{d}': {r}" for d, r in liked_domains.items()])
            )
        if disliked_domains:
            parts.append(
                "NEGATIVE FEEDBACK (domains the user disliked):\n"
                + "\n".join([f"- Disliked '{d}': {r}" for d, r in disliked_domains.items()])
            )
        if taken_domains:
            parts.append(
                "NEGATIVE FEEDBACK (these were good ideas, but already taken):\n- "
                + ", ".join(taken_domains)
            )
        return "\n\n".join(parts)

    def refine_brief(
        self,
        original_brief: str,
        liked_domains: Dict[str, str],
        taken_domains: List[str],
        disliked_domains: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, str]:
        disliked_domains = disliked_domains or {}
        feedback_summary = self._build_feedback_summary(
            liked_domains, taken_domains, disliked_domains
        )
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

class FeedbackCombinerAgent:
    """Combines the prior prompt, user feedback and answers into a new prompt."""

    def __init__(self):
        cfg = settings.PROMPT_SYNTHESIZER_AGENT_CONFIG
        self.model = cfg["model"]
        self.temperature = cfg["temperature"]
        self.ignore_answers = {"no", "none", "n/a", "", "no comment"}
        self.system_prompt = """
# ROLE
You are the final Prompt Synthesizer in our domain-naming pipeline. Your job is to merge:
  1) the previous prompt that generated candidate domains  
  2) the refined brief (post-feedback optimization)  
  3) the user’s like/dislike feedback patterns  
  4) the answers to the two follow-up questions  

Into one concise narrative “New Prompt” that:
  • Reaffirms patterns the user confirmed  
  • Omits or deprioritizes patterns they rejected  
  • Incorporates any new nuance from the follow-up answers  
  • Prepares the next creative agent to generate domain ideas

# RULES
• Output only the final paragraph (no extra text).  
• Stay strictly within the info given—don’t invent details.  
"""

    def _build_feedback_summary(
        self,
        liked_domains: Dict[str, str],
        taken_domains: List[str],
        disliked_domains: Dict[str, str],
    ) -> str:
        parts = []
        if liked_domains:
            parts.append(
                "POSITIVE FEEDBACK:\n" + "\n".join([f"- Liked '{d}': {r}" for d, r in liked_domains.items()])
            )
        if disliked_domains:
            parts.append(
                "NEGATIVE FEEDBACK:\n" + "\n".join([f"- Disliked '{d}': {r}" for d, r in disliked_domains.items()])
            )
        if taken_domains:
            parts.append(
                "TAKEN BUT LIKED:\n" + ", ".join(taken_domains)
            )
        return "\n\n".join(parts)

    def combine(
        self,
        previous_prompt: str,
        answers: Dict[str, str],
        question_map: Dict[str, str],
        liked_domains: Optional[Dict[str, str]] = None,
        taken_domains: Optional[List[str]] = None,
        refined_brief: Optional[str] = None,
        disliked_domains: Optional[Dict[str, str]] = None,
    ) -> str:
        liked_domains = liked_domains or {}
        disliked_domains = disliked_domains or {}
        taken_domains = taken_domains or []

        feedback_summary = self._build_feedback_summary(
            liked_domains, taken_domains, disliked_domains
        )

        qa_pairs = []
        for qid in sorted(question_map.keys(), key=lambda k: int(k[1:])):
            ans = answers.get(qid, "").strip()
            if ans.lower() in self.ignore_answers:
                continue
            q_text = question_map.get(qid)
            if q_text:
                qa_pairs.append(f"Q: {q_text}\nA: {ans}")

        qa_text = "\n".join(qa_pairs)

        context = (
            f"# PREVIOUS PROMPT\n{previous_prompt}\n\n"
            f"# REFINED BRIEF\n{refined_brief}\n\n"
            f"# USER FEEDBACK\n{feedback_summary}\n\n"
            f"# CLARIFYING ANSWERS\n{qa_text}\n\n"
            "New Prompt:"
        )

        log.debug(
            "--- START FeedbackCombinerAgent CONTEXT ---\n%s\n--- END FeedbackCombinerAgent CONTEXT ---",
            context,
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": context},
                ],
            )
            new_prompt = response.choices[0].message.content.strip()
            log.debug(
                "--- START FeedbackCombinerAgent RAW RESPONSE ---\n%s\n--- END FeedbackCombinerAgent RAW RESPONSE ---",
                new_prompt,
            )
            return new_prompt
        except Exception as e:
            log.error(f"FeedbackCombinerAgent failed: {e}")
            return previous_prompt
