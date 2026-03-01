import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
import os
import unicodedata
from openai import OpenAI
from readability import Document
from zoneinfo import ZoneInfo

print("===== INICIO GENERATE.PY =====")

API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    print("❌ OPENAI_API_KEY no encontrada")
    client = None
else:
    print("✅ OPENAI_API_KEY detectada")
    client = OpenAI(api_key=API_KEY)

MAX_NEWS = 7
MAX_SUMMARY_LENGTH = 280

BLOCKED_DOMAINS = ["nytimes.com"]
BLOCKED_PATHS = [
    "/opinion/",
    "/columnas",
    "/columnas-de-opinion",
    "/blogs/",
    "/editoriales/"
]

# =============================
# HELPERS
# =============================

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def clean_noise(text):
    patterns = [
        r'Publicidad.*?',
        r'Foto:.*?\.',
        r'©.*?',
        r'Suscríbete.*?',
        r'Google News.*?\.',
        r'WhatsApp.*?\.',
        r'Descargue.*?\.',
        r'Actualizado.*?\.'
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return clean_text(text)

def normalize_text(text):
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")
    return text

def get_next_edition_number():
    if os.path.exists("edition.json"):
        try:
            with open("edition.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("edition_number", 0) + 1
        except:
            return 1
    return 1

def title_is_question(title):
    title = title.strip()
    return "¿" in title or title.endswith("?")

# =============================
# IA — RESPUESTA DIRECTA
# =============================

def generate_answer_to_question(text, title):

    if not client:
        return None

    text = text[:2500]

    prompt = f"""
El siguiente titular es una pregunta.

Responde claramente la pregunta en máximo {MAX_SUMMARY_LENGTH} caracteres.

Reglas:
- Respuesta directa.
- No repitas la pregunta.
- No agregues contexto innecesario.
- Solo usa información explícita del texto.
- Tono periodístico neutral.
- Termina en punto.

Titular:
{title}

Noticia:
{text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=220
        )

        answer = clean_text(response.choices[0].message.content)

        # Recorte seguro
        if len(answer) > MAX_SUMMARY_LENGTH:
            trimmed = answer[:MAX_SUMMARY_LENGTH]
            last_period = trimmed.rfind(".")
            if last_period != -1:
                answer = trimmed[:last_period + 1]
            else:
                answer = trimmed.rsplit(" ", 1)[0] + "."

        if not answer.endswith("."):
            answer = answer.rstrip(" ,;:") + "."

        return answer

    except Exception as e:
        print("Error IA:", e)
        return None

# =============================
# SCRAPING
# =============================

def extract_article_data(url):

    try:
        print("🔎 Procesando:", url)

        if any(path in url.lower() for path in BLOCKED_PATHS):
            return None

        for domain in BLOCKED_DOMAINS:
            if domain in url:
                return None

        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=20)

        if response.status_code != 200:
            return None

        response.encoding = response.apparent_encoding
        original_soup = BeautifulSoup(response.text, "html.parser")

        title_tag = original_soup.find("meta", property="og:title")
        image_tag = original_soup.find("meta", property="og:image")
        source_tag = original_soup.find("meta", property="og:site_name")

        if not title_tag:
            return None

        title = clean_text(title_tag["content"].split("|")[0])

        # 🔥 SOLO PREGUNTAS
        if not title_is_question(title):
            print("⛔ No es pregunta, descartado")
            return None

        image = image_tag["content"] if image_tag else ""
        source = source_tag["content"] if source_tag else "Fuente"

        try:
            doc = Document(response.text)
            content_html = doc.summary()
            soup = BeautifulSoup(content_html, "html.parser")
        except:
            soup = original_soup

        paragraphs = soup.find_all(["p", "li"])
        clean_paragraphs = []

        for p in paragraphs:
            text_p = clean_text(p.get_text())
            if len(text_p) < 50:
                continue
            clean_paragraphs.append(text_p)

        article_text = clean_noise(" ".join(clean_paragraphs))

        if len(article_text) < 200:
            return None

        print("🟢 Generando respuesta directa")
        summary = generate_answer_to_question(article_text, title)

        if not summary:
            print("⚠ No se pudo generar respuesta clara")
            return None

        return {
            "titleOriginal": title,
            "summary280": summary,
            "sourceName": source,
            "sourceUrl": url,
            "imageUrl": image,
            "type": "question"
        }

    except Exception as e:
        print("Error procesando:", url, e)
        return None

# =============================
# MAIN
# =============================

def main():

    if not os.path.exists("links.txt"):
        print("No existe links.txt")
        return

    with open("links.txt", "r", encoding="utf-8") as f:
        raw_links = f.read()

    links = re.findall(r'https?://[^\s;]+', raw_links)

    headlines = []

    for link in links:

        data = extract_article_data(link)

        if data:
            headlines.append(data)

        if len(headlines) >= MAX_NEWS:
            break

    now = datetime.now(ZoneInfo("America/Bogota"))

    edition = {
        "edition_date": now.strftime("%d %b %Y"),
        "edition_number": get_next_edition_number(),
        "generated_at": now.isoformat(),
        "country": "Internacional",
        "headlines": headlines
    }

    with open("edition.json", "w", encoding="utf-8") as f:
        json.dump(edition, f, indent=2, ensure_ascii=False)

    print("===== FIN GENERATE.PY =====")

if __name__ == "__main__":
    main()
