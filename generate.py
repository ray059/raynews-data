import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
import os
from openai import OpenAI

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
Resume la siguiente noticia en máximo 500 caracteres.

Debe:
- Incluir el hecho principal
- Incluir datos clave
- Ser neutral
- No repetir el titular
- No usar puntos suspensivos
- No cortar frases
- No copiar frases textuales extensas
- Reformular la información

Noticia:
{text}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )

        summary = response.choices[0].message.content.strip()

        # eliminar ...
        summary = re.sub(r'\.\.\.$', '', summary).strip()

        # cortar bien si excede 500
        if len(summary) > 500:
            temp = summary[:500]
        
            # Buscar último cierre de frase
            last_period = max(
                temp.rfind("."),
                temp.rfind("?"),
                temp.rfind("!")
            )
        
            # Si encontramos un cierre razonable
            if last_period > 350:  # evitar cortar demasiado temprano
                summary = temp[:last_period + 1].strip()
            else:
                # cortar por última palabra completa
                summary = temp.rsplit(" ", 1)[0].strip()
        
            # asegurar que termine correctamente
            if not summary.endswith((".", "?", "!")):
                summary += "."

        print("✔ Resumen generado:", len(summary), "caracteres")
        return summary

    except Exception as e:
        print("❌ Error generando resumen:", e)
        return text[:500]


# =============================
# SCRAPING COMPLETO
# =============================

def extract_article_data(url):
    try:
        print("🔎 Procesando:", url)

        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=20)

        if response.status_code != 200:
            print("❌ HTTP error:", response.status_code)
            return None

        response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.text, "html.parser")

        # OG DATA
        title_tag = soup.find("meta", property="og:title")
        image_tag = soup.find("meta", property="og:image")
        source_tag = soup.find("meta", property="og:site_name")

        if not title_tag:
            print("❌ Sin og:title")
            return None

        title = clean_text(title_tag["content"].split("|")[0])
        image = image_tag["content"] if image_tag else ""
        source = source_tag["content"] if source_tag else "Fuente"

        # EXTRAER TEXTO REAL DEL ARTÍCULO
        article = soup.find("article")

        if article:
            paragraphs = article.find_all("p")
        else:
            paragraphs = soup.find_all("p")

        article_text = " ".join(p.get_text() for p in paragraphs)
        article_text = clean_text(article_text)

        if len(article_text) < 300:
            print("⚠ Texto muy corto, usando og:description como fallback")
            desc_tag = soup.find("meta", property="og:description")
            if desc_tag:
                article_text = clean_text(desc_tag["content"])

        if len(article_text) < 100:
            print("❌ No se pudo extraer texto útil")
            return None

        print("✔ Texto extraído:", len(article_text), "caracteres")

        summary = generate_summary_with_ai(article_text[:5000])

        return {
            "titleOriginal": title,
            "summary280": summary,
            "sourceName": source,
            "sourceUrl": url,
            "imageUrl": image
        }

    except Exception as e:
        print("❌ Error procesando:", url, e)
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

    links = re.findall(r'https?://[^\s;]+', raw_links)

    print("Total links detectados:", len(links))

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
