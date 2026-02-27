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

# 🔥 CONFIGURACIÓN ESTRATÉGICA MVP
MAX_NEWS = 7

# Dominios que bloquean scraping o no valen la pena
BLOCKED_DOMAINS = [
    "nytimes.com"
]

# =============================
# HELPERS
# =============================

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()


def clean_noise(text):
    text = re.sub(r'Publicidad', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Audio generado.*?0:00\s*/\s*0:00', '', text, flags=re.IGNORECASE)
    text = re.sub(r'por Agencia EFE', '', text, flags=re.IGNORECASE)
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


# =============================
# RESUMEN IA OPTIMIZADO
# =============================

def generate_summary_with_ai(text):

    if not client:
        print("⚠ No hay cliente OpenAI. Usando fallback.")
        return fallback_summary(text)

    text = text[:1500]  # 🔥 límite de texto enviado

    max_attempts = 3
    attempt = 0

    prompt = f"""Resume la siguiente noticia en máximo 280 caracteres.
Debe terminar en punto.
Explica únicamente el hecho principal sin frases abiertas.

Noticia:
{text}
"""

    while attempt < max_attempts:
        try:
            print(f"🔵 Intento {attempt+1} llamando a OpenAI...")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=180
            )

            summary = response.choices[0].message.content.strip()
            summary = clean_text(summary)
            summary = summary.replace("..", ".").replace(" .", ".")

            if (
                len(summary) <= 280
                and summary.endswith(".")
                and ".." not in summary
            ):
                print("✅ Resumen válido generado por IA")
                return summary

            print("⚠ Resumen inválido, reintentando...")
            prompt = f"Corrige y acorta este resumen a máximo 280 caracteres y ciérralo correctamente:\n\n{summary}"
            attempt += 1

        except Exception as e:
            print("🔴 Error en llamada OpenAI:", e)
            break

    print("⚠ Entrando en fallback final")
    return fallback_summary(text)


def fallback_summary(text):
    print("🟡 Generando resumen por fallback (NO IA)")
    fallback = text[:200].rsplit(" ", 1)[0]
    return fallback.rstrip(" ,;:") + "."


# =============================
# SCRAPING
# =============================

def extract_article_data(url):
    try:
        print("🔎 Procesando:", url)

        # 🔥 Bloqueo de dominios inútiles
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
        paragraphs = article.find_all("p") if article else soup.find_all("p")

        clean_paragraphs = []

        for p in paragraphs:
            text_p = clean_text(p.get_text())

            if len(text_p) < 50:
                continue
            if any(x in text_p for x in ["Publicidad", "Suscríbete", "©"]):
                continue

            clean_paragraphs.append(text_p)

        article_text = " ".join(clean_paragraphs)
        article_text = clean_noise(article_text)

        if len(article_text) < 120:
            print("❌ Texto muy corto")
            return None

        print("✔ Texto extraído:", len(article_text), "caracteres")

        summary = generate_summary_with_ai(article_text)

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

        # 🔥 Corte temprano si ya tenemos suficientes noticias
        if len(headlines) >= MAX_NEWS:
            print("🎯 Límite de noticias alcanzado. Deteniendo procesamiento.")
            break

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
