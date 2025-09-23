import json
from sentence_transformers import SentenceTransformer, util
from config.config import QA_MEMORY_FILE

def analyze_question_frequency():
    """
    Analyzes the QA memory file to find the most frequently asked types of questions,
    which are ideal candidates for creating new slots.
    """
    try:
        with open(QA_MEMORY_FILE, "r", encoding="utf-8") as f:
            mem = json.load(f)
    except FileNotFoundError:
        print(f"Error: {QA_MEMORY_FILE} not found.")
        return

    print("Step 1: Loading all questions from memory...")
    questions_to_process = [k for k in mem.keys() if not k.startswith('_')]
    
    if len(questions_to_process) < 2:
        print("Not enough questions in memory to analyze.")
        return

    # --- Use Sentence Transformers for accurate semantic clustering ---
    print("Step 2: Loading sentence transformer model...")
    model = SentenceTransformer('all-mpnet-base-v2')
    
    print("Step 3: Generating embeddings and clustering questions...")
    embeddings = model.encode(questions_to_process, convert_to_tensor=True)
    # A lower threshold is better for finding broader topics
    clusters = util.community_detection(embeddings, min_community_size=9, threshold=0.66)

    cluster_details = []
    for i, cluster in enumerate(clusters):
        # The representative question is a sample from the cluster
        representative_question = questions_to_process[cluster[0]]
        cluster_size = len(cluster)
        cluster_details.append({
            "representative_question": representative_question,
            "count": cluster_size
        })

    # --- Sort clusters by size to find the most frequent topics ---
    cluster_details.sort(key=lambda x: x["count"], reverse=True)

    print("\n" + "="*50)
    print("📊 Top 15 Most Frequent Question Topics 📊")
    print("="*50)
    print("These are your best candidates for new slots.")
    
    for i, detail in enumerate(cluster_details[:15]):
        print(f"  {i+1}. Count: {detail['count']:<5} | Topic: \"{detail['representative_question']}\"")

if __name__ == "__main__":
    analyze_question_frequency()