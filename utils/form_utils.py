import random
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from utils.ai_utils import application_field, application_select, heuristic_pick_for_slot
from utils.browser_utils import _click_option, _resolve, _safe_click, human_scroll_and_hover
from utils.memory_utils import recall_answer, recall_slot, remember_answer, remember_slot
from utils.question_utils import detect_slot, has_answer_on_page, is_select_answered, select_by_visible_text
from utils.text_utils import _norm
from selenium.webdriver.common.by import By


def try_autofill(driver, mem, questions):
    """
    For required text/textarea questions,
    call API, type the value, and remember it.
    Returns count of fields autofilled.
    """
    filled = 0
    for q in questions:
        if q["kind"] not in ("text", "textarea"):
            continue
        qtext = q.get("question") or ""
        # already answered?
        if has_answer_on_page(driver, q):
            continue
        if (recall_answer(mem, qtext) is not None):
            continue
        
        txt = application_field(qtext, q)
        if txt is None:
            continue

        el = _resolve(driver, q["input"], q["input_locator"])

        try:
            el.clear()
            el.send_keys(txt)
            remember_answer(mem, qtext, txt, kind=q["kind"])
            filled += 1

        except Exception as e:
            print(f"[years] Fill failed for '{qtext[:60]}…':", e)
    return filled

def try_autofill_selects(driver, mem, questions):
    """
    For unanswered <select> questions, try:
      1) slot memory (generic)
      2) heuristics by slot
      3) model-pick from options
    Saves per-question memory and slot memory when chosen.
    """
    filled = 0
    for q in questions:
        if q["kind"] == "radio" or q["kind"] == "checkbox":
            continue
         # only selects
        if q["kind"] != "select":
            continue
        el = _resolve(driver, q["input"], q["input_locator"])
        if not el:
            continue
        # already answered?
        if is_select_answered(el):
            continue

        opts = get_select_options(el)
        # flatten text list for picker
        option_texts = [o["text"] for o in opts if not is_placeholder_option(o)]
        if not option_texts:
            continue

        slot = detect_slot(q["element"])
        choice = None

        # 1) slot memory
        if slot:
            mem_val = recall_slot(mem, slot)
            if isinstance(mem_val, dict) and mem_val.get("text"):
                choice = mem_val["text"]
            elif isinstance(mem_val, str):
                choice = mem_val

        # 2) slot heuristics
        if not choice and slot:
            choice = heuristic_pick_for_slot(slot, option_texts)

        # 3) model choose
        if not choice:
            choice = application_select(q["question"], option_texts, q)

        if not choice:
            continue

        # Click chosen option
        if (select_by_visible_text(Select(el), choice)):
            # Remember
            remember_answer(mem, q["question"], {"text": choice}, kind="select")
            if slot:
                remember_slot(mem, slot, {"text": choice})
            filled += 1
            print(f"[select] Autofilled '{q['question'][:60]}…' with '{choice}'")
    return filled

def try_autofill_options(driver, mem, questions):
    """
    For unanswered radio/checkbox questions, try:
      1) memory recall
      2) heuristic pick
      3) model-pick from options
    """
    filled = 0
    for q in questions:
        # Only process radio/checkbox questions
        if q["kind"] not in ["radio", "checkbox"]:
            continue

        # Check if question is already answered on the page.
        if has_answer_on_page(driver, q):
            continue

        qtext = q.get("question") or ""
        option_texts = [o["label"] for o in q["options"]]
        choice = None

        # 1) Try memory recall
        mem_ans = recall_answer(mem, qtext)
        if isinstance(mem_ans, (str, list)):
            if q["kind"] == "radio":
                if mem_ans in option_texts:
                    choice = mem_ans
            elif q["kind"] == "checkbox":
                ans_list = [ans.strip().lower() for ans in mem_ans]
                chosen_options = [o for o in q["options"] if o["label"].strip().lower() in ans_list]
                for opt in chosen_options:
                    _click_option(driver, opt)
                if chosen_options:
                    remember_answer(mem, qtext, [o['label'] for o in chosen_options], kind="checkbox")
                    filled += 1
                    print(f"Autofilled '{qtext[:60]}…' with memory recall.")
                continue

        # 2) Slot heuristics (e.g., "yes" for work auth)
        if not choice:
            slot = detect_slot(q["element"])
            if slot:
                choice = heuristic_pick_for_slot(slot, option_texts)

        # 3) Use AI to pick an option
        if not choice:
            choice = application_select(qtext, option_texts, q)

        if choice:
            # Find and click the chosen option's label.
            target = next((o for o in q["options"] if o["label"] == choice), None)
            if target:
                if _click_option(driver, target):
                    remember_answer(mem, qtext, choice, kind=q["kind"])
                    filled += 1
                    print(f"[autofill_options] Autofilled '{qtext[:60]}…' with '{choice}'")
    return filled

def autofill_questions(driver):
    try:
        # Text inputs (e.g., short answers)
        text_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], textarea")
        for input_box in text_inputs:
            name_attr = input_box.get_attribute("name") or ""
            if "phone" in name_attr.lower():
                continue  # Skip phone if prefilled or irrelevant
            input_box.clear()
            input_box.send_keys("Yes")  # Or a custom response

        # Radio buttons or yes/no
        yes_labels = driver.find_elements(By.XPATH, "//label[contains(text(), 'Yes')]")
        for label in yes_labels:
            try:
                driver.execute_script("arguments[0].click();", label)
            except:
                pass

        # Dropdowns (select elements)
        selects = driver.find_elements(By.TAG_NAME, "select")
        for select in selects:
            options = select.find_elements(By.TAG_NAME, "option")
            for option in options:
                if "Yes" in option.text or "Remote" in option.text:
                    option.click()
                    break

    except Exception as e:
        print(f"Error autofilling questions: {e}")

def is_placeholder_option(op):
    t = _norm(op["text"])
    v = _norm(op["value"])
    return (v == "" or bool(re.match(r"^(select|choose|pick)\b", t)))

def get_select_options(select_el):
    """Return list of dicts [{'text','value','el'}] for options."""
    opts = []
    for op in select_el.find_elements(By.TAG_NAME, "option"):
        opts.append({
            "text": (op.text or "").strip(),
            "value": (op.get_attribute("value") or "").strip(),
            "el": op,
        })
    return opts

def select_by_text_contains(driver, select_el, needle_list):
    """Try exact/contains matches against option text; return True if clicked."""
    opts = get_select_options(select_el)
    needles = [_norm(n) for n in needle_list if n]
    # Prefer non-placeholder options only
    candidates = [o for o in opts if not is_placeholder_option(o)]
    # exact text first
    for n in needles:
        for o in candidates:
            if _norm(o["text"]) == n:
                _safe_click(driver, o["el"]); return True
    # contains
    for n in needles:
        for o in candidates:
            if n in _norm(o["text"]):
                _safe_click(driver, o["el"]); return True
    # try value, too
    for n in needles:
        for o in candidates:
            if _norm(o["value"]) == n or n in _norm(o["value"]):
                _safe_click(driver, o["el"]); return True
    return False

def click_apply(driver):
    try:
        apply_button = driver.find_element(By.XPATH, "//*[@aria-label='Apply now opens in a new tab']")
        actions = ActionChains(driver)
        actions.move_to_element(apply_button).pause(random.uniform(0.5, 1.0)).click().perform()
        return True
    except Exception as e:
        print(f"Apply button click failed: {e}")
        return False

def _click_first(driver, selectors, timeout=2):
    for xp in selectors:
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xp)))
            human_scroll_and_hover(driver, el)
            el.click()
            return True
        except Exception:
            pass
    return False

def click_continue(driver):
    # tries multiple shapes of the Continue button
    return _click_first(driver, [
 # Text on the button or within a child <span>
        '//button[not(@disabled) and (contains(normalize-space(.),"Review your application") or .//span[normalize-space()="Review your application"])]',
        # Common continue variants
        '//button[not(@disabled) and (contains(normalize-space(.),"Continue") or .//span[normalize-space()="Continue"])]',
        '//*[@role="button" and not(@disabled) and contains(normalize-space(.),"Continue")]',
        '//button[contains(@data-testid,"continue") or contains(@id,"continue")]',
        # Other labels Indeed sometimes uses
        '//button[not(@disabled) and (contains(normalize-space(.),"Next") or .//span[normalize-space()="Next"])]',
        '//button[not(@disabled) and (contains(normalize-space(.),"Save and continue") or .//span[normalize-space()="Save and continue"])]',
        '//button[not(@disabled) and (contains(normalize-space(.),"Continue application") or .//span[normalize-space()="Continue application"])]',
        '//button[not(@disabled) and (contains(normalize-space(.),"Continue to review") or .//span[normalize-space()="Continue to review"])]',
    ])

def click_add_cover(driver):
        # Switch to iframe if exists
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for iframe in iframes:
        try:
            driver.switch_to.frame(iframe)
            element = driver.find_element(By.XPATH, "//a[@aria-label='Add Supporting documents']")
            _safe_click(driver, element)
            driver.switch_to.default_content()
            return True
        except:
            driver.switch_to.default_content()
            continue
    return False

def click_submit(driver):
    return _click_first(driver, [
        '//button[not(@disabled) and (contains(normalize-space(.),"Submit") or .//span[contains(normalize-space(),"Submit")])]',
        '//*[@role="button" and not(@disabled) and contains(normalize-space(.),"Submit")]',
        '//button[contains(@data-testid,"submit") or contains(@id,"submit")]',
        # fallback for Indeed variants
        '//button[not(@disabled) and (contains(normalize-space(.),"Apply") or contains(normalize-space(.),"Finish"))]'
    ])