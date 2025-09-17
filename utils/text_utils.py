import re

def _normalize_q(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip().lower()
    t = re.sub(r"[ \u200b]", " ", t)
    return t

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())