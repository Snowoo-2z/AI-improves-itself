#!/usr/bin/env python3
"""Compose la miniature du jeu (preview-mini.png) : capture de combat + logo + accroches."""
import base64, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import assets  # noqa: E402

W, H = 1280, 720
OUT_SVG = "out/miniature.svg"

fond = base64.b64encode(open("out/p_bulle.png", "rb").read()).decode()
logo = base64.b64encode(assets.logo_svg().encode("utf-8")).decode()


def texte(txt, taille, cx, y, couleur, graisse=0.0):
    d, w = assets._texte_centre(txt, taille, cx, y, 0.0)
    return (f'<path d="{d}" fill="{couleur}" stroke="{couleur}" stroke-width="{graisse}" '
            f'stroke-linejoin="round"/>'), w


accroche, w1 = texte("6 ARMES - 8 BOTS - ARBRE DE TALENTS", 34, W / 2, H - 46, "#ffffff")
bas, _ = texte("CLIQUEZ SUR LE DRAPEAU VERT POUR JOUER", 26, W / 2, H - 16, "#c9b6ff")
svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
    f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
    '<defs>'
    '<linearGradient id="haut" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#0b0418" stop-opacity="0.95"/>'
    '<stop offset="0.55" stop-color="#0b0418" stop-opacity="0.15"/>'
    '<stop offset="1" stop-color="#0b0418" stop-opacity="0.95"/></linearGradient>'
    '</defs>'
    # capture de combat en fond (recadrée pour remplir la miniature)
    f'<image x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="xMidYMid slice" '
    f'xlink:href="data:image/png;base64,{fond}"/>'
    f'<rect width="{W}" height="{H}" fill="url(#haut)"/>'
    # bandeaux sombres : le logo et les accroches restent lisibles par-dessus la capture
    f'<rect x="0" y="0" width="{W}" height="215" fill="#08040f" opacity="0.62"/>'
    f'<rect x="0" y="{H-92}" width="{W}" height="92" fill="#08040f" opacity="0.66"/>'
    # logo
    f'<image x="{W/2-430/2:.0f}" y="26" width="430" height="168" '
    f'xlink:href="data:image/svg+xml;base64,{logo}"/>'
    + accroche + bas
    + '</svg>')
open(OUT_SVG, "w", encoding="utf-8").write(svg)
print("svg miniature écrit")
