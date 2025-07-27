"""
Main entry point for the Domain Agent CLI application.
"""
import os, sys, logging, time
from dotenv import load_dotenv

load_dotenv()

# --- Logging Setup ---
log_format = "%(asctime)s [%(levelname)-7s] [%(name)-22s] %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"
logging.Formatter.converter = time.gmtime
root_logger = logging.getLogger('')
root_logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
console_handler.setLevel(console_level)
console_formatter = logging.Formatter(log_format, datefmt=date_format)
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)
if console_level != logging.DEBUG:
    for logger_name in ["httpx", "httpcore", "openai._base_client", "urllib3.connectionpool", "charset_normalizer", "googleapiclient.discovery"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
log = logging.getLogger("domain-agent.main")

import settings
from store import SessionStore
from agents import QuestionAgent, RefinementQuestionAgent, PromptSynthesizerAgent, CreatorAgent, CheckerAgent, DirectionistAgent

def add_file_logger_for_session(session_id: str):
    """Adds a file handler to the root logger for detailed session debugging."""
    logs_dir = settings.LOGS_DIR
    os.makedirs(logs_dir, exist_ok=True)
    log_file_path = os.path.join(logs_dir, f"session_{session_id}.log")
    file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)
    logging.getLogger('').addHandler(file_handler)
    log.info(f"Full debug log for this session is being saved to: {log_file_path}")

def run_session():
    """Manages a single, complete user session from start to finish."""
    store = SessionStore()
    session_id = store.new()
    add_file_logger_for_session(session_id)

    question_agent, refinement_question_agent, prompt_synthesizer = QuestionAgent(), RefinementQuestionAgent(), PromptSynthesizerAgent()
    creator_agent, checker_agent, directionist_agent = CreatorAgent(), CheckerAgent(), DirectionistAgent()

    print("--- Domain Agent Initializing ---")
    initial_brief = input("Describe the business or project you need a domain for: ")
    current_brief = initial_brief
    
    failures, loop_count = 0, 1
    last_feedback_summary = ""

    while True:
        print("\n" + "="*50)
        log.info(f"Starting Loop #{loop_count} for session {session_id}")
        
        q_and_a = {}
        if loop_count == 1:
            print(f"Loop #{loop_count} | Initial Brief: \"{current_brief[:100]}...\"")
            questions = question_agent.ask(current_brief)
        else:
            print(f"Loop #{loop_count} | Refined Brief: \"{current_brief[:100]}...\"")
            questions = refinement_question_agent.ask(current_brief, last_feedback_summary)
        
        for q in questions:
            q_and_a[q] = input(f"❓ {q} ") or "no comment"

        final_prompt = prompt_synthesizer.synthesize(current_brief, q_and_a)
        
        # --- Simplified Single-Pass Generation ---
        log.info("Generating a new batch of domain ideas based on your settings...")
        ideas = creator_agent.create(final_prompt, store.seen(session_id))
        store.add(session_id, list(ideas.keys()))
        
        if not ideas:
            log.warning("CreatorAgent returned no new ideas for this loop.")
            available_domains, taken_domains = {}, {}
        else:
            available_domains, taken_domains = checker_agent.filter_available(ideas)
            log.info(f"Check complete. Found {len(available_domains)} available, {len(taken_domains)} taken.")

        if not available_domains:
            failures += 1
            log.warning(f"No available domains found in this batch. Failure count: {failures}/{settings.MAX_LOOP_FAILURES}")
            if failures >= settings.MAX_LOOP_FAILURES:
                print("\n❌ Too many consecutive loops with no available domains. Consider broadening your criteria. Aborting.")
                break
            
            # Auto-generate feedback to try and un-stick the generator for the next loop.
            dislike_reason = f"No available domains were found. The following ideas were all taken: {', '.join(taken_domains.keys())}" if taken_domains else "No available domains were found, and the generator returned few ideas."
            log.info(f"Automatically providing feedback to refine brief: {dislike_reason}")
            current_brief, last_feedback_summary = directionist_agent.refine_brief(initial_brief, {}, list(taken_domains.keys()), dislike_reason)
            loop_count += 1
            print("Trying again with a refined approach...")
            continue
        
        # Reset failure count on success
        failures = 0

        print("\n✅ The following domains appear to be AVAILABLE:")
        final_list_to_show = list(available_domains.items())
        for i, (name, source) in enumerate(final_list_to_show, 1): 
            print(f"  {i}. {name:<30} (from {source})")

        print("\n---")
        print("To continue, enter the numbers of liked domains (e.g., '1, 3').")
        print("To get a new batch with a different focus, just press Enter.")
        print("To stop, type 'n'.")
        choice = input("> ")

        if choice.strip().lower() in ["n", "no", "stop", "exit"]:
            print("\n👋 Session ended. Thank you!"); break

        liked_indices = [int(i.strip()) - 1 for i in choice.split(',') if i.strip().isdigit()]
        liked_domains_map, dislike_reason = {}, None
        
        if not liked_indices:
            dislike_reason = input("It looks like none of those worked. What did you dislike about them? ") or "User did not provide a reason."
        else:
            for i in liked_indices:
                if 0 <= i < len(final_list_to_show):
                    domain_name, _ = final_list_to_show[i]
                    liked_domains_map[domain_name] = input(f"  Why did you like '{domain_name}'? (Optional) ") or "No specific reason given."
        
        log.info(f"User liked: {list(liked_domains_map.keys())}. Dislike reason: {dislike_reason}")
        # Use the list of domains that were taken in this specific loop for feedback
        current_brief, last_feedback_summary = directionist_agent.refine_brief(initial_brief, liked_domains_map, list(taken_domains.keys()), dislike_reason)
        loop_count += 1

if __name__ == "__main__":
    try:
        run_session()
    except KeyboardInterrupt:
        print("\n\nCaught interrupt. Exiting gracefully."); sys.exit(0)
    except Exception as e:
        log.critical("An unexpected critical error occurred: %s", e, exc_info=True)
        print("\n💥 A critical error occurred. Please check the logs. Exiting."); sys.exit(1)
