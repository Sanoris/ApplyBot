import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException, TimeoutException, NoSuchElementException
import time
import random
from config import config

def setup_driver():
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={config.PROFILE_PATH}")
    options.add_argument(f"--profile-directory={config.PROFILE_NAME}")  # or 'Profile 1', etc.
    options.add_argument("--window-size=1280,800")
    driver = uc.Chrome(use_subprocess=True, options=options)
    driver.implicitly_wait(5)
    return driver

# === UTILITY FUNCTIONS === #
def human_sleep(min_sec=1, max_sec=3):
    #return
    time.sleep(random.uniform(min_sec, max_sec))

def human_scroll_and_hover(driver, element):
    actions = ActionChains(driver)
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
    human_sleep(0.5, 1.5)
    actions.move_to_element(element).perform()
    human_sleep(0.5, 1.2)

def explore_page(driver):
    print("Exploring page... Throwing off captchas....")
    print()
    extra_elements = driver.find_elements(By.CSS_SELECTOR, 'div.cardOutline')[:3]
    for el in extra_elements:
        try:
            human_scroll_and_hover(driver, el)
        except:
            pass

def _safe_click(driver, el):
    try:
        human_scroll_and_hover(driver, el)
        el.click()
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            return False

def _click_option(driver, opt):
    # Prefer label (inputs often hidden)
    if opt.get("input"):
        if _safe_click(driver, opt["input"]):
            return True
    # Re-find and click
    if opt.get("label_locator"):
        try:
            lab = driver.find_element(*opt["label_locator"])
            if _safe_click(driver, lab):
                return True
        except Exception:
            pass
    try:
        inp = driver.find_element(*opt["input_locator"])
        return _safe_click(driver, inp)
    except Exception:
        return False
    
def _resolve(driver, el, locator):
    if el:
        try:
            _ = el.tag_name
            return el
        except StaleElementReferenceException:
            pass
    if locator and not (locator[0] == By.XPATH and locator[1] == "."):
        try:
            return driver.find_element(*locator)
        except Exception:
            return None
    return None

def get_clickable_parent(driver, element):
    parent = element
    while parent:
        tag = parent.tag_name.lower()
        if tag in ['a', 'button']:
            return parent
        if parent.get_attribute('onclick'):
            return parent
        try:
            parent = parent.find_element(By.XPATH, '..')
        except:
            return None
    return None

def wait_for_document_ready(driver, timeout=10):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

def wait_for_url_settled(driver, timeout=20, settle_time=0.8, max_hops=3):
    """
    Waits for readyState=complete and follows quick JS redirects.
    Returns the final URL after it has remained unchanged for `settle_time` seconds.
    """
    start = time.time()
    hops = 0
    last_url = driver.current_url

    while True:
        # 1) Ensure DOM ready for the *current* URL
        remaining = max(1, timeout - (time.time() - start))
        try:
            WebDriverWait(driver, remaining).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            break  # bail; return whatever URL we have

        # 2) Give the page a moment to fire a script-based redirect
        #    If URL changes quickly, loop and wait ready again.
        changed = False
        try:
            remaining = max(1, timeout - (time.time() - start))
            WebDriverWait(driver, min(3, remaining)).until(lambda d: d.current_url != last_url)
            last_url = driver.current_url
            hops += 1
            changed = True
        except TimeoutException:
            pass

        if changed and hops < max_hops:
            # follow next hop
            continue

        # 3) If no immediate change, require the URL to remain stable for `settle_time`
        stable_start = time.time()
        while time.time() - stable_start < settle_time:
            if driver.current_url != last_url:
                # a late redirect—follow it
                last_url = driver.current_url
                hops += 1
                if hops >= max_hops:
                    return last_url
                # wait for this new page to be ready, then re-check stability
                break
            time.sleep(0.1)
        else:
            # stable for settle_time; we're done
            return last_url

        # loop to handle the late redirect
        if time.time() - start >= timeout:
            return driver.current_url

def wait_for_any(driver, selectors, timeout=10):
    for sel in selectors:
        try:
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, sel))
            )
        except TimeoutException:
            pass
    return None

def _locator_for_input(inp):
    _id = inp.get_attribute("id")
    if _id:
        return (By.ID, _id)
    name = inp.get_attribute("name")
    value = inp.get_attribute("value")
    if name and value:
        return (By.CSS_SELECTOR, f'input[name="{name}"][value="{value}"]')
    if name:
        return (By.NAME, name)
    return (By.XPATH, ".")  # last resort

def _locator_for_el(el):
    _id = el.get_attribute("id")
    if _id:
        return (By.ID, _id)
    name = el.get_attribute("name")
    if name:
        return (By.CSS_SELECTOR, f'[name="{name}"]')
    return (By.XPATH, ".")

def is_recaptcha_present(driver):
    selectors = [
        "//iframe[@title='reCAPTCHA']",
        "//textarea[contains(@class, 'g-recaptcha-response')]",
        "//div[@id='captcha-wrapper']"
    ]
    
    for selector in selectors:
        el = driver.find_elements(By.XPATH, selector)
        if len(el) > 0 and el[0].is_displayed():
            return True
    return False