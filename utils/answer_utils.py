from utils.text_utils import fuzzy_match_option, _norm

def adapt_answer_to_question(stored_answer, current_question, available_options=None):
    """
    Adapt a stored answer to work with the current question format
    """
    if stored_answer is None:
        return None
    
    # Extract the actual answer value
    if isinstance(stored_answer, dict):
        answer_value = stored_answer.get("text", stored_answer.get("value", ""))
    elif isinstance(stored_answer, list):
        answer_value = [str(item) for item in stored_answer]
    else:
        answer_value = str(stored_answer)
    
    # Handle different answer formats
    if available_options and isinstance(answer_value, (str, list)):
        return adapt_to_available_options(answer_value, available_options)
    
    return answer_value

def adapt_to_available_options(stored_answer, available_options):
    """
    Convert stored answer to match available options using fuzzy matching
    """
    if isinstance(stored_answer, list):
        # For checkbox/multi-select
        adapted_answers = []
        for answer in stored_answer:
            matched = fuzzy_match_option(answer, available_options)
            if matched:
                adapted_answers.append(matched)
        return adapted_answers if adapted_answers else None
    else:
        # For radio/select
        return fuzzy_match_option(stored_answer, available_options)