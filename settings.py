"""
Central configuration file for the Domain Agent system.
This makes it easy to swap models, change temperatures, or adjust parameters
without touching the core application logic.
"""

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
PERSIST_SESSIONS_TO_FILE = False
SESSION_FILE_DIR = "sessions"
LOGS_DIR = "logs"
