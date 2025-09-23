import json
import re
from sentence_transformers import SentenceTransformer, util
from config.config import *
from utils.text_utils import _normalize_q
from utils.text_utils import _norm

def infer_question_category(question_text, answer):
    """
    Infers a detailed category for a question based on its answer type
    and, for booleans, its polarity (positive/negative framing).
    """
    # First, determine the basic answer type
    answer_type = "text" # Default
    if isinstance(answer, list):
        answer_type = "list"
    elif isinstance(answer, dict):
        answer_type = "dict"
    elif isinstance(answer, (int, float)):
        answer_type = "numeric"
    elif isinstance(answer, str):
        if re.match(r'^\d+(\.\d+)?$', answer.strip()):
            answer_type = "numeric"
        elif answer.strip().lower() in ["yes", "no", "true", "false"]:
            answer_type = "boolean"

    # If it's a boolean question, determine its polarity
    if answer_type == "boolean":
        q_lower = question_text.lower()
        # Keywords indicating a negatively framed question (where 'No' is the desired answer for an authorized person)
        negative_keywords = ["require", "future", "need visa"]
        if any(keyword in q_lower for keyword in negative_keywords):
            return "boolean_negative"
        else:
            # Assume positive framing otherwise (e.g., "Are you authorized...")
            return "boolean_positive"
            
    return answer_type

def cleanup_qa_memory():
    """
    Interactively cleans the QA memory file by categorizing questions by answer
    type and polarity, then performs semantic clustering within each category.
    """
    try:
        with open(QA_MEMORY_FILE, "r", encoding="utf-8") as f:
            mem = json.load(f)
    except FileNotFoundError:
        print(f"Error: {QA_MEMORY_FILE} not found. Make sure you are in the correct directory.")
        return

    # --- 1. Categorize questions by type and polarity ---
    print("Step 1: Categorizing questions by type and polarity...")
    questions_to_process = {k: v for k, v in mem.items() if not k.startswith('_') and v.get("answer") is not None}
    
    categorized_questions = {
        "boolean_positive": [], "boolean_negative": [], "numeric": [], 
        "list": [], "dict": [], "text": []
    }

    for q_text, data in questions_to_process.items():
        category = infer_question_category(q_text, data["answer"])
        categorized_questions[category].append(q_text)
    
    print("Categorization complete.")

    # --- 2. Perform semantic clustering within each category ---
    print("\nStep 2: Performing semantic clustering...")
    print("Loading sentence transformer model...")
    model = SentenceTransformer('all-mpnet-base-v2')
    
    final_groups = []

    for category, q_list in categorized_questions.items():
        if not q_list: continue
        print(f"--- Clustering '{category}' questions ({len(q_list)} total) ---")
        
        if len(q_list) < 2:
            for q_text in q_list:
                final_groups.append({
                    "representative_question": q_text,
                    "questions": [{"text": q_text, "data": questions_to_process[q_text]}]
                })
            continue

        embeddings = model.encode(q_list, convert_to_tensor=True)
        clusters = util.community_detection(embeddings, min_community_size=15, threshold=0.55)
        
        processed_indices = set()
        for cluster in clusters:
            rep_q = q_list[cluster[0]]
            new_group = {"representative_question": rep_q, "questions": []}
            for q_index in cluster:
                q_text = q_list[q_index]
                new_group["questions"].append({"text": q_text, "data": questions_to_process[q_text]})
                processed_indices.add(q_index)
            final_groups.append(new_group)
        
        for i in range(len(q_list)):
            if i not in processed_indices:
                q_text = q_list[i]
                final_groups.append({
                    "representative_question": q_text,
                    "questions": [{"text": q_text, "data": questions_to_process[q_text]}]
                })

    print(f"\nClustering complete. Consolidated into {len(final_groups)} final groups.")

    # --- 3. Interactive conflict resolution ---
    print("\nStep 3: Resolving conflicting answers...")
    cleaned_mem = {"_slots": mem.get("_slots", {})}

    for i, group in enumerate(final_groups):
        unique_answers = {json.dumps(q["data"]["answer"], sort_keys=True): q["data"]["answer"] for q in group["questions"]}

        if len(unique_answers) == 1:
            canonical_question = group["representative_question"]
            canonical_data = group["questions"][0]["data"]
            cleaned_mem[_normalize_q(canonical_question)] = canonical_data
        else:
            print("\n" + "="*25 + f"\nCONFLICT in Group {i+1}/{len(final_groups)}\n" + "="*25)
            print("Similar questions with different answers:")
            for q in group["questions"]:
                print(f"  - Q: \"{q['text']}\" -> A: {q['data']['answer']}")

            print("\nPlease choose the single BEST answer for this group:")
            answer_options = list(unique_answers.values())
            for j, ans in enumerate(answer_options):
                print(f"  [{j+1}] {ans}")
            print(f"  [{len(answer_options) + 1}] Enter a new, corrected answer")

            choice = -1
            while choice < 1 or choice > len(answer_options) + 1:
                try:
                    choice = int(input(f"Your choice (1-{len(answer_options) + 1}): "))
                except ValueError:
                    print("Invalid input.")
            
            if choice == len(answer_options) + 1:
                new_answer_str = input("Enter the new correct answer (use JSON format for lists/dicts): ")
                try:
                    final_answer = json.loads(new_answer_str)
                except json.JSONDecodeError:
                    final_answer = new_answer_str
            else:
                final_answer = answer_options[choice - 1]

            canonical_question = group["representative_question"]
            final_data = group["questions"][0]["data"]
            final_data["answer"] = final_answer
            cleaned_mem[_normalize_q(canonical_question)] = final_data
            print(f"Resolution saved for group: '{_normalize_q(canonical_question)}'")

    # --- 4. Save the cleaned file ---
    output_file = QA_MEMORY_FILE.replace(".json", "_cleaned.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(cleaned_mem, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50 + "\n🎉 Cleanup complete! 🎉")
    print(f"A new file has been saved to: {output_file}")
    print(f"Please review it, then back up your old memory file and rename to '{QA_MEMORY_FILE}'.")
    print("="*50)

def compare_answers(slot_answer, question_answer):
    """
    Compares a canonical slot answer with a question's stored answer,
    handling different data types (string, dict).
    """
    if isinstance(slot_answer, dict):
        slot_answer = slot_answer.get("text", "")
    if isinstance(question_answer, dict):
        question_answer = question_answer.get("text", "")

    # Use the bot's normalization for a case-insensitive comparison
    return _norm(str(slot_answer)) == _norm(str(question_answer))

def prune_redundant_questions():
    """
    Removes questions from the QA memory if they are covered by a slot AND
    their answer is consistent with the slot's canonical answer. Flags
    inconsistencies for manual review.
    """
    try:
        with open(QA_MEMORY_FILE, "r", encoding="utf-8") as f:
            mem = json.load(f)
    except FileNotFoundError:
        print(f"Error: {QA_MEMORY_FILE} not found.")
        return

    slots = mem.get("_slots", {})
    questions_to_process = {k: v for k, v in mem.items() if not k.startswith('_')}
    pruned_mem = {"_slots": slots}
    
    questions_removed = 0
    questions_kept = 0
    conflicts_found = 0

    print("Analyzing and pruning memory file with safety checks...")
    datass = {}
    answers = {}
    for q_text, data in questions_to_process.items():
        matched_slot = None
        for slot_key, pattern in SLOT_PATTERNS.items():
            if pattern.search(q_text):
                matched_slot = slot_key
                break
        
        if matched_slot:
            # This question is covered by a slot. Now, check the answer.
            if matched_slot in slots:
                slot_answer = slots[matched_slot]
                question_answer = data.get("answer")

                if compare_answers(slot_answer, question_answer):
                    # Answers are consistent, so it's safe to prune.
                    #print(f"  - Removing: \"{q_text[:80]}...\" (consistent with slot: '{matched_slot}')")
                    questions_removed += 1
                else:
                    # CONFLICT! Keep the question and flag it.
                    #print(f"  - ⚠️  CONFLICT: Keeping \"{q_text[:80]}...\"")
                    #print(f"    Slot ('{matched_slot}') answer is '{slot_answer}', but question answer is '{question_answer}'. Please review.")
                    pruned_mem[q_text] = data # Keep the conflicting entry
                    questions_kept += 1
                    conflicts_found += 1

                    if(matched_slot not in datass):
                        datass[matched_slot] = ""
                    if(str(slot_answer) not in answers):
                        answers[str(slot_answer)] = 0
                    datass[matched_slot] = datass[matched_slot] + f"\n{matched_slot}|{slot_answer}|{question_answer}"
                    answers[str(slot_answer)] = answers[str(slot_answer)] + 1
            else:
                # The slot exists in patterns but not in the memory file's _slots dict.
                #print(f"  - WARNING: Question matches slot '{matched_slot}', but this slot is not defined in qa_memory.json. Keeping question.")
                pruned_mem[q_text] = data
                questions_kept += 1
        else:
            # This question is not covered by any slot, so keep it.
            pruned_mem[q_text] = data
            questions_kept += 1

    print(datass)
    print(answers)
    # --- Save the pruned file ---
    output_file = QA_MEMORY_FILE.replace(".json", "_pruned.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(pruned_mem, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50)
    print("✅ Pruning Complete! ✅")
    print(f"Questions Removed: {questions_removed}")
    print(f"Questions Kept:    {questions_kept}")
    print(f"Conflicts Found:   {conflicts_found} (These require manual review)")
    print(f"\nA new, safer memory file has been saved to: {output_file}")
    print(f"After reviewing any conflicts, you can replace '{QA_MEMORY_FILE}' with this new file.")
    print("="*50)

if __name__ == "__main__":
    cleanup_qa_memory()
    #prune_redundant_questions()