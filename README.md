# ApplyBot 🤖

ApplyBot is a sophisticated, AI-powered bot designed to automate the process of applying for jobs on Indeed. It uses Selenium and Undetected Chromedriver to navigate job postings, fill out application forms, and submit them, leveraging a persistent memory and OpenAI to handle questions intelligently.

---

## ✨ Features

* **Automated Job Application**: Navigates through Indeed search results and applies to jobs marked "Easily apply".
* **AI-Powered Form Filling**: Uses OpenAI to answer text-based questions and select the best options in dropdowns based on your resume and the job description.
* **Persistent Memory**: Remembers answers to previously seen questions, speeding up future applications.
* **Intelligent Question Handling**: Utilizes fuzzy logic and semantic matching to recognize variations of questions it has answered before.
* **Custom Cover Letters**: Generates tailored cover letters on the fly for each application using AI.
* **Human-like Behavior**: Simulates human scrolling and random delays to avoid detection.
* **Detailed Logging**: Keeps a CSV log of all submitted applications and unanswered questions for review.

---

## 🛠️ Setup & Installation

Follow these steps to get ApplyBot running on your local machine.

### 1. Prerequisites

* Python 3.8+
* Google Chrome browser

### 2. Clone the Repository

```bash
git clone https://github.com/Sanoris/ApplyBot.git
cd ApplyBot
```

### 3. Install Dependencies

Install all the required Python libraries using the provided `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 4. Create Configuration Files

The bot requires a few configuration files that are not checked into version control.

* **Create `config/config.py`**:
    In the `config` directory, copy the `config.py.example` file and rename it to `config.py`. Edit this file to add your details.

* **Create `config/resume.txt`**:
    In the `config` directory, create a new file named `resume.txt`. Paste the plain text of your resume into this file. The bot uses this to answer questions and generate cover letters.

### 5. Set up Chrome Profile

The bot uses a dedicated Chrome profile to maintain your Indeed login session.

1.  Close all instances of Google Chrome.
2.  Run the bot for the first time using the command: `python applyBot.py`
3.  The bot will open a new Chrome window. **Do not interact with the terminal yet.**
4.  In the Chrome window, sign in to your Indeed account and solve any CAPTCHAs that appear.
5.  Once you have logged in, make sure to upload your resume to Indeed (the bot currently only selects the pre-existing option)
6.  Go back to the terminal and press `Enter` to start the bot.

# TIP: Use firefox to browse, and you can watch vidya while you observe the application process 

---

## ▶️ Usage

To run the bot, simply execute the batch file from the root directory of the project:

```bash
applyBot.bat
```

This script first ensures all previous Chrome instances are closed and then starts the main Python script.

---

## 📁 Project File Structure (Required Placeholders)

Here are the files you need to create for the bot to run correctly. These are ignored by Git for security and personalization.

```
.
├── browser/                  # Will be created automatically for your Chrome profile data.
├── config/
│   ├── config.py             # **CREATE THIS**: Your personal configuration (API keys, URLs).
│   └── resume.txt            # **CREATE THIS**: Your resume in plain text.
├── data/
│   ├── qa_memory.json        # Will be created automatically to store question answers.
│   ├── missed_questions.csv  # Will be created automatically to log questions the bot couldn't answer.
└── ...                       # (rest of the project files)
```