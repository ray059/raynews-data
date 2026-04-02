import requests
import re
import json
import os
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

print("===== INICIO UPDATE_LINKS.PY PRO =====")

TARGET_NEWS = 100
MAX_PER_SOURCE = 25
MAX_PER_CATEGORY_POOL = 30

COLOMBIA_TZ = timezone(timedelta(hours=-5))

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

RSS_SOURCES = {
    # 🔹 FEEDS GENERALES (los que ya tenías)
    "general": {
        "BBC News Mundo": "https://feeds.bbci.co.uk/mundo/rss.xml",
        "El Tiempo": "https://www.eltiempo.com/rss/colombia.xml",
        "Infobae": "https://www.infobae.com/arc/outboundfeeds/rss/",
        "DW Español": "https://rss.dw.com/rdf/rss-sp-all"
    },

    # 🔹 NUEVO: ECONOMÍA
    "economia": {
        "El Tiempo": "https://www.eltiempo.com/rss/economia.xml",
        "El País": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada",
        "La FM": "https://www.lafm.com.co/rss/economia.xml"
    },

    # 🔹 NUEVO: FÚTBOL / DEPORTES
    "deportes": {
        "El Tiempo": "https://www.eltiempo.com/rss/deportes_futbol-internacional.xml",
        "La FM": "https://www.lafm.com.co/rss/deportes.xml"
    },

    # 🔹 NUEVO: CIENCIA Y TECNOLOGIA
    "ciencia y tecnología": {
        "DW Español": "https://rss.dw.com/rdf/rss-sp-cyt",
        "El Tiempo": "https://www.eltiempo.com/rss/vida_ciencia.xml",
        "El Tiempo": "https://www.eltiempo.com/rss/tecnosfera.xml"
    }
    
}

HIST_FILE = "historical_editions.json"

# -------------------------------------------------
# UTILIDADES
# -------------------------------------------------

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()

def make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()

# 🔥 PARSER ROBUSTO (RFC + ISO 8601)
def parse_date(pub_date_str):

    if not pub_date_str:
        return None

    # 1️⃣ RFC clásico (BBC, DW, Infobae)
    try:
        dt = parsedate_to_datetime(pub_date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(COLOMBIA_TZ)
    except:
        pass

    # 2️⃣ ISO 8601 (El Tiempo)
    try:
        dt = datetime.fromisoformat(pub_date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=COLOMBIA_TZ)
        return dt.astimezone(COLOMBIA_TZ)
    except:
        return None

def is_last_24h(dt):
    if not dt:
        return False
    now = datetime.now(COLOMBIA_TZ)
    return dt >= now - timedelta(hours=24)

def is_explainer(title):
    title = title.lower()
    keywords = [
        "qué", "como", "cómo", "por qué",
        "cuál", "cuáles", "quién",
        "claves", "lo que se sabe",
        "qué significa"
    ]
    return any(k in title for k in keywords)

# -------------------------------------------------
# CARGAR HISTÓRICO
# -------------------------------------------------

if os.path.exists(HIST_FILE):
    with open(HIST_FILE, "r", encoding="utf-8") as f:
        historical = json.load(f)
else:
    historical = {"news": {}}

# -------------------------------------------------
# RECOLECTAR RSS
# -------------------------------------------------

all_news = []
source_counts = {}
new_per_category = {}
MAX_NEW_PER_CATEGORY = 2

for category, sources in RSS_SOURCES.items():
    
    for source_name, rss_url in sources.items():

        raw_count = 0
        valid_date_count = 0
        last24_count = 0
        added_count = 0

        try:
            print(f"\nRevisando {source_name} ({category})")

            response = requests.get(rss_url, headers=HEADERS, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "xml")
            items = soup.find_all("item")

            print("Items encontrados:", len(items))

            for item in items:

                raw_count += 1

                title = item.title.text if item.title else ""
                link = item.link.text if item.link else ""
                pub_date_str = item.pubDate.text if item.pubDate else ""
                description = item.description.text if item.description else ""

                title = clean_text(title)
                description = clean_text(description)

                if not title or not link:
                    continue

                pub_date = parse_date(pub_date_str)

                # ✅ fecha válida
                if pub_date:
                    valid_date_count += 1

                if not pub_date:
                    continue

                # ✅ dentro de 24h
                if is_last_24h(pub_date):
                    last24_count += 1
                else:
                    continue

                # Solo exigir explainers a BBC (solo si es general)
                if category == "general" and source_name == "BBC News Mundo":
                    if not is_explainer(title):
                        continue

                news_id = make_id(link)

                if news_id in historical["news"]:
                    continue

                all_news.append({
                    "id": news_id,
                    "title": title,
                    "url": link,
                    "sourceName": source_name,
                    "pubDate": pub_date,
                    "description": description,
                    "category": category
                })

                added_count += 1

        except Exception as e:
            print(f"Error en {source_name}: {e}")

        # 🔥 LOG CLAVE POR SOURCE
        print(f"[DEBUG][{category}][{source_name}] "
              f"raw={raw_count} valid_date={valid_date_count} "
              f"last24h={last24_count} added={added_count}")


# -------------------------------------------------
# DEBUG GLOBAL
# -------------------------------------------------

print("\nCandidatos antes de ordenar:", len(all_news))

from collections import Counter

cat_counter = Counter([n["category"] for n in all_news])
print("[DEBUG] Distribución por categoría (antes de ordenar):")
for cat, count in cat_counter.items():
    print(f"  {cat}: {count}")


# -------------------------------------------------
# ORDENAR POR MÁS RECIENTES
# -------------------------------------------------

all_news.sort(key=lambda x: x["pubDate"], reverse=True)


# -------------------------------------------------
# BALANCE ENTRE CATEGORÍAS
# -------------------------------------------------

from collections import defaultdict

by_category = defaultdict(list)

for news in all_news:
    by_category[news["category"]].append(news)

# DEBUG
print("\n[DEBUG] Tamaño por categoría en by_category:")
for cat, items in by_category.items():
    print(f"  {cat}: {len(items)}")

# ordenar dentro de cada categoría
for cat in by_category:
    by_category[cat].sort(key=lambda x: x["pubDate"], reverse=True)

balanced_news = []

category_queues = {cat: list(items) for cat, items in by_category.items()}
category_counts = {}

while True:

    cat_order = sorted(
        category_queues.keys(),
        key=lambda c: category_counts.get(c, 0)
    )

    added = False

    for cat in cat_order:

        if category_counts.get(cat, 0) >= MAX_PER_CATEGORY_POOL:
            continue

        if not category_queues[cat]:
            continue

        news = category_queues[cat].pop(0)

        balanced_news.append(news)
        category_counts[cat] = category_counts.get(cat, 0) + 1

        added = True
        break

    # DEBUG cada 10
    if len(balanced_news) % 10 == 0:
        print("[DEBUG] Progreso balance:")
        for c in category_counts:
            print(f"  {c}: {category_counts[c]}")

    if not added:
        break


# -------------------------------------------------
# DEBUG ANTES DE FUENTE
# -------------------------------------------------

print("Noticias finales seleccionadas (antes de limitar fuente):", len(balanced_news))

cat_counter_balanced = Counter([n["category"] for n in balanced_news])
print("[DEBUG] Distribución antes de limitar fuente:")
for cat, count in cat_counter_balanced.items():
    print(f"  {cat}: {count}")


# -------------------------------------------------
# LIMITAR POR FUENTE
# -------------------------------------------------

final_news = []
source_counts = {}

for news in balanced_news:
    source = news["sourceName"]

    if source_counts.get(source, 0) >= MAX_PER_SOURCE:
        continue

    final_news.append(news)
    source_counts[source] = source_counts.get(source, 0) + 1

balanced_news = final_news


# -------------------------------------------------
# DEBUG FINAL
# -------------------------------------------------

print("Noticias finales seleccionadas (después de limitar fuente):", len(balanced_news))

cat_counter_final = Counter([n["category"] for n in balanced_news])
print("[DEBUG] Distribución FINAL:")
for cat, count in cat_counter_final.items():
    print(f"  {cat}: {count}")


# -------------------------------------------------
# GUARDAR LINKS
# -------------------------------------------------

with open("links.txt", "w", encoding="utf-8") as f:
    for news in balanced_news:
        f.write(
            f"{news['title']}||{news['url']}||{news['sourceName']}||{news['description']}||{news.get('category','general')}\n"
        )

print("Noticias guardadas en links.txt:", len(balanced_news))
print("===== FIN UPDATE_LINKS.PY PRO =====")
