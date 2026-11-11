"""
Google Skills Public Profile Scraper
Features resilient HTML extraction, rate limiting, retry backoff, and robust error detection.
"""
import re
import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
import httpx
from bs4 import BeautifulSoup
from core.campaign import evaluate_candidate

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
]

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENTS[0],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}


def clean_profile_url(raw_url: str) -> str:
    """Sanitizes and validates a Google Skills public profile URL."""
    url = raw_url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return url


def parse_profile_html(html: str, final_url: str, original_url: str) -> Dict[str, Any]:
    """Parses raw HTML from Google Skills public profile into structured candidate data."""
    soup = BeautifulSoup(html, "html.parser")

    # Detect private profile:
    # 1. Final URL redirected to root https://www.skills.google/ or does not contain public_profiles
    # 2. Page title is bare 'Google Skills' without candidate name
    is_root_redirect = "public_profiles" not in final_url and ("skills.google" in final_url or final_url == "https://www.skills.google/")
    
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    
    is_private_title = title_text.strip().lower() in ["google skills", "learn and earn with google skills"]
    if is_root_redirect or is_private_title:
        return {
            "url": original_url,
            "final_url": final_url,
            "name": "Private Account",
            "avatar": None,
            "league": None,
            "badges": [],
            "total_badges": 0,
            "is_private": True,
            "is_error": False,
            "error_message": "Profile is set to private or inaccessible."
        }

    # Extract Candidate Name
    name = "Unknown Candidate"
    if "|" in title_text:
        name = title_text.split("|")[0].strip()
    else:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            name = h1.get_text(strip=True)

    # Extract Avatar if present
    avatar_src = None
    avatar_tag = soup.find("ql-avatar")
    if avatar_tag and avatar_tag.get("src"):
        avatar_src = avatar_tag.get("src")
    else:
        img_avatar = soup.find("img", class_=re.compile(r"avatar", re.I))
        if img_avatar and img_avatar.get("src"):
            avatar_src = img_avatar.get("src")

    # Extract League / Level (e.g. Silver League, Bronze League)
    league = None
    for h in soup.find_all(["h2", "h3", "span"]):
        txt = h.get_text(strip=True)
        if "league" in txt.lower():
            league = txt
            break

    # Extract Badges
    badges = []
    # Search for badge containers
    badge_cards = soup.find_all("div", class_=lambda c: c and "profile-badge" in c)
    
    if badge_cards:
        for card in badge_cards:
            title_elem = card.find("span", class_=lambda c: c and "ql-title-medium" in c)
            date_elem = card.find("span", class_=lambda c: c and "ql-body-medium" in c)
            img_elem = card.find("img")
            link_elem = card.find("a", href=True)

            title = title_elem.get_text(strip=True) if title_elem else ""
            date_raw = date_elem.get_text(strip=True) if date_elem else ""
            date_clean = re.sub(r"^Earned\s+", "", date_raw, flags=re.I).strip()
            img_url = img_elem.get("src") if img_elem else ""
            badge_link = link_elem.get("href") if link_elem else ""
            if badge_link.startswith("/"):
                badge_link = "https://www.skills.google" + badge_link

            if title:
                badges.append({
                    "title": title,
                    "date": date_clean,
                    "image": img_url,
                    "url": badge_link
                })
    else:
        # Fallback regex extraction if HTML classes shift
        title_matches = re.findall(r'<span class=[\'"]ql-title-medium[^\'"]*[\'"]>\s*([^<]+)\s*</span>', html)
        date_matches = re.findall(r'<span class=[\'"]ql-body-medium[^\'"]*[\'"]>\s*(?:Earned\s+)?([^<]+)\s*</span>', html)
        img_matches = re.findall(r'<img[^>]*src=[\'"](https://cdn\.qwiklabs\.com/[^\'"]+)[\'"]', html)
        
        for i in range(len(title_matches)):
            badges.append({
                "title": title_matches[i].strip(),
                "date": date_matches[i].strip() if i < len(date_matches) else "",
                "image": img_matches[i] if i < len(img_matches) else "",
                "url": original_url
            })

    return {
        "url": original_url,
        "final_url": final_url,
        "name": name,
        "avatar": avatar_src,
        "league": league,
        "badges": badges,
        "total_badges": len(badges),
        "is_private": False,
        "is_error": False,
        "error_message": None
    }


async def scrape_single_profile(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 3,
    backoff_factor: float = 1.5
) -> Dict[str, Any]:
    """Scrapes a single profile URL asynchronously with retries and backoff."""
    clean_url = clean_profile_url(url)
    
    # Validate UUID pattern in URL
    if not re.search(r'public_profiles/[a-f0-9\-]+', clean_url, re.I):
        raw_result = {
            "url": clean_url,
            "final_url": clean_url,
            "name": "Invalid URL",
            "avatar": None,
            "league": None,
            "badges": [],
            "total_badges": 0,
            "is_private": False,
            "is_error": True,
            "error_message": "Malformed profile URL (missing UUID pattern)."
        }
        return evaluate_candidate(raw_result)

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            resp = await client.get(clean_url, headers=DEFAULT_HEADERS, timeout=15.0, follow_redirects=True)
            
            if resp.status_code == 404:
                raw_result = {
                    "url": clean_url,
                    "final_url": str(resp.url),
                    "name": "Not Found",
                    "avatar": None,
                    "league": None,
                    "badges": [],
                    "total_badges": 0,
                    "is_private": False,
                    "is_error": True,
                    "error_message": "Profile not found (HTTP 404)."
                }
                return evaluate_candidate(raw_result)

            if resp.status_code == 429:
                # Rate limit hit, back off
                await asyncio.sleep(backoff_factor * (2 ** (attempt - 1)))
                continue

            resp.raise_for_status()
            raw_data = parse_profile_html(resp.text, str(resp.url), clean_url)
            return evaluate_candidate(raw_data)

        except httpx.HTTPStatusError as e:
            if attempt == max_retries:
                raw_result = {
                    "url": clean_url,
                    "final_url": clean_url,
                    "name": "HTTP Error",
                    "avatar": None,
                    "league": None,
                    "badges": [],
                    "total_badges": 0,
                    "is_private": False,
                    "is_error": True,
                    "error_message": f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
                }
                return evaluate_candidate(raw_result)
            await asyncio.sleep(backoff_factor * attempt)

        except (httpx.ConnectTimeout, httpx.ReadTimeout):
            if attempt == max_retries:
                raw_result = {
                    "url": clean_url,
                    "final_url": clean_url,
                    "name": "Timeout",
                    "avatar": None,
                    "league": None,
                    "badges": [],
                    "total_badges": 0,
                    "is_private": False,
                    "is_error": True,
                    "error_message": "Connection timed out."
                }
                return evaluate_candidate(raw_result)
            await asyncio.sleep(backoff_factor * attempt)

        except Exception as e:
            if attempt == max_retries:
                raw_result = {
                    "url": clean_url,
                    "final_url": clean_url,
                    "name": "Error",
                    "avatar": None,
                    "league": None,
                    "badges": [],
                    "total_badges": 0,
                    "is_private": False,
                    "is_error": True,
                    "error_message": str(e)
                }
                return evaluate_candidate(raw_result)
            await asyncio.sleep(backoff_factor * attempt)

    raw_result = {
        "url": clean_url,
        "final_url": clean_url,
        "name": "Max Retries Reached",
        "avatar": None,
        "league": None,
        "badges": [],
        "total_badges": 0,
        "is_private": False,
        "is_error": True,
        "error_message": "Failed after max retries."
    }
    return evaluate_candidate(raw_result)


async def scrape_batch(
    records: List[Dict[str, Any]],
    progress_callback: Optional[Callable[[Dict[str, Any], int, int], None]] = None,
    delay_between_requests: float = 0.8,
    concurrency_limit: int = 2
) -> List[Dict[str, Any]]:
    """
    Scrapes a batch of student records with controlled concurrency and polite rate-limiting.
    records: list of dicts with at least 'url' key, optionally 'info' or 'name'.
    """
    semaphore = asyncio.Semaphore(concurrency_limit)
    results = []
    total = len(records)
    completed_counter = 0

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for idx, item in enumerate(records):
            async with semaphore:
                res = await scrape_single_profile(client, item["url"])
                # Attach extra original metadata if provided (e.g. INFO from CSV)
                if "info" in item:
                    res["original_info"] = item["info"]
                if "custom_id" in item:
                    res["custom_id"] = item["custom_id"]
                
                results.append(res)
                completed_counter += 1
                
                if progress_callback:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(res, completed_counter, total)
                    else:
                        progress_callback(res, completed_counter, total)

                # Respectful rate-limiting sleep between requests
                if idx < total - 1 and delay_between_requests > 0:
                    await asyncio.sleep(delay_between_requests)

    return results
