from config.config import *
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from utils.application_flow import go_to_job
from utils.browser_utils import _safe_click, explore_page, setup_driver
import sys
import time
import random
from utils.logging_utils import init_log
from utils.memory_utils import load_qa_memory, load_resume_text


def main():
    init_log()
    driver = setup_driver()
    driver.get(SEARCH_URL)
    root = driver.current_window_handle
    resume_text = load_resume_text(RESUME_PATH)
    mem = load_qa_memory()
    page = 10
    if(not skip_manual):
        test = input("Press Enter to start processing jobs...")
    while True:
        print(f"Processing jobs on page {page}")
        if random.random() < 0.3:
            explore_page(driver)
        title, company = go_to_job(driver, root, mem)
        
        page += 10
        el = driver.find_element(By.CSS_SELECTOR, '[data-testid="pagination-page-next"]')
        _safe_click(driver, el)
        time.sleep(2)

if __name__ == "__main__":
    if (len(sys.argv)>1):
        skip_manual = True
    main()
    #application_field("How many years of Jira projects experience do you have?")