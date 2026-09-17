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
    # nom, teinte, luminosité, PV, vitesse, aggro, garde, réaction, taille, arène, accessoire, arme de départ
    ("Kid Bleu", 133, 0, 70, 3.2, 25, 10, 14, 85, "dojo", "aucun", 1),
    ("Verdo", 67, 0, 85, 3.6, 35, 20, 12, 88, "dojo", "casquette", 1),
    ("Sunny", 30, 10, 100, 4.0, 45, 30, 10, 90, "toits", "lunettes", 1),
    ("Violette", 150, 0, 110, 4.4, 50, 40, 9, 92, "toits", "chat", 1),
    ("Cyan-X", 100, 0, 120, 4.8, 60, 45, 8, 95, "volcan", "bandeau", 6),
    ("Rosa", 178, 0, 130, 5.0, 65, 55, 7, 95, "volcan", "aureole", 5),
    ("Ombre", 0, -70, 150, 5.4, 75, 60, 5, 100, "cyber", "cornes", 2),
    ("Le Champion", 25, 20, 180, 5.8, 85, 70, 4, 108, "cyber", "couronne", 4),
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

# ------------------------------------------------------------------ ARMES
# Chaque arme modifie vraiment le combat : allonge, dégâts, vitesse de récupération,
# spécial remplacé, garde renforcée, projectiles...
#   nom, prix, costume, portee (+px sur poing et pied), dmgP, dmgK, totP, totK (frames totales),
#   spe (0 frappe, 1 estoc, 2 charge, 3 marteau, 4 tir), speDmg, speTot, spePortee, garde, proj,
#   ligne1, ligne2, ligne3 (description affichée dans la boutique)
ARMES = [
    ("Poings", 0, "fists", 0, 0, 0, 13, 20, 0, 24, 28, 100, 0, 0,
     "Mains nues, équilibre total.", "Poing 7, pied 11, spécial 24.", "Aucun bonus, aucune faiblesse."),
    ("Épée", 200, "epee", 48, 2, 2, 16, 24, 1, 26, 26, 128, 0, 0,
     "Frappe vite et loin.", "Allonge +48 px, poing 9, pied 13.", "Récupération plus longue."),
    ("Lance", 240, "lance", 72, -1, 0, 20, 30, 2, 30, 40, 168, 0, 0,
     "La plus grande allonge.", "Poing 6, pied 11, portée énorme.", "Spécial CHARGE 30 qui fonce."),
    ("Marteau", 280, "marteau", 32, 1, 2, 20, 32, 3, 34, 52, 112, 0, 0,
     "Brise la garde, très lent.", "Spécial MARTEAU 34, ignore la garde.", "52 images : très punissable."),
    ("Arc", 260, "arc", 22, -1, 0, 14, 24, 4, 30, 60, 150, 0, 1,
     "Combat à distance.", "K tire une flèche (13 dégâts).", "Spécial : triple tir (3 x 10)."),
    ("Bouclier", 220, "bouclier", -12, 1, -2, 16, 24, 0, 24, 28, 88, 1, 0,
     "Bloque sans rien subir.", "Garde : 0 dégât (12 % sinon).", "Garde brisée : 20 % au lieu de 50 %."),
]
ARME_NOM = [a[0] for a in ARMES]
ARME_PRIX = [a[1] for a in ARMES]
ARME_COST = [a[2] for a in ARMES]
ARME_PORTEE = [a[3] for a in ARMES]
ARME_DMGP = [a[4] for a in ARMES]
ARME_DMGK = [a[5] for a in ARMES]
ARME_TOTP = [a[6] for a in ARMES]
ARME_TOTK = [a[7] for a in ARMES]
ARME_SPE = [a[8] for a in ARMES]
ARME_SPEDMG = [a[9] for a in ARMES]
ARME_SPETOT = [a[10] for a in ARMES]
ARME_SPEPORTEE = [a[11] for a in ARMES]
ARME_GARDE = [a[12] for a in ARMES]
ARME_PROJ = [a[13] for a in ARMES]
ARME_L1 = [a[14] for a in ARMES]
ARME_L2 = [a[15] for a in ARMES]
ARME_L3 = [a[16] for a in ARMES]

# points d'apparition des armes au sol (x, y) : au sol ou en l'air (saut nécessaire)
SPAWNS = [(-185, GROUND), (185, GROUND), (-185, -8), (185, -8), (0, GROUND)]
PICKUP_DELAI = 4 * FPS       # délai avant qu'une arme repousse dans un emplacement libre
FLECHE_VITESSE = 11
FLECHE_DMG = 13
FLECHE_DMG_VOLLEY = 10

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
    ("dernierNiveauGagne", 0), ("P1Vis", 0), ("BotVis", 0), ("codeSauvegarde", ""), ("infoSauvegarde", ""), ("P1HitType", ""), ("BotHitType", ""),
    ("P1Arme", 1), ("BotArme", 1), ("P1ArmeOrig", 1), ("BotArmeOrig", 1), ("armeApercu", 1), ("shopPage", 1),
    ("solTimer", 0), ("solLibre", 0), ("solProcheX", 0), ("flX", 0), ("flY", 0), ("flDir", 90), ("flWho", 1), ("flDmg", 13),
    ("P1ArmeMain", 1), ("BotArmeMain", 1), ("armeMain", 1),
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
S.add_list("botArme", [b[11] for b in BOTS])
S.add_list("accId", [a[0] for a in ACCS])
S.add_list("accNom", [a[1] for a in ACCS])
S.add_list("accPrix", [a[2] for a in ACCS])
S.add_list("accPossede", [1] + [0] * (len(ACCS) - 1))
S.add_list("skinNom", [s[0] for s in SKINS])
S.add_list("skinTeinte", [s[1] for s in SKINS])
S.add_list("skinLum", [s[2] for s in SKINS])
S.add_list("skinPrix", [s[3] for s in SKINS])
S.add_list("skinPossede", [1] + [0] * (len(SKINS) - 1))
S.add_list("CODE DE SAUVEGARDE", [])
# --- armes : données de jeu + armes au sol (2 emplacements)
S.add_list("armeNom", ARME_NOM)
S.add_list("armePrix", ARME_PRIX)
S.add_list("armeCost", ARME_COST)
S.add_list("armePortee", ARME_PORTEE)
S.add_list("armeDmgP", ARME_DMGP)
S.add_list("armeDmgK", ARME_DMGK)
S.add_list("armeTotP", ARME_TOTP)
S.add_list("armeTotK", ARME_TOTK)
S.add_list("armeSpe", ARME_SPE)
S.add_list("armeSpeDmg", ARME_SPEDMG)
S.add_list("armeSpeTot", ARME_SPETOT)
S.add_list("armeSpePortee", ARME_SPEPORTEE)
S.add_list("armeGarde", ARME_GARDE)
S.add_list("armeProj", ARME_PROJ)
S.add_list("armeL1", ARME_L1)
S.add_list("armeL2", ARME_L2)
S.add_list("armeL3", ARME_L3)
S.add_list("armePossede", [1] + [0] * (len(ARMES) - 1))
S.add_list("solArme", [0, 0])          # 0 = emplacement vide, sinon index d'arme
S.add_list("solX", [SPAWNS[0][0], SPAWNS[1][0]])
S.add_list("solY", [SPAWNS[0][1], SPAWNS[1][1]])
S.add_list("solTimer", [0, 0])
S.add_list("spawnX", [p[0] for p in SPAWNS])
S.add_list("spawnY", [p[1] for p in SPAWNS])

# décors
for name, svg in assets.backdrops().items():
    S.add_costume(name, svg, 240, 180)

# glyphes (widths)
glyphs = assets.build_glyphs()
S.add_list("glyphW", [round(g[4], 2) for g in glyphs])

# costumes combattant + offsets tête
POSES = assets.fighter_poses()
POSE_ORDER = ["idle", "idle2", "walk1", "walk2", "jump", "punch", "kick", "special", "block", "hurt", "ko", "win"]
WEAPON_COSTUMES = ARME_COST  # une série de 12 poses par arme (l'arme est dessinée dans le costume)
fighter_costumes = []
headX, headY = [], []
for wid in WEAPON_COSTUMES:
    for pn in POSE_ORDER:
        pose = dict(POSES[pn])
        pose.update(assets.POSE_ARME.get(wid, {}).get(pn, {}))
        svg, (hx, hy), (ox, oy) = assets.fighter_svg(pose, pn, wid)
        fighter_costumes.append((wid + "_" + pn, svg, ox, oy))
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
# ordre des couches : les sprites créés plus tard sont dessinés devant, et leur boucle
# tourne après celle des sprites créés avant (positions d'une image plus fraîches).
# ArmeSol (fond) -> combattants -> accessoires (par-dessus la tête) -> FX/flèches -> Interface.
arme1 = P.sprite("ArmeSol1")      # armes au sol (derrière tout le reste)
arme2 = P.sprite("ArmeSol2")
joueur = P.sprite("Joueur")
bot = P.sprite("Bot")
accP1 = P.sprite("AccJoueur")      # accessoires de tête : devant les combattants
accBot = P.sprite("AccBot")
fx = P.sprite("FX")
fleche = P.sprite("Fleche")        # projectiles de l'arc
ui = P.sprite("Interface")

for t in (joueur, bot):
    for cname, svg, ox, oy in fighter_costumes:
        t.add_costume(cname, svg, ox, oy)
    t.rotation_style = "left-right"
    t.size = 85
    t.y = GROUND
    add_sounds(t, ["hit", "kick", "block", "jump", "special", "ko", "tir"])
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
ICONE_BASE = len(ui.costumes)  # les icônes d'armes viennent après les glyphes (glyphW indexé par n° de costume)
ui.add_costume("poings", assets.poing_icon_svg(), 60, 60)
for wid in ARME_COST[1:]:
    ui.add_costume(wid, assets.weapon_icon_svg(wid), 60, 60)

# armes au sol : mêmes icônes que le HUD (index de costume décalé de 1 : "poings" jamais au sol)
for t in (arme1, arme2):
    t.add_costume("poings", assets.poing_icon_svg(), 60, 60)
    for wid in ARME_COST[1:]:
        t.add_costume(wid, assets.weapon_icon_svg(wid), 60, 60)
    t.visible = False
add_sounds(arme1, ["coin"])
add_sounds(arme2, ["coin"])

# flèche de l'arc
fleche.add_costume("fleche", assets.arrow_svg(), 38, 10)
fleche.rotation_style = "all around"
fleche.visible = False
add_sounds(fleche, ["tir", "hit"])
ui.visible = False
add_sounds(ui, ["click", "coin", "win", "lose", "round", "ko"])

# ================================================================== INTERFACE (moteur texte + écrans)
U = ui
for v in ["cx", "i", "ch", "prefix", "bx", "by", "bw", "bh", "hover", "k", "ratio", "px", "py", "col", "n",
          "padded", "bits", "mult", "digits", "part", "somme", "ok", "pBitsArmes", "pArmeCode"]:
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


def icone_arme(arid, x, y, taille=30):
    """Vignette d'arme tamponnée au stylo (arid = index d'arme 1..6)."""
    return [
        switch_costume(add(ICONE_BASE, arid)),
        set_size(taille),
        goto_xy(x, y),
        pen_stamp(),
    ]



# --- sauvegarde : code numérique  N PPPPP AAA SS A S CC  (15 chiffres, affiché par groupes)
U.script(define("pad %s %s", ["valeur", "longueur"], [
    set_var("padded", join(arg("valeur"), "")),
    repeat_until(ge(strlen(var("padded")), arg("longueur")), [set_var("padded", join("0", var("padded")))]),
]))

U.script(define("extraire %s %s", ["debut", "longueur"], [
    set_var("part", ""),
    set_var("i", arg("debut")),
    repeat(arg("longueur"), [set_var("part", join(var("part"), letter(var("i"), var("digits")))), change_var("i", 1)]),
    set_var("part", add(var("part"), 0)),
]))

U.script(define("checksum %s %s %s %s %s %s", ["a", "b", "c", "d", "e", "f"], [
    set_var("somme", add(mul(arg("a"), 3), add(mul(arg("b"), 7), add(mul(arg("c"), 11),
                     add(mul(arg("d"), 13), add(mul(arg("e"), 17), mul(arg("f"), 19))))))),
    set_var("somme", mod(add(var("somme"), 29), 97)),
]))

U.script(define("genererCode", [], [
    # bits accessoires / couleurs possédés
    set_var("bits", 0), set_var("mult", 1), set_var("k", 1),
    repeat(len(ACCS), [
        if_(eq(item("accPossede", var("k")), 1), [change_var("bits", var("mult"))]),
        set_var("mult", mul(var("mult"), 2)), change_var("k", 1),
    ]),
    set_var("px", var("bits")),
    set_var("bits", 0), set_var("mult", 1), set_var("k", 1),
    repeat(len(SKINS), [
        if_(eq(item("skinPossede", var("k")), 1), [change_var("bits", var("mult"))]),
        set_var("mult", mul(var("mult"), 2)), change_var("k", 1),
    ]),
    set_var("py", var("bits")),
    set_var("bits", 0), set_var("mult", 1), set_var("k", 1),
    repeat(len(ARMES), [
        if_(eq(item("armePossede", var("k")), 1), [change_var("bits", var("mult"))]),
        set_var("mult", mul(var("mult"), 2)), change_var("k", 1),
    ]),
    set_var("pBitsArmes", var("bits")),          # 6 armes -> 2 chiffres
    set_var("pArmeCode", sub(var("P1Arme"), 1)),  # 0 = mains nues
    # l'arme équipée est forcément possédée : on allume son bit s'il ne l'est pas déjà
    # (on additionne un bit libre : jamais de retenue sur le bit suivant)
    set_var("bits", 1), set_var("k", 1),
    repeat(var("pArmeCode"), [set_var("bits", mul(var("bits"), 2)), change_var("k", 1)]),
    if_(not_(eq(item("armePossede", var("P1Arme")), 1)), [change_var("pBitsArmes", var("bits"))]),
    # index accessoire équipé
    set_var("n", 1), set_var("k", 1),
    repeat(len(ACCS), [if_(eq(item("accId", var("k")), var("P1Acc")), [set_var("n", var("k"))]), change_var("k", 1)]),
    if_(gt(var("pieces"), 99999), [set_var("pieces", 99999)]),
    call("checksum %s %s %s %s %s %s", var("niveauMax"), var("pieces"), var("px"), var("py"), var("n"), var("P1Skin")),
    set_var("codeSauvegarde", var("niveauMax")),
    call("pad %s %s", var("pieces"), 5), set_var("codeSauvegarde", join(var("codeSauvegarde"), var("padded"))),
    call("pad %s %s", var("px"), 3), set_var("codeSauvegarde", join(var("codeSauvegarde"), var("padded"))),
    call("pad %s %s", var("py"), 2), set_var("codeSauvegarde", join(var("codeSauvegarde"), var("padded"))),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), join(var("n"), var("P1Skin")))),
    call("pad %s %s", var("pBitsArmes"), 2), set_var("codeSauvegarde", join(var("codeSauvegarde"), var("padded"))),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), var("pArmeCode"))),
    call("pad %s %s", var("somme"), 2), set_var("codeSauvegarde", join(var("codeSauvegarde"), var("padded"))),
    # groupes lisibles : 1-5-3-2-1-1-2-1-2
    set_var("digits", var("codeSauvegarde")),
    set_var("codeSauvegarde", ""),
    set_var("i", 1),
    repeat(1, [set_var("codeSauvegarde", join(var("codeSauvegarde"), letter(var("i"), var("digits")))), change_var("i", 1)]),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), "-")),
    repeat(5, [set_var("codeSauvegarde", join(var("codeSauvegarde"), letter(var("i"), var("digits")))), change_var("i", 1)]),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), "-")),
    repeat(3, [set_var("codeSauvegarde", join(var("codeSauvegarde"), letter(var("i"), var("digits")))), change_var("i", 1)]),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), "-")),
    repeat(2, [set_var("codeSauvegarde", join(var("codeSauvegarde"), letter(var("i"), var("digits")))), change_var("i", 1)]),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), "-")),
    repeat(1, [set_var("codeSauvegarde", join(var("codeSauvegarde"), letter(var("i"), var("digits")))), change_var("i", 1)]),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), "-")),
    repeat(1, [set_var("codeSauvegarde", join(var("codeSauvegarde"), letter(var("i"), var("digits")))), change_var("i", 1)]),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), "-")),
    repeat(2, [set_var("codeSauvegarde", join(var("codeSauvegarde"), letter(var("i"), var("digits")))), change_var("i", 1)]),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), "-")),
    repeat(1, [set_var("codeSauvegarde", join(var("codeSauvegarde"), letter(var("i"), var("digits")))), change_var("i", 1)]),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), "-")),
    repeat(2, [set_var("codeSauvegarde", join(var("codeSauvegarde"), letter(var("i"), var("digits")))), change_var("i", 1)]),
    list_clear("CODE DE SAUVEGARDE"),
    list_add("CODE DE SAUVEGARDE", var("codeSauvegarde")),
]))

U.script(define("chargerCode %s", ["code"], [
    # ne garder que les chiffres
    set_var("digits", ""), set_var("i", 1),
    repeat(strlen(arg("code")), [
        set_var("ch", letter(var("i"), arg("code"))),
        if_(Blk("operator_contains", {"STRING1": "0123456789", "STRING2": var("ch")}), [set_var("digits", join(var("digits"), var("ch")))]),
        change_var("i", 1),
    ]),
    set_var("ok", 0),
    if_(or_(eq(strlen(var("digits")), 18), eq(strlen(var("digits")), 15)), [
        call("extraire %s %s", 1, 1), set_var("bx", var("part")),      # niveauMax
        call("extraire %s %s", 2, 5), set_var("by", var("part")),      # pièces
        call("extraire %s %s", 7, 3), set_var("px", var("part")),      # bits acc
        call("extraire %s %s", 10, 2), set_var("py", var("part")),     # bits skins
        call("extraire %s %s", 12, 1), set_var("n", var("part")),      # acc équipé
        call("extraire %s %s", 13, 1), set_var("k", var("part")),      # skin équipé
        # armes : présentes seulement dans le format à 18 chiffres
        if_else(eq(strlen(var("digits")), 18), [
            call("extraire %s %s", 14, 2), set_var("pBitsArmes", var("part")),
            call("extraire %s %s", 16, 1), set_var("pArmeCode", var("part")),
            call("extraire %s %s", 17, 2), set_var("cx", var("part")),  # checksum
        ], [
            set_var("pBitsArmes", 0), set_var("pArmeCode", 0),
            call("extraire %s %s", 14, 2), set_var("cx", var("part")),  # checksum (ancien format)
        ]),
        call("checksum %s %s %s %s %s %s", var("bx"), var("by"), var("px"), var("py"), var("n"), var("k")),
        if_(and_(eq(var("somme"), var("cx")), and_(and_(gt(var("bx"), 0), lt(var("bx"), len(BOTS) + 1)),
                                                    and_(and_(gt(var("n"), 0), lt(var("n"), len(ACCS) + 1)),
                                                         and_(and_(gt(var("k"), 0), lt(var("k"), len(SKINS) + 1)),
                                                              and_(ge(var("pArmeCode"), 0), lt(var("pArmeCode"), len(ARMES))))))), [
            set_var("ok", 1),
            set_var("niveauMax", var("bx")), set_var("pieces", var("by")),
            set_var("mult", 1), set_var("i", 1),
            repeat(len(ACCS), [
                list_replace("accPossede", var("i"), mod(floor(div(var("px"), var("mult"))), 2)),
                set_var("mult", mul(var("mult"), 2)), change_var("i", 1),
            ]),
            set_var("mult", 1), set_var("i", 1),
            repeat(len(SKINS), [
                list_replace("skinPossede", var("i"), mod(floor(div(var("py"), var("mult"))), 2)),
                set_var("mult", mul(var("mult"), 2)), change_var("i", 1),
            ]),
            list_replace("accPossede", 1, 1), list_replace("skinPossede", 1, 1),
            # armes possédées (bits) + arme équipée
            set_var("mult", 1), set_var("i", 1),
            repeat(len(ARMES), [
                list_replace("armePossede", var("i"), mod(floor(div(var("pBitsArmes"), var("mult"))), 2)),
                set_var("mult", mul(var("mult"), 2)), change_var("i", 1),
            ]),
            list_replace("armePossede", 1, 1),
            set_var("P1Arme", add(var("pArmeCode"), 1)), set_var("P1ArmeOrig", var("P1Arme")), set_var("armeApercu", var("P1Arme")),
            set_var("P1Acc", item("accId", var("n"))),
            set_var("P1Skin", var("k")),
            set_var("P1Teinte", item("skinTeinte", var("P1Skin"))),
            set_var("P1Lum", item("skinLum", var("P1Skin"))),
            set_var("niveau", var("niveauMax")),
        ]),
    ]),
    if_else(eq(var("ok"), 1), [
        set_var("infoSauvegarde", "Progression chargée !"), play_sound("coin"),
    ], [
        set_var("infoSauvegarde", "Code invalide"), play_sound("lose"),
    ]),
    set_var("phaseTimer", 90),
]))

# --- écran SAUVEGARDE
U.script(define("dessinerSauvegarde", [], [
    rect(-200, 10, 400, 260, COL["panel"], 15),
    ecrire("TON CODE DE SAUVEGARDE", 0, 100, 60, 30, 1),
    rect(-196, 40, 392, 56, "#000000", 30),
    # 18 chiffres + 8 tirets : on réduit la taille pour que le code tienne dans le cadre
    ecrire(var("codeSauvegarde"), 0, 28, 54, -1, 1),
    ecrire("Note ce code (ou copie-le dans la liste à l'écran).", 0, -10, 30, -1, 1),
    ecrire("Au prochain lancement : Menu, CHARGER, puis colle le code.", 0, -32, 30, -1, 1),
    ecrire("Il contient : niveau max, pièces, arme équipée et cosmétiques.", 0, -60, 26, -2, 1),
    bouton(0, -110, 160, 40, "RETOUR", "menu", COL["grey"], 42),
]))

# --- écran MENU
U.script(define("dessinerMenu", [], [
    rect(-240, 120, 480, 70, "#000000", 55),
    ecrire("ARENA CLASH", 3, 97, 115, -3, 1),
    ecrire("ARENA CLASH", 0, 100, 115, 178, 1),
    ecrire("Combat 2D - Arène - Bots - Cosmétiques", 0, 62, 36, -2, 1),
    bouton(80, 30, 200, 42, "JOUER", "jouer", COL["accent"], 50),
    bouton(80, -18, 200, 42, "BOUTIQUE", "boutique", COL["accent2"], 50),
    bouton(80, -66, 200, 42, "COMMANDES", "commandes", COL["grey"], 50),
    bouton(28, -112, 100, 34, "SAUVER", "sauver", COL["ok"], 32),
    bouton(134, -112, 100, 34, "CHARGER", "charger", COL["sp"], 32),
    if_(gt(var("phaseTimer"), 0), [
        change_var("phaseTimer", -1),
        if_else(eq(var("infoSauvegarde"), "Code invalide"), [
            ecrire(var("infoSauvegarde"), 80, -156, 30, 0, 1),
        ], [
            ecrire(var("infoSauvegarde"), 80, -156, 30, 67, 1),
        ]),
    ]),
    rect(-240, -150, 480, 40, "#000000", 40),
    ecrire(join(var("pieces"), " pièces"), -228, -156, 40, 30, 0),
    if_(eq(var("phaseTimer"), 0), [ecrire(join("Niveau max : ", var("niveauMax")), 228, -156, 40, -1, 2)]),
    ecrire("Ton combattant", -150, -128, 32, -2, 1),
]))

# --- écran COMMANDES
U.script(define("dessinerCommandes", [], [
    rect(-200, 0, 400, 300, COL["panel"], 15),
    ecrire("COMMANDES", 0, 105, 80, 30, 1),
    ecrire("Flèches gauche / droite : se déplacer", 0, 68, 36, -1, 1),
    ecrire("Flèche haut : sauter (on peut attaquer en l'air)", 0, 44, 32, -1, 1),
    ecrire("Flèche bas : garde. 12 % des dégâts, 0 avec le bouclier", 0, 18, 28, -1, 1),
    ecrire("En l'air, un pied ou un spécial brise la garde (50 % des dégâts).", 0, -4, 28, -2, 1),
    ecrire("J : poing  K : pied  L : SPÉCIAL (barre bleue pleine)", 0, -30, 34, 100, 1),
    ecrire("Ramasse une arme au sol (mains nues) : portée, dégâts et", 0, -56, 30, 67, 1),
    ecrire("spécial changent (perce-gardes, charge, tir, bouclier).", 0, -80, 30, 67, 1),
    ecrire("Gagne 2 rounds sur 3 pour remporter le combat !", 0, -106, 30, -2, 1),
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
    ecrire("BOUTIQUE", 0, 152, 64, 178, 1),
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
    ecrire("Clique pour acheter puis pour équiper", 80, -126, 28, -2, 1),
    bouton(-150, -150, 150, 40, "RETOUR", "menu", COL["grey"], 42),
    ecrire("Aperçu", -150, 58, 34, -2, 1),
    # onglets
    bouton(-180, 100, 84, 30, "LOOK", "tab1", COL["ok"], 26),
    bouton(-90, 100, 84, 30, "ARMES", "tab2", COL["grey"], 26),
]
U.script(define("dessinerBoutique", [], shop))

# ---------- page 2 : les armes
armes_shop = [
    rect(-240, 150, 480, 60, "#000000", 55),
    ecrire("ARMES", 0, 152, 64, 30, 1),
    ecrire(join(var("pieces"), " pièces"), 228, 152, 34, 30, 2),
    bouton(-180, 100, 84, 30, "LOOK", "tab1", COL["grey"], 26),
    bouton(-90, 100, 84, 30, "ARMES", "tab2", COL["ok"], 26),
    # 6 armes en 3 x 2
    set_var("k", 1),
]
armes_shop.append(repeat(len(ARMES), [
    set_var("bx", add(-160, mul(mod(sub(var("k"), 1), 3), 160))),
    set_var("by", sub(56, mul(floor(div(sub(var("k"), 1), 3)), 44))),
    if_else(eq(item("armePossede", var("k")), 1), [
        if_else(eq(var("k"), var("P1Arme")), [
            bouton(var("bx"), var("by"), 150, 36, item("armeNom", var("k")), join("arme", var("k")), COL["ok"], 32),
        ], [
            bouton(var("bx"), var("by"), 150, 36, item("armeNom", var("k")), join("arme", var("k")), COL["accent2"], 32),
        ]),
    ], [
        bouton(var("bx"), var("by"), 150, 36, join(item("armeNom", var("k")), join(" ", item("armePrix", var("k")))),
               join("arme", var("k")), COL["grey"], 30),
    ]),
    change_var("k", 1),
]))
armes_shop += [
    # panneau d'aperçu : à droite, sous la grille (le combattant d'aperçu reste à gauche)
    rect(105, -78, 260, 110, COL["panel"], 12),
    *icone_arme(var("armeApercu"), -8, -78, 46),
    ecrire(item("armeNom", var("armeApercu")), 135, -36, 28, 30, 1),
    ecrire(item("armeL1", var("armeApercu")), 135, -58, 24, -1, 1),
    ecrire(item("armeL2", var("armeApercu")), 135, -79, 22, -1, 1),
    ecrire(item("armeL3", var("armeApercu")), 135, -100, 20, -2, 1),
    if_else(eq(var("P1Arme"), var("armeApercu")), [
        ecrire("ÉQUIPÉE", 135, -122, 22, 67, 1),
    ], [
        if_else(eq(item("armePossede", var("armeApercu")), 1), [
            ecrire("Achetée : cliquer pour équiper", 135, -122, 20, 100, 1),
        ], [
            ecrire(join("Prix : ", join(item("armePrix", var("armeApercu")), " pièces")), 135, -122, 22, -2, 1),
        ]),
    ]),
    bouton(-150, -150, 150, 40, "RETOUR", "menu", COL["grey"], 42),
]
U.script(define("dessinerBoutiqueArmes", [], armes_shop))

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
    # arme en main (le joueur et le bot)
    rect(-238, -171, 476, 36, "#000000", 55),
    rect(-238, -189, 476, 2, COL["grey"], 0),
    *icone_arme(var("P1ArmeMain"), -212, -170, 30),
    ecrire(join("TOI : ", item("armeNom", var("P1ArmeMain"))), -180, -176, 30, -1, 0),
    if_(eq(item("armeProj", var("P1ArmeMain")), 1), [ecrire("K : tir / L : salve", -180, -160, 24, 100, 0)]),
    ecrire(join(var("BotNom"), join(" : ", item("armeNom", var("BotArmeMain")))), 180, -176, 30, -1, 2),
    *icone_arme(var("BotArmeMain"), 212, -170, 30),
    if_(gt(var("comboP1"), 1), [
        ecrire(join(var("comboP1"), " HITS !"), -228, 80, 44, 30, 0),
    ]),
    if_(not_(eq(var("message"), "")), [
        ecrire(var("message"), 3, 27, 90, -3, 1),
        ecrire(var("message"), 0, 30, 90, 30, 1),
    ]),
    if_(and_(eq(var("phase"), "intro"), eq(var("round"), 1)), [
        ecrire("Flèches : bouger / sauter / garde   J : poing   K : pied   L : spécial   (aussi en l'air !)", 0, -160, 26, -2, 1),
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
    # deux armes au sol, différentes, sur deux points d'apparition (au sol une fois sur deux)
    set_var("k", 1),
    repeat(2, [
        list_replace("solArme", var("k"), random(2, len(ARMES))),
        set_var("bx", add(1, mul(sub(var("k"), 1), 2))),
        if_(eq(mod(var("round"), 2), 0), [set_var("bx", add(3, mul(sub(var("k"), 1), 2)))]),
        list_replace("solX", var("k"), item("spawnX", var("bx"))),
        list_replace("solY", var("k"), item("spawnY", var("bx"))),
        list_replace("solTimer", var("k"), 0),
        change_var("k", 1),
    ]),
    if_(eq(item("solArme", 1), item("solArme", 2)), [
        # rotation dans 2..len(ARMES) : jamais la même arme, jamais d'indice hors table
        list_replace("solArme", 2, add(mod(sub(item("solArme", 2), 1), sub(len(ARMES), 1)), 2)),
    ]),
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
    set_var("BotArme", item("botArme", var("niveau"))),
    set_var("P1Arme", var("P1ArmeOrig")),
    switch_backdrop(item("botArene", var("niveau"))),
    set_var("victoiresP1", 0), set_var("victoiresBot", 0), set_var("round", 1),
    set_var("dernierNiveauGagne", 0),
    set_var("scene", "fight"),
    call("nouveauRound"),
]))

# --- gestion des clics
click_logic = [
    if_(eq(var("clic"), "jouer"), [set_var("scene", "select"), set_var("niveauApercu", 0)]),
    if_(eq(var("clic"), "boutique"), [set_var("scene", "shop"), set_var("P1Arme", var("P1ArmeOrig")), set_var("armeApercu", var("P1Arme"))]),
    if_(eq(var("clic"), "tab1"), [set_var("shopPage", 1)]),
    if_(eq(var("clic"), "tab2"), [set_var("shopPage", 2), set_var("armeApercu", var("P1Arme"))]),
    if_(eq(var("clic"), "commandes"), [set_var("scene", "commandes")]),
    if_(eq(var("clic"), "sauver"), [
        call("genererCode"), set_var("scene", "save"),
        Blk("data_showlist", fields={"LIST": ListRef("CODE DE SAUVEGARDE")}),
    ]),
    if_(eq(var("clic"), "charger"), [
        Blk("sensing_askandwait", {"QUESTION": "Colle ton code de sauvegarde puis appuie sur Entrée :"}),
        call("chargerCode %s", Blk("sensing_answer")),
    ]),
    if_(eq(var("clic"), "menu"), [
        set_var("scene", "menu"), set_var("P1Arme", var("P1ArmeOrig")),
        switch_backdrop("menu"), broadcast("resetRound"), set_var("phaseTimer", 0),
        Blk("data_hidelist", fields={"LIST": ListRef("CODE DE SAUVEGARDE")}),
    ]),
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
    # armes : achat puis équipement (id "armeK")
    if_(eq(join4(letter(1, var("clic")), letter(2, var("clic")), letter(3, var("clic")), letter(4, var("clic"))), "arme"), [
        set_var("k", add(letter(5, var("clic")), 0)),
        if_else(eq(item("armePossede", var("k")), 1), [
            set_var("P1Arme", var("k")), set_var("P1ArmeOrig", var("k")), set_var("armeApercu", var("k")), play_sound("click"),
        ], [
            if_else(ge(var("pieces"), item("armePrix", var("k"))), [
                change_var("pieces", mul(-1, item("armePrix", var("k")))),
                list_replace("armePossede", var("k"), 1),
                set_var("P1Arme", var("k")), set_var("P1ArmeOrig", var("k")), set_var("armeApercu", var("k")),
                play_sound("coin"),
            ], [
                set_var("message", "Pas assez de pièces !"), set_var("phaseTimer", 40),
            ]),
        ]),
    ]),
]
U.script(define("gererClic", [], click_logic))

# --- logique de round (appelée chaque frame en combat)
round_logic = [
    if_(gt(var("hitStop"), 0), [change_var("hitStop", -1)]),
    # armes au sol : compte à rebours puis réapparition d'une arme aléatoire
    if_(eq(var("phase"), "fight"), [
        set_var("k", 1),
        repeat(2, [
            if_(and_(eq(item("solArme", var("k")), 0), gt(item("solTimer", var("k")), 0)), [
                list_replace("solTimer", var("k"), sub(item("solTimer", var("k")), 1)),
                if_(eq(item("solTimer", var("k")), 0), [
                    set_var("solLibre", random(1, len(SPAWNS))),
                    set_var("solProcheX", item("spawnX", var("solLibre"))),
                    if_(or_(lt(abs_(sub(var("solProcheX"), var("P1X"))), 70),
                            lt(abs_(sub(var("solProcheX"), var("BotX"))), 70)), [
                        set_var("solLibre", random(1, len(SPAWNS))),
                    ]),
                    list_replace("solArme", var("k"), random(2, len(ARMES))),
                    list_replace("solX", var("k"), item("spawnX", var("solLibre"))),
                    list_replace("solY", var("k"), item("spawnY", var("solLibre"))),
                ]),
            ]),
            change_var("k", 1),
        ]),
    ]),
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
    Blk("data_hidelist", fields={"LIST": ListRef("CODE DE SAUVEGARDE")}),
    set_var("phaseTimer", 0),
    pen_clear(),
    forever([
        change_var("frame", 1),
        pen_clear(),
        set_var("hoverBtn", ""),
        if_(eq(var("scene"), "menu"), [call("dessinerMenu")]),
        if_(eq(var("scene"), "commandes"), [call("dessinerCommandes")]),
        if_(eq(var("scene"), "save"), [call("dessinerSauvegarde")]),
        if_(eq(var("scene"), "select"), [
            call("dessinerSelection"),
            set_var("niveauApercu", 0),
            if_(eq(join(letter(1, var("hoverBtn")), join(letter(2, var("hoverBtn")), letter(3, var("hoverBtn")))), "lvl"), [
                set_var("niveauApercu", add(letter(4, var("hoverBtn")), 0)),
            ]),
        ]),
        if_(eq(var("scene"), "shop"), [
            if_else(eq(var("shopPage"), 1), [call("dessinerBoutique")], [call("dessinerBoutiqueArmes")]),
            if_(eq(join4(letter(1, var("hoverBtn")), letter(2, var("hoverBtn")),
                         letter(3, var("hoverBtn")), letter(4, var("hoverBtn"))), "arme"), [
                set_var("armeApercu", add(letter(5, var("hoverBtn")), 0)),
            ]),
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
              "aiTimer", "attaqueTenue", "dx", "f", "dmg", "portee", "aStart", "aEnd", "aTotal", "dist", "r",
              "armeMain", "tirFait", "especeArme", "typeArme", "cibleX", "cibleY", "k"]:
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
        set_var("tirFait", 0),
        setV("State", "idle"),
        set_var("P1Arme", var("P1ArmeOrig")) if is_player else set_var("BotArme", item("botArme", var("niveau"))),
        setV("X", -120 if is_player else 120), setV("Y", GROUND), setV("Dir", 90 if is_player else -90),
        goto_xy(V("X"), V("Y")), point_dir(V("Dir")),
        switch_costume(join(item("armeCost", var("P1Arme") if is_player else var("BotArme")), "_idle")), show(),
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
                    if_(and_(gt(V("Y"), GROUND), lt(var("dist"), 100)), [
                        if_(lt(var("r"), var("BotAggro")), [set_var("iKick", 1)]),
                    ]),
                    if_else(gt(var("dist"), 90), [
                        if_else(gt(OV("X"), V("X")), [set_var("iMove", 1)], [set_var("iMove", -1)]),
                        if_(lt(var("r"), 3), [set_var("iJump", 1)]),
                        if_(and_(gt(OV("Y"), GROUND), lt(var("r"), var("BotGarde"))), [set_var("iMove", 0), set_var("iBlock", 1)]),
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
        # --- priorité 1 : à mains nues, aller chercher une arme au sol
        intents += [
            if_(and_(eq(V("Arme"), 1), or_(gt(item("solArme", 1), 0), gt(item("solArme", 2), 0))), [
                set_var("cibleX", 0), set_var("cibleY", 0), set_var("r", 0),
                if_(gt(item("solArme", 1), 0), [
                    set_var("cibleX", item("solX", 1)), set_var("cibleY", item("solY", 1)), set_var("r", 1),
                ]),
                if_(gt(item("solArme", 2), 0), [
                    if_else(or_(eq(var("r"), 0), lt(abs_(sub(item("solX", 2), V("X"))), abs_(sub(var("cibleX"), V("X"))))), [
                        set_var("cibleX", item("solX", 2)), set_var("cibleY", item("solY", 2)),
                    ], []),
                ]),
                if_(gt(var("dist"), 95), [
                    set_var("iMove", 0),
                    if_else(gt(var("cibleX"), add(V("X"), 12)), [set_var("iMove", 1)], [
                        if_(lt(var("cibleX"), sub(V("X"), 12)), [set_var("iMove", -1)]),
                    ]),
                    if_(and_(gt(var("cibleY"), add(V("Y"), 55)), eq(V("Y"), GROUND)), [set_var("iJump", 1)]),
                ]),
            ]),
            # --- priorité 2 : avec l'arc, garder ses distances et tirer
            if_(eq(item("armeProj", V("Arme")), 1), [
                if_(lt(var("dist"), 120), [
                    if_else(gt(OV("X"), V("X")), [set_var("iMove", -1)], [set_var("iMove", 1)]),
                    set_var("iPunch", 0), set_var("iJump", 0),
                ]),
                if_(and_(gt(var("dist"), 130), lt(var("dist"), 300)), [
                    if_else(eq(V("Special"), 100), [set_var("iSpecial", 1)], [set_var("iKick", 1)]),
                ]),
            ]),
        ]

    hit_fx = [set_var("fxX", V("X")), set_var("fxY", add(V("Y"), mul(0.65, V("Size")))), set_var("fxTeinte", 0)]

    # ----- réception des dégâts
    # l'arme du défenseur compte : le bouclier réduit les dégâts de garde (12 % -> 5 %,
    # garde brisée 50 % -> 20 %) et le marteau ("smash") traverse la garde au sol.
    briseurs = or_(or_(eq(V("HitType"), "kick"), eq(V("HitType"), "special")),
                    or_(eq(V("HitType"), "charge"), eq(V("HitType"), "smash")))
    take_hit = [
        if_(gt(V("Hit"), 0), [
            set_var("r", item("armeGarde", V("Arme"))),
            # 1) garde aérienne brisée par un coup de pied / spécial / charge / marteau
            if_(and_(eq(state, "block"), and_(gt(V("Y"), GROUND), briseurs)), [
                set_var("dmg", 0.5),
                if_(eq(var("r"), 1), [set_var("dmg", 0.2)]),
                setV("Hit", mathop("ceiling", mul(V("Hit"), var("dmg")))),
                setV("State", "idle"),
                set_var("fxType", "ring"), set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 50)),
                create_clone("FX"), create_clone("FX"),
            ]),
            if_else(and_(eq(state, "block"), not_(eq(V("Dir"), mul(90, V("HitDir"))))), [
                # 2) coup bloqué (on fait face à l'attaquant)
                if_else(eq(V("HitType"), "smash"), [
                    # le marteau casse la garde : 60 % des dégâts et le défenseur est sonné
                    setV("Hit", mathop("ceiling", mul(V("Hit"), 0.6))),
                    chV("HP", mul(-1, V("Hit"))),
                    setV("State", "hurt"), set_var("timer", 18),
                    set_var("vx", mul(V("HitDir"), 8)), set_var("vy", 5),
                    set_var("hitStop", 4), play_sound("hit"),
                    set_var("fxType", "spark"), set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 60)),
                    create_clone("FX"),
                ], [
                    # 12 % de dégâts de garde... sauf au bouclier, qui bloque à 100 %
                    set_var("dmg", 0.12),
                    if_(eq(var("r"), 1), [set_var("dmg", 0)]),
                    chV("HP", mul(-1, mathop("ceiling", mul(V("Hit"), var("dmg"))))),
                    set_var("vx", mul(V("HitDir"), 4)),
                    chV("Special", 4),
                    play_sound("block"),
                    set_var("fxType", "ring"),
                ] + hit_fx + [create_clone("FX")]),
            ], [
                # 3) coup encaissé de plein fouet
                chV("HP", mul(-1, V("Hit"))),
                setV("State", "hurt"), set_var("timer", 14),
                set_var("vx", mul(V("HitDir"), 7)), set_var("vy", 4),
                if_(eq(V("HitType"), "charge"), [set_var("vx", mul(V("HitDir"), 11)), set_var("vy", 6)]),
                if_(eq(V("HitType"), "smash"), [set_var("vx", mul(V("HitDir"), 10)), set_var("vy", 7)]),
                chV("Special", 8),
                set_var("hitStop", 3),
                play_sound("hit"),
                set_var("fxType", "spark"),
            ] + hit_fx + [create_clone("FX"), set_var("fxType", "dot")]
                # 6 particules : deroule (une boucle rendrait la main image par image)
                + [create_clone("FX")] * 6),
            if_(gt(V("Special"), 100), [setV("Special", 100)]),
            if_(lt(V("HP"), 0), [setV("HP", 0)]),
            setV("Hit", 0),
        ]),
    ]

    # ----- démarrage d'actions
    speed = var("P1Vitesse") if is_player else var("BotVitesse")
    start_actions = [
        if_(st_is("idle", "walk", "block"), [
            if_else(eq(var("iBlock"), 1), [
                if_(and_(not_(eq(state, "block")), gt(V("Y"), GROUND)), [
                    # garde aérienne : propulsion vers l'arrière
                    set_var("vx", mul(V("Dir"), -0.09)),
                    set_var("vy", 3),
                    set_var("fxType", "ring"), set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 40)), create_clone("FX"),
                ]),
                setV("State", "block"),
                if_(eq(V("Y"), GROUND), [set_var("vx", 0)]),
            ], [
                if_(eq(state, "block"), [setV("State", "idle")]),
                if_else(eq(var("iPunch"), 1), [
                    set_var("aTotal", item("armeTotP", V("Arme"))),
                    set_var("dmg", add(PUNCH["dmg"], item("armeDmgP", V("Arme")))),
                    set_var("portee", add(PUNCH["range"], item("armePortee", V("Arme")))),
                    set_var("aStart", add(PUNCH["start"], sub(var("aTotal"), PUNCH["total"]))),
                    set_var("aEnd", add(PUNCH["end"], sub(var("aTotal"), PUNCH["total"]))),
                    setV("State", "punch"), set_var("timer", var("aTotal")), set_var("hitDone", 0),
                ], [
                    if_else(eq(var("iKick"), 1), [
                        set_var("aTotal", item("armeTotK", V("Arme"))),
                        set_var("dmg", add(KICK["dmg"], item("armeDmgK", V("Arme")))),
                        set_var("portee", add(KICK["range"], item("armePortee", V("Arme")))),
                        set_var("aStart", add(KICK["start"], sub(var("aTotal"), KICK["total"]))),
                        set_var("aEnd", add(KICK["end"], sub(var("aTotal"), KICK["total"]))),
                        setV("State", "kick"), set_var("timer", var("aTotal")), set_var("hitDone", 0),
                    ], [
                        if_else(and_(eq(var("iSpecial"), 1), eq(V("Special"), 100)), [
                            set_var("aTotal", item("armeSpeTot", V("Arme"))),
                            set_var("dmg", item("armeSpeDmg", V("Arme"))),
                            set_var("portee", item("armeSpePortee", V("Arme"))),
                            set_var("aStart", add(SPECIAL["start"], sub(var("aTotal"), SPECIAL["total"]))),
                            set_var("aEnd", add(SPECIAL["end"], sub(var("aTotal"), SPECIAL["total"]))),
                            set_var("tirFait", 0),
                            setV("State", "special"), set_var("timer", var("aTotal")), set_var("hitDone", 0),
                            # spéciaux qui bougent : estoc (1), charge (2)
                            set_var("especeArme", item("armeSpe", V("Arme"))),
                            if_(eq(var("especeArme"), 1), [set_var("vx", mul(div(V("Dir"), 90), 5))]),
                            if_(eq(var("especeArme"), 2), [set_var("vx", mul(div(V("Dir"), 90), 9))]),
                            # type de frappe transmis au défenseur (marteau = perce la garde)
                            set_var("typeArme", "special"),
                            if_(eq(var("especeArme"), 1), [set_var("typeArme", "estoc")]),
                            if_(eq(var("especeArme"), 2), [set_var("typeArme", "charge")]),
                            if_(eq(var("especeArme"), 3), [set_var("typeArme", "smash")]),
                            setV("Special", 0), play_sound("special"),
                            set_var("fxType", "bolt"), set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 60)),
                            # 3 éclairs déroulés : pas de boucle dans le thread de combat
                        ] + [create_clone("FX")] * 3, [
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

    def tirer(dmgval, hauteur=56):
        """Tire une flèche : le sprite Fleche (clone) gère le vol et la collision."""
        return [
            set_var("flX", add(V("X"), mul(30, div(V("Dir"), 90)))),
            set_var("flY", add(V("Y"), hauteur)),
            set_var("flDir", V("Dir")),
            set_var("flWho", 1 if is_player else 2),
            set_var("flDmg", dmgval),
            create_clone("Fleche"),
            play_sound("tir"),
        ]

    def attack_block(name, spec, hittype=None):
        """spec : durées/dégâts de base ; l'arme en main décale la fenêtre active et la portée."""
        ht = hittype or name
        ht = var("typeArme") if hittype == "special" else ht
        return if_(eq(state, name), [
            set_var("f", sub(var("aTotal"), var("timer"))),
            # tir à l'arc : le coup part en flèche (kick) ou en salve (spécial)
            if_else(and_(eq(item("armeProj", V("Arme")), 1), eq(name, "kick")), [
                if_(and_(eq(var("hitDone"), 0), and_(ge(var("f"), var("aStart")), lt(var("f"), var("aEnd")))), [
                    set_var("hitDone", 1),
                    *tirer(FLECHE_DMG),
                ]),
            ], [
                if_else(and_(eq(item("armeProj", V("Arme")), 1), eq(name, "special")), [
                    # 3 flèches espacées de 8 images : la fenêtre du spécial (20 images) en contient bien 3
                    if_(and_(lt(var("tirFait"), 3), ge(var("f"), add(var("aStart"), mul(var("tirFait"), 8)))), [
                        set_var("tirFait", add(var("tirFait"), 1)),
                        *tirer(FLECHE_DMG_VOLLEY),
                    ]),
                ], [
                    if_(and_(eq(var("hitDone"), 0), and_(ge(var("f"), var("aStart")), lt(var("f"), var("aEnd")))), [
                        set_var("dx", sub(OV("X"), V("X"))),
                        if_(and_(lt(abs_(var("dx")), var("portee")),
                                 and_(gt(mul(var("dx"), V("Dir")), -1), lt(abs_(sub(OV("Y"), V("Y"))), 115))), [
                            if_(not_(eq(OV("State"), "ko")), [
                                set_var("hitDone", 1),
                                set_var(op + "Hit", var("dmg")),
                                set_var(op + "HitType", ht),
                                if_else(gt(var("dx"), 0), [set_var(op + "HitDir", 1)], [set_var(op + "HitDir", -1)]),
                                chV("Special", 12),
                                if_(gt(V("Special"), 100), [setV("Special", 100)]),
                            ] + ([change_var("comboP1", 1)] if is_player else [set_var("comboP1", 0)])
                              + ([play_sound("kick")] if name != "punch" else [])),
                        ]),
                    ]),
                ]),
            ]),
        ])

    attacks = [attack_block("punch", PUNCH), attack_block("kick", KICK),
               attack_block("special", SPECIAL, hittype="special")]

    # ----- ramassage d'une arme au sol (seulement à mains nues : l'arme équipée reste)
    # les deux emplacements sont déroulés : aucune boucle ne doit rendre la main dans le combat
    def slot_ramassage(k):
        return if_(gt(item("solArme", k), 0), [
            if_(and_(lt(abs_(sub(V("X"), item("solX", k))), 42),
                     lt(abs_(sub(V("Y"), item("solY", k))), 84)), [
                setV("Arme", item("solArme", k)),
                list_replace("solArme", k, 0),
                list_replace("solTimer", k, PICKUP_DELAI),
                play_sound("coin"),
                set_var("fxType", "ring"),
                set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 55)),
                create_clone("FX"),
            ]),
        ])

    ramassage = [
        if_(eq(V("Arme"), 1), [
            slot_ramassage(1),
            slot_ramassage(2),
        ]),
    ]

    # ----- physique
    physics = [
        chV("X", var("vx")),
        change_var("vy", -0.8),
        chV("Y", var("vy")),
        if_(lt(V("Y"), GROUND), [setV("Y", GROUND), set_var("vy", 0)]),
        if_(and_(not_(eq(state, "walk")), eq(V("Y"), GROUND)), [set_var("vx", mul(var("vx"), 0.7))]),
        if_(and_(eq(state, "block"), gt(V("Y"), GROUND)), [set_var("vx", mul(var("vx"), 0.93))]),
        if_(and_(gt(V("Y"), GROUND), st_is("idle", "walk")), [
            # contrôle aérien léger
            if_(not_(eq(var("iMove"), 0)), [set_var("vx", mul(var("iMove"), speed))]),
        ]),
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

    # ----- costume (une série de 12 poses par arme : l'arme est dessinée dans le costume)
    def COS(n):
        return switch_costume(join(item("armeCost", var("armeMain")), "_" + n))

    costume = [
        change_var("anim", 1),
        # arme affichée : celle en main, ou celle survolée dans la boutique
        set_var("armeMain", V("Arme")),
        if_(and_(eq(var("scene"), "shop"), gt(var("armeApercu"), 0)), [set_var("armeMain", var("armeApercu"))]),
        if_(eq(state, "idle"), [
            if_else(lt(mod(var("anim"), 30), 15), [COS("idle")], [COS("idle2")]),
        ]),
        if_(eq(state, "walk"), [
            if_else(lt(mod(var("anim"), 12), 6), [COS("walk1")], [COS("walk2")]),
        ]),
        if_(and_(st_is("idle", "walk"), gt(V("Y"), GROUND)), [COS("jump")]),
        if_(eq(state, "block"), [COS("block")]),
        if_(eq(state, "hurt"), [COS("hurt")]),
        if_(eq(state, "ko"), [COS("ko")]),
        if_(eq(state, "win"), [COS("win")]),
        if_(eq(state, "punch"), [
            if_else(lt(sub(var("aTotal"), var("timer")), var("aStart")), [COS("idle2")], [COS("punch")]),
        ]),
        if_(eq(state, "kick"), [
            if_else(lt(sub(var("aTotal"), var("timer")), var("aStart")), [COS("walk1")], [COS("kick")]),
        ]),
        if_(eq(state, "special"), [
            if_else(lt(sub(var("aTotal"), var("timer")), var("aStart")), [COS("block")], [COS("special")]),
        ]),
    ]

    apply_look = [
        set_var(me + "ArmeMain", V("Arme")),
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
                # page ARMES : le panneau d'aperçu montre l'arme, on masque le combattant
                if_(and_(eq(var("scene"), "shop"), eq(var("shopPage"), 2)), [hide(), setV("Vis", 0)]),
            ], [
                if_(eq(var("scene"), "select"), [hide(), setV("Vis", 0)]),
                if_(eq(var("scene"), "commandes"), [hide(), setV("Vis", 0)]),
                if_(eq(var("scene"), "save"), [hide(), setV("Vis", 0)]),
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
                    *ramassage,
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

# ================================================================== ARMES AU SOL / FLÈCHES
def arme_sol_scripts(t, slot):
    t.add_var("k", 0)
    t.script(
        when_flag(),
        hide(),
        forever([
            if_else(and_(eq(var("scene"), "fight"), gt(item("solArme", slot), 0)), [
                switch_costume(item("solArme", slot)),
                set_size(58),
                goto_xy(item("solX", slot),
                        add(item("solY", slot), mul(6, mathop("sin", mul(var("frame"), 6))))),
                show(),
            ], [hide()]),
        ]),
    )


arme_sol_scripts(arme1, 1)
arme_sol_scripts(arme2, 2)

for v, d in [("x", 0), ("y", 0), ("vx", 0), ("who", 1), ("dmg", 0), ("life", 0)]:
    fleche.add_var(v, d)
fleche.script(when_flag(), hide())
fleche.script(when_broadcast("resetRound"), delete_clone())
fleche.script(
    when_clone_start(),
    set_var("x", var("flX")), set_var("y", var("flY")),
    set_var("vx", mul(div(var("flDir"), 90), FLECHE_VITESSE)),
    set_var("who", var("flWho")), set_var("dmg", var("flDmg")), set_var("life", 70),
    point_dir(var("flDir")),
    goto_xy(var("x"), var("y")),
    show(),
    repeat_until(or_(lt(var("life"), 1), gt(abs_(var("x")), 250)), [
        change_var("x", var("vx")),
        change_var("life", -1),
        goto_xy(var("x"), var("y")),
        if_else(eq(var("who"), 1), [
            if_(and_(lt(abs_(sub(var("x"), var("BotX"))), 36),
                     lt(abs_(sub(var("y"), add(var("BotY"), 55))), 70)), [
                set_var("BotHit", var("dmg")), set_var("BotHitType", "fleche"),
                if_else(gt(var("vx"), 0), [set_var("BotHitDir", 1)], [set_var("BotHitDir", -1)]),
                set_var("life", 0),
            ]),
        ], [
            if_(and_(lt(abs_(sub(var("x"), var("P1X"))), 36),
                     lt(abs_(sub(var("y"), add(var("P1Y"), 55))), 70)), [
                set_var("P1Hit", var("dmg")), set_var("P1HitType", "fleche"),
                if_else(gt(var("vx"), 0), [set_var("P1HitDir", 1)], [set_var("P1HitDir", -1)]),
                set_var("life", 0),
            ]),
        ]),
    ]),
    hide(),
    delete_clone(),
)

# ================================================================== STAGE
S.script(when_flag(), switch_backdrop("menu"))

# ------------------------------------------------------------------ build
os.makedirs(os.path.dirname(OUT), exist_ok=True)
pj = P.build(OUT)
nblocks = sum(len(t["blocks"]) for t in pj["targets"])
print(f"OK -> {OUT}  ({os.path.getsize(OUT)//1024} Ko, {nblocks} blocs, {len(pj['targets'])} cibles)")
