import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
import os
from openai import OpenAI

# =============================
# OpenAI client
# =============================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =============================
# Helpers
# =============================

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_next_edition_number():
    if os.path.exists("edition.json"):
        try:
            with open("edition.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("edition_number", 0) + 1
        except:
            return 1
    return 1


def generate_summary_with_ai(text):
    try:
        prompt = f"""
Resume la siguiente noticia en máximo 280 caracteres exactos.
No incluyas puntos suspensivos al final.
No repitas el titular.
Sé claro, neutral y directo.
Texto:
{text}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        summary = response.choices[0].message.content.strip()

        if len(summary) > 280:
            summary = summary[:277].rsplit(" ", 1)[0] + "..."

        return summary

    except Exception as e:
        print("Error generando resumen IA:", e)
        return text[:277] + "..."


# =============================
# Scraping
# =============================

def extract_article_data(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = response.apparent_encoding

        if response.status_code != 200:
            print("Error status:", response.status_code, url)
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("meta", property="og:title")
        image_tag = soup.find("meta", property="og:image")
        source_tag = soup.find("meta", property="og:site_name")

        if not title_tag or not image_tag:
            print("Sin og tags:", url)
            return None

        title = title_tag["content"].split("|")[0].strip()
        image = image_tag["content"].strip()
        source = source_tag["content"].strip() if source_tag else "Fuente"

        # Intentar extraer solo contenido del <article>
        article_tag = soup.find("article")

        if article_tag:
            paragraphs = article_tag.find_all("p")
        else:
            paragraphs = soup.find_all("p")

        clean_paragraphs = []

        for p in paragraphs:
            text = p.get_text().strip()
            text = clean_text(text)

            if len(text) < 80:
                continue

            if re.search(r'(Publicidad|Suscríbete|Lee también|Audio generado)', text, re.IGNORECASE):
                continue

            if re.search(r'\d y \d', text):
                continue

            clean_paragraphs.append(text)

        article_text = " ".join(clean_paragraphs)

        if len(article_text) < 200:
            print("Texto muy corto:", url)
            return None

        summary = generate_summary_with_ai(article_text[:4000])

        return {
            "titleOriginal": title,
            "summary280": summary,
            "sourceName": source,
            "sourceUrl": url,
            "imageUrl": image
        }

    except Exception as e:
        print(f"Error procesando {url}: {e}")
        return None


# =============================
# Main
# =============================

def main():
    if not os.path.exists("links.txt"):
        print("No existe links.txt")
        return

    with open("links.txt", "r", encoding="utf-8") as f:
        raw_links = f.read()

    links = [l.strip() for l in raw_links.split(";") if l.strip()]

    headlines = []

    for link in links:
        print("Procesando:", link)
        data = extract_article_data(link)
        if data:
            headlines.append(data)

    edition = {
        "edition_date": datetime.now().strftime("%d %b %Y"),
        "edition_number": get_next_edition_number(),
        "generated_at": datetime.now().isoformat(),  # 🔥 fuerza cambio siempre
        "country": "Internacional",
        "headlines": headlines
    }

    with open("edition.json", "w", encoding="utf-8") as f:
        json.dump(edition, f, indent=2, ensure_ascii=False)

    print("Edition generada con", len(headlines), "noticias")


if __name__ == "__main__":
    main()
