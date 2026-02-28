import requests
import xml.etree.ElementTree as ET
import base64
import re

RSS_URL = "https://news.google.com/rss?hl=es-419&gl=CO&ceid=CO:es-419"
MAX_LINKS = 7


def decode_google_news_url(google_url):
    try:
        match = re.search(r'/articles/([^?]+)', google_url)
        if not match:
            return None

        encoded_part = match.group(1)

        padded = encoded_part + "=" * (-len(encoded_part) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")

        url_match = re.search(r'https?://[^"]+', decoded)
        if url_match:
            return url_match.group(0)

    except Exception as e:
        print("Decode error:", e)

    return None


def fetch_links():
    response = requests.get(RSS_URL, timeout=10)
    root = ET.fromstring(response.content)

    links = []
    count = 0

    for item in root.findall(".//item"):
        if count >= MAX_LINKS:
            break

        google_link = item.find("link").text
        real_url = decode_google_news_url(google_link)

        if real_url:
            links.append(real_url)
            count += 1

    return links


def main():
    print("🔎 Obteniendo enlaces reales desde Google News...")

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
