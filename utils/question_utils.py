from config.config import *
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException, TimeoutException, NoSuchElementException
from utils.browser_utils import _resolve, _safe_click, _click_option, _locator_for_input, _locator_for_el
from utils.memory_utils import recall_answer, remember_answer, get_adapted_answer
from utils.text_utils import _norm, _normalize_q, fuzzy_match_question, normalize_answer
import hashlib
from fuzzywuzzy import fuzz


def select_by_visible_text(selfie, text: str):
    """Select all options that display text matching the argument. That is,
    when given "Bar" this would select an option like:

        <option value="foo">Bar</option>

    :Args:
        - text - The visible text to match against

        throws NoSuchElementException If there is no option with specified text in SELECT
    """
    xpath = f".//option[normalize-space(.) = {selfie._escape_string(text)}]"
    opts = selfie._el.find_elements(By.XPATH, xpath)
    matched = False
    for opt in opts:
        selfie._set_selected(opt)
        if not selfie.is_multiple:
            return True
        matched = True

    if len(opts) == 0 and " " in text:
        sub_string_without_space = selfie._get_longest_token(text)
        if sub_string_without_space == "":
            candidates = selfie.options
        else:
            xpath = f".//option[contains(.,{selfie._escape_string(sub_string_without_space)})]"
            candidates = selfie._el.find_elements(By.XPATH, xpath)
        for candidate in candidates:
            if text == candidate.text:
                selfie._set_selected(candidate)
                if not selfie.is_multiple:
                    return True
                matched = True

    if not matched:
        return False

def _is_selected(el):
    try:
        return el.is_selected() or (el.get_attribute("checked") in ("true", "checked", "1"))
    except Exception:
        return False

def choose_answer_label(question_text, options_labels, mem):
    # 1) memory
    remembered = recall_answer(mem, question_text)
    if remembered and any(remembered.strip().lower() == o.strip().lower() for o in options_labels):
        return remembered

    ql = _normalize_q(question_text)
    # 2) simple heuristics (tune as you like)
    if any(o.lower() == "yes" for o in options_labels):
        return "Yes"
    if "background check" in ql and any("yes" == o.lower() for o in options_labels):
        return "Yes"
    if "consent" in ql and any("yes" == o.lower() for o in options_labels):
        return "Yes"
    # fallback: first option
    return options_labels[0] if options_labels else None

def remember_present_answers_without_pause(driver, questions, mem):
    """If page already has answers (e.g., defaults) and we don't have them in memory, save them."""
    saved = 0
    for q in questions:
        # Check if we already have an equivalent question in memory using fuzzy matching
        if is_equivalent_question_in_memory(mem, q["question"]):
            continue  # already known (fuzzy match)
        
        val = get_current_answer(driver, q)
        if not val or (isinstance(val, list) and not val):
            continue  # no answer to save
        
        # Normalize and standardize the answer before saving using the existing normalize_answer function
        normalized_val = normalize_answer_for_storage(val, q["kind"])
        
        if q["kind"] == "checkbox":
            remember_answer(mem, q["question"], normalized_val, kind="checkbox")
            saved += 1
        elif q["kind"] in ("radio", "text", "textarea"):
            remember_answer(mem, q["question"], normalized_val, kind=q["kind"])
            saved += 1
        elif q["kind"] == "select":
            if isinstance(normalized_val, dict) and (normalized_val.get("value") or normalized_val.get("text")):
                remember_answer(mem, q["question"], normalized_val, kind="select")
                saved += 1
    
    if saved:
        print(f"[memory] Recorded {saved} prefilled answer(s) without pause.")

def is_equivalent_question_in_memory(mem, current_question):
    """Check if a similar question already exists in memory"""
    current_norm = _normalize_q(current_question)
    
    for stored_question in mem.keys():
        if stored_question == "_slots":  # Skip the slots section
            continue
        if fuzzy_match_question(stored_question, current_norm):
            return True
    
    return False

def normalize_answer_for_storage(answer, answer_kind):
    """Normalize answers for consistent storage using the existing normalize_answer function"""
    if answer is None:
        return None
    
    if answer_kind in ("radio", "select"):
        return normalize_single_answer(answer)
    elif answer_kind == "checkbox":
        return normalize_multiple_answers(answer)
    elif answer_kind in ("text", "textarea"):
        return normalize_text_answer(answer)
    
    return answer

def normalize_single_answer(answer):
    """Normalize single-choice answers using the existing normalize_answer"""
    if isinstance(answer, dict):
        # For select answers with text/value - normalize both
        normalized_text = normalize_answer(answer.get("text", ""))
        normalized_value = normalize_answer(answer.get("value", ""))
        return {"text": normalized_text, "value": normalized_value}
    else:
        # For radio buttons and simple select values
        return normalize_answer(str(answer))

def normalize_multiple_answers(answer):
    """Normalize multiple-choice answers using the existing normalize_answer"""
    if not isinstance(answer, list):
        answer = [answer]
    
    return [normalize_answer(str(item)) for item in answer if item]

def normalize_text_answer(answer):
    """Normalize text answers - use as-is but ensure string format"""
    if isinstance(answer, dict):
        # Handle cases where text answer might be in a dict structure
        return str(answer.get("text", answer.get("value", "")))
    return str(answer)


def pause_and_remember_questions(driver):
    """
    1) Extract questions
    2) Pause execution so you can fill answers in the browser (DON'T click Continue yet)
    3) Read your selections and save them to qa_memory.json
    """
    qs = extract_questions_with_elements(driver)

    print("\n--- Indeed questions detected ---")
    for i, q in enumerate(qs, 1):
        print(f"{i}. [{q['kind']}] {q['question']}")
    print("Fill out answers in the browser. Do NOT click Continue yet.")
    input("When finished, press ENTER here to save your choices... ")

    saved_count = 0
    for q in qs:
        kind = q["kind"]
        if kind == "radio":
            chosen = None
            for opt in q["options"]:
                inp = _resolve(driver, opt["input"], opt["input_locator"])
                if inp and _is_selected(inp):
                    chosen = opt["label"]
                    break
            if chosen:
                remember_answer(mem, q["question"], chosen, kind="radio")
                saved_count += 1

        elif kind == "checkbox":
            chosen_labels = []
            for opt in q["options"]:
                inp = _resolve(driver, opt["input"], opt["input_locator"])
                if inp and _is_selected(inp):
                    chosen_labels.append(opt["label"])
            if chosen_labels:
                remember_answer(mem, q["question"], chosen_labels, kind="checkbox")
                saved_count += 1

        elif kind in ("text", "textarea"):
            el = _resolve(driver, q["input"], q["input_locator"])
            if el:
                val = (el.get_attribute("value") or "").strip()
                if val:
                    remember_answer(mem, q["question"], val, kind=kind)
                    saved_count += 1

        elif kind == "select":
            el = _resolve(driver, q["input"], q["input_locator"])
            if el:
                try:
                    opts = el.find_elements(By.TAG_NAME, "option")
                    sel = next((o for o in opts if o.is_selected()), None)
                    if sel:
                        remember_answer(mem, q["question"], {"text": sel.text.strip(), "value": sel.get_attribute("value")}, kind="select")
                        saved_count += 1
                except Exception:
                    pass
        # kind == "info" → nothing to save

    print(f"Saved {saved_count} answer(s) to {QA_MEMORY_FILE}.")


def prefill_from_memory(driver, questions, mem):
    """Apply remembered answers using fuzzy matching"""
    for q in questions:
        # Get available options for matching
        available_options = None
        if q["kind"] in ("radio", "checkbox") and q["options"]:
            available_options = [opt["label"] for opt in q["options"]]
        elif q["kind"] == "select":
            el = _resolve(driver, q["input"], q["input_locator"])
            if el:
                available_options = [o.text for o in el.find_elements(By.TAG_NAME, "option") if o.text.strip()]
        
        # Get adapted answer
        adapted_ans = get_adapted_answer(mem, q["question"], available_options)
        if adapted_ans is None:
            if q["kind"] in ("radio", "checkbox") and len(q["options"]) < 2:
                _click_option(driver, q["options"][0])
                print(f"[{q['kind']}] Only one option for '{q['question'][:60]}…', auto-selecting it.")
            continue

        if q["kind"] == "radio":
            if len(q["options"]) < 2:
                inp = _resolve(driver, q["options"][0]["input"], q["options"][0]["input_locator"])
                if inp and not _is_selected(inp):
                    _click_option(driver, q["options"][0])
                    print(f"[{q['kind']}] Only one option for '{q['question'][:60]}…', auto-selecting it.")
                    continue

            # Find the best matching option using fuzzy matching
            best_match = None
            best_score = 0
            for opt in q["options"]:
                score = fuzz.token_sort_ratio(_norm(opt["label"]), _norm(str(adapted_ans)))
                if score > best_score and score >= 75:  # 75% similarity threshold
                    best_score = score
                    best_match = opt
            
            if best_match:
                _click_option(driver, best_match)
                print(f"[{q['kind']}] Fuzzy matched '{adapted_ans}' to '{best_match['label']}' (score: {best_score})")
            else:
                # Fallback to first option if no good match found
                _click_option(driver, q["options"][0])
                print(f"[{q['kind']}] No good match found for '{adapted_ans}', selected first option")

        elif q["kind"] == "checkbox":
            if not isinstance(adapted_ans, (list, tuple)):
                adapted_ans = [adapted_ans]
            
            if len(q["options"]) == 1:
                _click_option(driver, q["options"][0])
                continue
            
            # Convert adapted answers to normalized set for comparison
            adapted_set = {_norm(str(a)) for a in adapted_ans}
            
            for opt in q["options"]:
                inp = _resolve(driver, opt["input"], opt["input_locator"])
                if not inp: 
                    continue
                
                # Check if this option should be selected using fuzzy matching
                opt_norm = _norm(opt["label"])
                should_be_on = any(
                    fuzz.token_sort_ratio(opt_norm, _norm(adapted_ans_item)) >= 75
                    for adapted_ans_item in adapted_ans
                )
                
                is_on = _is_selected(inp)
                if should_be_on and not is_on:
                    _click_option(driver, opt)
                    print(f"[{q['kind']}] Selected '{opt['label']}' based on fuzzy match")
                elif not should_be_on and is_on:
                    # Optionally deselect if it shouldn't be selected
                    _click_option(driver, opt)
                    print(f"[{q['kind']}] Deselected '{opt['label']}'")

        elif q["kind"] in ("text", "textarea"):
            el = _resolve(driver, q["input"], q["input_locator"])
            if el:
                current = (el.get_attribute("value") or "")
                if current.strip() != str(adapted_ans).strip():
                    el.clear()
                    el.send_keys(str(adapted_ans))
                    print(f"[{q['kind']}] Filled '{q['question'][:60]}…' with '{adapted_ans}'")

        elif q["kind"] == "select":
            el = _resolve(driver, q["input"], q["input_locator"])
            if not el:
                continue
            
            want_text = adapted_ans.get("text") if isinstance(adapted_ans, dict) else str(adapted_ans)
            
            try:
                # First, try to select by visible text with exact match
                select_by_visible_text(Select(el), want_text)
                print(f"[{q['kind']}] Selected '{want_text}' by exact text")
                
            except Exception as e:
                print(f"Failed to select by exact text for '{q['question']}': {e}")
                
                # Fallback to fuzzy matching with options
                opts = el.find_elements(By.TAG_NAME, "option")
                option_texts = [o.text.strip() for o in opts if o.text.strip()]
                
                if option_texts:
                    # Find best fuzzy match
                    best_option = None
                    best_score = 0
                    for opt_text in option_texts:
                        score = fuzz.token_sort_ratio(_norm(opt_text), _norm(want_text))
                        if score > best_score and score >= 75:
                            best_score = score
                            best_option = opt_text
                    
                    if best_option:
                        try:
                            select_by_visible_text(Select(el), best_option)
                            print(f"[{q['kind']}] Fuzzy matched '{want_text}' to '{best_option}' (score: {best_score})")
                        except Exception:
                            # Final fallback: click the option element directly
                            for op in opts:
                                if op.text.strip() == best_option:
                                    _safe_click(driver, op)
                                    break
                    else:
                        print(f"[{q['kind']}] No good match found for '{want_text}' in options")

def _question_key(q):
    """
    Build a stable key using normalized text + control id/name + inner data-testid (when present).
    """
    base = _normalize_q(q.get("question") or "")
    ctrl_id = ctrl_name = testid = ""
    try:
        el = q.get("element")
        if el:
            # first data-testid in the subtree (often stable)
            t = el.find_elements(By.CSS_SELECTOR, "[data-testid]")
            if t:
                testid = t[0].get_attribute("data-testid") or ""
    except Exception:
        return None

    # prefer a real control for id/name
    ctrl = None
    if q.get("input"):
        ctrl = q["input"]
    elif q.get("options"):
        ctrl = q["options"][0].get("input")
    if ctrl:
        try:
            ctrl_id = ctrl.get_attribute("id") or ""
        except Exception:
            pass
        try:
            ctrl_name = ctrl.get_attribute("name") or ""
        except Exception:
            pass

    sig = "|".join([base, ctrl_name, ctrl_id, testid])
    digest = hashlib.sha1(sig.encode("utf-8", "ignore")).hexdigest()[:12]
    return f"q:{digest}"


def _item_blob_for_slots(item):
    """
    Collect label/assistive text + relevant control attributes into one string
    so regexes can match regardless of exact phrasing.
    """
    parts = [(item.text or "")]
    for el in item.find_elements(By.CSS_SELECTOR, "input,textarea,select"):
        for a in ("name","id","placeholder","aria-label","data-testid","type"):
            try:
                v = el.get_attribute(a)
                if v:
                    parts.append(v)
            except Exception:
                pass
    return " ".join(parts).lower()

def detect_slot(item):
    """
    Map a question 'item' (the .ia-Questions-item element) to a generic slot key,
    like 'linkedin_url', 'country', etc., or return None if no match.
    """
    blob = _item_blob_for_slots(item)

    # Primary regex rules
    for key, rx in SLOT_PATTERNS.items():
        if rx.search(blob):
            # sanity: URL slots should target text/textarea inputs
            if key.endswith("_url"):
                if item.find_elements(By.CSS_SELECTOR, "input[type='text'], input:not([type]), textarea"):
                    return key
            else:
                return key

    # Strong fallback: explicit domain mention
    if "linkedin.com" in blob:
        return "linkedin_url"

    return None

def is_select_answered(sel):
    """True only if selected option is not the placeholder (value=='' or text like 'Select...')."""
    try:
        opts = sel.find_elements(By.TAG_NAME, 'option')
        sel_opt = next((o for o in opts if o.is_selected()), None)
        if not sel_opt:
            return False
        text = (sel_opt.text or '').strip()
        value = (sel_opt.get_attribute('value') or '').strip()
        if value == '' or PLACEHOLDER_RE.search(text):
            return False
        return True
    except Exception:
        return False

def get_current_answer(driver, q):
    """Return the current value for a question q (None/empty if not answered)."""
    kind = q["kind"]
    if kind == "radio":
        for opt in q["options"]:
            inp = _resolve(driver, opt["input"], opt["input_locator"])
            if inp and _is_selected(inp):
                return opt["label"]
        return None
    if kind == "checkbox":
        labels = []
        for opt in q["options"]:
            inp = _resolve(driver, opt["input"], opt["input_locator"])
            if inp and _is_selected(inp):
                labels.append(opt["label"])
        return labels
    if kind in ("text", "textarea"):
        el = _resolve(driver, q["input"], q["input_locator"])
        if not el: return None
        return (el.get_attribute("value") or "").strip() or None
    if kind == "select":
        el = _resolve(driver, q["input"], q["input_locator"])
        if not el: return None
        try:
            opts = el.find_elements(By.TAG_NAME, "option")
            sel = next((o for o in opts if o.is_selected()), None)
            if not sel: return None
            return {"text": sel.text.strip(), "value": sel.get_attribute("value")}
        except Exception:
            return None
    return None  # info

def has_answer_on_page(driver, q):
    kind = q["kind"]

    if kind == "checkbox":
        vals = get_current_answer(driver, q)
        return bool(vals) and len(vals) > 0

    if kind == "radio":
        return bool(get_current_answer(driver, q))

    if kind in ("text", "textarea"):
        val = get_current_answer(driver, q)
        return bool(val and val.strip())

    if kind == "select":
        el = _resolve(driver, q["input"], q["input_locator"])
        return bool(el) and is_select_answered(el)  # placeholder-aware

    return True  # info rows never block

def compute_required(item, debug=False):
    """
    Decide if a question item is required. Works for both 'mosaic-provider-*' and 'css-*' skins.
    Signals (any one => required):
      - Asterisk in/near label
      - Any control with [required] or aria-required="true"
      - Any control with aria-invalid="true"
      - Error/help text indicating the field must be answered
    """

    # 1) Asterisk anywhere under the item’s label area (generic, no testid dependency)
    has_asterisk = bool(item.find_elements(
        By.XPATH,
        ".//label//*[normalize-space(text())='*'] | .//*[normalize-space(text())='*' and (@aria-hidden='true' or self::span or self::div)]"
    ))

    # 2) Native/ARIA required on any descendant control
    has_required_attr = bool(item.find_elements(By.CSS_SELECTOR, "input[required], select[required], textarea[required], [aria-required='true']"))

    # 3) Currently invalid (Indeed flags empty required controls with aria-invalid='true')
    has_invalid = bool(item.find_elements(By.CSS_SELECTOR, "[aria-invalid='true']"))

    # 4) Error text — catch both mosaic and css variants; look for ids with 'error'
    err_nodes = item.find_elements(By.XPATH, ".//*[contains(@id,'error') or contains(@id,'error-text') or contains(@class,'error') or @role='alert' or @aria-live='assertive']")
    err_text = " ".join((n.text or "").strip() for n in err_nodes if (n.text or "").strip())
    has_err_text = bool(err_text and ERROR_TEXT_RE.search(err_text))

    if debug:
        # short line for console
        label_snip = (item.text or "").strip().split("\n")[0][:120]
        print(f"[required?] asterisk={has_asterisk} requiredAttr={has_required_attr} invalid={has_invalid} err={has_err_text} | {label_snip}")

    return has_asterisk or has_required_attr or has_invalid or has_err_text


def extract_questions_with_elements(driver, timeout=10):
    '''
    [
        {
            "question": str,          # The text of the question (e.g., "Do you have a driver's license?").
            "required": bool,         # Whether the question is required.
            "kind": str,              # The type of input field (e.g., "radio", "checkbox", "select", "text", "textarea", or "info").
            "element": WebElement,    # The parent WebDriver element of the entire question block.
            "options": list,          # A list of option dictionaries for "radio" or "checkbox" question types. Empty for others.
            "input": WebElement,      # The main input element (e.g., <select> or <input>). Null for "info" and "radio/checkbox" types.
            "input_locator": tuple,   # A tuple (By, str) for locating the main input element. Null for "info" and "radio/checkbox" types.
        },
        # ... more question dictionaries ...
    ]

    Options list Structure:
    [
        {
            "label": str,             # The text label for the option (e.g., "Yes" or "No").
            "input": WebElement,      # The WebDriver element for the radio button or checkbox itself.
            "label_el": WebElement,   # The WebDriver element for the <label> tag associated with the input.
            "input_locator": tuple,   # A tuple (By, str) for locating the input element.
            "label_locator": tuple,   # A tuple (By, str) for locating the label element. Can be None if no `id` is present on the input.
        },
        # ... more option dictionaries ...
    ]
    '''
    driver.implicitly_wait(0)
    items = driver.find_elements(By.CSS_SELECTOR, ".ia-Questions-item")
    results = []

    for item in items:
        q_text = None
        rich = item.find_elements(By.CSS_SELECTOR, '[data-testid="rich-text"] span')
        if rich:
            q_text = rich[0].text.strip()
        if not q_text:
            info = item.find_elements(By.CSS_SELECTOR, '[data-testid="information-question"]')
            if info:
                q_text = info[0].text.strip()
        if not q_text:
            # fallback: any label text inside the item (strip trailing asterisks)
            lbls = item.find_elements(By.TAG_NAME, "label")
            if lbls:
                t = (lbls[0].text or "").strip()
                q_text = re.sub(r"\s*\*\s*$", "", t).strip() or None
        if not q_text:
            continue

        required = compute_required(item)
        if("upload" in q_text.lower()):
            continue
        entry = {"question": q_text, "required": required, "kind": None,
                 "element": item, "options": [], "input": None, "input_locator": None}

        radios = item.find_elements(By.CSS_SELECTOR, 'label > input[type="radio"]')
        if radios:
            entry["kind"] = "radio"
            for lab in item.find_elements(By.CSS_SELECTOR, "label"):
                r = lab.find_elements(By.CSS_SELECTOR, 'input[type="radio"]')
                if not r: 
                    continue
                inp = r[0]
                span_texts = [s.text.strip() for s in lab.find_elements(By.CSS_SELECTOR, "span") if s.text.strip()]
                label_text = span_texts[0] if span_texts else lab.text.strip()
                _id = inp.get_attribute("id")
                entry["options"].append({
                    "label": label_text,
                    "input": inp,
                    "label_el": lab,
                    "input_locator": _locator_for_input(inp),
                    "label_locator": (By.CSS_SELECTOR, f'label[for="{_id}"]') if _id else None,
                    "selected": _is_selected(inp),
                })
                if(_is_selected(inp)):
                    entry["selected"] = label_text
            results.append(entry)
            print(f"Extracted radio question: '{q_text[:50]}' with {len(entry['options'])} options\n")
            print(f"\tOptions:\n\t" + "\n\t".join([o['label'] for o in entry['options']]))

            continue

        checks = item.find_elements(By.CSS_SELECTOR, 'label > input[type="checkbox"]')
        if checks:
            entry["kind"] = "checkbox"
            for lab in item.find_elements(By.CSS_SELECTOR, "label"):
                c = lab.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]')
                if not c:
                    continue
                inp = c[0]
                span_texts = [s.text.strip() for s in lab.find_elements(By.CSS_SELECTOR, "span") if s.text.strip()]
                label_text = span_texts[0] if span_texts else lab.text.strip()
                _id = inp.get_attribute("id")
                entry["options"].append({
                    "label": label_text,
                    "input": inp,
                    "label_el": lab,
                    "input_locator": _locator_for_input(inp),
                    "label_locator": (By.CSS_SELECTOR, f'label[for="{_id}"]') if _id else None,
                })
            results.append(entry)
            continue

        selects = item.find_elements(By.TAG_NAME, "select")
        if selects:
            entry["kind"] = "select"
            entry["input"] = selects[0]
            entry["input_locator"] = _locator_for_el(selects[0])
            results.append(entry)
            continue

        textboxes = item.find_elements(By.CSS_SELECTOR, 'textarea, input:not([type="radio"]):not([type="checkbox"])')
        if textboxes:
            el = textboxes[0]
            entry["kind"] = "textarea" if el.tag_name.lower() == "textarea" else "text"
            entry["input"] = el
            entry["input_locator"] = _locator_for_el(el)
            results.append(entry)
            continue

        entry["kind"] = "info"
        results.append(entry)
    driver.implicitly_wait(5)
    print(f"Extracted {len(results)} questions from the page.")
    return results

