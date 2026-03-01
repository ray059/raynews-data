import requests
import re
from bs4 import BeautifulSoup
from collections import Counter

print("===== INICIO UPDATE_LINKS.PY =====")

TARGET_NEWS = 12

RSS_SOURCES = [
    "https://feeds.bbci.co.uk/mundo/rss.xml",
    "https://cnnespanol.cnn.com/feed/",
    "https://www.infobae.com/arc/outboundfeeds/rss/",
    "https://www.dw.com/es/rss.xml"
]

STOPWORDS = {
    "qué","que","cómo","como","por","para","del","las","los","una","unos",
    "sobre","tras","ante","desde","hasta","contra","según","entre","donde"
}

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def is_valid_question(title):
    lower = title.lower()

    if "?" not in title and not lower.startswith(("qué","como","cómo","por qué","cuáles")):
        return False

    blocked = ["clima","horóscopo","temperatura","uv","dólar"]
    if any(b in lower for b in blocked):
        return False

    return True

def extract_keywords(title):
    words = re.findall(r'\b\w+\b', title.lower())
    words = [w for w in words if len(w) > 4 and w not in STOPWORDS]
    return words[:5]

def detect_country(title, link):
    lower = (title + " " + link).lower()
    if "colombia" in lower:
        return "colombia"
    elif "mexico" in lower:
        return "mexico"
    elif "peru" in lower:
        return "peru"
    elif "argentina" in lower:
        return "argentina"
    elif "ecuador" in lower:
        return "ecuador"
    return "internacional"

def detect_category(title):
    lower = title.lower()
    if any(w in lower for w in ["elección","presidente","senado","congreso","decreto"]):
        return "politica"
    if any(w in lower for w in ["econom","arancel","inflac","empleo"]):
        return "economia"
    if any(w in lower for w in ["salud","vacuna","enfermedad"]):
        return "salud"
    if any(w in lower for w in ["corte","justicia","condena"]):
        return "justicia"
    return "sociedad"

def extract_news():
    news = []

    for source in RSS_SOURCES:
        try:
            response = requests.get(source, timeout=15)
            soup = BeautifulSoup(response.content, "xml")
            items = soup.find_all("item")

            for item in items:
                title_tag = item.find("title")
                link_tag = item.find("link")

                if not title_tag or not link_tag:
                    continue

                title = clean_text(title_tag.text)
                link = clean_text(link_tag.text)

                if not is_valid_question(title):
                    continue

                news.append({
                    "title": title,
                    "link": link,
                    "country": detect_country(title, link),
                    "category": detect_category(title),
                    "keywords": extract_keywords(title)
                })

        except:
            continue

    return news

def balance_news(news):

    final = []
    country_used = {}
    category_used = {}
    macro_counter = Counter()

    for item in news:

        country = item["country"]
        category = item["category"]
        keywords = item["keywords"]

        # país
        if country != "colombia" and country_used.get(country,0) >= 1:
            continue

        # categoría
        if category_used.get(category,0) >= 2:
            continue

        # macrotema
        dominant = keywords[0] if keywords else None
        if dominant and macro_counter[dominant] >= 2:
            continue

        final.append(item)

        country_used[country] = country_used.get(country,0) + 1
        category_used[category] = category_used.get(category,0) + 1

        if dominant:
            macro_counter[dominant] += 1

        if len(final) >= TARGET_NEWS:
            break

    return final

def main():
    news = extract_news()
    balanced = balance_news(news)

    links = [item["link"] for item in balanced]

    with open("links.txt","w",encoding="utf-8") as f:
        f.write(";".join(links))

    print(f"✅ Links guardados: {len(links)}")
    print("===== FIN UPDATE_LINKS.PY =====")

if __name__ == "__main__":
    main()
