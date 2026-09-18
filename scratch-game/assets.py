"""
Génération procédurale des graphismes (SVG) et des sons (WAV) du jeu.
Tout est vectoriel : rendu net à n'importe quelle taille dans Scratch.
"""
import io
import math
import struct
import wave

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ------------------------------------------------------------------ Glyphes

GLYPH_CHARS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    ".,!?:-+/'%()<>=éèêàçùôîûÉÈÊÀÇ«»â→"
)
EM_PX = 40.0  # hauteur d'un em à 100 % de taille sprite


def build_glyphs():
    """Retourne une liste de (nom_costume, svg, cx, cy, avance_px) pour chaque caractère,
    avec deux variantes de couleur : blanc (W) et rouge (C, teintable via l'effet couleur)."""
    font = TTFont(FONT_PATH)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    upm = font["head"].unitsPerEm
    scale = EM_PX / upm
    ascent = font["hhea"].ascent * scale
    descent = -font["hhea"].descent * scale
    out = []
    for ch in GLYPH_CHARS:
        gname = cmap[ord(ch)]
        g = glyph_set[gname]
        pen = SVGPathPen(glyph_set)
        g.draw(pen)
        d = pen.getCommands()
        adv = g.width * scale
        # boîte : de 0..adv en x, de -descent..ascent en y (repère police, y vers le haut)
        pad = 2
        w = adv + 2 * pad
        h = ascent + descent + 2 * pad
        # transform : y inversé, origine au coin haut-gauche
        tx = pad
        ty = pad + ascent
        for variant, color in (("W", "#ffffff"), ("C", "#ff2020")):
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.2f}" height="{h:.2f}" '
                f'viewBox="0 0 {w:.2f} {h:.2f}">'
                f'<path transform="translate({tx:.2f},{ty:.2f}) scale({scale:.5f},{-scale:.5f})" '
                f'fill="{color}" d="{d}"/></svg>'
            )
            # centre de rotation : origine (gauche, ligne de base)
            out.append((variant + ch, svg, tx, ty, adv))
    return out


# ------------------------------------------------------------------ Logo & éléments d'interface

from fontTools.pens.transformPen import TransformPen  # noqa: E402


def _texte_path(txt, taille, x=0.0, y=0.0, espace_f=0.0):
    """Contours RÉELS du texte (police du jeu) dans un seul <path> :
    rendu net à n'importe quelle taille, contrairement au texte tamponné glyphe par glyphe.
    x, y = coin gauche de la ligne de base ; espace_f = interlettrage en fraction de la taille.
    Renvoie (d, largeur)."""
    font = TTFont(FONT_PATH)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    scale = taille / font["head"].unitsPerEm
    espace = taille * espace_f
    parts, cursor = [], x
    for ch in txt:
        if ch == " ":
            cursor += taille * 0.30 + espace
            continue
        if ch == "\u00b7":                      # « · » n'est pas dans la police embarquée
            cs = _cercle((cursor + taille * 0.12, y - taille * 0.30), taille * 0.075, "#ffffff")
            parts.append(cs)
            cursor += taille * 0.24 + espace
            continue
        pen = SVGPathPen(glyph_set)
        glyph_set[cmap[ord(ch)]].draw(TransformPen(pen, (scale, 0, 0, -scale, cursor, y)))
        parts.append(pen.getCommands())
        cursor += glyph_set[cmap[ord(ch)]].width * scale + espace
    return " ".join(parts), max(0.0, cursor - x - espace)


def _texte_largeur(txt, taille, espace_f=0.0):
    return _texte_path(txt, taille, 0, 0, espace_f)[1]


def _texte_centre(txt, taille, cx, y, espace_f=0.0):
    """Chemin du texte centré horizontalement sur cx, avec ajustement automatique de la
    taille pour ne pas dépasser max_w (la largeur est proportionnelle à la taille)."""
    w = _texte_largeur(txt, taille, espace_f)
    d, w = _texte_path(txt, taille, cx - w / 2.0, y, espace_f)
    return d, w


def _texte_ajuste(txt, cy, max_w, max_h, espace_f=0.0):
    """Renvoie (chemin, largeur) centré sur l'écusson ; la taille est réduite pour tenir
    à la fois en largeur (max_w) et en hauteur de capitale (max_h)."""
    taille = 100.0
    w = _texte_largeur(txt, taille, espace_f)
    taille = min(taille * max_w / w, max_h / 0.715)
    return _texte_centre(txt, taille, LOGO_W / 2.0, cy, espace_f)


LOGO_W, LOGO_H = 640, 250
_LOGO_INK = "#180a2a"


def _logo_texte(txt, cy, max_w, max_h, espace_f, c1, c2, gid, contour=9):
    """Lettrage du logo : contour sombre épais + remplissage dégradé."""
    d, w = _texte_ajuste(txt, cy, max_w, max_h, espace_f)
    return (
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0.15" y2="1">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="0.55" stop-color="{c2}"/>'
        f'<stop offset="1" stop-color="{c1}"/></linearGradient></defs>'
        f'<path d="{d}" fill="{_LOGO_INK}" stroke="{_LOGO_INK}" stroke-width="{contour}" '
        f'stroke-linejoin="round"/>'
        f'<path d="{d}" fill="url(#{gid})" stroke="#ffffff" stroke-opacity="0.22" stroke-width="1.4"/>'
    ), w


def logo_svg():
    """Logo du jeu : écusson dégradé + lettrage vectoriel « ARENA CLASH »."""
    W, H = LOGO_W, LOGO_H
    # épées croisées derrière le lettrage (bien visibles dans les coins)
    a, _ = _logo_texte("ARENA", 88, 380, 50, 0.14, "#ffffff", "#bcd6ff", "lgA", contour=8)
    b, _ = _logo_texte("CLASH", 198, 452, 80, 0.03, "#ffd54a", "#ff7a00", "lgB", contour=11)
    coins = "".join(
        f'<path d="M {cx} {cy+sign*30} L {cx} {cy} L {cx+sign*30} {cy}" fill="none" '
        f'stroke="#ff9ad2" stroke-width="5" stroke-linecap="round"/>'
        for cx, cy, sign in ((46, 46, 1), (W - 46, 46, -1), (46, H - 46, 1), (W - 46, H - 46, -1)))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        '<defs>'
        '<linearGradient id="fond" x1="0" y1="0" x2="0.3" y2="1">'
        '<stop offset="0" stop-color="#3a1470"/><stop offset="0.5" stop-color="#1b0a33"/>'
        '<stop offset="1" stop-color="#0d0518"/></linearGradient>'
        '<linearGradient id="barre" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#ff2d95" stop-opacity="0"/><stop offset="0.5" stop-color="#ff2d95"/>'
        '<stop offset="1" stop-color="#ff2d95" stop-opacity="0"/></linearGradient>'
        '</defs>'
        # halo
        f'<rect x="6" y="6" width="{W-12}" height="{H-12}" rx="42" fill="#ff2d95" opacity="0.40"/>'
        f'<rect x="12" y="12" width="{W-24}" height="{H-24}" rx="38" fill="#7c4dff" opacity="0.40"/>'
        # écusson
        f'<rect x="20" y="20" width="{W-40}" height="{H-40}" rx="32" fill="url(#fond)" '
        f'stroke="#ff2d95" stroke-width="7"/>'
        f'<rect x="31" y="31" width="{W-62}" height="{H-62}" rx="24" fill="none" '
        f'stroke="#ffffff" stroke-opacity="0.14" stroke-width="2"/>'
        + "".join(f'<polygon points="{x},31 {x+36},31 {x-18},{H-31} {x-54},{H-31}" fill="#ffffff" opacity="0.05"/>'
                  for x in (150, 300, 450, 600))
        + a
        + f'<rect x="{W/2-140}" y="116" width="280" height="7" rx="3.5" fill="url(#barre)"/>'
        + b
        + coins
        + '</svg>')


# ------------------------------------------------------------------ Combattant

SUIT = "#e53935"
SUIT_DARK = "#b71c1c"
SUIT_LIGHT = "#ff7961"
INK = "#1b1b24"
GLOVE = "#2c2c38"
VISOR = "#101018"
EYE = "#7cf6ff"

W, H = 170, 180
FEET = (85, 166)  # centre de rotation (pieds) — repère des costumes sans arme

# un costume avec arme a besoin de plus de place (lame tendue vers l'avant, arme levée)
W_ARME, H_ARME = 340, 300
FEET_ARME = (110, 250)

_ORIGIN = [FEET[0], FEET[1]]


def _p(x, y):
    return _ORIGIN[0] + x, _ORIGIN[1] - y


# ------------------------------------------------------------------ Armes
# Chaque arme est dessinée dans un repère local : origine = la main, +x vers l'avant,
# +y vers le bas. On l'insère ensuite dans le costume du combattant, avec un angle
# propre à chaque pose (l'arme suit donc vraiment la main et l'animation).
ACIER = "#e3e8f5"
ACIER2 = "#9aa6bd"
OR = "#ffc107"
BOIS = "#8d5524"
CUIR = "#3a2a1a"

_EPEE = (
    f'<rect x="-20" y="-5" width="20" height="10" rx="4" fill="{CUIR}" stroke="{INK}" stroke-width="3"/>'
    f'<circle cx="-23" cy="0" r="6" fill="{OR}" stroke="{INK}" stroke-width="3"/>'
    f'<rect x="0" y="-16" width="9" height="32" rx="4" fill="{OR}" stroke="{INK}" stroke-width="3"/>'
    f'<polygon points="9,-6 70,-6 92,0 70,6 9,6" fill="{ACIER}" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>'
    f'<line x1="16" y1="0" x2="72" y2="0" stroke="{ACIER2}" stroke-width="2"/>')

_LANCE = (
    f'<rect x="-30" y="-4" width="116" height="8" rx="4" fill="{BOIS}" stroke="{INK}" stroke-width="3"/>'
    f'<rect x="-32" y="-6" width="7" height="12" rx="3" fill="{CUIR}" stroke="{INK}" stroke-width="2.5"/>'
    f'<polygon points="84,-9 120,0 84,9" fill="{ACIER}" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>'
    f'<line x1="88" y1="0" x2="112" y2="0" stroke="{ACIER2}" stroke-width="2"/>')

_MARTEAU = (
    f'<rect x="-26" y="-5" width="72" height="10" rx="5" fill="{BOIS}" stroke="{INK}" stroke-width="3"/>'
    f'<rect x="-30" y="-6" width="8" height="12" rx="3" fill="{CUIR}" stroke="{INK}" stroke-width="2.5"/>'
    f'<rect x="32" y="-23" width="30" height="46" rx="7" fill="{ACIER2}" stroke="{INK}" stroke-width="3"/>'
    f'<rect x="37" y="-18" width="20" height="15" rx="4" fill="{ACIER}" opacity="0.85"/>'
    f'<rect x="37" y="4" width="20" height="14" rx="4" fill="#7d8aa3"/>')

_ARC = (
    f'<path d="M 10,-52 Q 42,0 10,52" fill="none" stroke="{INK}" stroke-width="12" stroke-linecap="round"/>'
    f'<path d="M 10,-52 Q 42,0 10,52" fill="none" stroke="{BOIS}" stroke-width="7" stroke-linecap="round"/>'
    f'<line x1="10" y1="-52" x2="10" y2="52" stroke="#f4f4f4" stroke-width="2.5"/>'
    f'<line x1="-26" y1="0" x2="60" y2="0" stroke="#c8a165" stroke-width="4"/>'
    f'<polygon points="60,-6 76,0 60,6" fill="{ACIER}" stroke="{INK}" stroke-width="2.5" stroke-linejoin="round"/>'
    f'<polygon points="-26,0 -15,-8 -6,0 -15,8" fill="#e74c3c"/>')

_BOUCLIER = (
    f'<rect x="-18" y="-34" width="48" height="68" rx="13" fill="#5c6bc0" stroke="{INK}" stroke-width="4"/>'
    f'<rect x="-11" y="-26" width="34" height="52" rx="9" fill="#7986cb"/>'
    f'<circle cx="6" cy="0" r="8" fill="{OR}" stroke="{INK}" stroke-width="3"/>'
    f'<line x1="6" y1="-26" x2="6" y2="-11" stroke="{INK}" stroke-width="3"/>'
    f'<line x1="6" y1="11" x2="6" y2="26" stroke="{INK}" stroke-width="3"/>')

# id -> (markup local, décalage dx/dy de la main) ; "poings" = pas d'arme dessinée
ARMES_COSTUME = {
    "epee": (_EPEE, -2, 0),
    "lance": (_LANCE, -6, 0),
    "marteau": (_MARTEAU, -8, 0),
    "arc": (_ARC, -4, 0),
    "bouclier": (_BOUCLIER, -16, 0),
}

# angle de l'arme (degrés, 0 = tendue vers l'avant, négatif = vers le haut)
ARME_ANGLES = {
    "defaut": {"idle": -55, "idle2": -50, "walk1": -46, "walk2": -52, "jump": -40,
               "punch": -4, "kick": -28, "special": -8, "block": 24, "hurt": -18, "ko": -12, "win": -76},
    "epee": {"block": -26},
    "lance": {"idle": -30, "idle2": -28, "walk1": -26, "walk2": -30, "jump": -22, "punch": -2,
              "kick": -20, "special": -4, "block": -18, "hurt": -20, "ko": -12, "win": -62},
    "marteau": {"idle": -48, "idle2": -44, "walk1": -42, "walk2": -46, "jump": -36, "punch": -6,
                "kick": -26, "special": -10, "block": -22, "hurt": -18, "ko": -12, "win": -70},
    "arc": {"idle": -12, "idle2": -10, "walk1": -14, "walk2": -12, "jump": -8, "punch": 0,
            "kick": -10, "special": 0, "block": 0, "hurt": -30, "ko": -20, "win": -30},
    "bouclier": {"idle": -8, "idle2": -6, "walk1": -10, "walk2": -8, "jump": -6, "punch": 0,
                 "kick": -6, "special": 0, "block": 0, "hurt": -20, "ko": -10, "win": -20},
}
# chaque entrée hérite des angles par défaut
for _k in ("epee", "lance", "marteau", "arc", "bouclier"):
    _base = dict(ARME_ANGLES["defaut"])
    _base.update(ARME_ANGLES[_k])
    ARME_ANGLES[_k] = _base


# longueur visuelle de chaque arme (pour l'échelle des icônes)
ARME_LONGUEUR = {"epee": 92, "lance": 120, "marteau": 62, "arc": 76, "bouclier": 48}


def weapon_icon_svg(wid):
    """Icône 120x120 : halo + arme, utilisée comme objet au sol et comme vignette du HUD."""
    markup = ARMES_COSTUME[wid][0]
    L = ARME_LONGUEUR[wid]
    s = round(min(1.0, 74.0 / L), 3)
    body = (f'<g transform="translate(60,60) rotate(-24) scale({s}) translate({-L * 0.48:.0f},0)">{markup}</g>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">'
            '<defs><radialGradient id="halo" cx="0.5" cy="0.5" r="0.5">'
            '<stop offset="0" stop-color="#fff59d" stop-opacity="0.95"/>'
            '<stop offset="0.55" stop-color="#ffb300" stop-opacity="0.45"/>'
            '<stop offset="1" stop-color="#ff6f00" stop-opacity="0"/></radialGradient></defs>'
            '<circle cx="60" cy="60" r="56" fill="url(#halo)"/>'
            f'<circle cx="60" cy="60" r="34" fill="#ffd54a" opacity="0.30"/>'
            f'{body}</svg>')


def poing_icon_svg():
    """Vignette « mains nues » pour le HUD."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">'
            f'<circle cx="60" cy="60" r="30" fill="{GLOVE}" stroke="{INK}" stroke-width="4"/>'
            f'<circle cx="74" cy="58" r="15" fill="{GLOVE}" stroke="{INK}" stroke-width="4"/>'
            f'<rect x="40" y="46" width="34" height="28" rx="12" fill="#43435a" opacity="0.9"/>'
            '</svg>')


def arrow_svg():
    """Flèche tirée à l'arc (sprite séparé, pointe vers la droite)."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="76" height="20" viewBox="0 0 76 20">'
            f'<line x1="6" y1="10" x2="60" y2="10" stroke="#c8a165" stroke-width="5"/>'
            f'<polygon points="58,3 76,10 58,17" fill="{ACIER}" stroke="{INK}" stroke-width="2.5" stroke-linejoin="round"/>'
            f'<polygon points="6,10 20,1 30,10 20,19" fill="#e74c3c"/>'
            f'<line x1="16" y1="4" x2="16" y2="16" stroke="{INK}" stroke-width="2"/></svg>')



def _seg(a, b, w, color, outline=True):
    (x1, y1), (x2, y2) = _p(*a), _p(*b)
    s = ""
    if outline:
        s += (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
              f'stroke="{INK}" stroke-width="{w + 5}" stroke-linecap="round"/>')
    s += (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
          f'stroke="{color}" stroke-width="{w}" stroke-linecap="round"/>')
    return s


def _circle(c, r, fill, outline=True, extra=""):
    x, y = _p(*c)
    s = ""
    if outline:
        s += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + 2.5}" fill="{INK}"/>'
    s += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" {extra}/>'
    return s


def _fk(origin, lengths, angles):
    """Cinématique directe : angles depuis la verticale vers le bas, positif = vers l'avant (droite)."""
    pts = [origin]
    x, y = origin
    total = 0
    for L, a in zip(lengths, angles):
        total += a
        x += L * math.sin(math.radians(total))
        y -= L * math.cos(math.radians(total))
        pts.append((x, y))
    return pts


def _fk_up(origin, lengths, angles):
    """Idem mais depuis la verticale vers le haut (pour les bras levés)."""
    pts = [origin]
    x, y = origin
    total = 0
    for L, a in zip(lengths, angles):
        total += a
        x += L * math.sin(math.radians(total))
        y += L * math.cos(math.radians(total))
        pts.append((x, y))
    return pts


def fighter_svg(pose, posename="idle", weapon="poings"):
    """pose : dict avec les clés
       hip_y, lean (deg, + = avant), legs: (backThigh, backKnee, frontThigh, frontKnee),
       arms: (backSh, backEl, frontSh, frontEl), head_tilt, rot (rotation globale), extra
       weapon : id d'arme ("poings" = mains nues) dessinée dans la main avant.
       Renvoie (svg, head_center_xy_relatif_pieds, (cx, cy))."""
    _ORIGIN[0], _ORIGIN[1] = FEET_ARME if weapon in ARMES_COSTUME else FEET
    hip_y = pose.get("hip_y", 62)
    lean = pose.get("lean", 0)
    rot = pose.get("rot", 0)
    lift = pose.get("lift", 0)  # translation verticale globale (saut)
    bt, bk, ft, fk = pose["legs"]
    bs, be, fs, fe = pose["arms"]
    thigh, shin = 30, 28
    upper, fore = 22, 21
    torso_len = 34
    hip = (0, hip_y)
    neck = (hip[0] + torso_len * math.sin(math.radians(lean)), hip[1] + torso_len * math.cos(math.radians(lean)))
    shoulder_b = (neck[0] - 6, neck[1] - 4)
    shoulder_f = (neck[0] + 6, neck[1] - 4)
    head = (neck[0] + 4 * math.sin(math.radians(lean)), neck[1] + 20)

    back_leg = _fk((hip[0] - 7, hip[1]), (thigh, shin), (bt, bk))
    front_leg = _fk((hip[0] + 7, hip[1]), (thigh, shin), (ft, fk))
    back_arm = _fk(shoulder_b, (upper, fore), (bs, be))
    front_arm = _fk(shoulder_f, (upper, fore), (fs, fe))

    parts = []
    # --- arrière
    parts.append(_seg(back_arm[0], back_arm[1], 12, SUIT_DARK))
    parts.append(_seg(back_arm[1], back_arm[2], 11, SUIT_DARK))
    parts.append(_circle(back_arm[2], 8.5, GLOVE))
    parts.append(_seg(back_leg[0], back_leg[1], 14, SUIT_DARK))
    parts.append(_seg(back_leg[1], back_leg[2], 13, SUIT_DARK))
    parts.append(_circle(back_leg[2], 8, GLOVE))
    # --- torse
    parts.append(_seg(hip, neck, 30, SUIT))
    # ceinture
    belt_a = (hip[0] - 15 * math.cos(math.radians(lean)), hip[1] + 2)
    belt_b = (hip[0] + 15 * math.cos(math.radians(lean)), hip[1] + 2)
    parts.append(_seg(belt_a, belt_b, 7, GLOVE, outline=False))
    # emblème poitrine
    chest = (hip[0] + 20 * math.sin(math.radians(lean)) + 3, hip[1] + 20 * math.cos(math.radians(lean)))
    parts.append(_circle(chest, 5, SUIT_LIGHT, outline=False))
    # --- tête
    parts.append(_circle(head, 18, SUIT))
    hx, hy = _p(*head)
    # visière
    parts.append(f'<rect x="{hx - 6:.1f}" y="{hy - 8:.1f}" width="22" height="13" rx="6" fill="{VISOR}"/>')
    parts.append(f'<rect x="{hx - 1:.1f}" y="{hy - 5:.1f}" width="13" height="5" rx="2.5" fill="{EYE}"/>')
    if pose.get("eyes") == "ko":
        parts[-1] = (f'<path d="M{hx+1:.1f} {hy-5:.1f} l6 6 m0 -6 l-6 6" stroke="{EYE}" stroke-width="2" '
                     f'stroke-linecap="round"/>')
    elif pose.get("eyes") == "happy":
        parts[-1] = (f'<path d="M{hx:.1f} {hy-1:.1f} q6 -7 12 0" stroke="{EYE}" stroke-width="2.5" '
                     f'fill="none" stroke-linecap="round"/>')
    elif pose.get("eyes") == "angry":
        parts[-1] = (f'<path d="M{hx:.1f} {hy-6:.1f} l13 4" stroke="{EYE}" stroke-width="4" '
                     f'stroke-linecap="round"/>')
    # reflet casque
    parts.append(f'<circle cx="{hx - 7:.1f}" cy="{hy - 9:.1f}" r="4" fill="{SUIT_LIGHT}" opacity="0.8"/>')
    # --- avant
    parts.append(_seg(front_leg[0], front_leg[1], 14, SUIT))
    parts.append(_seg(front_leg[1], front_leg[2], 13, SUIT))
    parts.append(_circle(front_leg[2], 8, GLOVE))
    parts.append(_seg(front_arm[0], front_arm[1], 12, SUIT))
    parts.append(_seg(front_arm[1], front_arm[2], 11, SUIT))
    parts.append(_circle(front_arm[2], 8.5, GLOVE))
    if weapon in ARMES_COSTUME:
        markup, dx, dy = ARMES_COSTUME[weapon]
        wx, wy = front_arm[2][0] + dx, front_arm[2][1] + dy
        hx_svg, hy_svg = _p(wx, wy)
        ang = ARME_ANGLES[weapon].get(posename, -45)
        parts.append(f'<g transform="translate({hx_svg:.1f},{hy_svg:.1f}) rotate({ang})">{markup}</g>')
    extra = pose.get("extra", "")

    body = "".join(parts)
    fx, fy = _ORIGIN
    w, h = (W_ARME, H_ARME) if weapon in ARMES_COSTUME else (W, H)
    transform = f'translate(0,{-lift}) rotate({rot} {fx} {fy})'
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
           f'<g transform="{transform}">{body}</g>{extra}</svg>')
    # centre de la tête après rotation / lift (relatif au centre de rotation, y vers le haut)
    hxr, hyr = head
    a = math.radians(-rot)  # rotation svg (sens horaire) -> repère y haut
    rx = hxr * math.cos(a) - hyr * math.sin(a)
    ry = hxr * math.sin(a) + hyr * math.cos(a)
    return svg, (round(rx, 1), round(ry + lift, 1)), (fx, fy)


# Poses retouchées pour certaines armes : un bouclier ne se tient pas à hauteur de visage
# dans la garde (il masquerait la tête), on baisse donc le bras avant en pose "block".
POSE_ARME = {
    "bouclier": {
        "block": dict(arms=(70, 140, 34, 92)),
        "idle": dict(arms=(55, 120, 60, 96)),
        "idle2": dict(arms=(58, 118, 62, 92)),
    },
}


def fighter_poses():
    P = {}
    P["idle"] = dict(hip_y=60, lean=4, legs=(-12, 14, 14, -14), arms=(55, 120, 70, 110))
    P["idle2"] = dict(hip_y=59, lean=5, legs=(-12, 16, 14, -16), arms=(58, 118, 72, 106))
    P["walk1"] = dict(hip_y=60, lean=6, legs=(-26, 30, 22, -6), arms=(40, 110, 75, 100))
    P["walk2"] = dict(hip_y=60, lean=6, legs=(22, -6, -26, 30), arms=(60, 110, 60, 110))
    P["jump"] = dict(hip_y=60, lean=8, legs=(-30, 60, 30, -70), arms=(-40, -30, 130, 40), lift=0)
    P["punch"] = dict(hip_y=58, lean=16, legs=(-24, 22, 30, -18), arms=(60, 120, 92, -2))
    P["kick"] = dict(hip_y=62, lean=-8, legs=(-14, 24, 88, -2), arms=(70, 100, 40, 120))
    P["special"] = dict(hip_y=56, lean=18, legs=(-34, 26, 40, -26), arms=(95, -5, 90, 0),
                        extra='<circle cx="150" cy="86" r="16" fill="#fff3a0" opacity="0.85"/>'
                              '<circle cx="150" cy="86" r="26" fill="#ffd54a" opacity="0.35"/>')
    P["block"] = dict(hip_y=54, lean=2, legs=(-20, 24, 20, -24), arms=(70, 140, 75, 150))
    P["hurt"] = dict(hip_y=58, lean=-22, legs=(-22, 20, 24, -10), arms=(-30, -60, -20, -50), eyes="angry")
    P["ko"] = dict(hip_y=60, lean=0, legs=(-10, 5, 12, -5), arms=(-40, -20, -50, -20), rot=-84, lift=-14, eyes="ko")
    P["win"] = dict(hip_y=60, lean=0, legs=(-10, 8, 10, -8), arms=(-160, -20, 160, 20), eyes="happy")
    return P


# ------------------------------------------------------------------ Accessoires

def accessory_svgs():
    """Chaque accessoire est dessiné dans une boîte 90x90 dont le centre (45,50) = centre de la tête."""
    A = {}
    box = '<svg xmlns="http://www.w3.org/2000/svg" width="90" height="90" viewBox="0 0 90 90">{}</svg>'
    A["aucun"] = box.format('<circle cx="45" cy="50" r="1" fill="#000" opacity="0.01"/>')
    # bandeau ninja
    A["bandeau"] = box.format(
        '<rect x="24" y="36" width="42" height="9" rx="4" fill="#1b1b24"/>'
        '<rect x="26" y="38" width="38" height="5" rx="2.5" fill="#f5f5f5"/>'
        '<path d="M26 40 l-14 -6 l4 10 z M26 40 l-16 4 l6 8 z" fill="#f5f5f5" stroke="#1b1b24" stroke-width="2" stroke-linejoin="round"/>')
    # casquette
    A["casquette"] = box.format(
        '<path d="M25 44 a20 20 0 0 1 40 0 z" fill="#1b1b24"/>'
        '<path d="M27 43 a18 18 0 0 1 36 0 z" fill="#2962ff"/>'
        '<rect x="40" y="43" width="42" height="7" rx="3.5" fill="#1b1b24"/>'
        '<rect x="42" y="44.5" width="38" height="4" rx="2" fill="#1e4fd6"/>'
        '<circle cx="45" cy="26" r="3.5" fill="#1b1b24"/><circle cx="45" cy="26" r="2" fill="#ffd54a"/>')
    # couronne
    A["couronne"] = box.format(
        '<path d="M26 44 L26 24 L35 33 L45 18 L55 33 L64 24 L64 44 Z" fill="#1b1b24"/>'
        '<path d="M29 41 L29 30 L35 37 L45 24 L55 37 L61 30 L61 41 Z" fill="#ffc107"/>'
        '<rect x="29" y="38" width="32" height="4" fill="#ff9800"/>'
        '<circle cx="45" cy="34" r="2.6" fill="#e53935"/><circle cx="35" cy="38" r="2" fill="#29b6f6"/>'
        '<circle cx="55" cy="38" r="2" fill="#29b6f6"/>')
    # cornes
    A["cornes"] = box.format(
        '<path d="M30 42 C 22 34, 20 22, 26 14 C 30 24, 34 30, 40 36 Z" fill="#1b1b24"/>'
        '<path d="M30 40 C 24 34, 23 24, 27 18 C 30 26, 33 31, 38 36 Z" fill="#b71c1c"/>'
        '<path d="M60 42 C 68 34, 70 22, 64 14 C 60 24, 56 30, 50 36 Z" fill="#1b1b24"/>'
        '<path d="M60 40 C 66 34, 67 24, 63 18 C 60 26, 57 31, 52 36 Z" fill="#b71c1c"/>')
    # auréole
    A["aureole"] = box.format(
        '<ellipse cx="45" cy="22" rx="20" ry="6" fill="none" stroke="#1b1b24" stroke-width="7"/>'
        '<ellipse cx="45" cy="22" rx="20" ry="6" fill="none" stroke="#ffe082" stroke-width="4"/>'
        '<ellipse cx="45" cy="22" rx="20" ry="6" fill="none" stroke="#fff8e1" stroke-width="1.5"/>')
    # haut-de-forme
    A["chapeau"] = box.format(
        '<rect x="22" y="38" width="46" height="8" rx="4" fill="#1b1b24"/>'
        '<rect x="29" y="8" width="32" height="34" rx="3" fill="#1b1b24"/>'
        '<rect x="31" y="10" width="28" height="30" rx="2" fill="#3a3a4a"/>'
        '<rect x="31" y="32" width="28" height="6" fill="#e53935"/>')
    # oreilles de chat
    A["chat"] = box.format(
        '<path d="M27 46 L24 20 L44 36 Z" fill="#1b1b24"/><path d="M29 43 L27 25 L41 36 Z" fill="#ff8a80"/>'
        '<path d="M63 46 L66 20 L46 36 Z" fill="#1b1b24"/><path d="M61 43 L63 25 L49 36 Z" fill="#ff8a80"/>')
    # lunettes de soleil
    A["lunettes"] = box.format(
        '<rect x="26" y="44" width="18" height="12" rx="4" fill="#1b1b24"/>'
        '<rect x="46" y="44" width="18" height="12" rx="4" fill="#1b1b24"/>'
        '<rect x="28" y="46" width="14" height="8" rx="3" fill="#7e57c2"/>'
        '<rect x="48" y="46" width="14" height="8" rx="3" fill="#7e57c2"/>'
        '<rect x="43" y="47" width="4" height="3" fill="#1b1b24"/>')
    return A


# ------------------------------------------------------------------ Décors

def _bg(w=480, h=360):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{{}}</svg>'


def backdrops():
    B = {}
    # Menu : dégradé sombre + formes géométriques
    B["menu"] = _bg().format(
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#1a1440"/><stop offset="1" stop-color="#0b0b1a"/></linearGradient></defs>'
        '<rect width="480" height="360" fill="url(#g)"/>'
        '<polygon points="0,360 200,0 260,0 60,360" fill="#ffffff" opacity="0.04"/>'
        '<polygon points="280,360 480,40 480,140 340,360" fill="#ffffff" opacity="0.04"/>'
        '<circle cx="420" cy="60" r="90" fill="#7c4dff" opacity="0.15"/>'
        '<circle cx="60" cy="320" r="120" fill="#ff4081" opacity="0.10"/>'
        '<rect x="0" y="300" width="480" height="60" fill="#000" opacity="0.35"/>')
    ground = ('<rect x="0" y="270" width="480" height="90" fill="{g1}"/>'
              '<rect x="0" y="270" width="480" height="6" fill="{g2}"/>'
              '<rect x="0" y="276" width="480" height="3" fill="#000" opacity="0.25"/>')
    # Dojo
    B["dojo"] = _bg().format(
        '<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#f6d9a7"/><stop offset="1" stop-color="#e2b07c"/></linearGradient></defs>'
        '<rect width="480" height="360" fill="url(#s)"/>'
        + "".join(f'<rect x="{x}" y="40" width="70" height="200" fill="#fff6e3" stroke="#6d3b1f" stroke-width="5"/>'
                  f'<line x1="{x+35}" y1="40" x2="{x+35}" y2="240" stroke="#6d3b1f" stroke-width="3"/>'
                  f'<line x1="{x}" y1="140" x2="{x+70}" y2="140" stroke="#6d3b1f" stroke-width="3"/>'
                  for x in (30, 120, 290, 380))
        + '<rect x="0" y="240" width="480" height="30" fill="#8b4a25"/>'
        '<rect x="0" y="0" width="480" height="40" fill="#6d3b1f"/>'
        '<rect x="0" y="36" width="480" height="8" fill="#4a2612"/>'
        '<circle cx="240" cy="130" r="45" fill="#e53935" opacity="0.9"/>'
        '<circle cx="240" cy="130" r="36" fill="#f6d9a7"/>'
        '<circle cx="240" cy="130" r="26" fill="#e53935"/>'
        + ground.format(g1="#c98b53", g2="#e8b07a"))
    # Toits de nuit
    stars = "".join(f'<circle cx="{(i*97)%480}" cy="{(i*53)%200}" r="{1+(i%3)*0.6}" fill="#fff" opacity="0.8"/>'
                    for i in range(40))
    builds = "".join(
        f'<rect x="{x}" y="{y}" width="{w}" height="{300-y}" fill="#1c2340"/>'
        + "".join(f'<rect x="{x+6+j*12}" y="{y+10+k*16}" width="6" height="9" fill="#ffe082" opacity="{0.9 if (j*7+k*3+x)%5 else 0.2}"/>'
                  for j in range((w-8)//12) for k in range((290-y)//16))
        for x, y, w in ((0, 120, 60), (70, 80, 50), (130, 150, 70), (210, 60, 60), (280, 130, 55), (345, 90, 65), (420, 140, 60)))
    B["toits"] = _bg().format(
        '<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#0a0f2e"/><stop offset="1" stop-color="#2c1e5c"/></linearGradient></defs>'
        '<rect width="480" height="360" fill="url(#s)"/>' + stars +
        '<circle cx="380" cy="70" r="34" fill="#fff8e1"/><circle cx="392" cy="60" r="30" fill="#0f1440" opacity="0.0"/>'
        + builds + ground.format(g1="#2a2f4a", g2="#4b527a"))
    # Volcan
    B["volcan"] = _bg().format(
        '<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#2b0a0a"/><stop offset="1" stop-color="#8b1e12"/></linearGradient>'
        '<radialGradient id="l" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#ffd54a"/>'
        '<stop offset="1" stop-color="#ff5722"/></radialGradient></defs>'
        '<rect width="480" height="360" fill="url(#s)"/>'
        '<polygon points="60,270 200,60 340,270" fill="#3b1616"/>'
        '<polygon points="120,270 200,140 280,270" fill="#2a0f0f"/>'
        '<polygon points="180,90 200,60 220,90 210,100 190,100" fill="#ff6d00"/>'
        '<polygon points="0,270 80,180 160,270" fill="#3b1616"/><polygon points="320,270 400,150 480,270" fill="#3b1616"/>'
        + "".join(f'<circle cx="{(i*131)%480}" cy="{(i*71)%250}" r="{1.5+(i%3)}" fill="#ffab40" opacity="0.7"/>' for i in range(25))
        + ground.format(g1="#3a1a12", g2="#ff7043")
        + '<rect x="0" y="330" width="480" height="30" fill="url(#l)" opacity="0.6"/>')
    # Cyber
    grid = "".join(f'<line x1="{x}" y1="270" x2="{240+(x-240)*3}" y2="360" stroke="#00e5ff" stroke-width="1.2" opacity="0.5"/>' for x in range(0, 481, 40))
    grid += "".join(f'<line x1="0" y1="{y}" x2="480" y2="{y}" stroke="#00e5ff" stroke-width="1" opacity="0.4"/>' for y in (285, 300, 320, 345))
    B["cyber"] = _bg().format(
        '<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#050014"/><stop offset="1" stop-color="#2a0a5e"/></linearGradient></defs>'
        '<rect width="480" height="360" fill="url(#s)"/>'
        '<circle cx="240" cy="200" r="120" fill="#ff2d95" opacity="0.35"/>'
        '<circle cx="240" cy="200" r="90" fill="#ff2d95" opacity="0.5"/>'
        '<rect x="0" y="200" width="480" height="70" fill="#050014" opacity="0.7"/>'
        + "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{270-y}" fill="#0b0524" stroke="#b388ff" stroke-width="1.5"/>'
                  for x, y, w in ((10, 150, 40), (60, 110, 30), (100, 170, 50), (160, 130, 30), (300, 120, 40), (350, 160, 30), (390, 100, 45), (445, 150, 30)))
        + '<rect x="0" y="270" width="480" height="90" fill="#0a0522"/>' + grid
        + '<rect x="0" y="268" width="480" height="4" fill="#00e5ff"/>')
    return B


# ------------------------------------------------------------------ FX

def fx_svgs():
    F = {}
    F["spark"] = ('<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">'
                  '<polygon points="30,2 36,22 58,30 36,38 30,58 24,38 2,30 24,22" fill="#fff59d"/>'
                  '<polygon points="30,12 34,25 48,30 34,35 30,48 26,35 12,30 26,25" fill="#ffffff"/></svg>')
    F["dot"] = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
                '<circle cx="12" cy="12" r="11" fill="#ff2020"/></svg>')
    F["ring"] = ('<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 80 80">'
                 '<circle cx="40" cy="40" r="34" fill="none" stroke="#ffffff" stroke-width="6"/></svg>')
    F["bolt"] = ('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="60" viewBox="0 0 40 60">'
                 '<polygon points="24,2 6,32 18,32 12,58 34,24 22,24 30,2" fill="#ffee58" stroke="#fff" stroke-width="2"/></svg>')
    F["bulle"] = ('<svg xmlns="http://www.w3.org/2000/svg" width="140" height="140" viewBox="0 0 140 140">'
                  '<circle cx="70" cy="70" r="64" fill="#7fd4ff" fill-opacity="0.16" stroke="#c9f0ff" stroke-width="6"/>'
                  '<circle cx="70" cy="70" r="58" fill="none" stroke="#ffffff" stroke-width="2" stroke-opacity="0.55"/>'
                  '<ellipse cx="46" cy="40" rx="16" ry="10" fill="#ffffff" fill-opacity="0.35" transform="rotate(-28 46 40)"/></svg>')
    # étincelle en étoile (K.O., impacts violents)
    F["etoile"] = ('<svg xmlns="http://www.w3.org/2000/svg" width="70" height="70" viewBox="0 0 70 70">'
                   '<polygon points="35,0 42,26 70,35 42,44 35,70 28,44 0,35 28,26" fill="#fff59d" '
                   'stroke="#ffd54a" stroke-width="3"/>'
                   '<circle cx="35" cy="35" r="9" fill="#ffffff"/></svg>')
    # éclat de lame / impact
    F["eclair"] = ('<svg xmlns="http://www.w3.org/2000/svg" width="80" height="60" viewBox="0 0 80 60">'
                   '<polygon points="6,30 40,18 74,30 40,42" fill="#ffffff" fill-opacity="0.9"/>'
                   '<polygon points="26,30 40,24 54,30 40,36" fill="#7cf6ff"/></svg>')
    # poussière (réception de saut, course)
    F["poussiere"] = ('<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30">'
                      '<circle cx="15" cy="15" r="13" fill="#ffffff" fill-opacity="0.55"/>'
                      '<circle cx="15" cy="15" r="8" fill="#ffffff" fill-opacity="0.8"/></svg>')
    F["pixel"] = ('<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4" viewBox="0 0 4 4">'
                  '<rect width="4" height="4" fill="#ffffff"/></svg>')
    return F


# ------------------------------------------------------------------ Sons

RATE = 22050


def _wav(samples):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in samples))
    return buf.getvalue(), len(samples)


def _env(i, n, attack=0.005, decay=None):
    t = i / RATE
    a = min(1, t / attack) if attack > 0 else 1
    d = 1 - i / n
    return a * (d ** (decay or 1.5))


def _noise_state():
    x = [12345]

    def nx():
        x[0] = (x[0] * 1103515245 + 12345) & 0x7FFFFFFF
        return (x[0] / 0x7FFFFFFF) * 2 - 1
    return nx


def sounds():
    S = {}
    nx = _noise_state()
    # coup : bruit + basse
    n = int(RATE * 0.16)
    S["hit"] = _wav([(_env(i, n, decay=2.5) * (0.6 * nx() + 0.7 * math.sin(2 * math.pi * (120 - 60 * i / n) * i / RATE))) * 0.8 for i in range(n)])
    n = int(RATE * 0.25)
    S["kick"] = _wav([(_env(i, n, decay=2) * (0.7 * nx() * (1 - i / n) + 0.8 * math.sin(2 * math.pi * (90 - 50 * i / n) * i / RATE))) * 0.9 for i in range(n)])
    n = int(RATE * 0.12)
    S["block"] = _wav([_env(i, n, decay=3) * 0.6 * math.sin(2 * math.pi * 900 * i / RATE) * (1 + 0.3 * math.sin(2 * math.pi * 1350 * i / RATE)) for i in range(n)])
    n = int(RATE * 0.06)
    S["click"] = _wav([_env(i, n, attack=0.001, decay=2) * 0.5 * math.sin(2 * math.pi * 1200 * i / RATE) for i in range(n)])
    n = int(RATE * 0.18)
    S["jump"] = _wav([_env(i, n, decay=1.2) * 0.4 * math.sin(2 * math.pi * (300 + 500 * i / n) * i / RATE) for i in range(n)])
    n = int(RATE * 0.3)
    S["coin"] = _wav([_env(i, n, decay=1.5) * 0.45 * math.sin(2 * math.pi * (988 if i < n * 0.35 else 1319) * i / RATE) for i in range(n)])
    n = int(RATE * 0.7)
    S["ko"] = _wav([(_env(i, n, decay=1.3) * (0.5 * nx() * (1 - i / n) ** 2 + 0.8 * math.sin(2 * math.pi * (160 - 120 * i / n) * i / RATE))) * 0.9 for i in range(n)])
    n = int(RATE * 0.5)
    S["special"] = _wav([_env(i, n, attack=0.05, decay=1) * 0.5 * (math.sin(2 * math.pi * (200 + 900 * (i / n) ** 2) * i / RATE) + 0.4 * math.sin(2 * math.pi * (400 + 1800 * (i / n) ** 2) * i / RATE)) for i in range(n)])
    # fanfare victoire (3 notes)
    seq = [(523.25, 0.15), (659.25, 0.15), (783.99, 0.15), (1046.5, 0.45)]
    samples = []
    for f, dur in seq:
        n = int(RATE * dur)
        samples += [_env(i, n, decay=0.8) * 0.4 * (math.sin(2 * math.pi * f * i / RATE) + 0.3 * math.sin(2 * math.pi * 2 * f * i / RATE)) for i in range(n)]
    S["win"] = _wav(samples)
    seq = [(392, 0.25), (369.99, 0.25), (349.23, 0.25), (329.63, 0.6)]
    samples = []
    for f, dur in seq:
        n = int(RATE * dur)
        samples += [_env(i, n, decay=0.8) * 0.4 * (math.sin(2 * math.pi * f * i / RATE) + 0.3 * math.sin(2 * math.pi * 0.5 * f * i / RATE)) for i in range(n)]
    S["lose"] = _wav(samples)
    n = int(RATE * 0.35)
    S["round"] = _wav([_env(i, n, decay=1) * 0.5 * (math.sin(2 * math.pi * 440 * i / RATE) + 0.5 * math.sin(2 * math.pi * 880 * i / RATE)) for i in range(n)])
    # tir à l'arc : corde qui claque (bruit court + chute de hauteur)
    n = int(RATE * 0.14)
    S["tir"] = _wav([(_env(i, n, attack=0.001, decay=2.2)
                      * (0.55 * nx() * (1 - i / n) ** 2
                         + 0.5 * math.sin(2 * math.pi * (700 - 420 * i / n) * i / RATE))) * 0.85 for i in range(n)])
    return S
