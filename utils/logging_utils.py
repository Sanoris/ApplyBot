from config.config import *
from selenium.webdriver.support import expected_conditions as EC
import os
import csv
from datetime import datetime
from utils.memory_utils import _load_counts, _save_counts, _append_rows_csv
from utils.question_utils import _question_key

def get_daily_log_path():
    return f"{LOG_FILE + datetime.now().strftime('%Y%m%d')}.csv"

def init_log():
    if not os.path.exists(get_daily_log_path()):
        with open(get_daily_log_path(), mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Job Title", "Company", "Job URL", "$$$", "Description"])

def log_job(title, company, url, status, desc):
    with open(get_daily_log_path(), mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([datetime.now().isoformat(), title, company, url, status, desc])

def log_missed_questions(driver, missing_required):
    """
    Log each required-but-unanswered question.
    Writes a CSV row per question and updates a JSON counter.
    """
    if not missing_required:
        return

    url = driver.current_url
    try:
        page_title = driver.title or driver.execute_script("return document.title") or ""
    except Exception:
        page_title = ""

    ts = datetime.now().isoformat(timespec="seconds")

    rows = []
    counts = _load_counts()

    for q in missing_required:
        key = _question_key(q)
        kind = q.get("kind")
        qtext = (q.get("question") or "").strip()

        # try to capture control id/name for debugging
        ctrl_id = ctrl_name = ctrl_opts = ""
        ctrl = q.get("input")
        if not ctrl and q.get("options"):
            for opt in q["options"]:
                if opt.get("label"):
                    ctrl_opts = ctrl_opts + " | " + opt["label"]
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

        rows.append({
            "timestamp": ts,
            "url": url,
            "page_title": page_title,
            "q_key": key,
            "kind": kind,
            "question": qtext,
            "control_id": ctrl_id,
            "control_name": ctrl_name,
            "options": ctrl_opts,
            "ans": "",  # no answer yet
        })

        # bump counts
        entry = counts.get(key) or {"question": qtext, "kind": kind, "count": 0}
        entry["count"] = int(entry.get("count", 0)) + 1
        # if the question text varies slightly, keep the most recent version
        entry["question"] = qtext or entry["question"]
        counts[key] = entry

    _append_rows_csv(
        MISSED_Q_LOG_CSV,
        rows,
        header=["timestamp", "url", "page_title", "q_key", "kind", "question", "control_id", "control_name", "options", "ans"],
    )
    _save_counts(counts)

    # quick console summary
    bumped = ", ".join(f"{r['q_key']}" for r in rows)
    print(f"[missed-log] Recorded {len(rows)} unanswered required question(s): {bumped}")
