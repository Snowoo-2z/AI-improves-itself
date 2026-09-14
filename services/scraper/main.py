"""Service de scraping Chromium (web service Render).

L'IA (ou un humain via /colab) envoie une URL → le service la charge dans
Chromium headless (rendu JS complet) → renvoie le texte de la page.

Déploiement : voir services/scraper/README.md (Render, instance 512 Mo).
Sécurité : domaine whitelist optionnel (ENV ALLOWED_DOMAINS), taille limitée.
"""
from __future__ import annotations

import ipaddress
import os
import socket
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


def _forbidden_target(url: str) -> str | None:
    """Garde-fou anti-SSRF : le service est public, il ne doit jamais servir
    de proxy vers le réseau interne (boucle locale, lien local 169.254.x.x —
    ex. la metadata cloud —, privées RFC1918, réservées, noms d'hôtes IPv6
    internes, etc.). Renvoie une raison si la cible est interdite, sinon None.
    """
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return "hôte vide"
    if host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
        return "nom d'hôte interne"
    # Hôte qui est lui-même une adresse IP (pas besoin de resolver) ?
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(ip):
            return "adresse IP interne/réservée"
        return None
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return "domaine inconnu"
    if not infos:
        return "domaine inconnu"
    for info in infos:
        try:
            if _is_blocked_ip(ipaddress.ip_address(info[4][0])):
                return "résout vers une adresse interne/réservée"
        except ValueError:
            return "adresse invalide"
    return None


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
        or ip.is_multicast
    )


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "scraper-chromium", "ts": time.time()}


@app.post("/scrape")
def scrape(req: ScrapeRequest) -> dict:
    from playwright.sync_api import sync_playwright

    if not req.url.lower().startswith(("http://", "https://")):
        return {"ok": False, "error": "url doit commencer par http(s)://"}
    forbidden = _forbidden_target(req.url)
    if forbidden:
        return {"ok": False, "error": f"cible interdite (anti-SSRF) : {forbidden}"}
    if not _allowed(req.url):
        return {"ok": False, "error": "domaine non autorisé (ALLOWED_DOMAINS)"}

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
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
            finally:
                browser.close()  # ne fuit pas le binaire Chromium en cas d'erreur
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
