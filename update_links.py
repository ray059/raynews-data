import requests
import os

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
MAX_LINKS = 7

URL = "https://gnews.io/api/v4/top-headlines"

PARAMS = {
    "lang": "es",
    "country": "co",
    "max": MAX_LINKS,
    "token": GNEWS_API_KEY
}

def fetch_links():
    response = requests.get(URL, params=PARAMS)

    if response.status_code != 200:
        print("❌ Error en GNews:", response.status_code)
        print(response.text)
        return []

    data = response.json()
    articles = data.get("articles", [])

    links = []
    for article in articles:
        url = article.get("url")
        if url:
            links.append(url)

    return links


def main():
    print("🔎 Obteniendo enlaces desde GNews...")

    if not GNEWS_API_KEY:
        print("❌ GNEWS_API_KEY no configurada")
        return

    links = fetch_links()

    if not links:
        print("❌ No se obtuvieron enlaces")
        return

    content = ";".join(links)

    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ links.txt actualizado correctamente")
    print("Total enlaces guardados:", len(links))


if __name__ == "__main__":
    main()
