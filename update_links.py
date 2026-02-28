import requests
import xml.etree.ElementTree as ET
import re

RSS_URL = "https://news.google.com/rss?hl=es-419&gl=CO&ceid=CO:es-419"
MAX_LINKS = 7


def extract_real_url_from_description(description):
    match = re.search(r'href="(https?://[^"]+)"', description)
    if match:
        return match.group(1)
    return None


def fetch_links():
    response = requests.get(RSS_URL, timeout=10)
    root = ET.fromstring(response.content)

    links = []
    count = 0

    for item in root.findall(".//item"):
        if count >= MAX_LINKS:
            break

        description = item.find("description").text
        real_url = extract_real_url_from_description(description)

        if real_url:
            links.append(real_url)
            count += 1

    return links


def main():
    print("🔎 Obteniendo enlaces reales desde Google News RSS...")

    links = fetch_links()

    if not links:
        print("❌ No se obtuvieron enlaces")
        return

    # 🔥 Separados por punto y coma SIN salto de línea
    content = ";".join(links)

    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ links.txt actualizado correctamente")
    print("Total enlaces guardados:", len(links))


if __name__ == "__main__":
    main()
