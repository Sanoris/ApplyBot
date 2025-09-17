import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException, TimeoutException, NoSuchElementException
from utils.browser_utils import _safe_click, human_scroll_and_hover, human_sleep, wait_for_url_settled
from .form_utils import click_apply, click_continue, click_submit, try_autofill, try_autofill_options, try_autofill_selects
from .logging_utils import log_missed_questions
from .memory_utils import recall_answer
from .question_utils import extract_questions_with_elements, has_answer_on_page, pause_and_remember_questions, prefill_from_memory

def go_to_job(driver, root, mem):
    job_cards = driver.find_elements(By.XPATH, "//div[contains(@class, 'cardOutline') and .//*[contains(text(), 'Easily apply')]]")
    print(f"Found {len(job_cards)} jobs with Indeed Apply button on this page.")
    #time.sleep(1000)
    for job in job_cards:
        try:
            if job:
                print("Found job with easily apply button")
                human_scroll_and_hover(driver, job)
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable(job)).click()
                human_sleep(2, 3)
                desc = driver.find_element(By.ID, "jobDescriptionText")
                if "clearance" in (desc.text or "").lower():
                    print("Skipping job requiring clearance")
                    continue
                click_apply(driver)  # opens new tab
                time.sleep(2)
                handle_application(driver, root, mem)  # <— walk the flow, answer, submit
        except Exception as e:
            print(f"Skip job: {e}")
    return None, None

def handle_application(driver, root, mem, timeout=20):
    """
    Switches to the new tab, walks the Indeed flow based on URL,
    answers questions (with memory), and submits at review.
    Then closes the tab and returns to root.
    """
       # wait for new tab and switch
    try:
        WebDriverWait(driver, timeout).until(lambda d: len(d.window_handles) >= 2)
    except Exception:
        return False

    new_tab = [h for h in driver.window_handles if h != root][-1]
    driver.switch_to.window(new_tab)

    # settle after tab switch (Indeed often does an initial SPA/redirect)
    wait_for_url_settled(driver, timeout=20, settle_time=0.8, max_hops=3)
    driver.implicitly_wait(1)
    done = False
    steps = 0
    while not done and steps < 15:
        try:
            steps += 1
            url = (driver.current_url or "").lower()
            print("Flow URL:", url)

            if "resume-selection-module" in url:
                el = driver.find_element(By.CSS_SELECTOR, '[data-testid="resume-selection-file-resume-radio-card"]')
                _safe_click(driver, el)

                click_continue(driver)
                wait_for_url_settled(driver, timeout=20, settle_time=0.8, max_hops=3)

            elif "question" in url:
                
                print("Extracting questions...")
                # 1) Extract and prefill from memory
                questions = extract_questions_with_elements(driver)  # ensure this returns locators

                print("Prefilling questions...")
                prefill_from_memory(driver, questions, mem)
                print("Prefill done.")
                
                try_autofill(driver, mem, questions)
                try_autofill_selects(driver, mem, questions)
                try_autofill_options(driver, mem, questions)
                # 2) Evaluate which required questions still lack answers
                missing_required = []
                for q in questions:
                    #TODO: answering all for now - uncomment later?
                    if not q.get("required"):
                        continue
                    if not has_answer_on_page(driver, q):
                        # If we also *don't* have a remembered answer, we'll need to pause
                        if recall_answer(mem, q["question"]) is None:
                            missing_required.append(q)

                if missing_required:
                    log_missed_questions(driver, missing_required)

                    # 3) Only now do we pause for manual input, read back, and remember
                    print("\nRequired unanswered questions detected:")
                    for i, q in enumerate(missing_required, 1):
                        print(f"  {i}. [{q['kind']}] {q['question']}")

                    if (True):
                        print("Skipping manual input as per configuration.")
                        done = True
                        break
                    print("Fill these in the browser (do NOT click Continue).")
                    input("Press ENTER here when finished to save your answers... ")
                    # read *all* answers on the page and persist (covers required + any others you just set)
                    pause_and_remember_questions(driver)
                #else:
                    # 4) No pause; optionally record any prefilled answers that weren't in memory yet
                    #remember_present_answers_without_pause(driver, questions, mem)

                # 5) Proceed
                click_continue(driver)
                wait_for_url_settled(driver, timeout=20, settle_time=0.8, max_hops=3)

            elif "review" in url:
                if click_submit(driver):
                    wait_for_url_settled(driver, timeout=20, settle_time=0.8, max_hops=3)
                    done = True
                else:
                    click_continue(driver)
                    wait_for_url_settled(driver, timeout=20, settle_time=0.8, max_hops=3)

            elif ("postresumeapply" in url):
                wait_for_url_settled(driver, timeout=4, settle_time=0.8, max_hops=3)

            elif("indeed.com" not in url):
                wait_for_url_settled(driver, timeout=10, settle_time=0.8, max_hops=3)
            elif("post-apply" in url):
                done = True
            elif("intervention" in url):
                done = True
            else:
                # Unknown step—try Continue and settle
                if click_continue(driver):
                    wait_for_url_settled(driver, timeout=20, settle_time=0.8, max_hops=3)
                else:
                    # If nothing clickable, still give redirects a chance to fire then exit
                    wait_for_url_settled(driver, timeout=10, settle_time=0.8, max_hops=2)
                    done = True
                if steps >= 5:
                    done = True
        
        except Exception as e:
            print(f"Error during application flow: {e}")

    driver.implicitly_wait(5)
    # close tab and return
    try:
        driver.close()
    except Exception:
        pass
    try:
        driver.switch_to.window(root)
    except Exception:
        pass

    return True