import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import hashlib
import subprocess
from collections import defaultdict

print("===== INICIO GENERATE.PY =====")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HIST_FILE = "historical_editions.json"
EDITION_FILE = "edition.json"

MAX_TOTAL = 20
MAX_PER_SOURCE = 5

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

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
Resume el artículo en máximo 280 caracteres.
Debe terminar en una frase completa.
No cortar palabras.
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

    if not OPENAI_API_KEY:
        print("No hay OPENAI_API_KEY")
        return

    if not headlines:
        print("No hay nuevas noticias para audio")
        return

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    audio_files = []

    print("Generando audio...")

    intro_text = f"Actualización de Ray News del {fecha_legible}."

    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=intro_text,
    ) as response:
        response.stream_to_file("part_0.mp3")

    audio_files.append("part_0.mp3")

    voices = ["nova", "alloy"]

    for i, h in enumerate(headlines):
        voice = voices[i % 2]
        text = h["titleOriginal"]
        filename = f"part_{i+1}.mp3"

        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice=voice,
            input=text,
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

    print("Audio generado correctamente")

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
fecha_legible = f"{now.day:02d} de {MESES_ES[now.month]} de {now.year}"

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
            "summary280": summary,
            "sourceName": source_name,
            "sourceUrl": url,
            "imageUrl": image,
            "first_seen": now.isoformat(),
            "last_used": now.isoformat()
        }

    headlines.append({
        "titleOriginal": title,
        "summary280": summary,
        "sourceName": source_name,
        "sourceUrl": url,
        "imageUrl": image,
        "type": "explainer",
        "isNew": is_new
    })

# -------------------------------------------------
# SELECCIÓN BALANCEADA
# -------------------------------------------------

grouped = defaultdict(list)

for h in headlines:
    grouped[h["sourceName"]].append(h)

final_headlines = []

# Tomar hasta MAX_PER_SOURCE por fuente
for source in grouped:
    for h in grouped[source][:MAX_PER_SOURCE]:
        if len(final_headlines) < MAX_TOTAL:
            final_headlines.append(h)

# Rellenar si faltan
if len(final_headlines) < MAX_TOTAL:
    remaining = []
    for source in grouped:
        remaining.extend(grouped[source][MAX_PER_SOURCE:])

    for h in remaining:
        if len(final_headlines) < MAX_TOTAL:
            final_headlines.append(h)

headlines = final_headlines

new_headlines = [h for h in headlines if h["isNew"]]

if new_headlines:
    print(f"Hay {len(new_headlines)} noticias nuevas → se genera audio")
else:
    print("No hay noticias nuevas → no se regenera audio")

edition = {
    "api_version": 2,
    "edition_date": fecha_legible,
    "generated_at": now.isoformat(),
    "country": "Internacional",
    "headlines": headlines
}

with open(EDITION_FILE, "w", encoding="utf-8") as f:
    json.dump(edition, f, indent=2, ensure_ascii=False)

with open(HIST_FILE, "w", encoding="utf-8") as f:
    json.dump(historical, f, indent=2, ensure_ascii=False)

if new_headlines:
    generate_audio_blocks(new_headlines, fecha_legible)

print("Noticias finales:", len(headlines))
print("===== FIN GENERATE.PY =====")
