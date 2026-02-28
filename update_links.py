import requests
import os
from datetime import datetime
from urllib.parse import urlparse

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

MAX_FETCH = 40          # Traemos más para tener margen
MAX_SAVE = 25           # Guardamos 25 en links.txt
MAX_PER_DOMAIN = 4      # Máximo 4 por medio

EXCLUDE_KEYWORDS = [
    "lotería",
    "loteria",
    "sorteo",
    "numeros ganadores",
    "chance",
    "baloto"
]


# =============================
# VALIDACIONES
# =============================

def is_valid_article(title):
    title_lower = title.lower()
    for word in EXCLUDE_KEYWORDS:
        if word in title_lower:
            return False
    return True


def normalize_url(url):
    """
    Limpia parámetros de tracking.
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def remove_duplicates(articles):
    seen_titles = set()
    seen_urls = set()
    unique = []

    for article in articles:
        title = article["title"].strip().lower()
        url = normalize_url(article["url"])

        if title in seen_titles:
            continue

        if url in seen_urls:
            continue

        seen_titles.add(title)
        seen_urls.add(url)
        article["url"] = url
        unique.append(article)

    return unique


def limit_per_domain(articles):
    """
    Evita que un solo medio domine la lista.
    """
    domain_count = {}
    balanced = []

    for article in articles:
        domain = urlparse(article["url"]).netloc

        if domain_count.get(domain, 0) >= MAX_PER_DOMAIN:
            continue

        domain_count[domain] = domain_count.get(domain, 0) + 1
        balanced.append(article)

    return balanced


# =============================
# FETCH GNEWS
# =============================

def fetch_articles():
    if not GNEWS_API_KEY:
        print("❌ GNEWS_API_KEY no configurada")
        return []

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

    if response.status_code != 200:
        print("❌ Error GNews:", response.status_code)
        print(response.text)
        return []

    data = response.json()
    return data.get("articles", [])


# =============================
# MAIN
# =============================

def main():
    print("🔎 Obteniendo noticias desde GNews...")

    articles = fetch_articles()

    if not articles:
        print("❌ No se obtuvieron artículos")
        return

    print("Total traídas:", len(articles))

    # 1️⃣ Quitar duplicados
    articles = remove_duplicates(articles)
    print("Después de quitar duplicados:", len(articles))

    # 2️⃣ Filtrar basura real
    filtered = [
        a for a in articles
        if is_valid_article(a["title"])
    ]
    print("Después de filtrar basura:", len(filtered))

    # 3️⃣ Ordenar por fecha
    filtered.sort(
        key=lambda x: datetime.fromisoformat(
            x["publishedAt"].replace("Z", "+00:00")
        ),
        reverse=True
    )

    # 4️⃣ Balancear por medio
    filtered = limit_per_domain(filtered)
    print("Después de balancear medios:", len(filtered))

    # 5️⃣ Guardar hasta MAX_SAVE
    final_articles = filtered[:MAX_SAVE]
    links = [a["url"] for a in final_articles]

    if len(links) < 15:
        print("⚠ Pocas noticias obtenidas. Revisa filtros.")

    content = ";".join(links)

    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ links.txt actualizado correctamente")
    print("Total enlaces guardados:", len(links))


if __name__ == "__main__":
    main()
