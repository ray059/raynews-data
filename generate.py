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

MAX_NEW_PER_EDITION = 1
MAX_NEW_PER_SOURCE = 1

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# -------------------------------------------------
# UTILIDADES
# -------------------------------------------------

def generate_audio_blocks(headlines, fecha_legible):
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
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "files.txt",
        "-c", "copy",
        "edition_audio.mp3"
    ])

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()

from datetime import timedelta

def clean_old_news(hist_data, days_limit):
    now = datetime.now(ZoneInfo("America/Bogota"))
    new_news = {}

    for nid, item in hist_data["news"].items():
        try:
            first_seen = datetime.fromisoformat(item["first_seen"])
            if now - first_seen <= timedelta(days=days_limit):
                new_news[nid] = item
        except:
            # si hay error, lo mantenemos por seguridad
            new_news[nid] = item

    return {"news": new_news}

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
now = datetime.now(ZoneInfo("America/Bogota"))

normalized_base = []
for h in base_edition:
    h_copy = h.copy()
    h_copy["isNew"] = False
    h_copy["category"] = h_copy.get("category", "general")

    # 🔥 FIX FECHA PARA EXISTENTES
    if not h_copy.get("publishedAt"):
        h_copy["publishedAt"] = now.isoformat()

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

def generate_summary(title, article_text, description=""):

    # 🟢 PRIORIDAD 1: usar descripción (gratis)
    if description and len(description) > 80:
        return description[:280]

    # 🔴 si no hay API key → fallback gratis
    if not OPENAI_API_KEY:
        return (article_text[:280] + "...") if article_text else title

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
Resume el artículo en máximo 280 caracteres.
Debe terminar en una frase completa.
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
        return (article_text[:280] + "...") if article_text else title

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

print("[TRACE] Total lines:", len(lines))

now = datetime.now(ZoneInfo("America/Bogota"))
fecha_legible = f"{now.day:02d} de {MESES_ES[now.month]} de {now.year}"

new_items = []

# 🔥 EXISTENTES POR CATEGORÍA (ANTES DEL LOOP)
existing_by_category_initial = {}

for item in normalized_base:
    cat = item.get("category", "general")
    existing_by_category_initial.setdefault(cat, []).append(item)
# -------------------------------------------------
# STATS DEBUG
# -------------------------------------------------
stats = {
    "total": 0,
    "passed_text": 0,
    "passed_image": 0,
    "passed_summary": 0,
    "final_new_items": 0,
    "drop_text": 0,
    "drop_image": 0,
    "drop_summary": 0
}
stats_by_category = {}
new_per_category = {}
MAX_NEW_PER_CATEGORY = 2
per_source_new_counter = {}


# 🔥 NUEVOS HISTÓRICOS
HIST_30_FILE = "historical_30d.json"
HIST_12_FILE = "historical_12m.json"

def load_hist(file):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"news": {}}

hist_30 = load_hist(HIST_30_FILE)
hist_12 = load_hist(HIST_12_FILE)

for line in lines:

    stats["total"] += 1

    # -------------------------
    # PARSE SEGURO + DEBUG
    # -------------------------
    parts = line.strip().split("||")
    published_at = parts[5] if len(parts) > 5 else None

    # 🔥 FIX: asegurar fecha siempre
    if not published_at:
        published_at = now.isoformat()

    if len(parts) < 4:
        print("\n[DROP][FORMAT]")
        print(f"LINE: {line}")
        print(f"PARTS LEN: {len(parts)}")
        continue

    title = parts[0]
    url = parts[1]
    source_name = parts[2]
    description = parts[3]
    category = parts[4] if len(parts) > 4 else "general"

    print(f"[INPUT] {source_name} | {category} | {title[:60]}")

    # -------------------------
    # STATS INIT
    # -------------------------
    stats_by_category.setdefault(category, {
        "total": 0,
        "drop_text": 0,
        "drop_image": 0,
        "drop_summary": 0,
        "final": 0
    })

    stats_by_category[category]["total"] += 1

    # -------------------------
    # ID
    # -------------------------
    news_id = make_id(url)
    print(f"[ID] {news_id[:10]}...")

    # -------------------------
    # DUPLICADOS
    # -------------------------
    existing_match = next((n for n in normalized_base if n.get("id") == news_id), None)

    if existing_match:
        print("[DROP][DUPLICATE]")
        print(f"  NEW: {title[:60]}")
        print(f"  EXISTING: {existing_match.get('titleOriginal','')[:60]}")
        print(f"  SOURCE: {existing_match.get('sourceName')}")
        continue
    else:
        print("[PASS][UNIQUE]")

    # -------------------------
    # TEXTO
    # -------------------------
    article_text = extract_article_text(url)

    if len(article_text) < 120:
        stats["drop_text"] += 1
        stats_by_category[category]["drop_text"] += 1
        print(f"[DROP][TEXT] len={len(article_text)}")
        continue
    else:
        stats["passed_text"] += 1
        print(f"[PASS][TEXT] len={len(article_text)}")

    # -------------------------
    # IMAGEN
    # -------------------------
    image = extract_image(url)

    if not image or "fallback-promo-image" in image:
        stats["drop_image"] += 1
        stats_by_category[category]["drop_image"] += 1
        print("[DROP][IMAGE]")
        continue
    else:
        stats["passed_image"] += 1
        print("[PASS][IMAGE]")

    # -------------------------
    # LÓGICA DE LÍMITES
    # -------------------------
    existing_count = len(existing_by_category_initial.get(category, []))
    count = new_per_category.get(category, 0)

    if existing_count >= 20:

        if per_source_new_counter.get(source_name, 0) >= MAX_NEW_PER_SOURCE:
            print("[DROP][SOURCE LIMIT]")
            continue

        if count >= MAX_NEW_PER_CATEGORY:
            print("[DROP][CATEGORY LIMIT]")
            continue

    # -------------------------
    # FINAL SELECCIONADO
    # -------------------------
    print("[PASS][FINAL NEW]")

    stats["final_new_items"] += 1
    stats_by_category[category]["final"] += 1

    summary = generate_summary(title, article_text, description)

    item = {
        "id": news_id,
        "titleOriginal": title,
        "summary280": summary,
        "articleText": article_text,
        "sourceName": source_name,
        "sourceUrl": url,
        "imageUrl": image,
        "type": "explainer",
        "isNew": True,
        "category": category,
        "publishedAt": published_at  # 🔥 AÑADIR
    }

    new_items.append(item)

    # -------------------------
    # HISTÓRICO
    # -------------------------
    historical["news"][news_id] = {
        "titleOriginal": title,
        "summary280": summary,
        "articleText": article_text,
        "sourceName": source_name,
        "sourceUrl": url,
        "imageUrl": image,
        "first_seen": now.isoformat()
    }

    hist_30["news"][news_id] = historical["news"][news_id]
    hist_12["news"][news_id] = historical["news"][news_id]

    new_per_category[category] = new_per_category.get(category, 0) + 1

    per_source_new_counter[source_name] = (
        per_source_new_counter.get(source_name, 0) + 1
    )
# -------------------------------------------------
# SEPARAR NUEVAS Y EXISTENTES POR CATEGORÍA
# -------------------------------------------------

new_by_category = {}
existing_by_category = {}

for item in new_items:
    cat = item.get("category", "general")
    new_by_category.setdefault(cat, []).append(item)

for item in normalized_base:
    cat = item.get("category", "general")
    existing_by_category.setdefault(cat, []).append(item)

print("\n[DEBUG] Nuevas por categoría:")
for cat, items in new_by_category.items():
    print(f"  {cat}: {len(items)}")

print("\n[DEBUG] Existentes por categoría:")
for cat, items in existing_by_category.items():
    print(f"  {cat}: {len(items)}")

by_category = {}

# -------------------------------------------------
# LIMITAR A 20 POR CATEGORÍA
# -------------------------------------------------

# -------------------------------------------------
# ORDENAR Y LIMITAR POR CATEGORÍA
# -------------------------------------------------

MAX_PER_CATEGORY = 20

# -------------------------------------------------
# LÓGICA INTELIGENTE POR CATEGORÍA
# -------------------------------------------------

MAX_PER_CATEGORY = 20
final_by_category = {}

all_categories = set(list(new_by_category.keys()) + list(existing_by_category.keys()))

for cat in all_categories:

    new_items_cat = new_by_category.get(cat, [])
    existing_items_cat = existing_by_category.get(cat, [])
    

    from datetime import datetime
    
    def safe_date(x):
        try:
            return datetime.fromisoformat(x.get("publishedAt", ""))
        except:
            return datetime.min
    
    existing_items_cat = sorted(
        existing_items_cat,
        key=safe_date,
        reverse=True
    )


    current_existing = len(existing_items_cat)

    selected = []

    if current_existing < MAX_PER_CATEGORY:
        # 🔥 llenar sin límite de nuevas
        needed = MAX_PER_CATEGORY - current_existing

        # 🔥 meter TODAS las nuevas primero
        take_new = new_items_cat[:needed]
        selected.extend(take_new)
        
        # 🔥 luego completar con existentes
        remaining_slots = MAX_PER_CATEGORY - len(selected)
        selected.extend(existing_items_cat[:remaining_slots])

    else:
        # 🔒 categoría llena → máximo 2 nuevas
        take_new = new_items_cat[:MAX_NEW_PER_CATEGORY]
        selected.extend(take_new)

        remaining_slots = MAX_PER_CATEGORY - len(selected)
        selected.extend(existing_items_cat[:remaining_slots])

    final_by_category[cat] = selected

final_headlines = []

# convertir cada categoría en cola (queue)
category_queues = {
    cat: list(items) for cat, items in final_by_category.items()
}

while True:

    added = False

    for cat in category_queues:
        if category_queues[cat]:
            final_headlines.append(category_queues[cat].pop(0))
            added = True

    if not added:
        break

edition = {
    "api_version": 3,
    "edition_date": fecha_legible,
    "generated_at": now.isoformat(),
    "country": "Internacional",
    "headlines": final_headlines
}

print(new_per_category)

with open("edition_tmp.json", "w", encoding="utf-8") as f:
    json.dump(edition, f, indent=2, ensure_ascii=False)

os.replace("edition_tmp.json", EDITION_FILE)

# 🔥 LIMPIEZA AUTOMÁTICA
hist_30 = clean_old_news(hist_30, 30)
hist_12 = clean_old_news(hist_12, 365)

with open("historical_tmp.json", "w", encoding="utf-8") as f:
    json.dump(historical, f, indent=2, ensure_ascii=False)

os.replace("historical_tmp.json", HIST_FILE)


# 🔥 GUARDAR históricos nuevos

with open("historical_30_tmp.json", "w", encoding="utf-8") as f:
    json.dump(hist_30, f, indent=2, ensure_ascii=False)

os.replace("historical_30_tmp.json", "historical_30d.json")

with open("historical_12_tmp.json", "w", encoding="utf-8") as f:
    json.dump(hist_12, f, indent=2, ensure_ascii=False)

os.replace("historical_12_tmp.json", "historical_12m.json")

# 🔒 AUDIO DESACTIVADO PARA AHORRO
# if new_items:
#     generate_audio_blocks(new_items, fecha_legible)

print("Noticias nuevas detectadas:", len(new_items))
print("\n[STATS]")
print("\n[STATS BY CATEGORY]")
for cat, data in stats_by_category.items():
    print(f"\n{cat}:")
    for k, v in data.items():
        print(f"  {k}: {v}")
for k, v in stats.items():
    print(f"{k}: {v}")
print("Noticias finales:", len(final_headlines))
print("===== FIN GENERATE.PY =====")
