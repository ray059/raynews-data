import requests
import xml.etree.ElementTree as ET
import re

RSS_URL = "https://news.google.com/rss?hl=es-419&gl=CO&ceid=CO:es-419"

def clean_google_redirect(url):
    match = re.search(r'url=(https?://[^&]+)', url)
    if match:
        return match.group(1)
    return url

def fetch_links():
    response = requests.get(RSS_URL)
    root = ET.fromstring(response.content)

    links = []

    for item in root.findall(".//item"):
        link = item.find("link").text
        clean_link = clean_google_redirect(link)
        links.append(clean_link)

    return links

def main():
    links = fetch_links()

    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(",\n".join(links))

    print("✅ links.txt actualizado automáticamente")

if __name__ == "__main__":
    main()
