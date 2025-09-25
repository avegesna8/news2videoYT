import time
import shutil
import os
import random
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl, urljoin, parse_qs
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re

#Define Headers
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.google.com/",
}

#Define User Agents
UA_POOL = [
    HEADERS["User-Agent"],
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

#Build Session
def build_session(timeout=10):
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("HEAD", "GET", "OPTIONS"),
        raise_on_status=False,
    )

    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))

    s.headers.update(HEADERS)

    return s

#Append AMP Version
def add_amp(url: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))

    if query.get("platform") != "amp":
        query["platform"] = "amp"
    
    return urlunparse(parsed._replace(query=urlencode(query)))

#Access ESPN Link
def get_link(url: str, timeout=10, retries=2, backoff=0.75) -> requests.Response:
    err = None
    session = build_session(timeout=timeout)

    for attempt in range(retries + 1):
        session.headers["User-Agent"] = random.choice(UA_POOL)
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code == 403:
                amp_url = add_amp(url)
                response_amp = session.get(amp_url, timeout=timeout)
                if response_amp.ok:
                    return response_amp
                response.raise_for_status()
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            err = e
            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
    raise err

#Return JSON Info
def parse_jsonld(soup):
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.text or "{}")
            items = data if isinstance(data, list) else [data]
            for it in items:
                if it.get("@type") in ("NewsArticle", "Article"):
                    return it
        except Exception:
            pass
    return {}

#Extract Text in Simple Format
def extract_text(el):
    return " ".join(el.stripped_strings) if el else ""

#CSS Selector
def select_first_element(soup, selectors):
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return el
    return None

#Get Absolute Full Url
def get_abs_url(u: str, base: str):
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    return urljoin(base, u)

#Identify Image Sizes
def parse_srcset(srcset: str):
    if not srcset:
        return []
    out = []
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        url = bits[0]
        width = None
        if len(bits) > 1 and bits[1].endswith("w"):
            try:
                width = int(bits[1][:-1])
            except Exception:
                pass
        out.append((url, width))
    return out

#Find Inline Images
def extract_inline_photo_images(html: str, page_url: str):
    soup = BeautifulSoup(html, "html.parser")

    results = []

    #Find Images wrapped inside <aside class="inline inline-photo ..."> blocks
    for aside in soup.select("aside.inline.inline-photo"):
        fig = aside.find("figure")
        if not fig:
            continue

        caption = None
        cap = fig.find("figcaption")

        if cap:
            caption = " ".join(cap.stripped_strings)

        img = fig.find("img")
        alt = img.get("alt") if img else None

        #Scrap <source> tag
        for src in fig.find_all("source"):
            for url, w in parse_srcset(src.get("srcset") or src.get("data-srcset", "")):
                results.append({
                    "src": get_abs_url(url, page_url),
                    "width": w,
                    "alt": alt,
                    "caption": caption,
                })
        
        #Scrape <img> tag
        if img:
            for url, w in parse_srcset(img.get("srcset") or img.get("data-srcset", "")):
                results.append({
                    "src": get_abs_url(url, page_url),
                    "width": w,
                    "alt": alt,
                    "caption": caption,
                })
            if img.get("src"):
                results.append({
                    "src": get_abs_url(img["src"], page_url),
                    "width": None,
                    "alt": alt,
                    "caption": caption,
                })

    #Remove Duplicates
    seen = set()
    deduped = []
    for it in results:
        if it["src"] not in seen:
            seen.add(it["src"])
            deduped.append(it)
    return deduped

# Make a canonical key that ignores ESPNs resizing knobs so variants collapse
def canonical_image_key(url: str) -> str:
    u = urlparse(url)
    q = parse_qs(u.query)

    # If it's an ESPN combiner URL, the real image path is in the 'img' param
    base = q.get("img", [u.path])[0]

    # Strip size suffixes like _1296x729 or _16x9 right before extension
    base = re.sub(r'_(\d{2,4}x\d{2,4})(_[\d:x=]+)?(?=\.)', "", base)

    # Build a key from host + cleaned base path, ignoring resizing query params
    host = u.netloc or "espncdn"
    return f"{host}:{base}"

#Extra Function to infer Width from URL if Width was set to 0
SIZE_TOKEN = re.compile(r'(?P<w>\d{2,4})x(?P<h>\d{2,4})')
def infer_width_from_url(url: str) -> int:
    try:
        q = parse_qs(urlparse(url).query)
        if "w" in q and q["w"]:
            return int(re.findall(r"\d+", q["w"][0])[0])
        m = SIZE_TOKEN.search(url)
        if m:
            return int(m.group("w"))
    except Exception:
        pass
    return 0

#Keep Largest Variant of Each Image
def dedupe_keep_largest(images: list[dict]) -> list[dict]:
    buckets = {}
    for it in images:
        w = it.get("width") or infer_width_from_url(it["src"]) or 0
        key = canonical_image_key(it["src"])
        prev = buckets.get(key)
        if (prev is None) or ((w or 0) > (prev.get("width") or 0)):
            it["width"] = w
            buckets[key] = it
    return list(buckets.values())

#Extra Image Extractor to Be Used if No Inline Images Found
def extract_captioned_images(html: str, page_url: str):
    soup = BeautifulSoup(html, "html.parser")

    results = []

    for fig in soup.find_all("figure"):
        cap_el = fig.find("figcaption")
        caption = " ".join(cap_el.stripped_strings) if cap_el else None
        if not caption:
            continue
        img = fig.find("img")
        alt = img.get("alt") if img else None

        #Scrap <source> tag
        for src in fig.find_all("source"):
            for url, w in parse_srcset(src.get("srcset") or src.get("data-srcset", "")):
                results.append({
                    "src": get_abs_url(url, page_url),
                    "width": w,
                    "alt": alt,
                    "caption": caption,
                })
        
        #Scrape <img> tag
        if img:
            for url, w in parse_srcset(img.get("srcset") or img.get("data-srcset", "")):
                results.append({
                    "src": get_abs_url(url, page_url),
                    "width": w,
                    "alt": alt,
                    "caption": caption,
                })
            if img.get("src"):
                results.append({
                    "src": get_abs_url(img["src"], page_url),
                    "width": None,
                    "alt": alt,
                    "caption": caption,
                })

    #Remove Duplicates
    seen = set()
    deduped = []
    for it in results:
        if it["src"] not in seen:
            seen.add(it["src"])
            deduped.append(it)
    return deduped

# FallBack Image Extractor Function
def get_article_images_with_fallback(html: str, page_url: str):
    imgs = extract_inline_photo_images(html, page_url)
    #Include Below Line if Always Want to Include Additional Image
    #imgs = extract_captioned_images(html, page_url) + imgs
    if imgs:
        return imgs, "inline + captioned"
    imgs = extract_captioned_images(html, page_url)
    if imgs:
        return imgs, "captioned"
    return [], "none"


#Parse ESPN Article
def parse_espn_article_html(html: str,page_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    ld = parse_jsonld(soup)
    
    headline = ld.get("headline")
    date_published = ld.get("datePublished")
    author = None
    if isinstance(ld.get("author"), dict):
        author = ld["author"].get("name")
    elif isinstance(ld.get("author"), list) and ld["author"]:
        author = ld["author"][0].get("name")
    
    if not headline:
        og = soup.find("meta", property="og:title")
        headline = og["content"] if og and og.get("content") else None
    
    if not date_published:
        ap = soup.find("meta", property="article:published_time")
        date_published = ap["content"] if ap and ap.get("content") else None

    body_container = select_first_element(soup, [
        '[data-testid="ArticleBody"]',
        'section[name="articleBody"]',
        'article .article-body',
        'main article',
        'div.article-body',
    ])

    paragraphs = []
    if body_container:
        for p in body_container.find_all(["p", "li"]):
            text = extract_text(p)
            if text and not text.lower().startswith(("editor’s note", "editor's note")):
                paragraphs.append(text)

    imgs_raw, strategy = get_article_images_with_fallback(html, page_url)
    images = dedupe_keep_largest(imgs_raw)
     
    iso_date = None
    if date_published:
        try:
            iso_date = datetime.fromisoformat(date_published.replace("Z", "+00:00")).isoformat()
        except Exception:
            iso_date = date_published

    return {
        "title": headline,
        "author": author,
        "published": iso_date,
        "paragraphs": paragraphs,
        "images": images,
    }

#Save Images to Local Folder
def save_images(images, folder="app/images"):
    if os.path.exists(folder):
        shutil.rmtree(folder)

    os.makedirs(folder, exist_ok=True)
    s = build_session()

    for i, img in enumerate(images, 1):
        url = img["src"]
        ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
        filename = os.path.join(folder, f"image_{i}{ext}")
        try:
            r = s.get(url, stream=True, timeout=12)
            r.raise_for_status()
            with open(filename, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            print(f"Saved {filename}")
        except Exception as e:
            print(f"Failed to save {url}: {e}")

#CLI Test
if __name__ == "__main__":
    url = "https://www.espn.com/nfl/story/_/id/46366297/drew-brees-larry-fitzgerald-headline-2026-hall-fame-nominees"
    response = get_link(url)
    data = parse_espn_article_html(response.text, response.url) 
    print("Fetched:", response.status_code, "from", response.url)

    preview = {
        "title": data["title"],
        "author": data["author"],
        "published": data["published"],
        "para_count": len(data["paragraphs"]),
        "first_para": (data["paragraphs"][0] if data["paragraphs"] else None),
        "image_count": len(data["images"]),
    }

    print(json.dumps(preview, indent=2)[:1200])

    save_images(data["images"], folder="images")