import requests
import re
import json
import os
import hashlib
from bs4 import BeautifulSoup

print("===== INICIO UPDATE_LINKS.PY =====")

TARGET_NEWS = 100          # Materia prima total
MAX_PER_SOURCE = 25        # Máximo por fuente (evita monopolio)

RSS_SOURCES = {
    "BBC News Mundo": "https://feeds.bbci.co.uk/mundo/rss.xml",
    "CNN Español": "https://cnnespanol.cnn.com/feed/",
    "Infobae": "https://www.infobae.com/arc/outboundfeeds/rss/",
    "DW Español": "https://rss.dw.com/rdf/rss-es-all"
}

HIST_FILE = "historical_editions.json"

# -------------------------------------------------
# UTILIDADES
# -------------------------------------------------

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
# FILTRO DE EXPLAINERS
# -------------------------------------------------

def is_explainer(title):
    title = title.strip().lower()

    keywords = [
        "qué",
        "que ",
        "cómo",
        "como ",
        "por qué",
        "cuál",
        "cuáles",
        "quién",
        "quienes",
        "claves",
        "lo que se sabe",
        "qué significa",
        "por qué ocurre",
        "así es"
    ]

    return any(k in title for k in keywords)

# -------------------------------------------------
# MAIN
# -------------------------------------------------

all_news = []
source_counts = {}

for source_name, rss_url in RSS_SOURCES.items():
    source_counts[source_name] = 0

    try:
        print(f"Revisando {source_name}")
        response = requests.get(rss_url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")

        for item in items:
            if len(all_news) >= TARGET_NEWS:
                break

            title = item.title.text if item.title else ""
            link = item.link.text if item.link else ""

            title = clean_text(title)

            if not title or not link:
                continue

            if not is_explainer(title):
                continue

            # Limitar por fuente
            if source_counts[source_name] >= MAX_PER_SOURCE:
                continue

            news_id = make_id(link)

            # Evitar noticias ya usadas en histórico
            if news_id in historical["news"]:
                continue

            all_news.append({
                "title": title,
                "url": link,
                "sourceName": source_name
            })

            source_counts[source_name] += 1

    except Exception as e:
        print(f"Error en {source_name}: {e}")

print(f"Total candidatos encontrados: {len(all_news)}")

# -------------------------------------------------
# GUARDAR LINKS
# -------------------------------------------------

with open("links.txt", "w", encoding="utf-8") as f:
    for news in all_news:
        f.write(f"{news['title']}||{news['url']}||{news['sourceName']}\n")

print("Noticias guardadas en links.txt:", len(all_news))
print("===== FIN UPDATE_LINKS.PY =====")
