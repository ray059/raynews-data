import requests
from bs4 import BeautifulSoup
from readability import Document
import json
from datetime import datetime
import re
import os
from openai import OpenAI

print("===== INICIO GENERATE.PY =====")

API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    print("❌ OPENAI_API_KEY no encontrada")
    client = None
else:
    print("✅ OPENAI_API_KEY detectada")
    client = OpenAI(api_key=API_KEY)

MAX_NEWS = 7
MAX_SUMMARY_LENGTH = 400

BLOCKED_DOMAINS = ["nytimes.com"]

BLOCKED_PATHS = [
    "/opinion/",
    "/columnas",
    "/columnas-de-opinion",
    "/blogs/",
    "/editoriales/"
]

# =====================================================
# HELPERS
# =====================================================

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()


def clean_noise(text):
    patterns = [
        r'Publicidad.*?',
        r'©.*?',
        r'Suscríbete.*?',
        r'Redes sociales.*?\.',
        r'Google News.*?\.',
        r'WhatsApp.*?\.',
        r'Canal.*?\.',
        r'App de EL TIEMPO.*?\.'
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    return clean_text(text)


def get_next_edition_number():
    if os.path.exists("edition.json"):
        try:
            with open("edition.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("edition_number", 0) + 1
        except:
            return 1
    return 1


def fallback_summary(text):
    fallback = text[:300].rsplit(" ", 1)[0]
    return fallback.rstrip(" ,;:") + "."


# =====================================================
# VALIDACIONES
# =====================================================

def is_question_title(title):
    return "¿" in title or any(
        w in title.lower()
        for w in ["por qué", "qué", "quién", "cómo", "cuándo", "dónde"]
    )


def summary_covers_title(summary, title):
    words = [w for w in re.findall(r'\w+', title.lower()) if len(w) > 4]
    if not words:
        return True

    summary_lower = summary.lower()
    matches = sum(1 for w in words if w in summary_lower)

    return (matches / len(words)) >= 0.3


def is_low_quality(summary):
    generic = [
        "según reportes",
        "mantente informado",
        "google news",
        "whatsapp",
        "descargue",
        "síganos"
    ]

    return (
        len(summary) < 150
        or any(g in summary.lower() for g in generic)
    )


# =====================================================
# EXTRACTORES
# =====================================================

def extract_with_readability(url):
    try:
        response = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        doc = Document(response.text)
        html = doc.summary()

        soup = BeautifulSoup(html, "html.parser")
        paragraphs = soup.find_all("p")

        text = " ".join(p.get_text() for p in paragraphs)
        text = clean_noise(text)

        if len(text) > 400:
            print("✅ Extraído con Readability")
            return text

        print("⚠ Readability devolvió poco contenido")
        return None

    except Exception as e:
        print("⚠ Error en Readability:", e)
        return None


def extract_with_bs(url):
    try:
        response = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        soup = BeautifulSoup(response.text, "html.parser")

        article = soup.find("article")
        paragraphs = article.find_all("p") if article else soup.find_all("p")

        clean_paragraphs = []

        for p in paragraphs:
            t = clean_text(p.get_text())
            if len(t) > 50:
                clean_paragraphs.append(t)

        text = " ".join(clean_paragraphs[:8])
        text = clean_noise(text)

        if len(text) > 200:
            print("✅ Extraído con BeautifulSoup fallback")
            return text

        return None

    except Exception as e:
        print("❌ Error en fallback BS:", e)
        return None


# =====================================================
# RESUMEN IA (ESTILO RESPUESTA DIRECTA)
# =====================================================

def generate_summary_with_ai(text, title):

    if not client:
        return fallback_summary(text)

    question_mode = is_question_title(title)

    focus = """
- El titular es pregunta.
- La primera oración debe responderla explícitamente.
""" if question_mode else """
- Explica qué ocurrió.
- Incluye actores clave y hechos concretos.
"""

    prompt = f"""
TITULAR:
{title}

{focus}

REGLAS:
- Usa únicamente información presente en el texto.
- No inventes datos.
- No agregues opinión.
- No agregues contexto externo.
- Prioriza hechos verificables.
- Máximo {MAX_SUMMARY_LENGTH} caracteres.
- Debe terminar en punto.
- Devuelve solo el resumen final.

NOTICIA:
{text[:3500]}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.05,
            max_tokens=350
        )

        summary = clean_text(response.choices[0].message.content.strip())

        if (
            len(summary) <= MAX_SUMMARY_LENGTH
            and summary.endswith(".")
            and summary_covers_title(summary, title)
            and not is_low_quality(summary)
        ):
            print("✅ Resumen válido")
            return summary

        print("⚠ Reintentando con mayor precisión...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": prompt + "\nReescribe con mayor precisión factual."
            }],
            temperature=0.02,
            max_tokens=350
        )

        return clean_text(response.choices[0].message.content.strip())

    except Exception as e:
        print("❌ Error IA:", e)
        return fallback_summary(text)


# =====================================================
# SCRAPING PRINCIPAL
# =====================================================

def extract_article_data(url):
    try:
        print("🔎 Procesando:", url)

        if any(p in url.lower() for p in BLOCKED_PATHS):
            print("⛔ Opinión detectada")
            return None

        if any(d in url for d in BLOCKED_DOMAINS):
            print("⛔ Dominio bloqueado")
            return None

        # 1️⃣ Intento con Readability
        text = extract_with_readability(url)

        # 2️⃣ Fallback si falla
        if not text:
            text = extract_with_bs(url)

        if not text:
            print("❌ No se pudo extraer contenido")
            return None

        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("meta", property="og:title")
        image_tag = soup.find("meta", property="og:image")
        source_tag = soup.find("meta", property="og:site_name")

        if not title_tag:
            return None

        title = clean_text(title_tag["content"].split("|")[0])
        image = image_tag["content"] if image_tag else ""
        source = source_tag["content"] if source_tag else "Fuente"

        summary = generate_summary_with_ai(text, title)

        return {
            "titleOriginal": title,
            "summary280": summary,
            "sourceName": source,
            "sourceUrl": url,
            "imageUrl": image
        }

    except Exception as e:
        print("❌ Error procesando:", e)
        return None


# =====================================================
# MAIN
# =====================================================

def main():

    if not os.path.exists("links.txt"):
        print("❌ No existe links.txt")
        return

    with open("links.txt", "r", encoding="utf-8") as f:
        raw_links = f.read()

    links = re.findall(r'https?://[^\s;]+', raw_links)

    headlines = []

    for link in links:

        data = extract_article_data(link)

        if data:
            headlines.append(data)
            print(f"✅ Noticias acumuladas: {len(headlines)}")

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
