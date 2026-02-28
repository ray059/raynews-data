import requests
import xml.etree.ElementTree as ET
import os
import json

RSS_URL = "https://news.google.com/rss?hl=es-419&gl=CO&ceid=CO:es-419"
MAX_LINKS = 7
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")


def resolve_redirect(url):
    try:
        response = requests.get(url, allow_redirects=True, timeout=10)
        return response.url
    except:
        return None


def fetch_from_rss():
    print("🔎 Intentando RSS oficial de Google News...")
    try:
        response = requests.get(RSS_URL, timeout=10)
        root = ET.fromstring(response.content)

        links = []
        for item in root.findall(".//item"):
            if len(links) >= MAX_LINKS:
                break

            google_link = item.find("link").text
            real_url = resolve_redirect(google_link)

            if real_url and "news.google.com" not in real_url:
                links.append(real_url)

        if len(links) == MAX_LINKS:
            print("✅ RSS funcionó correctamente")
            return links, "rss"

    except Exception as e:
        print("❌ Error RSS:", e)

    return [], None


def fetch_from_gnews():
    print("🔎 Intentando GNews como fallback...")
    if not GNEWS_API_KEY:
        print("❌ No hay GNEWS_API_KEY configurada")
        return [], None

    try:
        response = requests.get(
            "https://gnews.io/api/v4/top-headlines",
            params={
                "lang": "es",
                "country": "co",
                "max": MAX_LINKS,
                "token": GNEWS_API_KEY
            }
        )

        if response.status_code != 200:
            print("❌ Error GNews:", response.status_code)
            return [], None

        data = response.json()
        articles = data.get("articles", [])

        links = [a["url"] for a in articles if a.get("url")]

        if len(links) >= MAX_LINKS:
            print("✅ GNews funcionó correctamente")
            return links[:MAX_LINKS], "gnews"

    except Exception as e:
        print("❌ Error GNews:", e)

    return [], None


def main():
    links, source_used = fetch_from_rss()

    if not links:
        links, source_used = fetch_from_gnews()

    if not links:
        print("❌ Ninguna fuente funcionó")
        return

    content = ";".join(links)

    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(content)

    # Guardar metadata del motor usado
    metadata = {"source_used": source_used}
    with open("source_log.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f)

    print("🚀 Fuente usada:", source_used)
    print("Total enlaces guardados:", len(links))


if __name__ == "__main__":
    main()
