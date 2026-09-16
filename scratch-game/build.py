"""
ARENA CLASH — générateur du projet Scratch 3 (.sb3).
    python3 build.py  ->  dist/ArenaClash.sb3
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import assets  # noqa: E402
from sb3lib import *  # noqa: E402,F403

OUT = os.path.join(os.path.dirname(__file__), "dist", "ArenaClash.sb3")

GROUND = -92
FPS = 30
ROUND_SECONDS = 60

# ------------------------------------------------------------------ données de jeu
BOTS = [
    # nom, teinte, luminosité, PV, vitesse, aggro, garde, réaction, taille, arène, accessoire
    ("Kid Bleu", 133, 0, 70, 3.2, 25, 10, 14, 85, "dojo", "aucun"),
    ("Verdo", 67, 0, 85, 3.6, 35, 20, 12, 88, "dojo", "casquette"),
    ("Sunny", 30, 10, 100, 4.0, 45, 30, 10, 90, "toits", "lunettes"),
    ("Violette", 150, 0, 110, 4.4, 50, 40, 9, 92, "toits", "chat"),
    ("Cyan-X", 100, 0, 120, 4.8, 60, 45, 8, 95, "volcan", "bandeau"),
    ("Rosa", 178, 0, 130, 5.0, 65, 55, 7, 95, "volcan", "aureole"),
    ("Ombre", 0, -70, 150, 5.4, 75, 60, 5, 100, "cyber", "cornes"),
    ("Le Champion", 25, 20, 180, 5.8, 85, 70, 4, 108, "cyber", "couronne"),
]
ARENE_NOM = {"dojo": "Dojo", "toits": "Toits", "volcan": "Volcan", "cyber": "Cyber"}
ACCS = [  # id, nom affiché, prix
    ("aucun", "Aucun", 0), ("bandeau", "Bandeau", 60), ("casquette", "Casquette", 80),
    ("lunettes", "Lunettes", 90), ("chat", "Oreilles", 120), ("cornes", "Cornes", 150),
    ("chapeau", "Chapeau", 180), ("aureole", "Auréole", 200), ("couronne", "Couronne", 300),
]
SKINS = [  # nom, teinte, luminosité, prix
    ("Rouge", 0, 0, 0), ("Bleu", 133, 0, 80), ("Vert", 67, 0, 80),
    ("Or", 30, 15, 120), ("Violet", 150, 0, 100), ("Noir", 0, -70, 150),
]
PUNCH = dict(total=13, start=3, end=7, dmg=7, range=64)
KICK = dict(total=20, start=5, end=10, dmg=11, range=84)
SPECIAL = dict(total=28, start=8, end=15, dmg=24, range=100)

COL = dict(
    panel="#141426", panel2="#1f1f38", accent="#ff3d6e", accent2="#7c4dff", ok="#2ecc71",
    warn="#ffb300", grey="#3a3a55", hp="#2ecc71", hp2="#e74c3c", hpbg="#0d0d18",
    sp="#29b6f6", white="#ffffff",
)

# ------------------------------------------------------------------ projet
P = Project()
S = P.stage

# variables globales
for v, d in [
    ("scene", "menu"), ("niveau", 1), ("niveauMax", 1), ("pieces", 100), ("round", 1),
    ("victoiresP1", 0), ("victoiresBot", 0), ("chrono", 0), ("phase", "intro"), ("phaseTimer", 0),
    ("message", ""), ("hoverBtn", ""), ("clic", ""), ("sourisAvant", 0), ("hitStop", 0), ("flash", 0),
    ("P1HP", 100), ("BotHP", 100), ("P1Max", 100), ("BotMax", 100),
    ("P1X", -120), ("P1Y", GROUND), ("BotX", 120), ("BotY", GROUND), ("P1Dir", 90), ("BotDir", -90),
    ("P1State", "idle"), ("BotState", "idle"), ("P1Special", 0), ("BotSpecial", 0),
    ("P1Hit", 0), ("BotHit", 0), ("P1HitDir", 1), ("BotHitDir", 1), ("P1Costume", 1), ("BotCostume", 1),
    ("P1Size", 85), ("BotSize", 85), ("P1Acc", "aucun"), ("BotAcc", "aucun"),
    ("P1Teinte", 0), ("P1Lum", 0), ("BotTeinte", 0), ("BotLum", 0), ("P1Skin", 1),
    ("fxType", "spark"), ("fxX", 0), ("fxY", 0), ("fxTeinte", 0), ("niveauApercu", 0),
    ("gain", 0), ("resultat", ""), ("textW", 0), ("frame", 0), ("BotVitesse", 4), ("BotAggro", 30),
    ("BotGarde", 20), ("BotReaction", 10), ("BotNom", ""), ("P1Vitesse", 4.5), ("comboP1", 0),
    ("dernierNiveauGagne", 0), ("P1Vis", 0), ("BotVis", 0),
]:
    S.add_var(v, d)

S.add_list("botNom", [b[0] for b in BOTS])
S.add_list("botTeinte", [b[1] for b in BOTS])
S.add_list("botLum", [b[2] for b in BOTS])
S.add_list("botPV", [b[3] for b in BOTS])
S.add_list("botVitesse", [b[4] for b in BOTS])
S.add_list("botAggro", [b[5] for b in BOTS])
S.add_list("botGarde", [b[6] for b in BOTS])
S.add_list("botReaction", [b[7] for b in BOTS])
S.add_list("botTaille", [b[8] for b in BOTS])
S.add_list("botArene", [b[9] for b in BOTS])
S.add_list("botAreneNom", [ARENE_NOM[b[9]] for b in BOTS])
S.add_list("botAccessoire", [b[10] for b in BOTS])
S.add_list("accId", [a[0] for a in ACCS])
S.add_list("accNom", [a[1] for a in ACCS])
S.add_list("accPrix", [a[2] for a in ACCS])
S.add_list("accPossede", [1] + [0] * (len(ACCS) - 1))
S.add_list("skinNom", [s[0] for s in SKINS])
S.add_list("skinTeinte", [s[1] for s in SKINS])
S.add_list("skinLum", [s[2] for s in SKINS])
S.add_list("skinPrix", [s[3] for s in SKINS])
S.add_list("skinPossede", [1] + [0] * (len(SKINS) - 1))

# décors
for name, svg in assets.backdrops().items():
    S.add_costume(name, svg, 240, 180)

# glyphes (widths)
glyphs = assets.build_glyphs()
S.add_list("glyphW", [round(g[4], 2) for g in glyphs])

# costumes combattant + offsets tête
POSES = assets.fighter_poses()
POSE_ORDER = ["idle", "idle2", "walk1", "walk2", "jump", "punch", "kick", "special", "block", "hurt", "ko", "win"]
fighter_costumes = []
headX, headY = [], []
for pn in POSE_ORDER:
    svg, (hx, hy) = assets.fighter_svg(POSES[pn])
    fighter_costumes.append((pn, svg))
    headX.append(hx)
    headY.append(hy)
S.add_list("headX", headX)
S.add_list("headY", headY)

SOUNDS = assets.sounds()


def add_sounds(t, names):
    for n in names:
        data, cnt = SOUNDS[n]
        t.add_sound(n, data, assets.RATE, cnt)


# ------------------------------------------------------------------ sprites
# ordre des couches : AccJoueur / AccBot d'abord (leur thread tourne après celui des combattants)
accP1 = P.sprite("AccJoueur")
accBot = P.sprite("AccBot")
joueur = P.sprite("Joueur")
bot = P.sprite("Bot")
fx = P.sprite("FX")
ui = P.sprite("Interface")

for t in (joueur, bot):
    for pn, svg in fighter_costumes:
        t.add_costume(pn, svg, assets.FEET[0], assets.FEET[1])
    t.rotation_style = "left-right"
    t.size = 85
    t.y = GROUND
    add_sounds(t, ["hit", "kick", "block", "jump", "special", "ko"])
joueur.x, bot.x = -120, 120
bot.direction = -90

for t in (accP1, accBot):
    for an, svg in assets.accessory_svgs().items():
        t.add_costume(an, svg, 45, 50)
    t.rotation_style = "left-right"
    t.visible = False

for fn, svg in assets.fx_svgs().items():
    fx.add_costume(fn, svg, {"spark": 30, "dot": 12, "ring": 40, "bolt": 20, "pixel": 2}[fn],
                   {"spark": 30, "dot": 12, "ring": 40, "bolt": 30, "pixel": 2}[fn])
fx.visible = False

for gname, svg, cx, cy, adv in glyphs:
    ui.add_costume(gname, svg, cx, cy)
ui.visible = False
add_sounds(ui, ["click", "coin", "win", "lose", "round", "ko"])

# ================================================================== INTERFACE (moteur texte + écrans)
U = ui
for v in ["cx", "i", "ch", "prefix", "bx", "by", "bw", "bh", "hover", "k", "ratio", "px", "py", "col", "n"]:
    U.add_var(v, 0)

# --- bloc : rect x y w h couleur transparence  (x = bord gauche, y = centre vertical, coins arrondis)
U.script(define("rect %s %s %s %s %s %s", ["x", "y", "w", "h", "couleur", "transp"], [
    pen_up(),
    pen_color(arg("couleur")),
    pen_param("transparency", arg("transp")),
    if_else(lt(arg("w"), arg("h")), [
        pen_size(arg("w")),
        goto_xy(add(arg("x"), div(arg("w"), 2)), arg("y")),
        pen_down(), pen_up(),
    ], [
        if_else(gt(arg("h"), 48), [
            # grand panneau : coins arrondis de rayon 24, rempli par bandes
            set_var("px", 24),
            set_var("n", mathop("ceiling", div(sub(arg("h"), 24), 12))),
            set_var("py", sub(add(arg("y"), div(arg("h"), 2)), 12)),
            pen_size(24),
            repeat(add(var("n"), 1), [
                goto_xy(add(arg("x"), 12), var("py")),
                pen_down(),
                goto_xy(sub(add(arg("x"), arg("w")), 12), var("py")),
                pen_up(),
                change_var("py", -12),
                if_(lt(var("py"), add(sub(arg("y"), div(arg("h"), 2)), 12)), [set_var("py", add(sub(arg("y"), div(arg("h"), 2)), 12))]),
            ]),
            # cœur du panneau (sans double alpha : une seule bande large)
        ], [
            pen_size(arg("h")),
            goto_xy(add(arg("x"), div(arg("h"), 2)), arg("y")),
            pen_down(),
            goto_xy(sub(add(arg("x"), arg("w")), div(arg("h"), 2)), arg("y")),
            pen_up(),
        ]),
    ]),
]))

# --- bloc : mesurer texte taille -> textW
U.script(define("mesurer %s %s", ["txt", "taille"], [
    set_var("textW", 0),
    set_var("i", 1),
    repeat(strlen(arg("txt")), [
        set_var("ch", letter(var("i"), arg("txt"))),
        if_else(eq(var("ch"), " "), [
            change_var("textW", mul(13, div(arg("taille"), 100))),
        ], [
            switch_costume(join("W", var("ch"))),
            change_var("textW", mul(item("glyphW", costume_number()), div(arg("taille"), 100))),
        ]),
        change_var("i", 1),
    ]),
]))

# --- bloc : ecrire texte x y taille couleur align   (couleur : -1 blanc, -2 gris, -3 noir, sinon teinte 0..200)
U.script(define("ecrire %s %s %s %s %s %s", ["txt", "x", "y", "taille", "couleur", "align"], [
    set_size(arg("taille")),
    clear_effects(),
    set_var("prefix", "W"),
    if_(eq(arg("couleur"), -2), [set_effect("GHOST", 55)]),
    if_(eq(arg("couleur"), -3), [set_effect("BRIGHTNESS", -100)]),
    if_(gt(arg("couleur"), -1), [set_var("prefix", "C"), set_effect("COLOR", arg("couleur"))]),
    call("mesurer %s %s", arg("txt"), arg("taille")),
    set_var("cx", arg("x")),
    if_(eq(arg("align"), 1), [change_var("cx", mul(-0.5, var("textW")))]),
    if_(eq(arg("align"), 2), [change_var("cx", mul(-1, var("textW")))]),
    set_var("i", 1),
    repeat(strlen(arg("txt")), [
        set_var("ch", letter(var("i"), arg("txt"))),
        if_else(eq(var("ch"), " "), [
            change_var("cx", mul(13, div(arg("taille"), 100))),
        ], [
            switch_costume(join(var("prefix"), var("ch"))),
            goto_xy(var("cx"), arg("y")),
            pen_stamp(),
            change_var("cx", mul(item("glyphW", costume_number()), div(arg("taille"), 100))),
        ]),
        change_var("i", 1),
    ]),
    clear_effects(),
]))

# --- bloc : bouton x y w h label id couleur taille  (x,y = centre)
U.script(define("bouton %s %s %s %s %s %s %s %s", ["x", "y", "w", "h", "label", "id", "couleur", "taille"], [
    set_var("hover", 0),
    if_(and_(lt(abs_(sub(mouse_x(), arg("x"))), div(arg("w"), 2)),
             lt(abs_(sub(mouse_y(), arg("y"))), div(arg("h"), 2))), [
        if_(not_(eq(arg("id"), "")), [set_var("hover", 1), set_var("hoverBtn", arg("id"))]),
    ]),
    # ombre
    call("rect %s %s %s %s %s %s", sub(arg("x"), div(arg("w"), 2)), sub(arg("y"), 4), arg("w"), arg("h"), "#000000", 60),
    # contour blanc au survol
    if_(eq(var("hover"), 1), [
        call("rect %s %s %s %s %s %s", sub(sub(arg("x"), div(arg("w"), 2)), 3), arg("y"), add(arg("w"), 6), add(arg("h"), 6), "#ffffff", 0),
    ]),
    # fond
    pen_color(arg("couleur")),
    pen_param("transparency", 0),
    pen_size(arg("h")),
    goto_xy(sub(add(arg("x"), div(arg("h"), 2)), div(arg("w"), 2)), arg("y")),
    pen_down(),
    goto_xy(sub(add(arg("x"), div(arg("w"), 2)), div(arg("h"), 2)), arg("y")),
    pen_up(),
    # texte centré (légèrement au-dessus de la ligne de base)
    if_else(eq(arg("id"), ""), [
        call("ecrire %s %s %s %s %s %s", arg("label"), arg("x"), sub(arg("y"), mul(0.36, mul(arg("taille"), 0.4))), arg("taille"), -2, 1),
    ], [
        call("ecrire %s %s %s %s %s %s", arg("label"), arg("x"), sub(arg("y"), mul(0.36, mul(arg("taille"), 0.4))), arg("taille"), -1, 1),
    ]),
]))

# --- bloc : barre de vie  x y w h ratio couleur direction(1 = se vide vers la droite, -1 vers la gauche)
U.script(define("barre %s %s %s %s %s %s %s", ["x", "y", "w", "h", "ratio", "couleur", "sens"], [
    call("rect %s %s %s %s %s %s", sub(arg("x"), 3), arg("y"), add(arg("w"), 6), add(arg("h"), 6), "#000000", 0),
    call("rect %s %s %s %s %s %s", arg("x"), arg("y"), arg("w"), arg("h"), COL["hpbg"], 0),
    if_(gt(arg("ratio"), 0), [
        if_else(eq(arg("sens"), 1), [
            call("rect %s %s %s %s %s %s", arg("x"), arg("y"), mul(arg("w"), arg("ratio")), arg("h"), arg("couleur"), 0),
        ], [
            call("rect %s %s %s %s %s %s", add(arg("x"), mul(arg("w"), sub(1, arg("ratio")))), arg("y"),
                 mul(arg("w"), arg("ratio")), arg("h"), arg("couleur"), 0),
        ]),
    ]),
]))


def ecrire(txt, x, y, taille, couleur=-1, align=1):
    return call("ecrire %s %s %s %s %s %s", txt, x, y, taille, couleur, align)


def rect(x, y, w, h, couleur, transp=0):
    return call("rect %s %s %s %s %s %s", x, y, w, h, couleur, transp)


def bouton(x, y, w, h, label, bid, couleur, taille=45):
    return call("bouton %s %s %s %s %s %s %s %s", x, y, w, h, label, bid, couleur, taille)


def barre(x, y, w, h, ratio, couleur, sens):
    return call("barre %s %s %s %s %s %s %s", x, y, w, h, ratio, couleur, sens)


# --- écran MENU
U.script(define("dessinerMenu", [], [
    rect(-240, 120, 480, 70, "#000000", 55),
    ecrire("ARENA CLASH", 3, 97, 115, -3, 1),
    ecrire("ARENA CLASH", 0, 100, 115, 178, 1),
    ecrire("Combat 2D - Arène - Bots - Cosmétiques", 0, 62, 36, -2, 1),
    bouton(80, 20, 200, 44, "JOUER", "jouer", COL["accent"], 50),
    bouton(80, -36, 200, 44, "BOUTIQUE", "boutique", COL["accent2"], 50),
    bouton(80, -92, 200, 44, "COMMANDES", "commandes", COL["grey"], 50),
    rect(-240, -150, 480, 40, "#000000", 40),
    ecrire(join(var("pieces"), " pièces"), -228, -156, 40, 30, 0),
    ecrire(join("Niveau max : ", var("niveauMax")), 228, -156, 40, -1, 2),
    ecrire("Ton combattant", -150, -128, 32, -2, 1),
]))

# --- écran COMMANDES
U.script(define("dessinerCommandes", [], [
    rect(-200, 0, 400, 300, COL["panel"], 15),
    ecrire("COMMANDES", 0, 105, 80, 30, 1),
    ecrire("Flèches gauche / droite : se déplacer", 0, 60, 40, -1, 1),
    ecrire("Flèche haut : sauter", 0, 32, 40, -1, 1),
    ecrire("Flèche bas : garde (bloque les coups)", 0, 4, 40, -1, 1),
    ecrire("J : coup de poing (rapide)", 0, -24, 40, 100, 1),
    ecrire("K : coup de pied (puissant)", 0, -52, 40, 100, 1),
    ecrire("L : SPÉCIAL quand la barre bleue est pleine", 0, -80, 40, 30, 1),
    ecrire("Gagne 2 rounds sur 3 pour remporter le combat !", 0, -112, 34, -2, 1),
    bouton(0, -150, 160, 40, "RETOUR", "menu", COL["grey"], 42),
]))

# --- écran SÉLECTION
sel = [
    rect(-240, 150, 480, 60, "#000000", 55),
    ecrire("CHOISIS TON ADVERSAIRE", 0, 136, 70, 30, 1),
    ecrire("Chaque victoire débloque le suivant", 0, 112, 32, -2, 1),
    set_var("k", 1),
]
sel.append(repeat(len(BOTS), [
    set_var("bx", -130),
    if_(gt(var("k"), 4), [set_var("bx", 10)]),
    set_var("by", sub(80, mul(sub(mod(sub(var("k"), 1), 4), 0), 0))),
    set_var("by", sub(75, mul(mod(sub(var("k"), 1), 4), 52))),
    if_else(gt(var("k"), var("niveauMax")), [
        bouton(var("bx"), var("by"), 130, 42, join(join(var("k"), ". "), "?????"), "", COL["grey"], 40),
    ], [
        if_else(eq(var("k"), var("niveauMax")), [
            bouton(var("bx"), var("by"), 130, 42, join(join(var("k"), ". "), item("botNom", var("k"))),
                   join("lvl", var("k")), COL["accent"], 40),
        ], [
            bouton(var("bx"), var("by"), 130, 42, join(join(var("k"), ". "), item("botNom", var("k"))),
                   join("lvl", var("k")), COL["ok"], 40),
        ]),
    ]),
    change_var("k", 1),
]))
sel += [
    rect(100, -30, 130, 210, "#000000", 50),
    if_else(gt(var("niveauApercu"), 0), [
        ecrire(item("botNom", var("niveauApercu")), 165, 55, 44, 30, 1),
        ecrire(join("PV : ", item("botPV", var("niveauApercu"))), 165, -112, 30, -1, 1),
        ecrire(join("Arène : ", item("botAreneNom", var("niveauApercu"))), 165, -128, 26, -2, 1),
    ], [
        ecrire("Survole un", 165, 0, 36, -2, 1),
        ecrire("adversaire", 165, -20, 36, -2, 1),
    ]),
    bouton(-60, -150, 160, 40, "RETOUR", "menu", COL["grey"], 42),
]
U.script(define("dessinerSelection", [], sel))

# --- écran BOUTIQUE
shop = [
    rect(-240, 150, 480, 60, "#000000", 55),
    ecrire("BOUTIQUE", 0, 136, 70, 178, 1),
    ecrire(join(var("pieces"), " pièces"), 225, 138, 40, 30, 2),
    ecrire("Accessoires", 80, 100, 40, -2, 1),
    set_var("k", 1),
]
shop.append(repeat(len(ACCS), [
    set_var("bx", add(-15, mul(mod(sub(var("k"), 1), 3), 95))),
    set_var("by", sub(72, mul(floor(div(sub(var("k"), 1), 3)), 44))),
    if_else(eq(item("accPossede", var("k")), 1), [
        if_else(eq(item("accId", var("k")), var("P1Acc")), [
            bouton(var("bx"), var("by"), 92, 36, item("accNom", var("k")), join("acc", var("k")), COL["ok"], 34),
        ], [
            bouton(var("bx"), var("by"), 92, 36, item("accNom", var("k")), join("acc", var("k")), COL["accent2"], 34),
        ]),
    ], [
        bouton(var("bx"), var("by"), 92, 36, join(item("accNom", var("k")), join(" ", item("accPrix", var("k")))),
               join("acc", var("k")), COL["grey"], 30),
    ]),
    change_var("k", 1),
]))
shop += [
    ecrire("Couleurs", 80, -72, 40, -2, 1),
    set_var("k", 1),
    repeat(len(SKINS), [
        set_var("bx", add(-45, mul(sub(var("k"), 1), 50))),
        set_var("by", -100),
        if_else(eq(item("skinPossede", var("k")), 1), [
            if_else(eq(var("k"), var("P1Skin")), [
                bouton(var("bx"), var("by"), 46, 34, item("skinNom", var("k")), join("skin", var("k")), COL["ok"], 26),
            ], [
                bouton(var("bx"), var("by"), 46, 34, item("skinNom", var("k")), join("skin", var("k")), COL["accent2"], 26),
            ]),
        ], [
            bouton(var("bx"), var("by"), 46, 34, item("skinPrix", var("k")), join("skin", var("k")), COL["grey"], 26),
        ]),
        change_var("k", 1),
    ]),
    ecrire("Clique pour acheter puis pour équiper", 80, -134, 28, -2, 1),
    bouton(-150, -150, 150, 40, "RETOUR", "menu", COL["grey"], 42),
    ecrire("Aperçu", -150, 90, 36, -2, 1),
]
U.script(define("dessinerBoutique", [], shop))

# --- HUD combat
hud = [
    # barres de vie
    barre(-230, 150, 200, 16, div(var("P1HP"), var("P1Max")), COL["hp"], -1),
    barre(30, 150, 200, 16, div(var("BotHP"), var("BotMax")), COL["hp"], 1),
    # barres spéciales
    barre(-230, 132, 120, 7, div(var("P1Special"), 100), COL["sp"], -1),
    barre(110, 132, 120, 7, div(var("BotSpecial"), 100), COL["sp"], 1),
    ecrire("TOI", -228, 158, 30, -1, 0),
    ecrire(var("BotNom"), 228, 158, 30, -1, 2),
    # chrono
    rect(-30, 150, 60, 34, COL["panel"], 0),
    ecrire(mathop("ceiling", div(var("chrono"), FPS)), 0, 141, 55, -1, 1),
    # points de round
    set_var("k", 0),
    repeat(2, [
        if_else(gt(var("victoiresP1"), var("k")), [rect(sub(-60, mul(var("k"), 16)), 118, 12, 12, COL["warn"], 0)],
                [rect(sub(-60, mul(var("k"), 16)), 118, 12, 12, COL["grey"], 0)]),
        if_else(gt(var("victoiresBot"), var("k")), [rect(add(48, mul(var("k"), 16)), 118, 12, 12, COL["warn"], 0)],
                [rect(add(48, mul(var("k"), 16)), 118, 12, 12, COL["grey"], 0)]),
        change_var("k", 1),
    ]),
    if_(and_(eq(var("P1Special"), 100), lt(mod(var("frame"), 20), 10)), [
        ecrire("SPÉCIAL PRÊT (L)", -228, 108, 26, 100, 0),
    ]),
    if_(gt(var("comboP1"), 1), [
        ecrire(join(var("comboP1"), " HITS !"), -228, 80, 44, 30, 0),
    ]),
    if_(not_(eq(var("message"), "")), [
        ecrire(var("message"), 3, 27, 90, -3, 1),
        ecrire(var("message"), 0, 30, 90, 30, 1),
    ]),
    if_(and_(eq(var("phase"), "intro"), eq(var("round"), 1)), [
        ecrire("Flèches : bouger / sauter / garde   J : poing   K : pied   L : spécial", 0, -160, 28, -2, 1),
    ]),
    if_(gt(var("flash"), 0), [
        rect(-260, 0, 520, 400, "#ffffff", sub(100, mul(var("flash"), 12))),
        change_var("flash", -1),
    ]),
]
U.script(define("dessinerHUD", [], hud))

# --- écran RÉSULTAT
res = [
    rect(-260, 0, 520, 400, "#000000", 45),
    rect(-170, 20, 340, 200, COL["panel"], 10),
    if_else(eq(var("resultat"), "victoire"), [
        ecrire("VICTOIRE !", 3, 77, 110, -3, 1),
        ecrire("VICTOIRE !", 0, 80, 110, 30, 1),
        ecrire(join(join("Tu as battu ", var("BotNom")), " !"), 0, 45, 40, -1, 1),
    ], [
        ecrire("DÉFAITE", 3, 77, 110, -3, 1),
        ecrire("DÉFAITE", 0, 80, 110, 0, 1),
        ecrire(join(var("BotNom"), " était trop fort..."), 0, 45, 40, -1, 1),
    ]),
    ecrire(join(join("+ ", var("gain")), " pièces"), 0, 10, 60, 30, 1),
    if_(eq(var("dernierNiveauGagne"), 1), [ecrire("Nouvel adversaire débloqué !", 0, -20, 36, 67, 1)]),
    bouton(-105, -60, 130, 40, "REJOUER", "rejouer", COL["accent2"], 40),
    if_else(and_(eq(var("resultat"), "victoire"), lt(var("niveau"), len(BOTS))), [
        bouton(35, -60, 130, 40, "SUIVANT", "suivant", COL["accent"], 40),
    ], [
        bouton(35, -60, 130, 40, "BOUTIQUE", "boutique", COL["accent"], 40),
    ]),
    bouton(-35, -110, 130, 40, "MENU", "menu", COL["grey"], 40),
]
U.script(define("dessinerResultat", [], res))

U.script(define("nouveauRound", [], [
    set_var("P1HP", var("P1Max")), set_var("BotHP", var("BotMax")),
    set_var("P1Special", 0), set_var("BotSpecial", 0), set_var("P1Hit", 0), set_var("BotHit", 0),
    set_var("chrono", ROUND_SECONDS * FPS), set_var("comboP1", 0), set_var("hitStop", 0),
    set_var("phase", "intro"), set_var("phaseTimer", 45),
    set_var("message", join("ROUND ", var("round"))),
    play_sound("round"),
    broadcast("resetRound"),
]))

# --- lancer un combat (niveau courant)
U.script(define("lancerCombat", [], [
    set_var("BotNom", item("botNom", var("niveau"))),
    set_var("BotTeinte", item("botTeinte", var("niveau"))),
    set_var("BotLum", item("botLum", var("niveau"))),
    set_var("BotMax", item("botPV", var("niveau"))),
    set_var("BotVitesse", item("botVitesse", var("niveau"))),
    set_var("BotAggro", item("botAggro", var("niveau"))),
    set_var("BotGarde", item("botGarde", var("niveau"))),
    set_var("BotReaction", item("botReaction", var("niveau"))),
    set_var("BotSize", item("botTaille", var("niveau"))),
    set_var("BotAcc", item("botAccessoire", var("niveau"))),
    switch_backdrop(item("botArene", var("niveau"))),
    set_var("victoiresP1", 0), set_var("victoiresBot", 0), set_var("round", 1),
    set_var("dernierNiveauGagne", 0),
    set_var("scene", "fight"),
    call("nouveauRound"),
]))

# --- gestion des clics
click_logic = [
    if_(eq(var("clic"), "jouer"), [set_var("scene", "select"), set_var("niveauApercu", 0)]),
    if_(eq(var("clic"), "boutique"), [set_var("scene", "shop")]),
    if_(eq(var("clic"), "commandes"), [set_var("scene", "commandes")]),
    if_(eq(var("clic"), "menu"), [set_var("scene", "menu"), switch_backdrop("menu"), broadcast("resetRound")]),
    if_(eq(var("clic"), "rejouer"), [call("lancerCombat")]),
    if_(eq(var("clic"), "suivant"), [change_var("niveau", 1), call("lancerCombat")]),
    # niveaux
    if_(eq(join(letter(1, var("clic")), join(letter(2, var("clic")), letter(3, var("clic")))), "lvl"), [
        set_var("niveau", join(letter(4, var("clic")), "")),
        set_var("niveau", add(var("niveau"), 0)),
        call("lancerCombat"),
    ]),
    # accessoires
    if_(eq(join(letter(1, var("clic")), join(letter(2, var("clic")), letter(3, var("clic")))), "acc"), [
        set_var("k", add(letter(4, var("clic")), 0)),
        if_else(eq(item("accPossede", var("k")), 1), [
            set_var("P1Acc", item("accId", var("k"))),
        ], [
            if_else(ge(var("pieces"), item("accPrix", var("k"))), [
                change_var("pieces", mul(-1, item("accPrix", var("k")))),
                list_replace("accPossede", var("k"), 1),
                set_var("P1Acc", item("accId", var("k"))),
                play_sound("coin"),
            ], [
                set_var("message", "Pas assez de pièces !"), set_var("phaseTimer", 40),
            ]),
        ]),
    ]),
    # couleurs
    if_(eq(join(letter(1, var("clic")), join(letter(2, var("clic")), join(letter(3, var("clic")), letter(4, var("clic"))))), "skin"), [
        set_var("k", add(letter(5, var("clic")), 0)),
        if_else(eq(item("skinPossede", var("k")), 1), [
            set_var("P1Skin", var("k")),
        ], [
            if_else(ge(var("pieces"), item("skinPrix", var("k"))), [
                change_var("pieces", mul(-1, item("skinPrix", var("k")))),
                list_replace("skinPossede", var("k"), 1),
                set_var("P1Skin", var("k")),
                play_sound("coin"),
            ], [
                set_var("message", "Pas assez de pièces !"), set_var("phaseTimer", 40),
            ]),
        ]),
        set_var("P1Teinte", item("skinTeinte", var("P1Skin"))),
        set_var("P1Lum", item("skinLum", var("P1Skin"))),
    ]),
]
U.script(define("gererClic", [], click_logic))

# --- logique de round (appelée chaque frame en combat)
round_logic = [
    if_(gt(var("hitStop"), 0), [change_var("hitStop", -1)]),
    if_(eq(var("phase"), "intro"), [
        change_var("phaseTimer", -1),
        if_(eq(var("phaseTimer"), 0), [
            set_var("message", "FIGHT !"), set_var("phase", "fight"), set_var("phaseTimer", 20),
        ]),
    ]),
    if_(eq(var("phase"), "fight"), [
        if_(gt(var("phaseTimer"), 0), [
            change_var("phaseTimer", -1),
            if_(eq(var("phaseTimer"), 0), [set_var("message", "")]),
        ]),
        if_(eq(var("hitStop"), 0), [change_var("chrono", -1)]),
        if_(or_(or_(lt(var("P1HP"), 1), lt(var("BotHP"), 1)), lt(var("chrono"), 1)), [
            set_var("phase", "fin"), set_var("phaseTimer", 75), set_var("flash", 8),
            if_else(lt(var("chrono"), 1), [set_var("message", "TEMPS !")], [set_var("message", "K.O. !"), play_sound("ko")]),
            if_else(gt(var("P1HP"), var("BotHP")), [
                change_var("victoiresP1", 1), set_var("P1State", "win"), set_var("BotState", "ko"),
            ], [
                if_else(lt(var("P1HP"), var("BotHP")), [
                    change_var("victoiresBot", 1), set_var("BotState", "win"), set_var("P1State", "ko"),
                ], [
                    set_var("P1State", "ko"), set_var("BotState", "ko"),
                ]),
            ]),
        ]),
    ]),
    if_(eq(var("phase"), "fin"), [
        change_var("phaseTimer", -1),
        if_(eq(var("phaseTimer"), 40), [
            if_(gt(var("victoiresP1"), var("victoiresBot")), [set_var("message", "Round pour toi !")]),
            if_(lt(var("victoiresP1"), var("victoiresBot")), [set_var("message", join("Round pour ", var("BotNom")))]),
            if_(eq(var("victoiresP1"), var("victoiresBot")), [set_var("message", "Égalité")]),
        ]),
        if_(eq(var("phaseTimer"), 0), [
            if_else(or_(gt(var("victoiresP1"), 1), gt(var("victoiresBot"), 1)), [
                # fin du match
                set_var("scene", "result"), set_var("message", ""),
                if_else(gt(var("victoiresP1"), 1), [
                    set_var("resultat", "victoire"),
                    set_var("gain", add(40, mul(30, var("niveau")))),
                    if_(and_(eq(var("niveau"), var("niveauMax")), lt(var("niveauMax"), len(BOTS))), [
                        change_var("niveauMax", 1), set_var("dernierNiveauGagne", 1),
                    ]),
                    play_sound("win"),
                ], [
                    set_var("resultat", "defaite"), set_var("gain", 10), play_sound("lose"),
                ]),
                change_var("pieces", var("gain")),
            ], [
                change_var("round", 1),
                call("nouveauRound"),
            ]),
        ]),
    ]),
]
U.script(define("logiqueRound", [], round_logic))

# --- boucle principale
U.script(
    when_flag(),
    hide(),
    set_var("scene", "menu"),
    set_var("message", ""),
    set_var("hoverBtn", ""), set_var("clic", ""), set_var("sourisAvant", 1), set_var("frame", 0),
    set_var("niveauApercu", 0),
    set_var("P1Teinte", item("skinTeinte", var("P1Skin"))),
    set_var("P1Lum", item("skinLum", var("P1Skin"))),
    switch_backdrop("menu"),
    pen_clear(),
    forever([
        change_var("frame", 1),
        pen_clear(),
        set_var("hoverBtn", ""),
        if_(eq(var("scene"), "menu"), [call("dessinerMenu")]),
        if_(eq(var("scene"), "commandes"), [call("dessinerCommandes")]),
        if_(eq(var("scene"), "select"), [
            call("dessinerSelection"),
            set_var("niveauApercu", 0),
            if_(eq(join(letter(1, var("hoverBtn")), join(letter(2, var("hoverBtn")), letter(3, var("hoverBtn")))), "lvl"), [
                set_var("niveauApercu", add(letter(4, var("hoverBtn")), 0)),
            ]),
        ]),
        if_(eq(var("scene"), "shop"), [
            call("dessinerBoutique"),
            if_(gt(var("phaseTimer"), 0), [
                change_var("phaseTimer", -1),
                ecrire(var("message"), 80, -160, 36, 0, 1),
            ]),
        ]),
        if_(eq(var("scene"), "fight"), [call("logiqueRound"), call("dessinerHUD")]),
        if_(eq(var("scene"), "result"), [call("dessinerResultat")]),
        # clic
        set_var("clic", ""),
        if_else(mouse_down(), [
            if_(eq(var("sourisAvant"), 0), [
                set_var("clic", var("hoverBtn")),
                if_(not_(eq(var("clic"), "")), [play_sound("click"), call("gererClic")]),
            ]),
            set_var("sourisAvant", 1),
        ], [set_var("sourisAvant", 0)]),
    ]),
)


# ================================================================== COMBATTANTS
def fighter_scripts(t, me, op, is_player):
    for v in ["vx", "vy", "timer", "hitDone", "anim", "iMove", "iJump", "iPunch", "iKick", "iSpecial", "iBlock",
              "aiTimer", "attaqueTenue", "dx", "f", "dmg", "portee", "aStart", "aEnd", "aTotal", "dist", "r"]:
        t.add_var(v, 0)

    def V(n):
        return var(me + n)

    def OV(n):
        return var(op + n)

    def setV(n, val):
        return set_var(me + n, val)

    def chV(n, val):
        return change_var(me + n, val)

    state = V("State")

    def st_is(*names):
        c = eq(state, names[0])
        for n in names[1:]:
            c = or_(c, eq(state, n))
        return c

    reset_pose = [
        set_var("vx", 0), set_var("vy", 0), set_var("timer", 0), set_var("hitDone", 0), set_var("attaqueTenue", 0),
        setV("State", "idle"),
        setV("X", -120 if is_player else 120), setV("Y", GROUND), setV("Dir", 90 if is_player else -90),
        goto_xy(V("X"), V("Y")), point_dir(V("Dir")), switch_costume("idle"), show(),
    ]
    t.script(when_broadcast("resetRound"), reset_pose)

    # ----- intentions
    if is_player:
        intents = [
            set_var("iMove", 0),
            if_(key_pressed("right arrow"), [set_var("iMove", 1)]),
            if_(key_pressed("left arrow"), [set_var("iMove", -1)]),
            set_var("iJump", 0), if_(key_pressed("up arrow"), [set_var("iJump", 1)]),
            set_var("iBlock", 0), if_(key_pressed("down arrow"), [set_var("iBlock", 1)]),
            set_var("iPunch", 0), set_var("iKick", 0), set_var("iSpecial", 0),
            if_else(or_(or_(key_pressed("j"), key_pressed("k")), key_pressed("l")), [
                if_(eq(var("attaqueTenue"), 0), [
                    if_(key_pressed("j"), [set_var("iPunch", 1)]),
                    if_(key_pressed("k"), [set_var("iKick", 1)]),
                    if_(key_pressed("l"), [set_var("iSpecial", 1)]),
                ]),
                set_var("attaqueTenue", 1),
            ], [set_var("attaqueTenue", 0)]),
        ]
    else:
        intents = [
            if_else(gt(var("aiTimer"), 0), [
                change_var("aiTimer", -1),
                set_var("iPunch", 0), set_var("iKick", 0), set_var("iSpecial", 0), set_var("iJump", 0),
            ], [
                set_var("aiTimer", var("BotReaction")),
                set_var("iMove", 0), set_var("iJump", 0), set_var("iBlock", 0),
                set_var("iPunch", 0), set_var("iKick", 0), set_var("iSpecial", 0),
                set_var("dist", abs_(sub(OV("X"), V("X")))),
                set_var("r", random(1, 100)),
                if_else(and_(or_(eq(OV("State"), "punch"), or_(eq(OV("State"), "kick"), eq(OV("State"), "special"))),
                             and_(lt(var("dist"), 120), le(var("r"), var("BotGarde")))), [
                    set_var("iBlock", 1),
                ], [
                    if_else(gt(var("dist"), 90), [
                        if_else(gt(OV("X"), V("X")), [set_var("iMove", 1)], [set_var("iMove", -1)]),
                        if_(lt(var("r"), 3), [set_var("iJump", 1)]),
                        if_(and_(eq(V("Special"), 100), lt(var("r"), 40)), [set_var("iMove", 0)]),
                    ], [
                        if_else(and_(eq(V("Special"), 100), lt(var("r"), add(var("BotAggro"), 15))), [
                            set_var("iSpecial", 1),
                        ], [
                            if_else(le(var("r"), var("BotAggro")), [
                                if_else(lt(var("r"), div(var("BotAggro"), 2)), [set_var("iPunch", 1)], [set_var("iKick", 1)]),
                            ], [
                                if_(gt(var("r"), 88), [
                                    if_else(gt(OV("X"), V("X")), [set_var("iMove", -1)], [set_var("iMove", 1)]),
                                ]),
                                if_(and_(gt(var("r"), 85), lt(var("r"), 89)), [set_var("iJump", 1)]),
                            ]),
                        ]),
                    ]),
                ]),
            ]),
        ]

    hit_fx = [set_var("fxX", V("X")), set_var("fxY", add(V("Y"), mul(0.65, V("Size")))), set_var("fxTeinte", 0)]

    # ----- réception des dégâts
    take_hit = [
        if_(gt(V("Hit"), 0), [
            if_else(and_(eq(state, "block"), not_(eq(V("Dir"), mul(90, V("HitDir"))))), [
                # coup bloqué (on fait face à l'attaquant)
                chV("HP", mul(-1, mathop("ceiling", mul(V("Hit"), 0.12)))),
                set_var("vx", mul(V("HitDir"), 4)),
                chV("Special", 4),
                play_sound("block"),
                set_var("fxType", "ring"),
            ] + hit_fx + [create_clone("FX")], [
                chV("HP", mul(-1, V("Hit"))),
                setV("State", "hurt"), set_var("timer", 14),
                set_var("vx", mul(V("HitDir"), 7)), set_var("vy", 4),
                chV("Special", 8),
                set_var("hitStop", 3),
                play_sound("hit"),
                set_var("fxType", "spark"),
            ] + hit_fx + [create_clone("FX"), set_var("fxType", "dot"), repeat(6, [create_clone("FX")])]),
            if_(gt(V("Special"), 100), [setV("Special", 100)]),
            if_(lt(V("HP"), 0), [setV("HP", 0)]),
            setV("Hit", 0),
        ]),
    ]

    # ----- démarrage d'actions
    speed = var("P1Vitesse") if is_player else var("BotVitesse")
    start_actions = [
        if_(st_is("idle", "walk", "block"), [
            if_else(and_(eq(var("iBlock"), 1), and_(eq(V("Y"), GROUND), not_(eq(state, "hurt")))), [
                setV("State", "block"), set_var("vx", 0),
            ], [
                if_(eq(state, "block"), [setV("State", "idle")]),
                if_else(eq(var("iPunch"), 1), [
                    setV("State", "punch"), set_var("timer", PUNCH["total"]), set_var("hitDone", 0),
                ], [
                    if_else(eq(var("iKick"), 1), [
                        setV("State", "kick"), set_var("timer", KICK["total"]), set_var("hitDone", 0),
                    ], [
                        if_else(and_(eq(var("iSpecial"), 1), eq(V("Special"), 100)), [
                            setV("State", "special"), set_var("timer", SPECIAL["total"]), set_var("hitDone", 0),
                            setV("Special", 0), play_sound("special"),
                            set_var("fxType", "bolt"), set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 60)),
                            repeat(3, [create_clone("FX")]),
                        ], [
                            # déplacement
                            set_var("vx", mul(var("iMove"), speed)),
                            if_else(eq(var("iMove"), 0), [setV("State", "idle")], [setV("State", "walk")]),
                            if_(and_(eq(var("iJump"), 1), eq(V("Y"), GROUND)), [
                                set_var("vy", 13), play_sound("jump"),
                            ]),
                        ]),
                    ]),
                ]),
            ]),
        ]),
    ]

    # ----- résolution des attaques
    def attack_block(name, spec):
        return if_(eq(state, name), [
            set_var("f", sub(spec["total"], var("timer"))),
            if_(and_(eq(var("hitDone"), 0), and_(ge(var("f"), spec["start"]), lt(var("f"), spec["end"]))), [
                set_var("dx", sub(OV("X"), V("X"))),
                if_(and_(lt(abs_(var("dx")), spec["range"]),
                         and_(gt(mul(var("dx"), V("Dir")), -1), lt(abs_(sub(OV("Y"), V("Y"))), 80))), [
                    if_(not_(eq(OV("State"), "ko")), [
                        set_var("hitDone", 1),
                        set_var(op + "Hit", spec["dmg"]),
                        if_else(gt(var("dx"), 0), [set_var(op + "HitDir", 1)], [set_var(op + "HitDir", -1)]),
                        chV("Special", 12),
                        if_(gt(V("Special"), 100), [setV("Special", 100)]),
                    ] + ([change_var("comboP1", 1)] if is_player else [set_var("comboP1", 0)])
                      + ([play_sound("kick")] if name != "punch" else [])),
                ]),
            ]),
        ])

    attacks = [attack_block("punch", PUNCH), attack_block("kick", KICK), attack_block("special", SPECIAL)]

    # ----- physique
    physics = [
        chV("X", var("vx")),
        change_var("vy", -0.8),
        chV("Y", var("vy")),
        if_(lt(V("Y"), GROUND), [setV("Y", GROUND), set_var("vy", 0)]),
        if_(not_(eq(state, "walk")), [set_var("vx", mul(var("vx"), 0.7))]),
        if_(lt(abs_(var("vx")), 0.3), [set_var("vx", 0)]),
        if_(gt(V("X"), 205), [setV("X", 205)]),
        if_(lt(V("X"), -205), [setV("X", -205)]),
        # repousser les corps
        set_var("dx", sub(OV("X"), V("X"))),
        if_(and_(lt(abs_(var("dx")), 34), and_(not_(eq(state, "ko")), not_(eq(OV("State"), "ko")))), [
            if_else(gt(var("dx"), 0), [chV("X", -2)], [chV("X", 2)]),
            if_(eq(var("dx"), 0), [chV("X", -2 if is_player else 2)]),
        ]),
        # orientation
        if_(st_is("idle", "walk"), [
            if_(gt(var("dx"), 0), [setV("Dir", 90)]),
            if_(lt(var("dx"), 0), [setV("Dir", -90)]),
        ]),
        # timers
        if_(gt(var("timer"), 0), [
            change_var("timer", -1),
            if_(and_(eq(var("timer"), 0), st_is("punch", "kick", "special", "hurt")), [setV("State", "idle")]),
        ]),
    ]

    # ----- costume
    costume = [
        change_var("anim", 1),
        if_(eq(state, "idle"), [
            if_else(lt(mod(var("anim"), 30), 15), [switch_costume("idle")], [switch_costume("idle2")]),
        ]),
        if_(eq(state, "walk"), [
            if_else(lt(mod(var("anim"), 12), 6), [switch_costume("walk1")], [switch_costume("walk2")]),
        ]),
        if_(and_(st_is("idle", "walk"), gt(V("Y"), GROUND)), [switch_costume("jump")]),
        if_(eq(state, "block"), [switch_costume("block")]),
        if_(eq(state, "hurt"), [switch_costume("hurt")]),
        if_(eq(state, "ko"), [switch_costume("ko")]),
        if_(eq(state, "win"), [switch_costume("win")]),
        if_(eq(state, "punch"), [
            if_else(lt(sub(PUNCH["total"], var("timer")), PUNCH["start"]), [switch_costume("idle2")], [switch_costume("punch")]),
        ]),
        if_(eq(state, "kick"), [
            if_else(lt(sub(KICK["total"], var("timer")), KICK["start"]), [switch_costume("walk1")], [switch_costume("kick")]),
        ]),
        if_(eq(state, "special"), [
            if_else(lt(sub(SPECIAL["total"], var("timer")), SPECIAL["start"]), [switch_costume("block")], [switch_costume("special")]),
        ]),
    ]

    apply_look = [
        set_size(V("Size")),
        set_effect("COLOR", V("Teinte")),
        set_effect("BRIGHTNESS", V("Lum")),
        if_(eq(state, "hurt"), [set_effect("BRIGHTNESS", 60)]),
        goto_xy(V("X"), V("Y")),
        point_dir(V("Dir")),
        setV("Costume", costume_number()),
    ]

    # positions d'aperçu hors combat
    if is_player:
        preview = [
            if_else(or_(eq(var("scene"), "menu"), eq(var("scene"), "shop")), [
                show(), setV("Vis", 1),
                setV("Size", 85),
                setV("X", -150), setV("Y", -110), setV("Dir", 90),
                setV("State", "idle"), set_var("vx", 0), set_var("vy", 0),
                if_(eq(var("scene"), "menu"), [setV("State", "win")]),
                if_(and_(eq(var("scene"), "menu"), lt(mod(var("frame"), 60), 30)), [setV("State", "idle")]),
            ], [
                if_(eq(var("scene"), "select"), [hide(), setV("Vis", 0)]),
                if_(eq(var("scene"), "commandes"), [hide(), setV("Vis", 0)]),
            ]),
        ]
    else:
        preview = [
            if_else(and_(eq(var("scene"), "select"), gt(var("niveauApercu"), 0)), [
                show(), setV("Vis", 1),
                setV("Size", item("botTaille", var("niveauApercu"))),
                setV("Teinte", item("botTeinte", var("niveauApercu"))),
                setV("Lum", item("botLum", var("niveauApercu"))),
                setV("Acc", item("botAccessoire", var("niveauApercu"))),
                setV("X", 165), setV("Y", -92), setV("Dir", -90),
                setV("Size", mul(item("botTaille", var("niveauApercu")), 0.8)),
                setV("State", "idle"), set_var("vx", 0), set_var("vy", 0),
            ], [
                if_(not_(eq(var("scene"), "fight")), [hide(), setV("Vis", 0)]),
            ]),
        ]

    t.script(
        when_flag(),
        set_rotation_style("left-right"),
        setV("Hit", 0), setV("State", "idle"),
        set_var("anim", 0),
        forever([
            if_(eq(var("scene"), "fight"), [show(), setV("Vis", 1)] + ([setV("Size", 85)] if is_player else [])),
            if_(eq(var("scene"), "result"), [hide(), setV("Vis", 0)]),
            if_(eq(var("scene"), "fight"), [
                if_(and_(eq(var("phase"), "fight"), eq(var("hitStop"), 0)), [
                    *take_hit,
                    *intents,
                    *start_actions,
                    *attacks,
                ]),
                if_(and_(eq(var("phase"), "intro"), eq(var("hitStop"), 0)), [
                    if_(gt(var("timer"), 0), [set_var("timer", 0)]),
                ]),
                if_(eq(var("hitStop"), 0), [*physics]),
                if_(eq(var("phase"), "fin"), [
                    # le vainqueur pose, le perdant reste au sol
                    set_var("vx", mul(var("vx"), 0.8)),
                ]),
            ]),
            *preview,
            *costume,
            *apply_look,
        ]),
    )


fighter_scripts(joueur, "P1", "Bot", True)
fighter_scripts(bot, "Bot", "P1", False)


# ================================================================== ACCESSOIRES
def acc_scripts(t, me):
    t.script(
        when_flag(),
        set_rotation_style("left-right"),
        hide(),
        forever([
            if_else(and_(eq(var(me + "Vis"), 1), not_(eq(var(me + "Acc"), "aucun"))), [
                switch_costume(var(me + "Acc")),
                set_size(var(me + "Size")),
                point_dir(var(me + "Dir")),
                goto_xy(add(var(me + "X"), mul(mul(item("headX", var(me + "Costume")), div(var(me + "Dir"), 90)), div(var(me + "Size"), 100))),
                        add(var(me + "Y"), mul(item("headY", var(me + "Costume")), div(var(me + "Size"), 100)))),
                show(),
            ], [hide()]),
        ]),
    )


acc_scripts(accP1, "P1")
acc_scripts(accBot, "Bot")

# ================================================================== FX (clones)
fx.add_var("life", 0)
fx.add_var("vx", 0)
fx.add_var("vy", 0)
fx.script(when_flag(), hide())
fx.script(
    when_clone_start(),
    switch_costume(var("fxType")),
    goto_xy(var("fxX"), var("fxY")),
    clear_effects(),
    go_front(),
    if_(eq(var("fxType"), "spark"), [
        set_size(60), point_dir(random(-180, 180)), show(),
        repeat(7, [change_size(14), change_effect("GHOST", 14), Blk("motion_turnright", {"DEGREES": 12})]),
    ]),
    if_(eq(var("fxType"), "ring"), [
        set_size(30), point_dir(90), set_effect("COLOR", 100), show(),
        repeat(8, [change_size(18), change_effect("GHOST", 12)]),
    ]),
    if_(eq(var("fxType"), "dot"), [
        set_size(random(40, 90)), point_dir(90), set_effect("COLOR", var("fxTeinte")), show(),
        set_var("vx", random(-8, 8)), set_var("vy", random(2, 10)),
        repeat(14, [
            change_x(var("vx")), change_y(var("vy")), change_var("vy", -0.9), change_effect("GHOST", 7), change_size(-4),
        ]),
    ]),
    if_(eq(var("fxType"), "bolt"), [
        set_size(random(60, 110)), point_dir(90), show(),
        change_x(random(-40, 40)), change_y(random(-10, 40)),
        repeat(10, [change_y(6), change_effect("GHOST", 10)]),
    ]),
    delete_clone(),
)

# ================================================================== STAGE
S.script(when_flag(), switch_backdrop("menu"))

# ------------------------------------------------------------------ build
os.makedirs(os.path.dirname(OUT), exist_ok=True)
pj = P.build(OUT)
nblocks = sum(len(t["blocks"]) for t in pj["targets"])
print(f"OK -> {OUT}  ({os.path.getsize(OUT)//1024} Ko, {nblocks} blocs, {len(pj['targets'])} cibles)")
