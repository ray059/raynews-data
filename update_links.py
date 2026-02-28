import requests
import os
from datetime import datetime

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

MAX_PER_QUERY = 10      # 10 por categoría
MAX_SAVE = 30           # guardamos hasta 30 enlaces

EXCLUDE_KEYWORDS = [
    "lotería",
    "loteria",
    "sorteo",
    "numeros ganadores",
    "chance",
    "baloto"
]

# 🔥 Consultas temáticas separadas
QUERIES = [
    "Colombia política elecciones gobierno",
    "Colombia salud epidemia vacunación",
    "Colombia justicia fiscalía investigación",
    "Colombia economía inflación empleo empresas",
    "Colombia internacional relaciones diplomáticas"
]


def is_valid_article(title):
    title_lower = title.lower()
    for word in EXCLUDE_KEYWORDS:
        if word in title_lower:
            return False
    return True


def remove_duplicates(articles):
    seen_urls = set()
    unique = []

    for article in articles:
        url = article["url"]
        if url not in seen_urls:
            seen_urls.add(url)
            unique.append(article)

    return unique


def fetch_query(query):

    response = requests.get(
        "https://gnews.io/api/v4/search",
        params={
            "q": query,
            "lang": "es",
            "country": "co",
            "max": MAX_PER_QUERY,
            "sortby": "publishedAt",
            "token": GNEWS_API_KEY
        }
    )

    if response.status_code != 200:
        print("❌ Error en query:", query)
        return []

    data = response.json()
    return data.get("articles", [])


def main():

    if not GNEWS_API_KEY:
        print("❌ GNEWS_API_KEY no configurada")
        return

    print("🔎 Iniciando consultas múltiples...")

    all_articles = []

    for query in QUERIES:
        print(f"📡 Consultando: {query}")
        articles = fetch_query(query)
        print("   → obtenidos:", len(articles))
        all_articles.extend(articles)

    print("Total bruto:", len(all_articles))

    # 1️⃣ eliminar duplicados por URL
    all_articles = remove_duplicates(all_articles)
    print("Después de quitar duplicados:", len(all_articles))

    # 2️⃣ filtrar basura real
    filtered = [
        a for a in all_articles
        if is_valid_article(a["title"])
    ]

    print("Después de filtrar ruido:", len(filtered))

    # 3️⃣ ordenar por fecha
    filtered.sort(
        key=lambda x: datetime.fromisoformat(
            x["publishedAt"].replace("Z", "+00:00")
        ),
        reverse=True
    )

    # 4️⃣ guardar hasta 30
    final_articles = filtered[:MAX_SAVE]

    links = [a["url"] for a in final_articles]

    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(";".join(links))

    print("✅ links.txt actualizado")
    print("Total enlaces guardados:", len(links))


if __name__ == "__main__":
    main()
