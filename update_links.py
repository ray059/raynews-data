import requests
import xml.etree.ElementTree as ET

# Feed alternativo que devuelve links reales
RSS_URL = "https://news.google.com/rss/search?q=when:1d&hl=es-419&gl=CO&ceid=CO:es-419"
MAX_LINKS = 7


def fetch_links():
    response = requests.get(RSS_URL, timeout=10)
    root = ET.fromstring(response.content)

    links = []
    count = 0

    for item in root.findall(".//item"):
        if count >= MAX_LINKS:
            break

        link = item.find("link").text

        # Este feed ya trae la URL real
        if link and not link.startswith("https://news.google.com"):
            links.append(link)
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
