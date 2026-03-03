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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
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
# SNAPSHOT EDITION ACTUAL
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
# EXTRAER TEXTO
# -------------------------------------------------

def extract_article_text(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text() for p in paragraphs])
        return clean_text(text)
    except Exception as e:
        print("Error extrayendo artículo:", e)
        return ""

# -------------------------------------------------
# EXTRAER IMAGEN
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
# GENERAR RESUMEN IA
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
            temperature=0.2,
        )

        summary = clean_text(response.choices[0].message.content)

        if len(summary) > 280:
            summary = summary[:280]
            summary = summary.rsplit(".", 1)[0] + "."

        return summary

    except Exception as e:
        print("Error generando resumen:", e)
        return None

# -------------------------------------------------
# GENERAR AUDIO
# -------------------------------------------------

def generate_audio_blocks(headlines, fecha_legible):

    if not OPENAI_API_KEY or not headlines:
        return

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    audio_files = []

    intro_text = f"Actualización de Ray News del {fecha_legible}."

    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=intro_text,
    ) as response:
        response.stream_to_file("part_0.mp3")

    audio_files.append("part_0.mp3")

    for i, h in enumerate(headlines):
        filename = f"part_{i+1}.mp3"

        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="nova",
            input=h["titleOriginal"],
        ) as response:
            response.stream_to_file(filename)

        audio_files.append(filename)

    with open("files.txt", "w") as f:
        for file in audio_files:
            f.write(f"file '{file}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "files.txt",
        "-c", "copy",
        "edition_audio.mp3"
    ])

    for file in audio_files:
        if os.path.exists(file):
            os.remove(file)

    if os.path.exists("files.txt"):
        os.remove("files.txt")

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

for line in lines:
    parts = line.strip().split("||")
    if len(parts) != 3:
        continue

    title, url, source_name = parts
    news_id = make_id(url)

    if news_id in historical["news"]:
        continue

    article_text = extract_article_text(url)
    if len(article_text) < 400:
        continue

    summary = generate_summary(title, article_text)
    if not summary:
        continue

    image = extract_image(url)

    historical["news"][news_id] = {
        "titleOriginal": title,
        "summary280": summary,
        "sourceName": source_name,
        "sourceUrl": url,
        "imageUrl": image,
        "first_seen": now.isoformat()
    }

    new_items.append({
        "titleOriginal": title,
        "summary280": summary,
        "sourceName": source_name,
        "sourceUrl": url,
        "imageUrl": image,
        "type": "explainer",
        "isNew": True
    })

# -------------------------------------------------
# PRIORIDAD A FUENTES AUSENTES
# -------------------------------------------------

if edition_exists and new_items:

    # Contar cuántas noticias tiene cada fuente en la edición actual
    source_counter = {}
    for h in normalized_base:
        src = h["sourceName"]
        source_counter[src] = source_counter.get(src, 0) + 1

    def priority(item):
        count = source_counter.get(item["sourceName"], 0)

        # Prioridad máxima si la fuente no existe en edición
        if count == 0:
            return (0, 0)
        else:
            return (1, count)

    new_items.sort(key=priority)

    new_items = new_items[:MAX_NEW_PER_EDITION]

# -------------------------------------------------
# CONSTRUIR EDICIÓN BALANCEADA
# -------------------------------------------------

combined = new_items + normalized_base

source_counts = {}
balanced_final = []

while combined and len(balanced_final) < MAX_TOTAL:

    combined.sort(
        key=lambda x: source_counts.get(x["sourceName"], 0)
    )

    selected = combined.pop(0)
    balanced_final.append(selected)

    src = selected["sourceName"]
    source_counts[src] = source_counts.get(src, 0) + 1

final_headlines = balanced_final

edition = {
    "api_version": 3,
    "edition_date": fecha_legible,
    "generated_at": now.isoformat(),
    "country": "Internacional",
    "headlines": final_headlines
}

edition_tmp = "edition_tmp.json"
with open(edition_tmp, "w", encoding="utf-8") as f:
    json.dump(edition, f, indent=2, ensure_ascii=False)

os.replace(edition_tmp, EDITION_FILE)

hist_tmp = "historical_tmp.json"
with open(hist_tmp, "w", encoding="utf-8") as f:
    json.dump(historical, f, indent=2, ensure_ascii=False)

os.replace(hist_tmp, HIST_FILE)

if new_items:
    generate_audio_blocks(new_items, fecha_legible)

print("Noticias finales:", len(final_headlines))
print("===== FIN GENERATE.PY =====")
