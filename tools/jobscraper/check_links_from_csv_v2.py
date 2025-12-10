#!/usr/bin/env python3
import asyncio, csv, random, sys, os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Set
from urllib.parse import urlparse

import httpx

# ---------------- Config ----------------
HTTP_CONCURRENCY = 12
DOMAIN_CONCURRENCY = 2
TIMEOUT_S = 15.0
RETRIES = 1
FALLBACK_CODES = {401, 403, 405, 409, 429, 500, 502, 503, 504}

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# ------------- Data & I/O ---------------
@dataclass
class Row:
    name: str
    link: str
    working: str       # "yes" / "no"
    status_code: str   # e.g. "200"
    response: str      # reason or short error
    mode: str          # "httpx" or "browser"

def load_pairs(csv_path: Path) -> List[Tuple[str, str]]:
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = {c.lower(): c for c in (reader.fieldnames or [])}
        name_col = cols.get("name") or cols.get("company") or cols.get("title")
        link_col = cols.get("link") or cols.get("url")
        if not name_col or not link_col:
            raise SystemExit("Input CSV must have headers like 'name,link' (or 'company,url').")
        pairs = []
        for r in reader:
            n = (r.get(name_col) or "").strip()
            u = (r.get(link_col) or "").strip()
            if n and u:
                pairs.append((n, u))
        return pairs

def write_csv(rows: List[Row], out_path: Path):
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name","link","working","status_code","response","mode"])
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))

# --------------- Helpers ----------------
def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return "?"

def origin_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"

def random_headers(origin: str) -> Dict[str, str]:
    return {
        "User-Agent": random.choice(UA_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.google.com/",
        "Origin": origin,
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }

# --------------- HTTP pass --------------
async def http_fetch(client: httpx.AsyncClient, url: str) -> Tuple[Optional[int], str]:
    try:
        # Warm up origin (some CDNs set cookies on origin)
        try:
            await client.get(origin_of(url), timeout=TIMEOUT_S)
        except Exception:
            pass
        r = await client.get(url, timeout=TIMEOUT_S)
        return r.status_code, (r.reason_phrase or "")
    except httpx.HTTPError as e:
        return None, f"{type(e).__name__}: {e}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

async def http_task(sems: Dict[str, asyncio.Semaphore], url: str) -> Tuple[Optional[int], str]:
    dom = domain_of(url)
    async with sems[dom]:
        await asyncio.sleep(random.uniform(0.1, 0.5))
        async with httpx.AsyncClient(
            headers=random_headers(origin_of(url)),
            follow_redirects=True,
            http2=True,
            timeout=httpx.Timeout(TIMEOUT_S),
        ) as client:
            status, reason = await http_fetch(client, url)
            if status in {429, 500, 502, 503, 504}:
                await asyncio.sleep(1.0)
                status, reason = await http_fetch(client, url)
            return status, reason

# --------- Playwright fallback ----------
class BrowserPool:
    def __init__(self, headless: bool = True):
        self._play = None
        self._browser = None
        self._headless = headless

    async def start(self):
        from playwright.async_api import async_playwright  # lazy import
        self._play = await async_playwright().start()
        self._browser = await self._play.chromium.launch(
            headless=self._headless, args=["--no-sandbox"]
        )

    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._play:
            await self._play.stop()

    async def check(self, url: str, save_debug_dir: Optional[Path]=None) -> Tuple[Optional[int], str, bool]:
        """
        Returns: (status_code, status_text, rendered_ok)
        rendered_ok = True if either status 2xx/3xx OR page renders with a non-empty title
                      and HTML length is reasonable (> 1500)
        """
        ctx = await self._browser.new_context(
            locale="en-US",
            user_agent=random.choice(UA_POOL),
            timezone_id="America/Los_Angeles",
            viewport={"width": 1366, "height": 860},
        )
        page = await ctx.new_page()
        status = None
        status_text = ""
        rendered_ok = False
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_S * 1000)
            if resp:
                status = resp.status
                status_text = resp.status_text or ""
            # give JS a brief moment for interstitials/cookie banners
            await page.wait_for_timeout(1200)
            title = (await page.title()) or ""
            html = await page.content()
            if (status is not None and 200 <= status < 400) or (title.strip() and len(html) > 1500):
                rendered_ok = True
            # Optional second try if 403/429: a soft reload sometimes passes a CDN check
            if not rendered_ok and status in {403, 429, 503}:
                await page.reload(wait_until="domcontentloaded")
                await page.wait_for_timeout(800)
                resp2 = page.response
                if resp2:
                    status = resp2.status
                    status_text = resp2.status_text or status_text
                title2 = (await page.title()) or ""
                html2 = await page.content()
                if (status is not None and 200 <= status < 400) or (title2.strip() and len(html2) > 1500):
                    rendered_ok = True
            # Save debug artifacts if still failing
            if save_debug_dir and not rendered_ok:
                save_debug_dir.mkdir(parents=True, exist_ok=True)
                safe = urlparse(url).netloc.replace(":", "_")
                await page.screenshot(path=str(save_debug_dir / f"{safe}.png"), full_page=True)
                with open(save_debug_dir / f"{safe}.html", "w", encoding="utf-8") as f:
                    f.write(html)
        except Exception as e:
            status_text = f"{type(e).__name__}: {e}"
        finally:
            await ctx.close()
        return status, status_text, rendered_ok

# --------------- Orchestrator -----------
async def run(
    input_csv: Path,
    out_csv: Path,
    engine: str = "auto",
    browser_domains: Optional[Set[str]] = None,
    save_debug: Optional[Path] = None,
    headless: bool = True,
):
    pairs = load_pairs(input_csv)
    print(f"Found {len(pairs)} links in {input_csv}.")

    # Per-domain semaphores
    sems: Dict[str, asyncio.Semaphore] = {}
    for _, link in pairs:
        sems.setdefault(domain_of(link), asyncio.Semaphore(DOMAIN_CONCURRENCY))

    rows: List[Row] = [Row(n, u, "no", "", "", "httpx") for n, u in pairs]

    # 1) HTTP pass
    async def do_http(i: int, n: str, u: str):
        status, reason = await http_task(sems, u)
        rows[i].status_code = str(status or "")
        rows[i].response = reason or ""
        rows[i].working = "yes" if (status is not None and 200 <= status < 400) else "no"

    tasks = []
    sem_all = asyncio.Semaphore(HTTP_CONCURRENCY)
    for i, (n, u) in enumerate(pairs):
        async def guard(i=i, n=n, u=u):
            async with sem_all:
                await do_http(i, n, u)
        tasks.append(asyncio.create_task(guard()))
    await asyncio.gather(*tasks)

    if engine == "httpx":
        write_csv(rows, out_csv)
        print(f"Wrote {len(rows)} rows to {out_csv} (HTTP mode).")
        return

    # Which need browser? (blocked/false-negative or user-forced domains)
    need_browser_idx: List[int] = []
    bdomains = {d.lower().strip() for d in (browser_domains or set()) if d.strip()}
    for i, r in enumerate(rows):
        dom = domain_of(r.link)
        force = (dom in bdomains or any(dom.endswith("."+d) for d in bdomains))
        if engine == "playwright" or force or (not r.status_code or int(r.status_code) in FALLBACK_CODES):
            need_browser_idx.append(i)

    if not need_browser_idx:
        write_csv(rows, out_csv)
        print(f"Wrote {len(rows)} rows to {out_csv} (no browser fallback needed).")
        return

    print(f"{len(need_browser_idx)} links need browser checks…")
    bf = BrowserPool(headless=headless)
    try:
        await bf.start()
    except Exception as e:
        print(f"Playwright init failed ({e}); writing HTTP-only results.", file=sys.stderr)
        write_csv(rows, out_csv)
        return

    for i in need_browser_idx:
        r = rows[i]
        status, status_text, ok = await bf.check(r.link, save_debug_dir=save_debug)
        if status is not None:
            rows[i].status_code = str(status)
        if status_text:
            rows[i].response = status_text
        if ok:
            rows[i].working = "yes"
        rows[i].mode = "browser"

    await bf.stop()
    write_csv(rows, out_csv)
    print(f"Wrote {len(rows)} rows to {out_csv} (HTTP + browser fallback).")

# ------------------- CLI ----------------
def main():
    import argparse
    ap = argparse.ArgumentParser(description="Check career links from CSV with browser fallback for 403/429.")
    ap.add_argument("--input", required=True, help="Input CSV with headers: name,link (or company,url).")
    ap.add_argument("--out", default="link_status.csv", help="Output CSV.")
    ap.add_argument("--engine", choices=["auto","httpx","playwright"], default="auto",
                    help="httpx=fast only; playwright=browser only; auto=httpx then browser fallback.")
    ap.add_argument("--browser-domains", default="",
                    help="Comma-separated domains to always verify in browser (e.g., 'tesla.com,careers.microsoft.com').")
    ap.add_argument("--save-debug", default="",
                    help="Directory to save HTML/screenshots for failures.")
    ap.add_argument("--no-headless", action="store_true", help="Run browser visibly (debug).")
    args = ap.parse_args()

    bdomains = set([d.strip() for d in args.browser_domains.split(",") if d.strip()])
    save_dir = Path(args.save_debug) if args.save_debug else None

    try:
        asyncio.run(run(
            input_csv=Path(args.input),
            out_csv=Path(args.out),
            engine=args.engine,
            browser_domains=bdomains,
            save_debug=save_dir,
            headless=not args.no_headless,
        ))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)

if __name__ == "__main__":
    main()
