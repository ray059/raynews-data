import requests
import os
from datetime import datetime

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

MAX_FETCH = 30          # 🔥 Traemos 30
MAX_SAVE = 25           # 🔥 Guardamos 25 en links.txt

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

    print("Total traídas:", len(articles))

    # 1️⃣ Eliminar duplicados
    articles = remove_duplicates(articles)
    print("Después de quitar duplicados:", len(articles))

    # 2️⃣ Filtrar basura real (no clickbait atractivo)
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

    # 🔥 4️⃣ Guardamos 25, NO 7
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
