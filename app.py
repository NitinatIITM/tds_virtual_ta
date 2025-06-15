import os
import re
import base64
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from collections import Counter

# --- CONFIGURATION ---
TDS_FILE_PATH = "tds_2025_01_raw.txt"
DISCOURSE_FILE_PATH = "structured_tds_kb.txt"
API_KEY = os.getenv("API_KEY")
API_URL = "https://aipipe.org/openrouter/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"

# --- LOAD COURSE CONTENT ---
if not os.path.exists(TDS_FILE_PATH):
    raise FileNotFoundError(f"Course content file not found: {TDS_FILE_PATH}")
with open(TDS_FILE_PATH, "r", encoding="utf-8") as f:
    TDS_CONTEXT = f.read()

# --- PARSE STRUCTURED FORUM TEXT ---
def parse_structured_text(file_path):
    posts = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_post, content_lines = {"title": "", "url": "", "content": ""}, []

    for line in lines:
        line = line.strip()
        if line.startswith("# "):
            if current_post["title"]:
                current_post["content"] = "\n".join(content_lines).strip()
                posts.append(current_post)
                current_post, content_lines = {"title": "", "url": "", "content": ""}, []
            current_post["title"] = line[2:]
        elif line.startswith("🧭 URL:"):
            current_post["url"] = line.replace("🧭 URL:", "").strip()
        elif line.startswith("📄 Content:"):
            content_lines = []
        elif line.startswith("---"):
            continue
        else:
            content_lines.append(line)

    if current_post["title"]:
        current_post["content"] = "\n".join(content_lines).strip()
        posts.append(current_post)

    return posts

DISCOURSE_DATA = parse_structured_text(DISCOURSE_FILE_PATH)

# --- INIT FLASK APP ---
app = Flask(__name__)
CORS(app)

# --- UTILITY FUNCTIONS ---
def tokenize(text):
    return re.findall(r'\b\w+\b', text.lower())

def compute_relevance_score(post, tokens):
    title_tokens = tokenize(post.get("title", ""))
    content_tokens = tokenize(post.get("content", ""))[:100]
    all_tokens = title_tokens + content_tokens
    token_counts = Counter(all_tokens)
    return sum(token_counts.get(token, 0) for token in tokens)

def extract_snippet(content, max_lines=3):
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    return " ".join(lines[:max_lines])

def find_related_links_by_text(reference_text, top_k=3):
    tokens = tokenize(reference_text)
    scored_posts = []

    for post in DISCOURSE_DATA:
        score = compute_relevance_score(post, tokens)
        if score > 0:
            scored_posts.append((score, post))

    scored_posts.sort(reverse=True, key=lambda x: x[0])
    top_posts = [post for _, post in scored_posts[:top_k]]

    return [
        {
            "url": post["url"],
            "text": extract_snippet(post["content"])
        }
        for post in top_posts
    ]

# --- API ENDPOINT ---
@app.route("/api/", methods=["POST"])
def virtual_ta():
    try:
        data = request.get_json()
        question = data.get("question", "").strip()
        image_base64 = data.get("image", "").strip()

        if not question:
            return jsonify({"error": "Missing 'question' field"}), 400

        # Step 1: Get related forum content
        initial_links = find_related_links_by_text(question)
        forum_context = "\n\n".join([
            f"(Post URL: {item['url']}) {item['text']}" for item in initial_links
        ])

        full_context = (
            f"### COURSE MATERIAL ###\n{TDS_CONTEXT}\n\n"
            f"### RELATED FORUM POSTS ###\n{forum_context}"
        )

        # Message setup
        messages = [
            {"role": "system", "content": "You are a teaching assistant for TDS. Use only provided content to answer."},
            {"role": "user", "content": f"{full_context}\n\n### STUDENT QUESTION:\n{question}\n\n### ANSWER:"}
        ]

        if image_base64:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Attached is an image relevant to the question."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]
            })

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": MODEL,
            "messages": messages,
            "temperature": 0.15,
            "max_tokens": 700
        }

        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        answer = result["choices"][0]["message"]["content"].strip()

        final_links = find_related_links_by_text(answer)

        return jsonify({
            "answer": answer,
            "links": final_links
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return render_template("index.html")

# --- START SERVER ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
