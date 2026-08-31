from urllib.parse import parse_qs, quote, urlparse

import httpx
from bs4 import BeautifulSoup


async def search_web(topic: str, limit: int = 8) -> list[dict]:
    """Best-effort public search. Returned snippets are untrusted reference data."""
    query = quote(f"{topic} 数据 研究 报告 正方 反方")
    headers = {"User-Agent": "Mozilla/5.0 DebateSpark/1.0"}
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers=headers) as client:
            response = await client.get(f"https://html.duckduckgo.com/html/?q={query}")
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        seen = set()
        for item in soup.select(".result"):
            link = item.select_one(".result__a")
            snippet = item.select_one(".result__snippet")
            if not link:
                continue
            href = link.get("href", "")
            if href.startswith("//"):
                href = "https:" + href
            if "duckduckgo.com/l/" in href:
                href = parse_qs(urlparse(href).query).get("uddg", [href])[0]
            if not href.startswith("http") or href in seen:
                continue
            seen.add(href)
            results.append({
                "title": link.get_text(" ", strip=True),
                "url": href,
                "domain": urlparse(href).netloc,
                "snippet": snippet.get_text(" ", strip=True) if snippet else "",
            })
            if len(results) >= limit:
                break
        return results
    except Exception:
        return []
