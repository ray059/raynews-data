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

# Zona horaria Colombia (UTC-5)
COLOMBIA_TZ = timezone(timedelta(hours=-5))

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

RSS_SOURCES = {
    "BBC News Mundo": "https://feeds.bbci.co.uk/mundo/rss.xml",

    # CNN vía Google News RSS
    "CNN Español": "https://news.google.com/rss/search?q=site:cnnespanol.cnn.com&hl=es-419&gl=CO&ceid=CO:es-419",

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

def parse_date(pub_date_str):
    try:
        dt = parsedate_to_datetime(pub_date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(COLOMBIA_TZ)
    except:
        return None

def is_last_24h(dt):
    if not dt:
        return False
    now = datetime.now(COLOMBIA_TZ)
    return dt >= now - timedelta(hours=24)

def is_explainer(title):
    title = title.strip().lower()

    keywords = [
        "qué", "que ", "cómo", "como ", "por qué",
        "cuál", "cuáles", "quién", "quienes",
        "claves", "lo que se sabe",
        "qué significa", "por qué ocurre", "así es"
    ]

    return any(k in title for k in keywords)

# -------------------------------------------------
# RESOLVER LINK REAL DE GOOGLE NEWS (CNN)
# -------------------------------------------------

def resolve_google_news_link(google_url):
    try:
        r = requests.get(google_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a"):
            href = a.get("href", "")
            if "cnnespanol.cnn.com" in href:
                if href.startswith("./"):
                    href = "https://news.google.com" + href[1:]
                return href

    except Exception as e:
        print("Error resolviendo Google News:", e)

    return google_url

# -------------------------------------------------
# CARGAR HISTÓRICO
# -------------------------------------------------

if os.path.exists(HIST_FILE):
    with open(HIST_FILE, "r", encoding="utf-8") as f:
        historical = json.load(f)
else:
    historical = {"news": {}}

# -------------------------------------------------
# RECOLECTAR
# -------------------------------------------------

all_news = []
source_counts = {s: 0 for s in RSS_SOURCES}

for source_name, rss_url in RSS_SOURCES.items():

    try:
        print(f"Revisando {source_name}")
        response = requests.get(rss_url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")

        for item in items:

            title = item.title.text if item.title else ""
            link = item.link.text if item.link else ""
            pub_date_str = item.pubDate.text if item.pubDate else ""

            title = clean_text(title)

            if not title or not link:
                continue

            # 🔵 Resolver link real si viene de Google News
            if "news.google.com" in link:
                real_link = resolve_google_news_link(link)
                if real_link:
                    link = real_link

            pub_date = parse_date(pub_date_str)

            # Solo últimas 24h
            if not is_last_24h(pub_date):
                continue

            # Solo explainers
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
                "pubDate": pub_date
            })

    except Exception as e:
        print(f"Error en {source_name}: {e}")

print("Candidatos antes de ordenar:", len(all_news))

# -------------------------------------------------
# ORDENAR POR MÁS RECIENTES
# -------------------------------------------------

all_news.sort(key=lambda x: x["pubDate"], reverse=True)

# -------------------------------------------------
# BALANCE ENTRE FUENTES
# -------------------------------------------------

balanced_news = []

for news in all_news:
    if len(balanced_news) >= TARGET_NEWS:
        break

    source = news["sourceName"]

    if source_counts[source] >= MAX_PER_SOURCE:
        continue

    balanced_news.append(news)
    source_counts[source] += 1

print("Noticias finales seleccionadas:", len(balanced_news))

# -------------------------------------------------
# GUARDAR LINKS
# -------------------------------------------------

with open("links.txt", "w", encoding="utf-8") as f:
    for news in balanced_news:
        f.write(f"{news['title']}||{news['url']}||{news['sourceName']}\n")

print("Noticias guardadas en links.txt:", len(balanced_news))
print("===== FIN UPDATE_LINKS.PY PRO =====")
