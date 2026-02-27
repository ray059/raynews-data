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
    Lee COMPLETAMENTE la siguiente noticia.
    
    Genera un resumen global que incluya:
    - El hecho principal
    - Los datos clave
    - El contexto relevante
    
    Debe:
    - Tener máximo 280 caracteres
    - No repetir el titular
    - No usar puntos suspensivos
    - No cortar frases
    - Ser neutral y claro
    - Ser un resumen integral, no solo del primer párrafo
    
    Noticia:
    {text}
    """
    
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
    
            summary = response.choices[0].message.content.strip()
    
            # Limpiar puntos suspensivos finales
            summary = re.sub(r'\.\.\.$', '', summary).strip()
    
            # Forzar límite sin agregar "..."
            if len(summary) > 280:
                summary = summary[:280].rsplit(" ", 1)[0]
    
            return summary
    
        except Exception as e:
            print("Error generando resumen IA:", e)
            return text[:280]


# =============================
# Scraping
# =============================

def extract_article_data(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "es-ES,es;q=0.9"
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = response.apparent_encoding

        if response.status_code != 200:
            print("Error status:", response.status_code, url)
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # TÍTULO
        title_tag = soup.find("meta", property="og:title")
        if not title_tag:
            title_tag = soup.find("title")

        if not title_tag:
            print("Sin título:", url)
            return None

        title = title_tag.get("content") if title_tag.has_attr("content") else title_tag.text
        title = title.split("|")[0].strip()

        # IMAGEN (YA NO ES OBLIGATORIA)
        image_tag = soup.find("meta", property="og:image")
        image = image_tag["content"].strip() if image_tag else ""

        # FUENTE
        source_tag = soup.find("meta", property="og:site_name")
        source = source_tag["content"].strip() if source_tag else "Fuente"

        # TEXTO
        article_tag = soup.find("article")

        if article_tag:
            paragraphs = article_tag.find_all("p")
        else:
            paragraphs = soup.find_all("p")

        texts = []
        for p in paragraphs:
            t = clean_text(p.get_text())
            if len(t) > 60:
                texts.append(t)

        article_text = " ".join(texts)

        # 🔥 SI QUEDA CORTO, USAR OG DESCRIPTION
        if len(article_text) < 150:
            desc_tag = soup.find("meta", property="og:description")
            if desc_tag:
                article_text = desc_tag["content"]
            else:
                print("Texto insuficiente:", url)
                return None

        summary = generate_summary_with_ai(article_text[:6000])

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
