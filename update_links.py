import requests
import re
from bs4 import BeautifulSoup

print("===== INICIO UPDATE_LINKS.PY =====")

MAX_LINKS = 30

RSS_SOURCES = [
    # Nacional
    "https://www.eltiempo.com/rss",
    "https://www.elheraldo.co/rss.xml",

    # Internacional en español
    "https://feeds.bbci.co.uk/mundo/rss.xml",
    "https://cnnespanol.cnn.com/feed/",
    "https://www.infobae.com/arc/outboundfeeds/rss/",
    "https://www.dw.com/es/rss.xml"
]

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def is_clickbait_title(title):
    lower = title.lower()

    clickbait_patterns = [
        "esta es",
        "este es",
        "esto es",
        "lo que",
        "lo que debe",
        "el dato",
        "la razón",
        "el motivo",
        "así es",
        "atención",
        "por qué",
        "qué pasó",
        "que pasó",
        "cómo",
        "como ",
        "qué es",
        "cuáles son",
        "cuales son",
        "qué se sabe",
        "que se sabe"
    ]

    return any(p in lower for p in clickbait_patterns)

def extract_links_from_rss(url):
    try:
        print(f"🔎 Revisando RSS: {url}")
        response = requests.get(url, timeout=15)

        if response.status_code != 200:
            print("❌ Error RSS:", url)
            return []

        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")

        links = []

        for item in items:
            title_tag = item.find("title")
            link_tag = item.find("link")

            if not title_tag or not link_tag:
                continue

            title = clean_text(title_tag.text)
            link = clean_text(link_tag.text)

            if not is_clickbait_title(title):
                continue

            print("🟢 Clickbait detectado:", title)
            links.append(link)

        return links

    except Exception as e:
        print("⚠ Error procesando RSS:", url, e)
        return []

def main():

    all_links = []

    for source in RSS_SOURCES:
        links = extract_links_from_rss(source)
        all_links.extend(links)

    # Eliminar duplicados manteniendo orden
    unique_links = list(dict.fromkeys(all_links))

    final_links = unique_links[:MAX_LINKS]

    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(";".join(final_links))

    print(f"✅ Links guardados: {len(final_links)}")
    print("===== FIN UPDATE_LINKS.PY =====")

if __name__ == "__main__":
    main()
