import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import hashlib
import subprocess

print("===== INICIO GENERATE.PY =====")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HIST_FILE = "historical_editions.json"
EDITION_FILE = "edition.json"

MAX_TOTAL = 20
MAX_NEW_PER_EDITION = 1
MAX_NEW_PER_SOURCE = 1

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# -------------------------------------------------
# UTILIDADES
# -------------------------------------------------

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()

def make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre",
    11: "noviembre", 12: "diciembre",
}

# -------------------------------------------------
# CARGAR HISTÓRICO
# -------------------------------------------------

if os.path.exists(HIST_FILE):
    with open(HIST_FILE, "r", encoding="utf-8") as f:
        historical = json.load(f)
else:
    historical = {"news": {}}

# -------------------------------------------------
# SNAPSHOT EDICIÓN ACTUAL
# -------------------------------------------------

base_edition = []

if os.path.exists(EDITION_FILE):
    with open(EDITION_FILE, "r", encoding="utf-8") as f:
        current_data = json.load(f)
        base_edition = current_data.get("headlines", [])

edition_exists = len(base_edition) > 0

normalized_base = []
for h in base_edition:
    h_copy = h.copy()
    h_copy["isNew"] = False
    normalized_base.append(h_copy)

# -------------------------------------------------
# EXTRAER ARTÍCULO
# -------------------------------------------------

def extract_article_text(url):

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        paragraphs = soup.find_all("p")

        text = " ".join([p.get_text() for p in paragraphs])
        text = clean_text(text)

        return text[:4000]

    except:
        return ""

# -------------------------------------------------
# RESUMEN IA
# -------------------------------------------------

def generate_summary(title, article_text):

    if not OPENAI_API_KEY:
        return None

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
Resume el artículo en máximo 280 caracteres.
Debe terminar en una frase completa.
No usar puntos suspensivos.
No inventar información.

Titular: {title}

Artículo:
{article_text[:4000]}
"""

    try:

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        summary = clean_text(response.choices[0].message.content)

        if len(summary) > 280:
            summary = summary[:280]
            summary = summary.rsplit(".", 1)[0] + "."

        return summary

    except:
        return None

# -------------------------------------------------
# IMAGEN
# -------------------------------------------------

def extract_image(url):

    try:

        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        og_image = soup.find("meta", property="og:image")

        if og_image and og_image.get("content"):
            return og_image["content"]

    except:
        pass

    return None

# -------------------------------------------------
# MAIN
# -------------------------------------------------

if not os.path.exists("links.txt"):
    print("No hay links.txt")
    exit()

with open("links.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

now = datetime.now(ZoneInfo("America/Bogota"))
fecha_legible = f"{now.day:02d} de {MESES_ES[now.month]} de {now.year}"

new_items = []
per_source_new_counter = {}

for line in lines:

    parts = line.strip().split("||")

    if len(parts) != 4:
        continue

    title, url, source_name, description = parts

    news_id = make_id(url)

    if news_id in historical["news"]:
        continue

    article_text = extract_article_text(url)

    if len(article_text) < 120:
        continue

    summary = generate_summary(title, article_text)

    if not summary:
        continue

    image = extract_image(url)
    if not image or "fallback-promo-image" in image:
        continue

    historical["news"][news_id] = {
        "titleOriginal": title,
        "summary280": summary,
        "articleText": article_text,
        "sourceName": source_name,
        "sourceUrl": url,
        "imageUrl": image,
        "first_seen": now.isoformat()
    }

    if per_source_new_counter.get(source_name, 0) >= MAX_NEW_PER_SOURCE:
        continue

    new_items.append({
        "titleOriginal": title,
        "summary280": summary,
        "articleText": article_text,
        "sourceName": source_name,
        "sourceUrl": url,
        "imageUrl": image,
        "type": "explainer",
        "isNew": True
    })

    per_source_new_counter[source_name] = (
        per_source_new_counter.get(source_name, 0) + 1
    )

combined = new_items + normalized_base
final_headlines = combined[:MAX_TOTAL]

edition = {
    "api_version": 3,
    "edition_date": fecha_legible,
    "generated_at": now.isoformat(),
    "country": "Internacional",
    "headlines": final_headlines
}

with open("edition_tmp.json", "w", encoding="utf-8") as f:
    json.dump(edition, f, indent=2, ensure_ascii=False)

os.replace("edition_tmp.json", EDITION_FILE)

with open("historical_tmp.json", "w", encoding="utf-8") as f:
    json.dump(historical, f, indent=2, ensure_ascii=False)

os.replace("historical_tmp.json", HIST_FILE)

print("Noticias nuevas detectadas:", len(new_items))
print("Noticias finales:", len(final_headlines))
print("===== FIN GENERATE.PY =====")
