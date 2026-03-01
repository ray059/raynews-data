import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import hashlib

print("===== INICIO GENERATE.PY =====")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HIST_FILE = "historical_editions.json"

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()

def make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()

# -------------------------------------------------
# CARGAR HISTÓRICO
# -------------------------------------------------
if os.path.exists(HIST_FILE):
    with open(HIST_FILE, "r", encoding="utf-8") as f:
        historical = json.load(f)
else:
    historical = {"news": {}}

# -------------------------------------------------
# EXTRAER TEXTO
# -------------------------------------------------
def extract_article_text(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text() for p in paragraphs])
        return clean_text(text)
    except:
        return ""

# -------------------------------------------------
# EXTRAER IMAGEN
# -------------------------------------------------
def extract_image(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]
    except:
        pass
    return None

# -------------------------------------------------
# GENERAR RESUMEN IA
# -------------------------------------------------
def generate_summary(title, article_text):
    if not OPENAI_API_KEY:
        return None

    import openai
    openai.api_key = OPENAI_API_KEY

    prompt = f"""
Responde claramente el titular en máximo 280 caracteres.
Basate únicamente en el texto proporcionado.
No inventes información.

Titular: {title}

Artículo:
{article_text[:4000]}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return clean_text(response["choices"][0]["message"]["content"])
    except:
        return None

# -------------------------------------------------
# MAIN
# -------------------------------------------------
headlines = []

if not os.path.exists("links.txt"):
    print("No hay links.txt")
    exit()

with open("links.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

now = datetime.now(ZoneInfo("America/Bogota"))

for line in lines:
    parts = line.strip().split("||")
    if len(parts) != 3:
        continue

    title, url, source_name = parts
    news_id = make_id(url)

    is_new = False

    if news_id in historical["news"]:
        stored = historical["news"][news_id]
        summary = stored["summary280"]
        image = stored.get("imageUrl")
        historical["news"][news_id]["last_used"] = now.isoformat()
    else:
        is_new = True

        article_text = extract_article_text(url)
        if len(article_text) < 400:
            continue

        summary = generate_summary(title, article_text)
        if not summary:
            continue

        image = extract_image(url)

        historical["news"][news_id] = {
            "titleOriginal": title,
            "summary280": summary[:280],
            "sourceName": source_name,
            "sourceUrl": url,
            "imageUrl": image,
            "first_seen": now.isoformat(),
            "last_used": now.isoformat()
        }

    headlines.append({
        "titleOriginal": title,
        "summary280": summary[:280],
        "sourceName": source_name,
        "sourceUrl": url,
        "imageUrl": image,
        "type": "explainer",
        "isNew": is_new
    })

    if len(headlines) >= 20:
        break

# Ordenar por first_seen descendente
headlines = sorted(
    headlines,
    key=lambda x: historical["news"][make_id(x["sourceUrl"])]["first_seen"],
    reverse=True
)

edition = {
    "api_version": 2,
    "edition_date": now.strftime("%d %b %Y"),
    "generated_at": now.isoformat(),
    "country": "Internacional",
    "headlines": headlines
}

with open("edition.json", "w", encoding="utf-8") as f:
    json.dump(edition, f, indent=2, ensure_ascii=False)

with open(HIST_FILE, "w", encoding="utf-8") as f:
    json.dump(historical, f, indent=2, ensure_ascii=False)

print("Noticias finales:", len(headlines))
print("===== FIN GENERATE.PY =====")
