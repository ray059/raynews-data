import requests
import re
from bs4 import BeautifulSoup

print("===== INICIO UPDATE_LINKS.PY =====")

MAX_LINKS = 30

RSS_SOURCES = [
    "https://www.eltiempo.com/rss",
    "https://www.elheraldo.co/rss.xml"
]

def is_question_title(title):
    title = title.strip()
    return "¿" in title or title.endswith("?")

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

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

            if not is_question_title(title):
                continue

            links.append(link)

        return links

    except Exception as e:
        print("Error procesando RSS:", e)
        return []

def main():

    all_links = []

    for source in RSS_SOURCES:
        links = extract_links_from_rss(source)
        all_links.extend(links)

    # Eliminar duplicados manteniendo orden
    unique_links = list(dict.fromkeys(all_links))

    # Limitar cantidad
    final_links = unique_links[:MAX_LINKS]

    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(";".join(final_links))

    print(f"✅ Links guardados: {len(final_links)}")
    print("===== FIN UPDATE_LINKS.PY =====")

if __name__ == "__main__":
    main()
