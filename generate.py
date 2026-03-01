import os
import json
import requests
from bs4 import BeautifulSoup
from readability import Document
from openai import OpenAI
from datetime import datetime
import pytz

print("===== INICIO GENERATE.PY =====")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
TARGET_NEWS = 12

def safe_trim(text, limit=280):
    if len(text)<=limit:
        return text
    trimmed=text[:limit]
    if "." in trimmed:
        trimmed=trimmed.rsplit(".",1)[0]+"."
    return trimmed

def extract_article(url):
    try:
        r=requests.get(url,timeout=20)
        doc=Document(r.text)
        soup=BeautifulSoup(doc.summary(),"html.parser")
        return " ".join(p.get_text() for p in soup.find_all("p"))
    except:
        return None

def extract_title_image(url):
    try:
        r=requests.get(url,timeout=15)
        soup=BeautifulSoup(r.text,"html.parser")
        og_title=soup.find("meta",property="og:title")
        og_image=soup.find("meta",property="og:image")
        title=og_title["content"] if og_title else soup.title.string
        image=og_image["content"] if og_image else None
        return title.strip(),image
    except:
        return None,None

def is_duplicate(summary,existing):
    base=summary[:120].lower()
    for item in existing:
        if base==item["summary280"][:120].lower():
            return True
    return False

def generate_answer(title,content):

    prompt=f"""
Responde directamente la pregunta del titular.
La respuesta debe terminar en una oración completa.
No repitas el titular.
Máximo 280 caracteres.

Titular:
{title}

Contenido:
{content[:4000]}
"""

    try:
        response=client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":"Eres editor periodístico. Responde con precisión."},
                {"role":"user","content":prompt}
            ],
            temperature=0.2
        )
        answer=response.choices[0].message.content.strip()
        return safe_trim(answer,280)
    except:
        return None

def load_links():
    if not os.path.exists("links.txt"):
        return []
    with open("links.txt","r",encoding="utf-8") as f:
        content=f.read().strip()
    return content.split(";") if content else []

def main():
    links=load_links()
    headlines=[]

    for url in links:
        if len(headlines)>=TARGET_NEWS:
            break

        title,image=extract_title_image(url)
        content=extract_article(url)

        if not title or not content:
            continue

        answer=generate_answer(title,content)
        if not answer:
            continue

        if is_duplicate(answer,headlines):
            continue

        headlines.append({
            "titleOriginal": title,
            "summary280": answer,
            "sourceUrl": url,
            "imageUrl": image,
            "type":"question"
        })

    tz=pytz.timezone("America/Bogota")
    now=datetime.now(tz)

    edition={
        "edition_date":now.strftime("%d %b %Y"),
        "generated_at":now.isoformat(),
        "country":"Internacional",
        "headlines":headlines
    }

    with open("edition.json","w",encoding="utf-8") as f:
        json.dump(edition,f,ensure_ascii=False,indent=2)

    print(f"✅ Noticias generadas: {len(headlines)}")
    print("===== FIN GENERATE.PY =====")

if __name__=="__main__":
    main()
