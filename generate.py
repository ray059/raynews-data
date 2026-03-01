import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from readability import Document
from openai import OpenAI

print("===== INICIO GENERATE.PY =====")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

TARGET_NEWS = 12

def clean_text(text):
    return " ".join(text.split())

def extract_article(url):
    try:
        response = requests.get(url, timeout=20)
        doc = Document(response.text)
        html = doc.summary()
        soup = BeautifulSoup(html, "html.parser")

        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text() for p in paragraphs])

        return clean_text(text)
    except:
        return None

def get_title(url):
    try:
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.find("title")
        if title:
            return clean_text(title.text)
        return ""
    except:
        return ""

def generate_answer(title, content):

    prompt = f"""
Responde directamente la pregunta del titular con claridad y precisión.
No resumas la noticia.
No expliques el contexto.
Responde como si aclararas la duda del lector.

Titular:
{title}

Contenido:
{content[:4000]}

Respuesta máxima 280 caracteres.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un periodista que responde preguntas con claridad absoluta."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )

        answer = response.choices[0].message.content.strip()
        return answer[:280]

    except Exception as e:
        print("❌ Error OpenAI:", e)
        return None

def load_links():
    if not os.path.exists("links.txt"):
        return []

    with open("links.txt", "r", encoding="utf-8") as f:
        content = f.read().strip()

    if not content:
        return []

    return content.split(";")

def main():

    links = load_links()
    headlines = []

    for url in links:

        if len(headlines) >= TARGET_NEWS:
            break

        print("🔎 Procesando:", url)

        title = get_title(url)
        content = extract_article(url)

        if not title or not content:
            continue

        answer = generate_answer(title, content)

        if not answer:
            continue

        headlines.append({
            "titleOriginal": title,
            "summary280": answer,
            "sourceUrl": url,
            "type": "question"
        })

    edition = {
        "edition_date": datetime.now().strftime("%d %b %Y"),
        "generated_at": datetime.now().isoformat(),
        "country": "Internacional",
        "headlines": headlines
    }

    with open("edition.json", "w", encoding="utf-8") as f:
        json.dump(edition, f, ensure_ascii=False, indent=2)

    print(f"✅ Noticias generadas: {len(headlines)}")
    print("===== FIN GENERATE.PY =====")

if __name__ == "__main__":
    main()
