import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import re
from collections import Counter

print("===== INICIO GENERATE.PY =====")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()

def extract_image(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]

        img = soup.find("img")
        if img and img.get("src"):
            return img["src"]

    except:
        pass

    return None

def generate_summary(title, url):
    if not OPENAI_API_KEY:
        return "Resumen no disponible."

    import openai
    openai.api_key = OPENAI_API_KEY

    prompt = f"""
Responde claramente la pregunta del titular en máximo 280 caracteres.
Titular: {title}
URL: {url}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        summary = response.choices[0].message["content"]
        return clean_text(summary)[:280]

    except Exception as e:
        print("Error OpenAI:", e)
        return "Resumen no disponible."

def is_duplicate(title, used_keywords):
    words = re.findall(r"\w+", title.lower())
    keywords = [w for w in words if len(w) > 4]

    overlap = set(keywords) & used_keywords
    return len(overlap) > 3

headlines = []
used_keywords = set()

if not os.path.exists("links.txt"):
    print("No hay links.txt")
    exit()

with open("links.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    parts = line.strip().split("||")
    if len(parts) != 3:
        continue

    title, url, source_name = parts

    if is_duplicate(title, used_keywords):
        continue

    summary = generate_summary(title, url)
    image = extract_image(url)

    words = re.findall(r"\w+", title.lower())
    for w in words:
        if len(w) > 4:
            used_keywords.add(w)

    headlines.append({
        "titleOriginal": title,
        "summary280": summary,
        "sourceName": source_name,
        "sourceUrl": url,
        "imageUrl": image,
        "type": "question"
    })

    if len(headlines) >= 12:
        break

now = datetime.now(ZoneInfo("America/Bogota"))

edition = {
    "edition_date": now.strftime("%d %b %Y"),
    "generated_at": now.isoformat(),
    "country": "Internacional",
    "headlines": headlines
}

with open("edition.json", "w", encoding="utf-8") as f:
    json.dump(edition, f, indent=2, ensure_ascii=False)

print("===== FIN GENERATE.PY =====")
