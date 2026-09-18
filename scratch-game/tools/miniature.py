#!/usr/bin/env python3
"""Miniatures du jeu (montages) : capture de combat + logo vectoriel + accroches.

  python3 miniature.py            -> miniature-logo.png   (480x360 : taille de la scène Scratch)
  python3 miniature.py 1280       -> preview-mini.png     (1280x720 : vignette large pour GitHub)

Les captures de départ (out/m_*.svg) viennent de play.js : ce sont de vrais rendus de la VM.
"""
import base64
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import assets  # noqa: E402

RACINE = os.path.join(os.path.dirname(__file__), "..")
LARGE = len(sys.argv) > 1 and sys.argv[1] == "1280"
W, H = (1280, 720) if LARGE else (480, 360)
SORTIE = os.path.join(RACINE, "preview-mini.png" if LARGE else "miniature-logo.png")
FOND = "out/m_fleche.svg"           # combat (arc + bouclier) : les deux combattants sont nets


def donnees(chemin):
    return base64.b64encode(open(chemin, "rb").read()).decode()


fond = donnees(FOND)
logo = base64.b64encode(assets.logo_svg().encode("utf-8")).decode()


def texte(txt, taille, cx, y, couleur, max_w=None):
    """Texte centré ; la taille est réduite si nécessaire pour rester dans max_w."""
    if max_w:
        w = assets._texte_largeur(txt, taille, 0.0)
        if w > max_w:
            taille *= max_w / w
    d, _ = assets._texte_centre(txt, taille, cx, y, 0.0)
    return f'<path d="{d}" fill="{couleur}"/>'


k = W / 480.0                                  # facteur d'échelle par rapport à la scène Scratch
logo_w = 0.44 * W
logo_h = logo_w * assets.LOGO_H / assets.LOGO_W
bandeau = 34 * k

accroche = texte("6 ARMES - 8 BOTS - TALENTS - BOUCLIER", 26 * k, W / 2, H - bandeau - 10 * k, "#ffffff", max_w=W - 20 * k)
bas = texte("CLIQUE SUR LE DRAPEAU VERT POUR JOUER", 18 * k, W / 2, H - 10 * k, "#c9b6ff", max_w=W - 20 * k)

svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
    f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
    '<defs>'
    '<linearGradient id="haut" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#08040f" stop-opacity="0.92"/>'
    '<stop offset="0.45" stop-color="#08040f" stop-opacity="0.05"/>'
    '<stop offset="0.72" stop-color="#08040f" stop-opacity="0.35"/>'
    '<stop offset="1" stop-color="#08040f" stop-opacity="0.95"/></linearGradient>'
    '<linearGradient id="teinte" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#2a0a5e" stop-opacity="0.55"/>'
    '<stop offset="1" stop-color="#0b0418" stop-opacity="0.65"/></linearGradient>'
    '</defs>'
    # capture de combat en fond (recadrée pour remplir la miniature)
    f'<image x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="xMidYMid slice" '
    f'xlink:href="data:image/svg+xml;base64,{fond}"/>'
    f'<rect width="{W}" height="{H}" fill="url(#haut)"/>'
    # logo vectoriel en haut
    f'<image x="{W/2-logo_w/2:.0f}" y="{0.06*H:.0f}" width="{logo_w:.0f}" height="{logo_h:.0f}" '
    f'xlink:href="data:image/svg+xml;base64,{logo}"/>'
    f'<rect x="0" y="{H-bandeau:.0f}" width="{W}" height="{bandeau:.0f}" fill="#08040f" opacity="0.72"/>'
    + accroche + bas
    + '</svg>')

svg_path = "out/miniature-logo.svg"
open(svg_path, "w", encoding="utf-8").write(svg)
print("svg ->", svg_path, "|", W, "x", H)
