from config.config import *
import os
import csv
import json
from utils.text_utils import _norm, _normalize_q
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
    key = _normalize_q(question_text)
    rec = mem.get(key)
    return (rec or {}).get("answer")

