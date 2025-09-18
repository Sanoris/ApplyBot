from utils.memory_utils import load_resume_text
from utils.text_utils import _norm, _normalize_q
from config.config import *
from openai import OpenAI
from datetime import datetime


def application_select(question: str, options: list[str], qDict: dict) -> str | None:
    """Return a number of years (float) or None if unknown."""
    if(not USE_OPENAI):
        return None
    client = OpenAI(api_key=OPENAI_KEY)
    print(f"[{qDict["kind"] or "huh??"}] Autofilling for question: {question}")
    text = load_resume_text(RESUME_PATH)[:MAX_RESUME_CHARS]
    slim_opts = options[:20]
    # Ask for JUST a number; robustly parse the first number back.
    messages = [
        {
            "role": "system",
            "content": (
                "Your task is to help this user find a job as quickly as possible. If you are unsure of the correct answer, choose the answer most likely to result in an employment offer."
                "Given a question and a list of options (as visible to a user), "
                "choose the SINGLE best option based on the resume. "
                "IMPORTANT: Respond with the option text EXACTLY as provided. "
                "The user is a U.S. citizen. The correct answer to an inquiry about requiring sponsorship is 'No'"
                f"Question: {question}\n"
                f"Options:\n- " + "\n- ".join(slim_opts) + "\n\n"
                "Resume:\n<<<\n" + text + "\n>>>\n"
                "Answer with exactly one of the options or 'unknown'."
            ),
        }
    ]
    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=messages,
        )
        # Return exact match if present
        for o in slim_opts:
            if response.output_text == o:
                return o
        # Try case-insensitive
        for o in slim_opts:
            if _norm(response.output_text) == _norm(o):
                return o
    except Exception as e:
        print("[select] API choose_option failed:", e)
    return None

def application_field(question: str, qDict: dict) -> str | None:
    """Return a number of years (float) or None if unknown."""
    if(not USE_OPENAI):
        return None
    client = OpenAI(api_key=OPENAI_KEY)
    print(f"[{qDict["kind"] or "huh??"}] Autofilling for question: {question}")
    text = load_resume_text(RESUME_PATH)[:MAX_RESUME_CHARS]
    # Ask for JUST a number; robustly parse the first number back.
    messages = [
        {
            "role": "system",
            "content": (
                "You fill job-application text fields using only facts from the provided resume. "
                "If a question can be answered professionally with a single word, do so."
                f"Limit to {max_chars} characters unless the question explicitly requests a list. "
                "If the resume lacks enough info, make your best guess based on typical experience levels."
                "If the question is asking for years, make sure to give an integer number only."
                "If question can be answered with a number, only return the number."
                "Your task is to help this user find a job as quickly as possible. You may take a few liberties to achieve this goal."
                "You may answer with 'N/A' if the question is not applicable to the user."
                f"If the question asks for a date, answer in mm/dd/yyyy format. The current date is {datetime.now().isoformat()[:10]}."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{question}\n\n"
                "Resume:\n<<<\n"
                f"{text}\n"
                ">>>\n\n"
                "Return ONLY the filled answer text (no labels, no quotes, no markdown)."
            ),
        },
    ]
    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=messages,
        )
        print(response.output_text)
        return response.output_text

    except Exception as e:
        print("API call failed:", e)
    return None

def heuristic_pick_for_slot(slot_key, options_texts):
    nopts = [_norm(x) for x in options_texts]
    if slot_key == "country":
        hits = ["united states", "united states (+1)", "united states of america", "usa", "us"]
        for h in hits:
            # exact/contains check on normalized text
            for i, t in enumerate(nopts):
                if t == _norm(h) or _norm("united states") in t or "(+1)" in t and "united states" in t:
                    return options_texts[i]
    if slot_key == "work_auth":
        # prioritize yes/authorized options
        for i,t in enumerate(nopts):
            if "yes" == t or "authorized" in t and "not" not in t:
                return options_texts[i]
    if slot_key == "relocate":
        # default: No (change if you want auto-Yes)
        for i,t in enumerate(nopts):
            if t == "no":
                return options_texts[i]
    if slot_key == "education_level":
        # choose the highest plausible degree
        rank = {
            "high school":1, "associate":2, "bachelor":3, "ba":3, "bs":3,
            "master":4, "ms":4, "ma":4, "mba":4, "phd":5, "doctor":5
        }
        best_i, best_r = None, -1
        for i,t in enumerate(nopts):
            r = max([rank[k] for k in rank if k in t] + [-1])
            if r > best_r:
                best_r = r; best_i = i
        if best_i is not None and best_r>=0:
            return options_texts[best_i]
    return None

def cover_letter_ai(desc: str) -> str | None:
    if(not USE_OPENAI):
        return None
    client = OpenAI(api_key=OPENAI_KEY)
    text = load_resume_text(RESUME_PATH)[:MAX_RESUME_CHARS]
    # Ask for JUST a number; robustly parse the first number back.
    messages = [
        {
            "role": "system",
            "content": """You are an expert career coach and professional writer. Your task is to craft a highly compelling, authentic, and tailored cover letter in the user's own voice.

                **CRITICAL GUIDELINES:**
                1.  **Voice and Persona:** Write in the first person, as if you are the user. Adopt a tone that is professional, confident, and enthusiastic, reflecting their level of experience.
                2.  **Content Sourcing:** Base the letter *exclusively* on the information provided in the user's resume and the job description. Do not invent skills, experiences, or accomplishments that are not present or directly implied. You may, however, frame existing experiences in the most positive and relevant light.
                3.  **Strategic Goal:** The letter must not be a summary of the resume. It must connect the user's specific experiences and skills directly to the requirements and language of the job description. Answer: "Why am I the perfect fit for *this* role at *this* company?"
                4.  **Structure:**
                    -   Start with a strong opening paragraph stating the role you're applying for and a powerful hook (e.g., a key achievement relevant to the role).
                    -   Use 1-2 body paragraphs to draw clear parallels between your past successes and the role's responsibilities. Use examples and metrics from the resume.
                    -   Conclude by reiterating your enthusiasm for the company specifically and your confidence that you can contribute to their goals.
                5.  **Formatting:** Return ONLY the raw text of the cover letter, ready to be copied and pasted. Do not use markdown (no **bold**, no headings). Use line breaks between paragraphs.
                """
        },
        {
            "role": "user",
            "content": f"""Please write a cover letter for me based on my resume and the following job description.

                **Job Description:**
                <<<
                {desc}
                >>>

                **My Resume:**
                <<<
                {text}
                >>>

                Please write the cover letter as if you are me, using the first person perspective. Focus on aligning my background with the key requirements of the role. The letter should be concise, persuasive, and approximately one page in length when written in a word processor.
                """
        },
    ]
    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=messages,
        )
        print(response.output_text)
        return response.output_text

    except Exception as e:
        print("API call failed:", e)
    return None