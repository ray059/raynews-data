import requests
import os
from datetime import datetime

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

MAX_FETCH = 25
MAX_FINAL = 7

# 🔥 Solo filtramos basura real, NO clickbait atractivo
EXCLUDE_KEYWORDS = [
    "lotería",
    "loteria",
    "sorteo",
    "numeros ganadores",
    "chance",
    "baloto"
]


def is_valid_article(title):
    title_lower = title.lower()

    for word in EXCLUDE_KEYWORDS:
        if word in title_lower:
            return False

    return True


def remove_duplicates(articles):
    seen_titles = set()
    unique = []

    for article in articles:
        normalized = article["title"].strip().lower()

        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique.append(article)

    return unique


def fetch_articles():
    if not GNEWS_API_KEY:
        print("❌ GNEWS_API_KEY no configurada")
        return []

    response = requests.get(
        "https://gnews.io/api/v4/search",
        params={
            "q": "Colombia OR política OR economía OR internacional OR gobierno OR justicia",
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


def main():
    print("🔎 Obteniendo noticias desde GNews...")

    articles = fetch_articles()

    if not articles:
        print("❌ No se obtuvieron artículos")
        return

    # 1️⃣ Eliminar duplicados
    articles = remove_duplicates(articles)

    # 2️⃣ Filtrar basura irrelevante
    filtered = [
        a for a in articles
        if is_valid_article(a["title"])
    ]

    # 3️⃣ Ordenar por fecha (más recientes primero)
    filtered.sort(
        key=lambda x: datetime.fromisoformat(
            x["publishedAt"].replace("Z", "+00:00")
        ),
        reverse=True
    )

    # 4️⃣ Tomar las 7 finales
    final_articles = filtered[:MAX_FINAL]

    links = [a["url"] for a in final_articles]

    if len(links) < MAX_FINAL:
        print("⚠ Menos de 7 noticias después del filtro")

    content = ";".join(links)

    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ links.txt actualizado correctamente")
    print("Total enlaces guardados:", len(links))


if __name__ == "__main__":
    main()
