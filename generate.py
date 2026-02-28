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
    client = None
else:
    print("✅ OPENAI_API_KEY detectada")
    client = OpenAI(api_key=API_KEY)

MAX_NEWS = 7
MAX_SUMMARY_LENGTH = 400

BLOCKED_DOMAINS = [
    "nytimes.com"
]

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
        r'Ingrese o regístrese.*?\.',
        r'©.*?',
        r'Suscríbete.*?',
        r'Redes sociales.*?\.',
        r'Audio generado.*?',
        r'Por Agencia EFE.*?\.'
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


def summary_is_incomplete(summary):
    generic_phrases = [
        "según reportes",
        "ha generado preocupación",
        "ha generado alerta",
        "se insta a"
    ]

    if any(p in summary.lower() for p in generic_phrases):
        return True

    if len(summary) < 120:
        return True

    return False


# =============================
# RESUMEN IA PROFESIONAL
# =============================

def generate_summary_with_ai(text, title):

    if not client:
        print("⚠ No hay cliente OpenAI. Usando fallback.")
        return fallback_summary(text)

    text = text[:2500]

    max_attempts = 2
    attempt = 0
    last_summary = None

    while attempt < max_attempts:

        prompt = f"""
Resume la siguiente noticia en máximo {MAX_SUMMARY_LENGTH} caracteres.

Reglas estrictas:
- Usa únicamente información explícitamente presente en el texto proporcionado.
- No agregues datos externos.
- No infieras hechos.
- No inventes cifras, fechas, arrestos, decisiones o consecuencias si no aparecen claramente en el texto.
- No uses frases vagas.
- Mantén tono periodístico neutral.
- Debe terminar en punto.

Noticia:
{text}
"""

        try:
            print(f"🔵 Intento {attempt+1} llamando a OpenAI...")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300
            )

            summary = response.choices[0].message.content.strip()
            summary = clean_text(summary)
            last_summary = summary

            if (
                len(summary) <= MAX_SUMMARY_LENGTH
                and summary.endswith(".")
                and not summary_is_incomplete(summary)
            ):
                print("✅ Resumen válido generado por IA")
                return summary

            print("⚠ Resumen insuficiente, reintentando...")
            attempt += 1

        except Exception as e:
            print("🔴 Error en llamada OpenAI:", e)
            break

    if last_summary:
        print("⚠ Validación estricta falló. Usando último resumen IA.")
        return last_summary

    print("⚠ Fallback por error real.")
    return fallback_summary(text)


def fallback_summary(text):
    print("🟡 Generando resumen por fallback (NO IA)")
    fallback = text[:250].rsplit(" ", 1)[0]
    return fallback.rstrip(" ,;:") + "."


# =============================
# SCRAPING
# =============================

def extract_article_data(url):
    try:
        print("🔎 Procesando:", url)

        if any(path in url.lower() for path in BLOCKED_PATHS):
            print("⛔ Artículo de opinión detectado. Saltando.")
            return None

        for domain in BLOCKED_DOMAINS:
            if domain in url:
                print(f"⛔ Dominio bloqueado ({domain}). Saltando.")
                return None

        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=20)

        if response.status_code != 200:
            print("❌ HTTP error:", response.status_code)
            return None

        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("meta", property="og:title")
        image_tag = soup.find("meta", property="og:image")
        source_tag = soup.find("meta", property="og:site_name")

        if not title_tag:
            print("❌ Sin og:title")
            return None

        title = clean_text(title_tag["content"].split("|")[0])
        image = image_tag["content"] if image_tag else ""
        source = source_tag["content"] if source_tag else "Fuente"

        article = soup.find("article")
        paragraphs = article.find_all(["p", "li"]) if article else soup.find_all(["p", "li"])

        clean_paragraphs = []

        for p in paragraphs:
            text_p = clean_text(p.get_text())
            if len(text_p) < 40:
                continue
            if any(x in text_p for x in ["Publicidad", "Suscríbete", "©"]):
                continue
            clean_paragraphs.append(text_p)

        article_text = " ".join(clean_paragraphs)
        article_text = clean_noise(article_text)

        if len(article_text) < 150:
            print("❌ Texto muy corto")
            return None

        print("✔ Texto extraído:", len(article_text), "caracteres")

        summary = generate_summary_with_ai(article_text, title)

        return {
            "titleOriginal": title,
            "summary400": summary,
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
            print(f"✅ Noticias válidas acumuladas: {len(headlines)}")

        if len(headlines) >= MAX_NEWS:
            print("🎯 Se alcanzaron las 7 noticias válidas.")
            break

    if len(headlines) < MAX_NEWS:
        print(f"⚠ Solo se pudieron obtener {len(headlines)} noticias válidas.")

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
