import requests
import os
from urllib.parse import urlparse

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

MAX_FETCH_PER_QUERY = 25   # Cada query trae hasta 25
MAX_SAVE = 25              # Guardamos 25 finales
MAX_PER_DOMAIN = 4         # Máximo 4 por medio

BLOCKED_PATHS = [
    "/opinion/",
    "/columnas",
    "/columnas-de-opinion",
    "/blogs/",
    "/editoriales/"
]

EXCLUDE_KEYWORDS = [
    "lotería", "loteria", "sorteo",
    "numeros ganadores", "chance", "baloto"
]


# =============================
# UTILIDADES
# =============================

def normalize_url(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def is_valid_article(title, url):
    title_lower = title.lower()
    url_lower = url.lower()

    # Filtrar basura tipo lotería
    for word in EXCLUDE_KEYWORDS:
        if word in title_lower:
            return False

    # Filtrar opinión/editorial por URL
    for path in BLOCKED_PATHS:
        if path in url_lower:
            return False

    return True


def remove_duplicates(articles):
    seen_titles = set()
    seen_urls = set()
    unique = []

    for a in articles:
        title = a["title"].strip().lower()
        url = normalize_url(a["url"])

        if title in seen_titles:
            continue
        if url in seen_urls:
            continue

        seen_titles.add(title)
        seen_urls.add(url)
        a["url"] = url
        unique.append(a)

    return unique


def limit_per_domain(articles):
    domain_count = {}
    balanced = []

    for a in articles:
        domain = urlparse(a["url"]).netloc

        if domain_count.get(domain, 0) >= MAX_PER_DOMAIN:
            continue

        domain_count[domain] = domain_count.get(domain, 0) + 1
        balanced.append(a)

    return balanced


# =============================
# FETCH GNEWS
# =============================

def fetch_gnews(query):
    if not GNEWS_API_KEY:
        print("❌ GNEWS_API_KEY no configurada")
        return []

    response = requests.get(
        "https://gnews.io/api/v4/search",
        params={
            "q": query,
            "lang": "es",
            "country": "co",
            "max": MAX_FETCH_PER_QUERY,
            "sortby": "publishedAt",
            "token": GNEWS_API_KEY
        }
    )

    if response.status_code != 200:
        print("❌ Error GNews:", response.status_code)
        return []

    data = response.json()
    return data.get("articles", [])


# =============================
# MAIN
# =============================

def main():
    print("🔎 Ejecutando doble consulta a GNews...")

    query1 = "Colombia OR política OR gobierno OR justicia"
    query2 = "salud OR economía OR internacional OR educación OR deportes"

    results1 = fetch_gnews(query1)
    print("Resultados query1:", len(results1))

    results2 = fetch_gnews(query2)
    print("Resultados query2:", len(results2))

    combined = results1 + results2
    print("Total combinados:", len(combined))

    if not combined:
        print("❌ No se obtuvieron artículos")
        return

    # Filtrar basura
    filtered = [
        {"title": a["title"], "url": a["url"]}
        for a in combined
        if is_valid_article(a["title"], a["url"])
    ]

    print("Después de filtrar basura:", len(filtered))

    # Quitar duplicados
    unique = remove_duplicates(filtered)
    print("Después de quitar duplicados:", len(unique))

    # Balancear medios
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
