from config.config import *
import os
import csv
import json
from utils.answer_utils import adapt_answer_to_question
from utils.text_utils import _norm, _normalize_q, fuzzy_match_question
from datetime import datetime

def _append_rows_csv(path, rows, header):
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow(r)

def _load_counts():
    try:
        with open(MISSED_Q_COUNTS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_counts(d):
    with open(MISSED_Q_COUNTS_JSON, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def load_resume_text(path: str) -> str:
    try:
        # fall back to plain text
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""

def recall_slot(mem, slot_key):
    """Read a generic slot value (e.g., 'linkedin_url') from qa_memory.json dict."""
    return (mem.get("_slots") or {}).get(slot_key)

def remember_slot(mem, slot_key, value):
    """Write/update a generic slot value and persist qa_memory.json via save_qa_memory()."""
    mem.setdefault("_slots", {})[slot_key] = value
    save_qa_memory(mem)

def load_qa_memory():
    try:
        with open(QA_MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_qa_memory(mem):
    with open(QA_MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)

def remember_answer(mem, question_text, answer, kind=None):
    """
    answer can be:
      - str (radio/text/textarea/select text)
      - list[str] (checkboxes)
      - dict like {"text": "...", "value": "..."} for selects
    """
    key = _normalize_q(question_text)
    mem[key] = {"kind": kind, "answer": answer, "ts": datetime.now().isoformat()}
    save_qa_memory(mem)

def recall_answer(mem, question_text):
    """Find the best matching answer using fuzzy question matching"""
    norm_current = _normalize_q(question_text)
    
    # First try exact match
    exact_key = next((k for k in mem.keys() if _normalize_q(k) == norm_current), None)
    if exact_key:
        return mem[exact_key].get("answer")
    
    # Then try fuzzy match
    for stored_question, data in mem.items():
        if fuzzy_match_question(stored_question, question_text):
            return data.get("answer")
    
    return None

def get_adapted_answer(mem, current_question, available_options=None):
    """
    Get and adapt a stored answer for the current question
    """
    stored_answer = recall_answer(mem, current_question)
    if stored_answer is None:
        return None
    
    return adapt_answer_to_question(stored_answer, current_question, available_options)

