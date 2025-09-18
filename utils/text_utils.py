import re
from fuzzywuzzy import fuzz, process

ANSWER_NORMALIZATION_PATTERNS = {
    r'^(yes|yep|yeah|y|true|1)$': 'Yes',
    r'^(no|nope|nah|n|false|0)$': 'No',
    r'^(male|m)$': 'Male',
    r'^(female|f)$': 'Female',
    r'^(bachelor|bs|ba|b\.s\.|b\.a\.)$': "Bachelor's",
    r'^(master|ms|ma|m\.s\.|m\.a\.)$': "Master's",
    r'^(phd|ph\.d\.|doctorate)$': "PhD",
}

def normalize_answer(answer):
    """Normalize common answer variations to standard forms"""
    if not isinstance(answer, str):
        return answer
    
    norm_answer = _norm(answer)
    for pattern, standard in ANSWER_NORMALIZATION_PATTERNS.items():
        if re.match(pattern, norm_answer):
            return standard
    
    return answer

def _normalize_q(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip().lower()
    t = re.sub(r"[ \u200b]", " ", t)
    # Remove common question prefixes and suffixes
    t = re.sub(r'^(do you |have you |are you |what is |how many |please )', '', t)
    t = re.sub(r'[?\.!]$', '', t)
    return t

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def fuzzy_match_question(stored_question, current_question, threshold=85):
    """Fuzzy match questions to handle slight wording variations"""
    norm_stored = _normalize_q(stored_question)
    norm_current = _normalize_q(current_question)
    
    # Exact match first
    if norm_stored == norm_current:
        return True
    
    # Fuzzy match
    ratio = fuzz.token_sort_ratio(norm_stored, norm_current)
    return ratio >= threshold

def fuzzy_match_option(stored_option, available_options, threshold=80):
    """Fuzzy match options to handle different phrasings"""
    if not available_options:
        return None
    
    norm_stored = _norm(stored_option)
    norm_available = [_norm(opt) for opt in available_options]
    
    # Exact match first
    for i, opt in enumerate(norm_available):
        if opt == norm_stored:
            return available_options[i]
    
    # Fuzzy match
    best_match, score = process.extractOne(norm_stored, norm_available, scorer=fuzz.token_sort_ratio)
    if score >= threshold:
        return available_options[norm_available.index(best_match)]
    
    return None