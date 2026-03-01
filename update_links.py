import requests
import re
from bs4 import BeautifulSoup

print("===== INICIO UPDATE_LINKS.PY =====")

TARGET_NEWS = 80  # Queremos suficiente materia prima

RSS_SOURCES = {
    "BBC News Mundo": "https://feeds.bbci.co.uk/mundo/rss.xml",
    "CNN Español": "https://cnnespanol.cnn.com/feed/",
    "Infobae": "https://www.infobae.com/arc/outboundfeeds/rss/",
    "DW Español": "https://rss.dw.com/rdf/rss-es-all"
}

def is_question(title):
    title = title.strip().lower()
    return (
        title.startswith("¿") or
        title.startswith(("qué", "como", "cómo", "por qué", "cuál", "cuáles"))
    )

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()

all_news = []

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

            all_news.append({
                "title": title,
                "url": link,
                "sourceName": source_name
            })

    except Exception as e:
        print(f"Error en {source_name}: {e}")

print(f"Total noticias encontradas: {len(all_news)}")

# Limitar después, no por medio
all_news = all_news[:TARGET_NEWS]

with open("links.txt", "w", encoding="utf-8") as f:
    for news in all_news:
        f.write(f"{news['title']}||{news['url']}||{news['sourceName']}\n")

print("Noticias guardadas en links.txt:", len(all_news))
print("===== FIN UPDATE_LINKS.PY =====")
