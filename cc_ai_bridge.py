"""
Claude Code AI Bridge — File-based communication between longform_bot and Claude Code.

The bot writes questions to cc_question.json, Claude Code reads them,
generates answers, and writes to cc_answer.json. Zero API cost.

Usage:
    # In longform_bot.py — replace gpt() calls:
    from cc_ai_bridge import ask_claude_code

    answer = ask_claude_code(system_prompt, user_prompt)

    # Claude Code runs the monitor loop separately to answer questions
"""
import os
import json
import time

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTION_FILE = os.path.join(DATA_DIR, "cc_question.json")
ANSWER_FILE = os.path.join(DATA_DIR, "cc_answer.json")
BATCH_QUESTION_FILE = os.path.join(DATA_DIR, "cc_batch_question.json")
BATCH_ANSWER_FILE = os.path.join(DATA_DIR, "cc_batch_answer.json")


def ask_claude_code(system_prompt, user_prompt, timeout=300):
    """
    Write a question for Claude Code and wait for the answer.
    Returns the answer text, or empty string on timeout.
    """
    # Clean up any stale files
    for f in [QUESTION_FILE, ANSWER_FILE]:
        try:
            if os.path.exists(f):
                os.remove(f)
        except:
            pass

    # Write the question
    question = {
        "timestamp": time.time(),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "status": "waiting",
    }
    with open(QUESTION_FILE, "w", encoding="utf-8") as f:
        json.dump(question, f, indent=2, ensure_ascii=False)

    print(f"    [CC] Question written — waiting for Claude Code answer...")

    # Poll for answer
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(ANSWER_FILE):
            try:
                with open(ANSWER_FILE, "r", encoding="utf-8") as f:
                    answer_data = json.load(f)
                answer = answer_data.get("answer", "")
                if answer:
                    # Clean up
                    try: os.remove(QUESTION_FILE)
                    except: pass
                    try: os.remove(ANSWER_FILE)
                    except: pass
                    print(f"    [CC] Answer received ({len(answer)} chars)")
                    return answer
            except (json.JSONDecodeError, IOError):
                pass  # File still being written
        time.sleep(1)

    print(f"    [CC] Timeout waiting for answer ({timeout}s)")
    try: os.remove(QUESTION_FILE)
    except: pass
    return ""


def ask_claude_code_batch(fields_data, job_context, timeout=600):
    """
    Send all form fields at once for batch answering.
    More efficient than one-by-one — Claude Code sees the whole form.
    Returns dict mapping field index to answer.
    """
    # Clean up stale files
    for f in [BATCH_QUESTION_FILE, BATCH_ANSWER_FILE]:
        try:
            if os.path.exists(f):
                os.remove(f)
        except:
            pass

    batch = {
        "timestamp": time.time(),
        "job": job_context,
        "fields": fields_data,
        "status": "waiting",
    }
    with open(BATCH_QUESTION_FILE, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    print(f"    [CC] Batch question written ({len(fields_data)} fields) — waiting for Claude Code...")

    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(BATCH_ANSWER_FILE):
            try:
                with open(BATCH_ANSWER_FILE, "r", encoding="utf-8") as f:
                    answers = json.load(f)
                if answers.get("status") == "done":
                    try: os.remove(BATCH_QUESTION_FILE)
                    except: pass
                    try: os.remove(BATCH_ANSWER_FILE)
                    except: pass
                    print(f"    [CC] Batch answers received!")
                    return answers.get("answers", {})
            except (json.JSONDecodeError, IOError):
                pass
        time.sleep(2)

    print(f"    [CC] Batch timeout ({timeout}s)")
    try: os.remove(BATCH_QUESTION_FILE)
    except: pass
    return {}


def is_question_pending():
    """Check if there's a pending question (used by Claude Code monitor)."""
    return os.path.exists(QUESTION_FILE) or os.path.exists(BATCH_QUESTION_FILE)


def read_pending_question():
    """Read pending question (used by Claude Code monitor)."""
    if os.path.exists(BATCH_QUESTION_FILE):
        with open(BATCH_QUESTION_FILE, "r", encoding="utf-8") as f:
            return "batch", json.load(f)
    if os.path.exists(QUESTION_FILE):
        with open(QUESTION_FILE, "r", encoding="utf-8") as f:
            return "single", json.load(f)
    return None, None


def write_answer(answer_text):
    """Write answer for a single question (used by Claude Code monitor)."""
    with open(ANSWER_FILE, "w", encoding="utf-8") as f:
        json.dump({"answer": answer_text, "timestamp": time.time()}, f)


def write_batch_answers(answers_dict):
    """Write answers for batch question (used by Claude Code monitor)."""
    with open(BATCH_ANSWER_FILE, "w", encoding="utf-8") as f:
        json.dump({"answers": answers_dict, "status": "done", "timestamp": time.time()}, f)
