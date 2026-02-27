import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
import os
from openai import OpenAI

# =============================
# CONFIG / DEBUG
# =============================

print("===== INICIO GENERATE.PY =====")

API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    print("❌ OPENAI_API_KEY no encontrada")
else:
    print("✅ OPENAI_API_KEY detectada")

client = OpenAI(api_key=API_KEY)

# =============================
# Helpers
# =============================

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()


def get_next_edition_number():
    if os.path.exists("edition.json"):
        try:
            with open("edition.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("edition_number", 0) + 1
        except Exception as e:
            print("Error leyendo edition.json:", e)
            return 1
    return 1


def generate_summary_with_ai(text):
    try:
        prompt = f"""
Resume la siguiente noticia en máximo 280 caracteres.
Debe ser un resumen global.
No repitas el titular.
No uses puntos suspensivos.
Sé claro y neutral.

Noticia:
{text}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        summary = response.choices[0].message.content.strip()

        summary = re.sub(r'\.\.\.$', '', summary).strip()

        if len(summary) > 280:
            summary = summary[:280].rsplit(" ", 1)[0]

        print("✔ Resumen generado correctamente")
        return summary

    except Exception as e:
        print("❌ Error generando resumen IA:", e)
        return text[:280]


# =============================
# SCRAPING (OG ONLY)
# =============================

def extract_article_data(url):
    try:
        print("🔎 Procesando URL:", url)

        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(url, headers=headers, timeout=15)
        print("Status code:", response.status_code)

        if response.status_code != 200:
            print("❌ Error HTTP:", url)
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("meta", property="og:title")
        desc_tag = soup.find("meta", property="og:description")
        image_tag = soup.find("meta", property="og:image")
        source_tag = soup.find("meta", property="og:site_name")

        if not title_tag or not desc_tag:
            print("❌ Faltan og:title o og:description")
            return None

        title = title_tag["content"].split("|")[0].strip()
        description = desc_tag["content"].strip()
        image = image_tag["content"].strip() if image_tag else ""
        source = source_tag["content"].strip() if source_tag else "Fuente"

        print("✔ OG tags encontrados")

        summary = generate_summary_with_ai(description)

        return {
            "titleOriginal": title,
            "summary280": summary,
            "sourceName": source,
            "sourceUrl": url,
            "imageUrl": image
        }

    except Exception as e:
        print("❌ Error procesando URL:", url, e)
        return None


# =============================
# MAIN
# =============================

def main():

    if not os.path.exists("links.txt"):
        print("❌ No existe links.txt")
        return

    with open("links.txt", "r", encoding="utf-8") as f:
        raw_links = f.read()

    # Extraer solo URLs válidas con regex
    links = re.findall(r'https?://[^\s;]+', raw_links)

    print("Links detectados:", links)

    headlines = []

    for link in links:
        data = extract_article_data(link)
        if data:
            headlines.append(data)

    print("Total noticias válidas:", len(headlines))

    edition = {
        "edition_date": datetime.now().strftime("%d %b %Y"),
        "edition_number": get_next_edition_number(),
        "generated_at": datetime.now().isoformat(),
        "country": "Internacional",
        "headlines": headlines
    }

    with open("edition.json", "w", encoding="utf-8") as f:
        json.dump(edition, f, indent=2, ensure_ascii=False)

    print("===== FIN GENERATE.PY =====")


if __name__ == "__main__":
    main()
