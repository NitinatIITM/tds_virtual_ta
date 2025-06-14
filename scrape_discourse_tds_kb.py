import requests
import time
from datetime import datetime

# --- CONFIGURATION ---
BASE_URL = "https://discourse.onlinedegree.iitm.ac.in"
CATEGORY_ID = 34
CATEGORY_URL = f"{BASE_URL}/c/courses/tds-kb/{CATEGORY_ID}.json"
TOPIC_URL_TEMPLATE = f"{BASE_URL}/t/{{slug}}/{{id}}.json"
SAVE_FILE = "structured_tds_kb.txt"

COOKIES = {
    "_t": "XsnPuVBpqDlogcQ5txUfZBHr0AMJLOzP5qbIjDO1XHmxIRE%2B8ghXpPwCem25x0GZhTG4pSVkbdrIYwodzN%2FvZHnUPHJEBUbCvDRPFKdw64Smie533Hw%2FaFXjhwGLmrWd%2F9znzGJ7Q3xqNIjHxdXTlt%2FYE%2Br5D%2Fnv13Ygn7nX73JJnZXKA6EWYaSa2LaaRmUCQMfHn0teAlB97tJ5K7V49WsbkhYb6RpySEE%2FFm1GWlV2QrqRR6WnzSr9JaCxVL6fysSTRMAUuXaHu9KSBMzAwFkB%2BH%2Fm9teA%2FN5iWqyd%2BbdafGaNQgQB408Z76Vv4luo--1D768a18bHTYVFMN--W0a5ravPjMZknzHLratblw%3D%3D"
}
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}
session = requests.Session()
session.headers.update(HEADERS)
session.cookies.update(COOKIES)

# --- FILTER RANGE ---
START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 4, 30)

# --- STEP 1: Fetch all topics across pages ---
def get_all_topic_links():
    print("🔍 Fetching topics across pages...")
    topics = []
    page = 0

    while True:
        url = f"{BASE_URL}/c/courses/tds-kb/{CATEGORY_ID}.json?page={page}"
        res = session.get(url)
        res.raise_for_status()
        data = res.json()

        page_topics = data["topic_list"]["topics"]
        if not page_topics:
            break

        for topic in page_topics:
            created_at = topic.get("created_at") or topic.get("last_posted_at")
            created_date = datetime.fromisoformat(created_at.split("T")[0])

            if START_DATE <= created_date <= END_DATE:
                title = topic["title"]
                topic_id = topic["id"]
                slug = topic["slug"]
                url = f"{BASE_URL}/t/{slug}/{topic_id}"
                json_url = f"{url}.json"
                topics.append((title, url, json_url))

        page += 1
        time.sleep(0.5)

    print(f"✅ Found {len(topics)} topics from Jan–Apr 2025")
    return topics

# --- STEP 2: Scrape each topic's JSON content ---
def scrape_topic_json(title, url, json_url):
    print(f"📄 Scraping: {title}")
    try:
        res = session.get(json_url)
        res.raise_for_status()
        data = res.json()

        posts = data["post_stream"]["posts"]
        content = "\n\n".join(
            post["cooked"]
            .replace("<p>", "")
            .replace("</p>", "")
            .replace("<br>", "")
            .strip()
            for post in posts
        )
        return content
    except Exception as e:
        print(f"❌ Failed to scrape {json_url}: {e}")
        return "[Error fetching content]"

# --- STEP 3: Format and Save ---
def save_all():
    topics = get_all_topic_links()
    output = []

    for title, url, json_url in topics:
        content = scrape_topic_json(title, url, json_url)
        entry = (
            "--------------------------------------------------------------------------------\n"
            f"# {title}\n\n"
            f"🧭 URL: {url}\n\n"
            "📄 Content:\n"
            f"{content.strip()}\n"
        )
        output.append(entry)
        time.sleep(1.0)

    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output))

    print(f"\n✅ Scraped {len(output)} posts. Saved to {SAVE_FILE}")

# --- MAIN ---
if __name__ == "__main__":
    save_all()