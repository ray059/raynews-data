import asyncio
from playwright.async_api import async_playwright

GOOGLE_NEWS_URL = "https://news.google.com/home?hl=es-419&gl=CO&ceid=CO:es-419"
MAX_LINKS = 7


async def fetch_links():
    links = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(GOOGLE_NEWS_URL, timeout=60000)
        await page.wait_for_timeout(5000)

        anchors = await page.query_selector_all("article a")

        for a in anchors:
            href = await a.get_attribute("href")

            if not href:
                continue

            if href.startswith("./articles/"):
                full_url = "https://news.google.com" + href[1:]
                page2 = await browser.new_page()
                await page2.goto(full_url, timeout=60000)

                final_url = page2.url

                if "news.google.com" not in final_url:
                    if final_url not in links:
                        links.append(final_url)

                await page2.close()

            if len(links) >= MAX_LINKS:
                break

        await browser.close()

    return links


async def main():
    print("🔎 Obteniendo enlaces reales con Playwright...")

    links = await fetch_links()

    if not links:
        print("❌ No se obtuvieron enlaces")
        return

    content = ";".join(links)

    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ links.txt actualizado correctamente")
    print("Total enlaces guardados:", len(links))


if __name__ == "__main__":
    asyncio.run(main())
