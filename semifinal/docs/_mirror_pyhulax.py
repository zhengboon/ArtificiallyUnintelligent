"""Recursively mirror https://pyhulax.xenops.ae/ to ./pyhulax/.
Run from D:\\hackerverse\\semifinal\\docs\\. Handles HTML pages, CSS, JS, images.
Stays within the pyhulax.xenops.ae host. Idempotent."""

import os
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

BASE = "https://pyhulax.xenops.ae"
HOST = urlparse(BASE).netloc
OUT  = os.path.join(os.path.dirname(__file__), "pyhulax")

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) docs mirror"}
TIMEOUT = 30
SLEEP   = 0.1

os.makedirs(OUT, exist_ok=True)

def url_to_path(url: str) -> str:
    """Map a URL to a local filesystem path inside OUT."""
    u = urlparse(url)
    path = u.path
    if path.endswith("/") or path == "":
        path = path + "index.html"
    elif "." not in os.path.basename(path):
        # path like /sdk/configuration → save as /sdk/configuration/index.html
        path = path.rstrip("/") + "/index.html"
    return os.path.join(OUT, path.lstrip("/"))

def is_internal(url: str) -> bool:
    u = urlparse(url)
    if u.scheme and u.scheme not in ("http", "https"):
        return False
    if u.netloc and u.netloc != HOST:
        return False
    return True

def save(url: str, content: bytes) -> str:
    p = url_to_path(url)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(content)
    return p

def extract_links(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    found = set()
    for tag, attr in [("a", "href"), ("link", "href"),
                      ("script", "src"), ("img", "src"),
                      ("source", "src")]:
        for el in soup.find_all(tag):
            v = el.get(attr)
            if not v:
                continue
            u = urljoin(base_url, v)
            u = urldefrag(u)[0]
            if is_internal(u):
                found.add(u)
    return found

def main():
    queue = deque([BASE + "/"])
    seen = set()
    fetched = 0
    failed = []
    while queue:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code != 200:
                failed.append((url, r.status_code))
                continue
            p = save(url, r.content)
            fetched += 1
            ctype = r.headers.get("content-type", "")
            if "html" in ctype:
                for link in extract_links(r.text, url):
                    if link not in seen:
                        queue.append(link)
            if fetched % 10 == 0:
                print(f"[{fetched}] {url} -> {os.path.relpath(p, OUT)}")
            time.sleep(SLEEP)
        except Exception as e:
            failed.append((url, str(e)))
    print(f"\nDone. {fetched} fetched, {len(failed)} failed, {len(seen)} URLs seen.")
    if failed:
        print("\nFailures:")
        for u, e in failed[:20]:
            print(f"  {e}  {u}")

if __name__ == "__main__":
    main()
