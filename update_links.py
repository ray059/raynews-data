import requests
import re
from bs4 import BeautifulSoup
from collections import defaultdict

print("===== INICIO UPDATE_LINKS.PY =====")

TARGET_NEWS = 60

RSS_SOURCES = {
    "BBC News Mundo": "https://feeds.bbci.co.uk/mundo/rss.xml",
    "CNN Español": "https://cnnespanol.cnn.com/feed/",
    "Infobae": "https://www.infobae.com/arc/outboundfeeds/rss/",
    "DW Español": "https://rss.dw.com/rdf/rss-es-all"
}

def is_question(title):
    title = title.strip()
    return (
        title.startswith("¿") or
        title.lower().startswith(("qué", "como", "cómo", "por qué", "cuál", "cuáles"))
    )

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()

all_news = []
source_count = defaultdict(int)

for source_name, rss_url in RSS_SOURCES.items():
    try:
        print(f"Revisando {source_name}")
        response = requests.get(rss_url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")

        for item in items:
            title = item.title.text if item.title else ""
            link = item.link.text if item.link else ""

            title = clean_text(title)

            if not title or not link:
                continue

            if not is_question(title):
                continue

            if source_count[source_name] >= 3:
                continue

            all_news.append({
                "title": title,
                "url": link,
                "sourceName": source_name
            })

            source_count[source_name] += 1

            if len(all_news) >= TARGET_NEWS:
                break

    except Exception as e:
        print(f"Error en {source_name}: {e}")

print(f"Noticias guardadas: {len(all_news)}")

with open("links.txt", "w", encoding="utf-8") as f:
    for news in all_news:
        f.write(f"{news['title']}||{news['url']}||{news['sourceName']}\n")

print("===== FIN UPDATE_LINKS.PY =====")
