import requests
import os
from datetime import datetime
from urllib.parse import urlparse

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

MAX_FETCH = 40          # traer más para margen
MAX_SAVE = 25           # guardar hasta 25 en links.txt
MAX_PER_DOMAIN = 4      # máximo 4 por medio

# Palabras que no queremos en títulos/URL
BLOCKED_PATHS = [
    "/opinion/",
    "/columnas",
    "/columnas-de-opinion",
    "/blogs/",
    "/editoriales/",
    "/cartas-al-editor/"
]

EXCLUDE_KEYWORDS = [
    "lotería", "loteria", "sorteo",
    "numeros ganadores", "chance",
    "baloto"
]


def is_valid_url(url):
    """Descartar opinión / columnistas por ruta en URL."""
    lower = url.lower()
    for path in BLOCKED_PATHS:
        if path in lower:
            return False
    return True


def is_valid_title(title):
    """Descartar titulares claramente de ruido/lotería."""
    if not title:
        return False
    text = title.lower()
    for kw in EXCLUDE_KEYWORDS:
        if kw in text:
            return False
    return True


def normalize_url(url):
    """Limpia parámetros de tracking en la URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def remove_duplicates(articles):
    seen_titles = set()
    seen_urls = set()
    unique = []

    for a in articles:
        title_norm = a["title"].strip().lower()
        url_norm = normalize_url(a["url"])

        if title_norm in seen_titles:
            continue
        if url_norm in seen_urls:
            continue

        seen_titles.add(title_norm)
        seen_urls.add(url_norm)

        a["url"] = url_norm
        unique.append(a)

    return unique


def limit_per_domain(articles):
    """Limita cuántos enlaces por dominio."""
    domain_count = {}
    balanced = []

    for a in articles:
        domain = urlparse(a["url"]).netloc
        if domain_count.get(domain, 0) >= MAX_PER_DOMAIN:
            continue
        domain_count[domain] = domain_count.get(domain, 0) + 1
        balanced.append(a)

    return balanced


def fetch_articles():
    if not GNEWS_API_KEY:
        print("❌ GNEWS_API_KEY no configurada")
        return []

    try:
        response = requests.get(
            "https://gnews.io/api/v4/search",
            params={
                "q": "Colombia OR política OR economía OR internacional OR gobierno OR justicia OR educación OR deportes",
                "lang": "es",
                "country": "co",
                "max": MAX_FETCH,
                "sortby": "publishedAt",
                "token": GNEWS_API_KEY
            }
        )
        response.raise_for_status()
        data = response.json()
        return data.get("articles", [])
    except Exception as e:
        print("❌ Error GNews:", e)
        return []


def main():
    print("🔎 Obteniendo noticias desde GNews...")

    raw = fetch_articles()

    if not raw:
        print("❌ No se obtuvieron artículos")
        return

    print("Total traídas:", len(raw))

    # Filtrar por título y URL
    filtered = [
        {"title": a.get("title", ""), "url": a.get("url", "")}
        for a in raw
        if is_valid_title(a.get("title", "")) and is_valid_url(a.get("url", ""))
    ]
    print("Después de filtrar opinion/editorial/lotería:", len(filtered))

    # Eliminar duplicados
    unique = remove_duplicates(filtered)
    print("Después de quitar duplicados:", len(unique))

    # Ordenar por orden original (ya viene ordenado por publishedAt)
    # Balancear cuántos por dominio
    balanced = limit_per_domain(unique)
    print("Después de balancear por dominio:", len(balanced))

    # Guardar hasta MAX_SAVE
    final = balanced[:MAX_SAVE]
    links = [a["url"] for a in final]

    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(";".join(links))

    print("✅ links.txt actualizado")
    print("✔ Enlaces guardados:", len(links))


if __name__ == "__main__":
    main()
