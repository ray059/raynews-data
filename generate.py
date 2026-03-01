import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
import os
import unicodedata
from openai import OpenAI
from readability import Document

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

CORE_EVENT_WORDS = [
    "sarampion",
    "fiebre amarilla",
    "elecciones",
    "gran consulta",
    "eps",
    "decreto",
    "sobretasa",
    "arancel",
    "guerra arancelaria",
    "trasplante",
    "empleo",
    "violencia"
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

def normalize_title(title):
    title = normalize_text(title)
    title = re.sub(r'[^a-z0-9\s]', '', title)
    words = title.split()
    words = [w for w in words if len(w) > 4]
    return set(words)

def is_similar_title(title, existing_titles):
    current_words = normalize_title(title)
    for t in existing_titles:
        other_words = normalize_title(t)
        if len(current_words.intersection(other_words)) >= 3:
            return True
    return False

def detect_event_keyword(title):
    normalized_title = normalize_text(title)
    for word in CORE_EVENT_WORDS:
        if normalize_text(word) in normalized_title:
            return normalize_text(word)
    return None

# =============================
# RESUMEN IA
# =============================

def generate_summary_with_ai(text):

    if not client:
        return fallback_summary(text)

    text = text[:2500]

    prompt = f"""
Resume la siguiente noticia en máximo {MAX_SUMMARY_LENGTH} caracteres.

Reglas:
- Usa solo información explícita del texto.
- No inventes datos.
- No agregues contexto externo.
- Tono periodístico neutral.
- Debe terminar en punto.

Noticia:
{text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200
        )

        summary = response.choices[0].message.content.strip()
        summary = clean_text(summary)

        if len(summary) <= MAX_SUMMARY_LENGTH and summary.endswith("."):
            return summary

        if len(summary) > MAX_SUMMARY_LENGTH:
            summary = summary[:MAX_SUMMARY_LENGTH]

        last_period = summary.rfind(".")
        if last_period > 150:
            summary = summary[:last_period + 1]
        else:
            summary = summary.rsplit(" ", 1)[0] + "."

        return summary

    except Exception as e:
        print("Error IA:", e)
        return fallback_summary(text)

def fallback_summary(text):
    fallback = text[:250].rsplit(" ", 1)[0]
    return fallback.rstrip(" ,;:") + "."

# =============================
# SCRAPING
# =============================

def extract_article_data(url, existing_titles):

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

        # META TAGS desde HTML original
        original_soup = BeautifulSoup(response.text, "html.parser")

        title_tag = original_soup.find("meta", property="og:title")
        image_tag = original_soup.find("meta", property="og:image")
        source_tag = original_soup.find("meta", property="og:site_name")

        if not title_tag:
            return None

        title = clean_text(title_tag["content"].split("|")[0])

        # Anti-duplicado por título
        if is_similar_title(title, existing_titles):
            print("⚠ Título similar descartado")
            return None

        image = image_tag["content"] if image_tag else ""
        source = source_tag["content"] if source_tag else "Fuente"

        # Readability para el cuerpo
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

        article_text = " ".join(clean_paragraphs)
        article_text = clean_noise(article_text)

        if len(article_text) < 200:
            return None

        summary = generate_summary_with_ai(article_text)

        return {
            "titleOriginal": title,
            "summary280": summary,
            "sourceName": source,
            "sourceUrl": url,
            "imageUrl": image
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
    used_events = set()

    for link in links:

        existing_titles = [h["titleOriginal"] for h in headlines]
        data = extract_article_data(link, existing_titles)

        if data:
            event = detect_event_keyword(data["titleOriginal"])

            if event:
                if event in used_events:
                    print("⚠ Evento ya cubierto:", event)
                    continue
                used_events.add(event)

            headlines.append(data)
            print("✅ Noticias acumuladas:", len(headlines))

        if len(headlines) >= MAX_NEWS:
            break

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
