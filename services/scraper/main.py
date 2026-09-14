"""Service de scraping Chromium (web service Render).

L'IA (ou un humain via /colab) envoie une URL → le service la charge dans
Chromium headless (rendu JS complet) → renvoie le texte de la page.

Déploiement : voir services/scraper/README.md (Render, instance 512 Mo).
Sécurité : domaine whitelist optionnel (ENV ALLOWED_DOMAINS), taille limitée.
"""
from __future__ import annotations

import os
import time
from urllib.parse import urlparse

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="AI-improves-itself — scraper Chromium", version="0.1.0")


class ScrapeRequest(BaseModel):
    url: str
    wait_ms: int = Field(default=2000, ge=0, le=15000)
    max_chars: int = Field(default=12000, ge=200, le=60000)


def _allowed(url: str) -> bool:
    allowed = os.environ.get("ALLOWED_DOMAINS", "").lower()
    if not allowed:
        return True
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in (x.strip() for x in allowed.split(",") if x.strip()))


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "scraper-chromium", "ts": time.time()}


@app.post("/scrape")
def scrape(req: ScrapeRequest) -> dict:
    from playwright.sync_api import sync_playwright

    if not req.url.lower().startswith(("http://", "https://")):
        return {"ok": False, "error": "url doit commencer par http(s)://"}
    if not _allowed(req.url):
        return {"ok": False, "error": "domaine non autorisé (ALLOWED_DOMAINS)"}

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 900},
            )
            page = context.new_page()
            page.goto(req.url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(req.wait_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:  # noqa: BLE001 — pas bloquant
                pass
            title = page.title()
            text = page.evaluate("() => document.body ? document.body.innerText : ''")
            browser.close()
        return {
            "ok": True,
            "url": req.url,
            "title": title,
            "text": text[: req.max_chars],
            "chars_total": len(text),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"scraping impossible : {exc}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
