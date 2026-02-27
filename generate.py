import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
import os

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def smart_summary(text, max_chars=280):
    sentences = re.split(r'(?<=[.!?]) +', text)
    summary = ""

    for sentence in sentences:
        if len(summary) + len(sentence) <= max_chars:
            summary += sentence + " "
        else:
            break

    summary = summary.strip()

    if len(summary) < 100:
        summary = text[:max_chars-3].rsplit(" ", 1)[0] + "..."

    return summary

def extract_article_data(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = response.apparent_encoding

        if response.status_code != 200:
            print(f"❌ Error {response.status_code} en {url}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("meta", property="og:title")
        image_tag = soup.find("meta", property="og:image")
        source_tag = soup.find("meta", property="og:site_name")

        if not title_tag or not image_tag:
            return None

        title = title_tag["content"].split("|")[0].strip()
        image = image_tag["content"].strip()
        source = source_tag["content"].strip() if source_tag else "Fuente"

        paragraphs = soup.find_all("p")
        article_text = " ".join([p.get_text() for p in paragraphs])
        article_text = clean_text(article_text)

        if len(article_text) < 300:
            return None

        summary = smart_summary(article_text, 280)

        return {
            "titleOriginal": title,
            "summary280": summary,
            "sourceName": source,
            "sourceUrl": url,
            "imageUrl": image
        }

    except Exception as e:
        print(f"Error en {url}: {e}")
        return None

def main():
    if not os.path.exists("links.txt"):
        print("No existe links.txt")
        return

    with open("links.txt", "r") as f:
        raw_links = f.read()

    links = [l.strip() for l in raw_links.split(";") if l.strip()]

    headlines = []

    for link in links:
        print(f"Procesando {link}")
        data = extract_article_data(link)
        if data:
            headlines.append(data)

    edition = {
        "edition_date": datetime.now().strftime("%d %b %Y"),
        "edition_number": 1,
        "country": "Internacional",
        "headlines": headlines
    }

    with open("edition.json", "w", encoding="utf-8") as f:
        json.dump(edition, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
