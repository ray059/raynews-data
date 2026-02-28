import requests
import xml.etree.ElementTree as ET

RSS_URL = "https://news.google.com/rss?hl=es-419&gl=CO&ceid=CO:es-419"
MAX_LINKS = 7


def resolve_redirect(url):
    try:
        response = requests.get(url, allow_redirects=True, timeout=10)
        return response.url
    except Exception as e:
        print("Error resolviendo redirect:", e)
        return None


def fetch_links():
    response = requests.get(RSS_URL, timeout=10)
    root = ET.fromstring(response.content)

    links = []
    count = 0

    for item in root.findall(".//item"):
        if count >= MAX_LINKS:
            break

        link = item.find("link").text
        real_url = resolve_redirect(link)

        if real_url:
            links.append(real_url)
            count += 1

    return links


def main():
    print("🔎 Obteniendo enlaces desde Google News RSS...")

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
