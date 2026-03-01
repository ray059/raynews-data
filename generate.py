import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import re

print("===== INICIO GENERATE.PY =====")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()

# -------------------------------------------------
# EXTRAER TEXTO REAL DEL ARTÍCULO
# -------------------------------------------------
def extract_article_text(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text() for p in paragraphs])

        return clean_text(text)
    except Exception as e:
        print("Error extrayendo artículo:", e)
        return ""

# -------------------------------------------------
# EXTRAER IMAGEN PRINCIPAL
# -------------------------------------------------
def extract_image(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]
    except:
        pass

    return None

# -------------------------------------------------
# GENERAR RESUMEN EDITORIAL PRUDENTE
# -------------------------------------------------
def generate_summary(title, article_text):
    if not OPENAI_API_KEY:
        return None

    import openai
    openai.api_key = OPENAI_API_KEY

    prompt = f"""
Responde claramente la pregunta del titular en máximo 280 caracteres.

Reglas obligatorias:
- Basate únicamente en el texto proporcionado.
- No inventes información.
- Mantén tono analítico y prudente.
- Si el artículo menciona hipótesis o falta de confirmación, indícalo.
- No afirmes como hecho algo que el texto no confirme explícitamente.
- No incluyas listas de números tipo lotería.
- No confirmes muertes salvo que el texto lo afirme explícitamente.

Titular: {title}

Artículo:
{article_text[:4000]}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        summary = response["choices"][0]["message"]["content"]
        return clean_text(summary)

    except Exception as e:
        print("Error OpenAI:", e)
        return None

# -------------------------------------------------
# VALIDADOR BÁSICO
# -------------------------------------------------
def validate_summary(summary):
    if not summary:
        return False

    if len(summary) < 80 or len(summary) > 280:
        return False

    if not summary.endswith((".", "!", "?")):
        return False

    forbidden = [
        "no puedo acceder",
        "como modelo de lenguaje",
        "no tengo información",
        "url proporcionada"
    ]

    lower = summary.lower()
    for f in forbidden:
        if f in lower:
            return False

    return True

# -------------------------------------------------
# FILTRO DE CONTENIDO RIESGOSO
# -------------------------------------------------
def contains_risky_content(summary):
    lower = summary.lower()

    # Bloquear secuencias de números tipo lotería
    if re.search(r"\b\d{1,2},\s?\d{1,2},\s?\d{1,2}", lower):
        return True

    risky_words = [
        "confirmó",
        "confirmado",
        "ha confirmado",
        "murió",
        "muerte confirmada",
        "fallecimiento confirmado"
    ]

    for word in risky_words:
        if word in lower:
            return True

    return False

# -------------------------------------------------
# PROCESAMIENTO PRINCIPAL
# -------------------------------------------------
headlines = []

if not os.path.exists("links.txt"):
    print("No hay links.txt")
    exit()

with open("links.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    parts = line.strip().split("||")
    if len(parts) != 3:
        continue

    title, url, source_name = parts
    print("Procesando:", title)

    article_text = extract_article_text(url)

    if len(article_text) < 500:
        print("Artículo muy corto. Saltando.")
        continue

    summary = generate_summary(title, article_text)

    # Validación básica
    if not validate_summary(summary):
        print("Resumen inválido. Reintentando...")
        summary = generate_summary(title, article_text)

    # Filtro de riesgo
    if contains_risky_content(summary):
        print("Contenido riesgoso detectado. Regenerando en modo prudente...")
        summary = generate_summary(title, article_text)

    # Validación final
    if not validate_summary(summary) or contains_risky_content(summary):
        print("Resumen descartado por seguridad editorial.")
        continue

    image = extract_image(url)

    headlines.append({
        "titleOriginal": title,
        "summary280": summary[:280],
        "sourceName": source_name,
        "sourceUrl": url,
        "imageUrl": image,
        "type": "question"
    })

    if len(headlines) >= 20:
        break

now = datetime.now(ZoneInfo("America/Bogota"))

edition = {
    "edition_date": now.strftime("%d %b %Y"),
    "generated_at": now.isoformat(),
    "country": "Internacional",
    "headlines": headlines
}

with open("edition.json", "w", encoding="utf-8") as f:
    json.dump(edition, f, indent=2, ensure_ascii=False)

print("Noticias finales:", len(headlines))
print("===== FIN GENERATE.PY =====")
