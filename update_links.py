import requests
import re
from bs4 import BeautifulSoup
from collections import Counter

print("===== INICIO UPDATE_LINKS.PY =====")

TARGET_NEWS = 12

RSS_SOURCES = {
    "bbc": "https://feeds.bbci.co.uk/mundo/rss.xml",
    "cnn": "https://cnnespanol.cnn.com/feed/",
    "infobae": "https://www.infobae.com/arc/outboundfeeds/rss/",
    "dw": "https://www.dw.com/es/rss.xml"
}

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
    return words[:3]

def detect_country(title):
    lower = title.lower()
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

    for source_name, url in RSS_SOURCES.items():
        try:
            response = requests.get(url, timeout=15)
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
                    "country": detect_country(title),
                    "category": detect_category(title),
                    "keywords": extract_keywords(title),
                    "source": source_name
                })

        except:
            continue

    return news

def progressive_balance(news):

    final = []
    macro_counter = Counter()
    country_counter = Counter()
    category_counter = Counter()
    source_counter = Counter()

    def dominant_keyword(item):
        return item["keywords"][0] if item["keywords"] else None

    def base_constraints(item):
        # NUNCA se relajan
        if source_counter[item["source"]] >= 3:
            return False
        dk = dominant_keyword(item)
        if dk and macro_counter[dk] >= 2:
            return False
        return True

    # FASE 1 (estricta)
    for item in news:
        if not base_constraints(item):
            continue
        if item["country"] != "colombia" and country_counter[item["country"]] >= 1:
            continue
        if category_counter[item["category"]] >= 2:
            continue

        final.append(item)
        dk = dominant_keyword(item)
        if dk:
            macro_counter[dk] += 1
        country_counter[item["country"]] += 1
        category_counter[item["category"]] += 1
        source_counter[item["source"]] += 1

        if len(final) >= TARGET_NEWS:
            return final

    # FASE 2 (relajar país)
    for item in news:
        if item in final:
            continue
        if not base_constraints(item):
            continue
        if category_counter[item["category"]] >= 2:
            continue

        final.append(item)
        dk = dominant_keyword(item)
        if dk:
            macro_counter[dk] += 1
        country_counter[item["country"]] += 1
        category_counter[item["category"]] += 1
        source_counter[item["source"]] += 1

        if len(final) >= TARGET_NEWS:
            return final

    # FASE 3 (relajar categoría)
    for item in news:
        if item in final:
            continue
        if not base_constraints(item):
            continue

        final.append(item)
        dk = dominant_keyword(item)
        if dk:
            macro_counter[dk] += 1
        source_counter[item["source"]] += 1

        if len(final) >= TARGET_NEWS:
            return final

    return final

def main():
    news = extract_news()
    balanced = progressive_balance(news)

    links = [item["link"] for item in balanced]

    with open("links.txt","w",encoding="utf-8") as f:
        f.write(";".join(links))

    print(f"✅ Links guardados: {len(links)}")
    print("===== FIN UPDATE_LINKS.PY =====")

if __name__ == "__main__":
    main()
