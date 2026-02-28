import asyncio
from playwright.async_api import async_playwright

TEST_URL = "https://news.google.com/rss/articles/CBMikwJBVV95cUxQeXRlZUFQSU1xVmVGOWdGalBvQWdoLXhwZTNGbUdnMTJTZ1RmbU9vZGUtR25wZU1BY2ZQb3RWTWZvUk8xSi1ycHVrU3BZV2JNVlpnZS04TnVqaVcyRkxnRlpCV1RHcWhoelRReTItR2liMVQ4M1VIOHFqTG5kaXBkUXdfR05Gbnd2WThjbUltaFMwVXQ5NkhtVnpDQnMwYWc0eUlrUTgtRm0tSDhxQ0dmd2R3UW9YaGpuVk1GT1EyLWNJdjlqdEdJTTdia0YteXV5V1pkVHBiWlQzWlNlamxGdlFVY3RrU2hvZFNXa25vRXJPdGExX0VrRVUzMkdzRU8tRlZTUUk5c2ZacVFfdUttN1huSQ?oc=5"  # pega aquí una real tuya


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        response = await page.goto(TEST_URL, timeout=60000, wait_until="networkidle")

        print("URL después de navegar:")
        print(page.url)

        await browser.close()


asyncio.run(main())
