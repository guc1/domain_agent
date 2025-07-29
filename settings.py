"""
Central configuration file for the Domain Agent system.
This makes it easy to swap models, change temperatures, or adjust parameters
without touching the core application logic.
"""
import os

# API key required by the FastAPI server
API_KEY = os.getenv("DOMAIN_API_KEY")

# --- Model & Agent Configuration ---
QUESTION_AGENT_CONFIG = {
    "model": "gemini-1.5-flash-latest",
    "temperature": 0.2,
}

PROMPT_SYNTHESIZER_AGENT_CONFIG = {
    "model": "gpt-4o-mini",
    "temperature": 0.3,
}

CREATOR_A_CONFIG = {  # Balanced creator
    "model": "gpt-4o",
    "temperature": 1.0,
    # The number of domains this creator will be asked to generate per feedback cycle.
    "generation_count": 1,
}

CREATOR_B_CONFIG = {  # Creative/Spicy creator
    "model": "gpt-4o",
    "temperature": 1.3,
    # The number of domains this creator will be asked to generate per feedback cycle.
    "generation_count": 1,
}

CREATOR_C_CONFIG = {  # Conservative/Direct creator
    "model": "gpt-4o",
    "temperature": 0.2,
    # The number of domains this creator will be asked to generate per feedback cycle.
    "generation_count": 1,
}

# ### MODIFIED FOR INDIVIDUAL CHECKING ###
CHECKER_AGENT_CONFIG = {
    # --- The mode toggle ---
    "mode": "MODEL",  # Options: "LOCAL" or "MODEL"
    
    # Model for MODEL mode (must support web_search tool in Responses API)
    "search_model": "o4-mini",
    
    # Timeout for LOCAL mode's direct requests
    "request_timeout": 10,
    
    # Sleep between checks to be kind to servers (used in both LOCAL and MODEL modes)
    "check_sleep": 0.5,
}

REFINEMENT_QUESTION_AGENT_CONFIG = {
    "model": "gemini-1.5-flash-latest",
    "temperature": 0.4,
}

DIRECTIONIST_AGENT_CONFIG = {
    "model": "gpt-4o-mini",
}

# --- Application Flow Configuration ---
MAX_LOOP_FAILURES = 20 # The number of consecutive loops with no available domains before aborting.

# --- Session & Logging Configuration ---
PERSIST_SESSIONS_TO_FILE = True
SESSION_FILE_DIR = "sessions"
LOGS_DIR = "logs"

# --- Domain Generation Goals ---
# How many available domains the checker should aim to find in one generate
# request. The API will loop locally until this many free domains are
# discovered or until MAX_GENERATION_ATTEMPTS is reached.
MIN_AVAILABLE_DOMAINS = int(os.getenv("MIN_AVAILABLE_DOMAINS", "3"))

# Safety cap on how many batches will be generated/checked per request.
MAX_GENERATION_ATTEMPTS = int(os.getenv("MAX_GENERATION_ATTEMPTS", "5"))

# --- Client Display Options ---
# When False, the interactive client will suppress verbose logs such as the
# prompt, taken domains and refined briefs.  This is useful for a more
# streamlined user experience.
SHOW_LOGS = os.getenv("SHOW_LOGS", "1") != "0"
