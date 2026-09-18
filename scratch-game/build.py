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
    # nom, teinte, luminosité, PV, vitesse, aggro, garde, réaction, taille, arène, accessoire,
    # arme équipée, niveau de cette arme (1..5)
    ("Kid Bleu", 133, 0, 70, 3.2, 25, 10, 14, 85, "dojo", "aucun", 1, 1),
    ("Verdo", 67, 0, 85, 3.6, 35, 20, 12, 88, "dojo", "casquette", 1, 1),
    ("Sunny", 30, 10, 100, 4.0, 45, 30, 10, 90, "toits", "lunettes", 1, 2),
    ("Violette", 150, 0, 110, 4.4, 50, 40, 9, 92, "toits", "chat", 1, 2),
    ("Cyan-X", 100, 0, 120, 4.8, 60, 45, 8, 95, "volcan", "bandeau", 6, 3),
    ("Rosa", 178, 0, 130, 5.0, 65, 55, 7, 95, "volcan", "aureole", 5, 2),
    ("Ombre", 0, -70, 150, 5.4, 75, 60, 5, 100, "cyber", "cornes", 2, 3),
    ("Le Champion", 25, 20, 180, 5.8, 85, 70, 4, 108, "cyber", "couronne", 4, 4),
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
# Chaque arme change vraiment le combat (allonge, dégâts, vitesse, spécial, garde, projectiles).
# Elle s'ACHÈTE en boutique puis s'AMÉLIORE de niveau 1 à 5 : chaque niveau au-dessus du 1er
# ajoute incP / incK / incS points de dégâts et incR px d'allonge.
#   nom, prix, costume, portee (+px poing/pied), dmgP, dmgK, totP, totK (images),
#   spe (0 frappe, 1 estoc, 2 charge, 3 marteau), speDmg, speTot, spePortee, garde, proj,
#   incP, incK, incS, incR, prixUpg (amélioration niveau L -> L+1 = prixUpg * L),
#   ligne1 (effet), ligne2 (spécial), ligne3 (faiblesse)
ARMES = [
    ("Poings", 0, "fists", 0, 0, 0, 13, 20, 0, 24, 28, 100, 0, 0, 1, 1, 2, 4, 30,
     "Style de référence, sans défaut.", "Spécial : coup direct.",
     "Aucune allonge bonus."),
    ("Épée", 200, "epee", 48, 2, 2, 16, 24, 1, 26, 26, 128, 0, 0, 1, 1, 2, 8, 40,
     "Frappe vite et loin.", "Spécial : estoc qui avance.",
     "Récupération plus longue."),
    ("Lance", 240, "lance", 72, -1, 0, 20, 30, 2, 30, 40, 168, 0, 0, 1, 1, 3, 8, 45,
     "La plus grande allonge.", "Spécial : CHARGE qui fonce.",
     "Poing faible au niveau 1."),
    ("Marteau", 280, "marteau", 32, 1, 2, 20, 32, 3, 34, 52, 112, 0, 0, 1, 2, 4, 6, 50,
     "Brise la garde (60 % des dégâts).", "Spécial : smash qui sonne.",
     "Très lent : 52 images."),
    ("Arc", 260, "arc", 22, -1, 2, 14, 24, 4, 10, 60, 150, 0, 1, 1, 2, 2, 4, 50,
     "Combat à distance.", "Spécial : salve de 3 flèches.",
     "Corps à corps faible."),
    ("Bouclier", 220, "bouclier", -12, 1, -2, 16, 24, 0, 24, 28, 88, 1, 0, 1, 1, 2, 4, 40,
     "Garde : 0 dégât subi.", "Garde brisée : 20 % au lieu de 50 %.",
     "Allonge réduite."),
]
ARME_NIVEAU_MAX = 5
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
ARME_INCP = [a[14] for a in ARMES]
ARME_INCK = [a[15] for a in ARMES]
ARME_INCS = [a[16] for a in ARMES]
ARME_INCR = [a[17] for a in ARMES]
ARME_UPG = [a[18] for a in ARMES]
ARME_L1 = [a[19] for a in ARMES]
ARME_L2 = [a[20] for a in ARMES]
ARME_L3 = [a[21] for a in ARMES]

FLECHE_VITESSE = 9
FLECHE_VIE = 55            # portée : 55 x 9 = 495 px (l'arène fait 480 de large)
RECHARGE_TIR = 30
BULLE_DUREE = 90      # bouclier personnel : 3 s
BULLE_CD = 150        # ... puis 5 s de recharge          # images de rechargement après chaque flèche (arc)

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
    ("flX", 0), ("flY", 0), ("flDir", 90), ("flWho", 1), ("flDmg", 13), ("fxVie", 90), ("fxWho", 1),
    ("P1BulleT", 0), ("P1BulleCd", 0), ("fxFort", 0),
    ("P1ArmeMain", 1), ("BotArmeMain", 1), ("armeMain", 1), ("pNiv", 0), ("pNivTxt", "111111"),
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
S.add_list("armeNiveau", [1] * len(ARMES))          # niveau 1..5 de chaque arme (joueur)
S.add_list("armeIncP", ARME_INCP)
S.add_list("armeIncK", ARME_INCK)
S.add_list("armeIncS", ARME_INCS)
S.add_list("armeIncR", ARME_INCR)
S.add_list("armeUpgBase", ARME_UPG)
S.add_list("botArmeNiv", [b[12] for b in BOTS])

# --- arbre de talents : deux voies par arme, 1 point par niveau au-dessus de 1.
#     (voie A : nom, stat, incrément par point, texte ; idem voie B)
TALENTES = {
    1: (("Furie", "dmg", 2, "+2 dégâts par point"), ("Ombre", "dash", 2, "esquive +2 images par point")),
    2: (("Estoc", "range", 12, "+12 portée par point"), ("Danse", "vit", 0.4, "+0,4 vitesse par point")),
    3: (("Charge", "spe", 4, "+4 dégâts de charge par point"), ("Allonge", "range", 12, "+12 portée par point")),
    4: (("Broyeur", "spe", 5, "+5 dégâts de smash par point"), ("Acier", "def", 5, "-5 % dégâts subis par point")),
    5: (("Tir tendu", "cut", 4, "recharge -4 images par point"), ("Tir lourd", "dmg", 3, "+3 dégâts par point")),
    6: (("Rempart", "def", 4, "-4 % dégâts subis par point"), ("Regain", "regen", 1, "+1 PV / 25 images par point")),
}
TAL_VAR = {"dmg": "talDmg", "spe": "talSpe", "range": "talRange", "vit": "talVit",
           "def": "talParry", "cut": "talCut", "dash": "talDash", "regen": "talRegen"}
S.add_list("talNomA", [TALENTES[k][0][0] for k in sorted(TALENTES)])
S.add_list("talNomB", [TALENTES[k][1][0] for k in sorted(TALENTES)])
S.add_list("talStatA", [TALENTES[k][0][1] for k in sorted(TALENTES)])
S.add_list("talStatB", [TALENTES[k][1][1] for k in sorted(TALENTES)])
S.add_list("talIncA", [TALENTES[k][0][2] for k in sorted(TALENTES)])
S.add_list("talIncB", [TALENTES[k][1][2] for k in sorted(TALENTES)])
S.add_list("talTxtA", [TALENTES[k][0][3] for k in sorted(TALENTES)])
S.add_list("talTxtB", [TALENTES[k][1][3] for k in sorted(TALENTES)])
S.add_list("talPts", [0] * (2 * len(TALENTES)))          # points investis (2 par arme)
S.add_list("talEffet", ["", "", "", "", "", "", "", ""])  # non utilisé : résumé texte recalculé
# variables de la page TALENTS
for v, d in [("talPtsRestants", 0), ("talTotal", 0), ("talDepense", 0), ("talLigne", "")]:
    S.add_var(v, d)

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
# Combattants -> accessoires (par-dessus la tête) -> FX/flèches -> Interface.
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
    _FXC = {"spark": (30, 30), "dot": (12, 12), "ring": (40, 40), "bolt": (20, 30), "pixel": (2, 2),
        "bulle": (70, 70), "etoile": (35, 35), "eclair": (40, 30), "poussiere": (15, 15)}
for fn, svg in assets.fx_svgs().items():
    cx, cy = _FXC[fn]
    fx.add_costume(fn, svg, cx, cy)
fx.visible = False

for gname, svg, cx, cy, adv in glyphs:
    ui.add_costume(gname, svg, cx, cy)
ICONE_BASE = len(ui.costumes)  # les icônes d'armes viennent après les glyphes (glyphW indexé par n° de costume)
ui.add_costume("poings", assets.poing_icon_svg(), 60, 60)
for wid in ARME_COST[1:]:
    ui.add_costume(wid, assets.weapon_icon_svg(wid), 60, 60)

# flèche de l'arc
fleche.add_costume("fleche", assets.arrow_svg(), 38, 10)
fleche.rotation_style = "all around"
fleche.visible = False
add_sounds(fleche, ["tir", "hit"])
ui.visible = False
add_sounds(ui, ["click", "coin", "win", "lose", "round", "ko"])

# Logo du jeu : costume vectoriel unique (créé en dernier, il passe donc devant l'interface).
# Affiché seulement dans le menu principal, il remplace l'ancien titre tamponné glyphe par glyphe.
logo = P.sprite("Logo")
logo.add_costume("logo", assets.logo_svg(), assets.LOGO_W / 2, assets.LOGO_H / 2)
logo.visible = False
# (le forever DOIT être accroché au drapeau : un bloc C isolé ne tourne jamais)
logo.script(when_flag(), set_size(46), goto_xy(0, 124), hide(), forever([
    if_else(eq(var("scene"), "menu"), [show()], [hide()]),
]))

# ================================================================== INTERFACE (moteur texte + écrans)
U = ui
for v in ["cx", "i", "ch", "prefix", "bx", "by", "bw", "bh", "hover", "k", "ratio", "px", "py", "col", "n",
          "padded", "bits", "mult", "digits", "part", "somme", "ok", "pBitsArmes", "pArmeCode", "pNivTxt",
          "pTalTxt", "pTal", "dep", "maxi",
          # aperçu d'arme : valeurs courantes / niveau suivant
          "dmP", "dmK", "dmS", "allg", "nxP", "nxK", "nxS", "nxR", "cout", "sA", "sB", "m", "lab"]:
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
            # grand panneau : coins arrondis de rayon 24, rempli par bandes horizontales
            # (pas de 8 px pour un stylo de 24 : les bandes se chevauchent, aucun trou)
            pen_size(24),
            set_var("py", sub(add(arg("y"), div(arg("h"), 2)), 12)),
            repeat_until(lt(var("py"), add(sub(arg("y"), div(arg("h"), 2)), 12)), [
                goto_xy(add(arg("x"), 12), var("py")),
                pen_down(),
                goto_xy(sub(add(arg("x"), arg("w")), 12), var("py")),
                pen_up(),
                change_var("py", -8),
            ]),
            # dernière bande collée au bas du panneau (sinon le bord reste déchiqueté)
            goto_xy(add(arg("x"), 12), add(sub(arg("y"), div(arg("h"), 2)), 12)),
            pen_down(),
            goto_xy(sub(add(arg("x"), arg("w")), 12), add(sub(arg("y"), div(arg("h"), 2)), 12)),
            pen_up(),
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



# --- bloc : apercuArme k   -> sA, sB (stats : niveau actuel -> suivant), cout (amélioration)
U.script(define("apercuArme %s", ["k"], [
    set_var("n", item("armeNiveau", arg("k"))),
    set_var("m", sub(var("n"), 1)),                       # niveaux acquis au-dessus du 1er
    set_var("dmP", add(add(PUNCH["dmg"], item("armeDmgP", arg("k"))), mul(var("m"), item("armeIncP", arg("k"))))),
    set_var("dmK", add(add(KICK["dmg"], item("armeDmgK", arg("k"))), mul(var("m"), item("armeIncK", arg("k"))))),
    set_var("dmS", add(item("armeSpeDmg", arg("k")), mul(var("m"), item("armeIncS", arg("k"))))),
    set_var("allg", add(item("armePortee", arg("k")), mul(var("m"), item("armeIncR", arg("k"))))),
    # valeurs du niveau suivant (identiques si l'arme est déjà au niveau maximum)
    set_var("m", var("n")),
    if_(ge(var("n"), ARME_NIVEAU_MAX), [set_var("m", sub(var("n"), 1))]),
    set_var("nxP", add(add(PUNCH["dmg"], item("armeDmgP", arg("k"))), mul(var("m"), item("armeIncP", arg("k"))))),
    set_var("nxK", add(add(KICK["dmg"], item("armeDmgK", arg("k"))), mul(var("m"), item("armeIncK", arg("k"))))),
    set_var("nxS", add(item("armeSpeDmg", arg("k")), mul(var("m"), item("armeIncS", arg("k"))))),
    set_var("nxR", add(item("armePortee", arg("k")), mul(var("m"), item("armeIncR", arg("k"))))),
    # l'arc n'a pas de coup de pied : c'est la flèche qui part
    set_var("lab", "Pied "),
    if_(eq(item("armeProj", arg("k")), 1), [set_var("lab", "Flèche ")]),
    if_else(lt(var("n"), ARME_NIVEAU_MAX), [
        set_var("sA", join4("Poing ", var("dmP"), "  →  ",
                            join4(var("nxP"), join("   ", var("lab")), var("dmK"), join("  →  ", var("nxK"))))),
        set_var("sB", join4("Spé ", var("dmS"), "  →  ",
                            join4(var("nxS"), "    Allonge +", var("allg"), join("  →  +", var("nxR"))))),
    ], [
        set_var("sA", join4("Poing ", var("dmP"), join("    ", var("lab")), var("dmK"))),
        set_var("sB", join4("Spé ", var("dmS"), "    Allonge +", var("allg"))),
    ]),
    set_var("cout", mul(item("armeUpgBase", arg("k")), var("n"))),
]))


# --- sauvegarde : code numérique  N PPPPP AAA SS A S BB A NNNNNN CC  (24 chiffres, par groupes)
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

U.script(define("checksum %s %s %s %s %s %s %s %s", ["a", "b", "c", "d", "e", "f", "g", "h"], [
    set_var("somme", add(mul(arg("a"), 3), add(mul(arg("b"), 7), add(mul(arg("c"), 11),
                     add(mul(arg("d"), 13), add(mul(arg("e"), 17), add(mul(arg("f"), 19),
                     add(mul(arg("g"), 23), mul(arg("h"), 29))))))))),
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
    # niveaux des 6 armes (1 chiffre chacune) : ajoutés au code et à la somme de contrôle
    set_var("pNivTxt", ""), set_var("k", 1),
    repeat(len(ARMES), [
        set_var("pNivTxt", join(var("pNivTxt"), item("armeNiveau", var("k")))),
        change_var("k", 1),
    ]),
    set_var("pNiv", add(var("pNivTxt"), 0)),
    # points de talent investis (2 par arme = 12 chiffres)
    set_var("pTalTxt", ""), set_var("k", 1),
    repeat(mul(len(ARMES), 2), [
        set_var("pTalTxt", join(var("pTalTxt"), item("talPts", var("k")))),
        change_var("k", 1),
    ]),
    set_var("pTal", add(var("pTalTxt"), 0)),
    if_(gt(var("pieces"), 99999), [set_var("pieces", 99999)]),
    call("checksum %s %s %s %s %s %s %s %s", var("niveauMax"), var("pieces"), var("px"), var("py"), var("n"),
         var("P1Skin"), var("pNiv"), var("pTal")),
    set_var("codeSauvegarde", var("niveauMax")),
    call("pad %s %s", var("pieces"), 5), set_var("codeSauvegarde", join(var("codeSauvegarde"), var("padded"))),
    call("pad %s %s", var("px"), 3), set_var("codeSauvegarde", join(var("codeSauvegarde"), var("padded"))),
    call("pad %s %s", var("py"), 2), set_var("codeSauvegarde", join(var("codeSauvegarde"), var("padded"))),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), join(var("n"), var("P1Skin")))),
    call("pad %s %s", var("pBitsArmes"), 2), set_var("codeSauvegarde", join(var("codeSauvegarde"), var("padded"))),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), var("pArmeCode"))),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), var("pNivTxt"))),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), var("pTalTxt"))),
    call("pad %s %s", var("somme"), 2), set_var("codeSauvegarde", join(var("codeSauvegarde"), var("padded"))),
    # groupes lisibles : 1-5-3-2-1-1-2-1-6-12-2
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
    repeat(6, [set_var("codeSauvegarde", join(var("codeSauvegarde"), letter(var("i"), var("digits")))), change_var("i", 1)]),
    set_var("codeSauvegarde", join(var("codeSauvegarde"), "-")),
    repeat(12, [set_var("codeSauvegarde", join(var("codeSauvegarde"), letter(var("i"), var("digits")))), change_var("i", 1)]),
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
    if_(or_(eq(strlen(var("digits")), 36),
            or_(eq(strlen(var("digits")), 24), or_(eq(strlen(var("digits")), 18), eq(strlen(var("digits")), 15)))), [
        call("extraire %s %s", 1, 1), set_var("bx", var("part")),      # niveauMax
        call("extraire %s %s", 2, 5), set_var("by", var("part")),      # pièces
        call("extraire %s %s", 7, 3), set_var("px", var("part")),      # bits acc
        call("extraire %s %s", 10, 2), set_var("py", var("part")),     # bits skins
        call("extraire %s %s", 12, 1), set_var("n", var("part")),      # acc équipé
        call("extraire %s %s", 13, 1), set_var("k", var("part")),      # skin équipé
        # armes (bits + équipée) : format 24 ou 18 chiffres ; niveaux : format 24 seulement
        set_var("pNivTxt", "111111"), set_var("pNiv", 0),   # 0 = pas de niveaux dans le code
        set_var("pTalTxt", "000000000000"), set_var("pTal", 0),   # 0 = aucun point de talent placé
        if_else(eq(strlen(var("digits")), 15), [
            set_var("pBitsArmes", 0), set_var("pArmeCode", 0),
            call("extraire %s %s", 14, 2), set_var("cx", var("part")),  # checksum (format d'origine)
        ], [
            call("extraire %s %s", 14, 2), set_var("pBitsArmes", var("part")),
            call("extraire %s %s", 16, 1), set_var("pArmeCode", var("part")),
            if_else(or_(eq(strlen(var("digits")), 24), eq(strlen(var("digits")), 36)), [
                # niveaux des armes (6 chiffres), puis talents (12 chiffres) au format 36
                set_var("pNivTxt", ""), set_var("i", 1),
                repeat(len(ARMES), [
                    set_var("pNivTxt", join(var("pNivTxt"), letter(add(var("i"), 16), var("digits")))),
                    change_var("i", 1),
                ]),
                set_var("pNiv", add(var("pNivTxt"), 0)),
                if_else(eq(strlen(var("digits")), 36), [
                    # les 12 chiffres de talents, recopiés un par un (les zéros de tête comptent)
                    set_var("pTalTxt", ""), set_var("i", 1),
                    repeat(mul(len(ARMES), 2), [
                        set_var("pTalTxt", join(var("pTalTxt"), letter(add(var("i"), 22), var("digits")))),
                        change_var("i", 1),
                    ]),
                    set_var("pTal", add(var("pTalTxt"), 0)),
                    call("extraire %s %s", 35, 2), set_var("cx", var("part")),
                ], [
                    call("extraire %s %s", 23, 2), set_var("cx", var("part")),
                ]),
            ], [
                call("extraire %s %s", 17, 2), set_var("cx", var("part")),
            ]),
        ]),
        call("checksum %s %s %s %s %s %s %s %s", var("bx"), var("by"), var("px"), var("py"), var("n"), var("k"),
             var("pNiv"), var("pTal")),
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
            # niveaux d'armes : lus dans le code (1 par défaut), bornés à 1..5
            set_var("i", 1),
            repeat(len(ARMES), [
                set_var("part", letter(var("i"), var("pNivTxt"))),
                set_var("part", add(var("part"), 0)),
                if_(lt(var("part"), 1), [set_var("part", 1)]),
                if_(gt(var("part"), ARME_NIVEAU_MAX), [set_var("part", ARME_NIVEAU_MAX)]),
                list_replace("armeNiveau", var("i"), var("part")),
                change_var("i", 1),
            ]),
            # points de talent : un chiffre par voie, bornés par le niveau de l'arme
            set_var("i", 1),
            repeat(mul(len(ARMES), 2), [
                set_var("part", letter(var("i"), var("pTalTxt"))),
                set_var("part", add(var("part"), 0)),
                if_(lt(var("part"), 0), [set_var("part", 0)]),
                if_(gt(var("part"), ARME_NIVEAU_MAX - 1), [set_var("part", ARME_NIVEAU_MAX - 1)]),
                list_replace("talPts", var("i"), var("part")),
                change_var("i", 1),
            ]),
            # on ne garde jamais plus de points que le niveau de l'arme n'en donne
            set_var("i", 1),
            repeat(len(ARMES), [
                set_var("dep", add(item("talPts", sub(mul(var("i"), 2), 1)), item("talPts", mul(var("i"), 2)))),
                set_var("maxi", sub(item("armeNiveau", var("i")), 1)),
                if_(gt(var("dep"), var("maxi")), [
                    list_replace("talPts", sub(mul(var("i"), 2), 1), 0),
                    list_replace("talPts", mul(var("i"), 2), 0),
                ]),
                change_var("i", 1),
            ]),
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
    rect(-200, 40, 400, 56, "#000000", 30),
    # 36 chiffres + 10 tirets : police adaptée pour que le code tienne dans le cadre
    ecrire(var("codeSauvegarde"), 0, 30, 28, -1, 1),
    ecrire("Note ce code (ou copie-le dans la liste à l'écran).", 0, -10, 30, -1, 1),
    ecrire("Au prochain lancement : Menu, CHARGER, puis colle le code.", 0, -32, 30, -1, 1),
    ecrire("Il contient : niveau max, pièces, armes (niveaux + talents) et cosmétiques.", 0, -58, 22, -2, 1),
    bouton(0, -110, 160, 40, "RETOUR", "menu", COL["grey"], 42),
]))

# --- écran MENU
U.script(define("dessinerMenu", [], [
    # le titre est un vrai logo vectoriel (sprite Logo, posé au-dessus) : ici on ne garde
    # que la baseline et l'accroche de la boutique
    ecrire("COMBAT 2D - 8 BOTS - 6 ARMES - 4 ARÈNES", 0, 46, 24, -2, 1),
    bouton(80, 20, 200, 42, "JOUER", "jouer", COL["accent"], 50),
    bouton(80, -28, 200, 42, "BOUTIQUE", "boutique", COL["accent2"], 50),
    bouton(80, -76, 200, 42, "COMMANDES", "commandes", COL["grey"], 50),
    bouton(28, -116, 100, 32, "SAUVER", "sauver", COL["ok"], 32),
    bouton(134, -116, 100, 32, "CHARGER", "charger", COL["sp"], 32),
    # au centre de la barre du bas : le message de sauvegarde s'il y en a un, sinon l'arme équipée
    if_else(gt(var("phaseTimer"), 0), [
        change_var("phaseTimer", -1),
        if_else(eq(var("infoSauvegarde"), "Code invalide"), [
            ecrire(var("infoSauvegarde"), 80, -158, 28, 0, 1),
        ], [
            ecrire(var("infoSauvegarde"), 80, -158, 28, 67, 1),
        ]),
    ], [
        ecrire(join(item("armeNom", var("P1ArmeOrig")), join(" niv.", item("armeNiveau", var("P1ArmeOrig")))),
               -14, -156, 26, 30, 1),
    ]),
    rect(-240, -150, 480, 40, "#000000", 40),
    ecrire(join(var("pieces"), " pièces"), -228, -156, 40, 30, 0),
    if_(eq(var("phaseTimer"), 0), [ecrire(join("Niveau max : ", var("niveauMax")), 228, -156, 40, -1, 2)]),
]))

# --- écran COMMANDES
U.script(define("dessinerCommandes", [], [
    rect(-200, 0, 400, 300, COL["panel"], 15),
    ecrire("COMMANDES", 0, 105, 80, 30, 1),
    ecrire("Flèches gauche / droite : se déplacer", 0, 74, 30, -1, 1),
    ecrire("Double-appui sur une flèche : esquive invulnérable", 0, 52, 28, 30, 1),
    ecrire("Flèche haut : sauter (on attaque en l'air)", 0, 30, 28, -1, 1),
    ecrire("Flèche bas : garde (12 % des dégâts, 0 avec le bouclier)", 0, 8, 28, -1, 1),
    ecrire("U : bouclier 3 s (-70 % des dégâts), puis 5 s de recharge", 0, -14, 28, 100, 1),
    ecrire("J : poing  K : pied (flèche avec l'arc)  L : SPÉCIAL", 0, -42, 28, 30, 1),
    ecrire("Boutique : achète, équipe, améliore l'arme jusqu'au niveau 5", 0, -64, 28, 67, 1),
    ecrire("Atelier : 1 point de talent par niveau, 2 voies par arme,", 0, -86, 28, 67, 1),
    ecrire("à répartir et à changer quand tu veux.", 0, -108, 28, 67, 1),
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
    bouton(0, 100, 84, 30, "TALENTS", "tab3", COL["grey"], 26),
]
U.script(define("dessinerBoutique", [], shop))

# ---------- page 2 : les armes (achat, équipement, amélioration niveau 1..5)
armes_shop = [
    rect(-240, 150, 480, 60, "#000000", 55),
    ecrire("ARMES", 0, 152, 64, 30, 1),
    ecrire(join(var("pieces"), " pièces"), 228, 152, 34, 30, 2),
    bouton(-180, 100, 84, 30, "LOOK", "tab1", COL["grey"], 26),
    bouton(-90, 100, 84, 30, "ARMES", "tab2", COL["ok"], 26),
    bouton(0, 100, 84, 30, "TALENTS", "tab3", COL["grey"], 26),
    # 6 armes en 3 x 2 ; le niveau est écrit dans le bouton des armes possédées
    set_var("k", 1),
]
armes_shop.append(repeat(len(ARMES), [
    set_var("bx", add(-160, mul(mod(sub(var("k"), 1), 3), 160))),
    set_var("by", sub(70, mul(floor(div(sub(var("k"), 1), 3)), 37))),
    if_else(eq(item("armePossede", var("k")), 1), [
        if_else(eq(var("k"), var("P1Arme")), [
            bouton(var("bx"), var("by"), 150, 32, join(item("armeNom", var("k")), join(" niv.", item("armeNiveau", var("k")))),
                   join("arme", var("k")), COL["ok"], 28),
        ], [
            bouton(var("bx"), var("by"), 150, 32, join(item("armeNom", var("k")), join(" niv.", item("armeNiveau", var("k")))),
                   join("arme", var("k")), COL["accent2"], 28),
        ]),
    ], [
        bouton(var("bx"), var("by"), 150, 32, join(item("armeNom", var("k")), join(" ", item("armePrix", var("k")))),
               join("arme", var("k")), COL["grey"], 28),
    ]),
    change_var("k", 1),
]))
armes_shop += [
    # panneau d'aperçu : nom + niveau, stats (niveau courant -> suivant), effet, amélioration
    rect(-235, -63, 470, 142, COL["panel"], 12),
    *icone_arme(var("armeApercu"), -205, -30, 40),
    call("apercuArme %s", var("armeApercu")),
    ecrire(join(item("armeNom", var("armeApercu")), join("   Niv. ", join(item("armeNiveau", var("armeApercu")), "/5"))),
           -150, -6, 30, 30, 0),
    ecrire(var("sA"), -150, -34, 22, -1, 0),
    ecrire(var("sB"), -150, -56, 22, -1, 0),
    ecrire(join(item("armeL1", var("armeApercu")), join(" ", item("armeL3", var("armeApercu")))),
           -150, -80, 21, -2, 0),
    if_else(and_(eq(item("armePossede", var("armeApercu")), 1), lt(item("armeNiveau", var("armeApercu")), ARME_NIVEAU_MAX)), [
        bouton(60, -106, 340, 28, join("AMÉLIORER   ", join(var("cout"), " pièces")), "upg", COL["warn"], 24),
    ], [
        if_else(eq(item("armePossede", var("armeApercu")), 1), [
            ecrire("NIVEAU MAX", 60, -106, 24, 67, 1),
        ], [
            ecrire(join("Achat : ", join(item("armePrix", var("armeApercu")), " pièces")), 60, -106, 24, -2, 1),
        ]),
    ]),
    if_else(eq(var("P1Arme"), var("armeApercu")), [
        ecrire("ÉQUIPÉE", 60, -130, 21, 67, 1),
    ], [
        if_else(eq(item("armePossede", var("armeApercu")), 1), [
            ecrire("Achetée : cliquer pour équiper", 60, -130, 21, 100, 1),
        ], [
            ecrire("Cliquer sur l'arme pour l'acheter", 60, -130, 21, -2, 1),
        ]),
    ]),
    bouton(-150, -150, 150, 40, "RETOUR", "menu", COL["grey"], 42),
]
U.script(define("dessinerBoutiqueArmes", [], armes_shop))


# ---------- page 3 : l'atelier (arbre de talents par arme)
talents_shop = [
    rect(-240, 150, 480, 60, "#000000", 55),
    ecrire("ATELIER", 0, 152, 64, 67, 1),
    ecrire(join(var("pieces"), " pièces"), 228, 152, 34, 30, 2),
    bouton(-180, 100, 84, 30, "LOOK", "tab1", COL["grey"], 26),
    bouton(-90, 100, 84, 30, "ARMES", "tab2", COL["grey"], 26),
    bouton(0, 100, 84, 30, "TALENTS", "tab3", COL["ok"], 26),
    # sélection de l'arme (1 par niveau au-dessus de 1)
    set_var("k", 1),
    repeat(len(ARMES), [
        set_var("bx", add(-190, mul(sub(var("k"), 1), 76))),
        if_else(eq(var("k"), var("armeApercu")), [
            bouton(var("bx"), 62, 72, 26, item("armeNom", var("k")), join("talw", var("k")), COL["ok"], 20),
        ], [
            bouton(var("bx"), 62, 72, 26, item("armeNom", var("k")), join("talw", var("k")), COL["grey"], 20),
        ]),
        change_var("k", 1),
    ]),
    # points disponibles pour l'arme affichée
    set_var("talTotal", sub(item("armeNiveau", var("armeApercu")), 1)),
    set_var("talDepense", add(item("talPts", sub(mul(var("armeApercu"), 2), 1)), item("talPts", mul(var("armeApercu"), 2)))),
    set_var("talPtsRestants", sub(var("talTotal"), var("talDepense"))),
    if_(lt(var("talPtsRestants"), 0), [set_var("talPtsRestants", 0)]),
    rect(-235, -58, 470, 152, COL["panel"], 14),
    *icone_arme(var("armeApercu"), -205, -10, 36),
    ecrire(join(item("armeNom", var("armeApercu")), join("   Niv. ", item("armeNiveau", var("armeApercu")))),
           -178, 2, 28, 30, 0),
    ecrire(join(join("Points à placer : ", var("talPtsRestants")), join(join(" / ", var("talTotal")),
           "   (1 par niveau, modifiable)")), -178, -20, 22, 30, 0),
    # voie A
    ecrire(join("VOIE A   ", item("talNomA", var("armeApercu"))), -215, -44, 24, 100, 0),
    ecrire(join("investi : ", join(item("talPts", sub(mul(var("armeApercu"), 2), 1)), "")), -215, -64, 20, -1, 0),
    ecrire(item("talTxtA", var("armeApercu")), -90, -64, 20, -2, 0),
    bouton(150, -40, 70, 26, "+1", "talA", COL["accent"], 28),
    # voie B
    ecrire(join("VOIE B   ", item("talNomB", var("armeApercu"))), -215, -88, 24, 30, 0),
    ecrire(join("investi : ", join(item("talPts", mul(var("armeApercu"), 2)), "")), -215, -108, 20, -1, 0),
    ecrire(item("talTxtB", var("armeApercu")), -90, -108, 20, -2, 0),
    bouton(150, -84, 70, 26, "+1", "talB", COL["accent"], 28),
    bouton(150, -120, 70, 24, "EFFACER", "talR", COL["grey"], 20),
    bouton(-150, -158, 150, 36, "RETOUR", "menu", COL["grey"], 42),
]
U.script(define("dessinerTalents", [], talents_shop))

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
        ecrire("SPÉCIAL PRÊT (L)", -228, 94, 26, 100, 0),
    ]),
    # bouclier personnel (touche U) : vert tant qu'il protège, sinon la recharge se remplit
    ecrire("BOUCLIER (U)", -228, 126, 22, 100, 0),
    if_else(gt(var("P1BulleT"), 0),
            [barre(-112, 112, 82, 8, 1, COL["hp"], -1)],
            [barre(-112, 112, 82, 8, div(sub(BULLE_CD, var("P1BulleCd")), BULLE_CD), COL["sp"], -1)]),
    # arme en main (le joueur et le bot)
    rect(-238, -171, 476, 36, "#000000", 55),
    rect(-238, -189, 476, 2, COL["grey"], 0),
    *icone_arme(var("P1ArmeMain"), -212, -170, 30),
    ecrire(join("TOI : ", join(item("armeNom", var("P1ArmeMain")), join(" niv.", item("armeNiveau", var("P1ArmeMain"))))),
           -180, -176, 28, -1, 0),
    if_(eq(item("armeProj", var("P1ArmeMain")), 1), [ecrire("K : tir / L : salve", -180, -160, 22, 100, 0)]),
    ecrire(join(var("BotNom"), join(" : ", join(item("armeNom", var("BotArmeMain")),
           join(" niv.", item("botArmeNiv", var("niveau")))))), 180, -176, 28, -1, 2),
    *icone_arme(var("BotArmeMain"), 212, -170, 30),
    if_(gt(var("comboP1"), 1), [
        ecrire(join(var("comboP1"), " HITS !"), -228, 80, 44, 30, 0),
    ]),
    if_(not_(eq(var("message"), "")), [
        ecrire(var("message"), 3, 27, 90, -3, 1),
        ecrire(var("message"), 0, 30, 90, 30, 1),
    ]),
    if_(and_(eq(var("phase"), "intro"), eq(var("round"), 1)), [
        ecrire("Double-appui : esquive   U : bouclier   Flèches : bouger / sauter / garde   J/K/L : attaques", 0, -160, 26, -2, 1),
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
    # atelier : sélection de l'arme affichée + points de talent
    if_(eq(join4(letter(1, var("clic")), letter(2, var("clic")), letter(3, var("clic")), letter(4, var("clic"))), "talw"), [
        set_var("armeApercu", add(letter(5, var("clic")), 0)),
        play_sound("click"),
    ]),
    if_(or_(eq(var("clic"), "talA"), eq(var("clic"), "talB")), [
        set_var("k", var("armeApercu")),
        set_var("talTotal", sub(item("armeNiveau", var("k")), 1)),
        set_var("talDepense", add(item("talPts", sub(mul(var("k"), 2), 1)), item("talPts", mul(var("k"), 2)))),
        if_else(ge(var("talDepense"), var("talTotal")), [
            set_var("message", "Plus de points : améliore l'arme !"), set_var("phaseTimer", 40),
        ], [
            if_(eq(var("clic"), "talA"), [
                set_var("i", sub(mul(var("k"), 2), 1)),
            ]),
            if_(eq(var("clic"), "talB"), [set_var("i", mul(var("k"), 2))]),
            list_replace("talPts", var("i"), add(item("talPts", var("i")), 1)),
            play_sound("click"),
        ]),
    ]),
    if_(eq(var("clic"), "talR"), [
        set_var("k", var("armeApercu")),
        list_replace("talPts", sub(mul(var("k"), 2), 1), 0),
        list_replace("talPts", mul(var("k"), 2), 0),
        play_sound("click"), set_var("message", "Points rendus !"), set_var("phaseTimer", 40),
    ]),
    if_(eq(var("clic"), "tab3"), [set_var("shopPage", 3), set_var("armeApercu", var("P1Arme"))]),
    # amélioration de l'arme affichée (niveau 1 -> 5, coût = prixUpg x niveau courant)
    if_(eq(var("clic"), "upg"), [
        set_var("k", var("armeApercu")),
        set_var("n", item("armeNiveau", var("k"))),
        set_var("cout", mul(item("armeUpgBase", var("k")), var("n"))),
        if_else(and_(eq(item("armePossede", var("k")), 1), lt(var("n"), ARME_NIVEAU_MAX)), [
            if_else(ge(var("pieces"), var("cout")), [
                change_var("pieces", mul(-1, var("cout"))),
                list_replace("armeNiveau", var("k"), add(var("n"), 1)),
                # un niveau de plus = un point de talent de plus pour cette arme
                set_var("talTotal", sub(item("armeNiveau", var("k")), 1)),
                set_var("talDepense", add(item("talPts", sub(mul(var("k"), 2), 1)), item("talPts", mul(var("k"), 2)))),
                if_(lt(var("talTotal"), var("talDepense")), [
                    list_replace("talPts", sub(mul(var("k"), 2), 1), 0),
                    list_replace("talPts", mul(var("k"), 2), 0),
                ]),
                play_sound("coin"),
                set_var("fxType", "ring"), set_var("fxX", 60), set_var("fxY", -100), create_clone("FX"),
            ], [
                set_var("message", "Pas assez de pièces !"), set_var("phaseTimer", 40),
            ]),
        ], [set_var("message", "Niveau maximum !"), set_var("phaseTimer", 40)]),
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
            if_else(eq(var("shopPage"), 1), [call("dessinerBoutique")],
                    [if_else(eq(var("shopPage"), 2), [call("dessinerBoutiqueArmes")], [call("dessinerTalents")])]),
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
    for v in ["vx", "vy", "timer", "hitDone", "anim", "iMove", "iJump", "iPunch", "iKick", "iSpecial", "iBlock", "iBulle",
              "aiTimer", "attaqueTenue", "dx", "f", "dmg", "portee", "aStart", "aEnd", "aTotal", "dist", "r",
              "armeMain", "tirFait", "especeArme", "typeArme", "nivArme",
              "recharge", "dashT", "dashVx", "invT", "dashCd", "tapT", "tapDir", "avantG", "avantD", "presse",
              "lent", "talDmg", "talRange", "talSpe", "talVit", "talRegen", "talParry", "talCut", "talDash",
              "talBulle", "regenT", "bulleT", "bulleCd", "bulleCdMax"]:
        t.add_var(v, 0)

    def V(n):
        return var(me + n)

    def OV(n):
        return var(op + n)

    def setV(n, val):
        return set_var(me + n, val)

    # niveau (1..5) de l'arme en main : le joueur lit ses améliorations, le bot a le sien
    NIV = (lambda: item("armeNiveau", V("Arme"))) if is_player else (lambda: item("botArmeNiv", var("niveau")))

    def BOOST(inc_list):
        """Bonus de niveau : (niveau - 1) x incrément de l'arme."""
        return mul(sub(var("nivArme"), 1), item(inc_list, V("Arme")))

    def chV(n, val):
        return change_var(me + n, val)

    state = V("State")

    def st_is(*names):
        c = eq(state, names[0])
        for n in names[1:]:
            c = or_(c, eq(state, n))
        return c

    # ----- talents : 1 point par niveau d'arme au-dessus de 1, répartis entre deux voies
    talents = []
    if is_player:
        talents = [
            set_var(v, 0) for v in TAL_VAR.values()
        ] + [
            set_var("talPtsRestants", sub(item("armeNiveau", V("Arme")), 1)),
            set_var("talTotal", sub(item("armeNiveau", V("Arme")), 1)),
            set_var("talDepense", add(item("talPts", sub(mul(V("Arme"), 2), 1)),
                                      item("talPts", mul(V("Arme"), 2)))),
            set_var("talPtsRestants", sub(var("talTotal"), var("talDepense"))),
            if_(lt(var("talPtsRestants"), 0), [set_var("talPtsRestants", 0)]),
        ]
        for stat, vname in TAL_VAR.items():
            talents += [
                if_(eq(item("talStatA", V("Arme")), stat),
                    [change_var(vname, mul(item("talPts", sub(mul(V("Arme"), 2), 1)), item("talIncA", V("Arme"))))]),
                if_(eq(item("talStatB", V("Arme")), stat),
                    [change_var(vname, mul(item("talPts", mul(V("Arme"), 2)), item("talIncB", V("Arme"))))]),
            ]

    reset_pose = [
        set_var("vx", 0), set_var("vy", 0), set_var("timer", 0), set_var("hitDone", 0), set_var("attaqueTenue", 0),
        set_var("tirFait", 0),
        setV("State", "idle"),
        set_var("P1Arme", var("P1ArmeOrig")) if is_player else set_var("BotArme", item("botArme", var("niveau"))),
        setV("X", -120 if is_player else 120), setV("Y", GROUND), setV("Dir", 90 if is_player else -90),
        goto_xy(V("X"), V("Y")), point_dir(V("Dir")),
        switch_costume(join(item("armeCost", var("P1Arme") if is_player else var("BotArme")), "_idle")), show(),
    ]
    t.script(when_broadcast("resetRound"), reset_pose + talents)

    # ----- intentions
    if is_player:
        intents = [
            set_var("lent", 1),
            set_var("iMove", 0),
            if_(key_pressed("right arrow"), [set_var("iMove", 1)]),
            if_(key_pressed("left arrow"), [set_var("iMove", -1)]),
            # ----- ESQUIVE : double-tap gauche ou droite (invulnérable pendant la glissade)
            set_var("presse", 0),
            if_(key_pressed("right arrow"), [
                if_(eq(var("avantD"), 0), [set_var("presse", 1)]),
                set_var("avantD", 1),
            ]),
            if_(not_(key_pressed("right arrow")), [set_var("avantD", 0)]),
            if_(key_pressed("left arrow"), [
                if_(eq(var("avantG"), 0), [set_var("presse", -1)]),
                set_var("avantG", 1),
            ]),
            if_(not_(key_pressed("left arrow")), [set_var("avantG", 0)]),
            if_(and_(not_(eq(var("presse"), 0)),
                     and_(eq(var("presse"), var("tapDir")), and_(lt(var("tapT"), 14), eq(var("dashCd"), 0)))), [
                set_var("tapDir", 0), set_var("tapT", 99),
                set_var("dashT", add(10, var("talDash"))),
                set_var("dashVx", mul(var("presse"), add(9, mul(var("talDash"), 0.5)))),
                set_var("dashCd", 36),
                set_var("invT", add(8, mul(var("talDash"), 3))),
                set_var("fxType", "ring"), set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 40)),
                create_clone("FX"),
                play_sound("jump"),
            ]),
            if_(not_(eq(var("presse"), 0)), [
                if_(not_(and_(eq(var("presse"), var("tapDir")), lt(var("tapT"), 14))), [
                    set_var("tapDir", var("presse")), set_var("tapT", 0),
                ]),
            ]),
            change_var("tapT", 1),
            if_(gt(var("dashCd"), 0), [change_var("dashCd", -1)]),
            set_var("iJump", 0), if_(key_pressed("up arrow"), [set_var("iJump", 1)]),
            set_var("iBlock", 0), if_(key_pressed("down arrow"), [set_var("iBlock", 1)]),
            set_var("iBulle", 0), if_(key_pressed("u"), [set_var("iBulle", 1)]),
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
            set_var("lent", 1),
            if_else(gt(var("aiTimer"), 0), [
                change_var("aiTimer", -1),
                set_var("iPunch", 0), set_var("iKick", 0), set_var("iSpecial", 0), set_var("iJump", 0),
            ], [
                set_var("aiTimer", var("BotReaction")),
                set_var("iMove", 0), set_var("iJump", 0), set_var("iBlock", 0), set_var("iBulle", 0),
                set_var("iPunch", 0), set_var("iKick", 0), set_var("iSpecial", 0),
                # sous 35 % de vie, il tente son bouclier (une fois par recharge)
                if_(and_(eq(var("bulleCd"), 0), lt(mul(V("HP"), 100), mul(V("Max"), 35))), [
                    if_(lt(var("r"), 70), [set_var("iBulle", 1)]),
                ]),
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
        # --- avec un arc : garder ses distances et tirer
        intents += [
            if_(eq(item("armeProj", V("Arme")), 1), [
                # il ne recule que collé au corps à corps, et au ralenti (on peut le rattraper)
                if_(lt(var("dist"), 96), [
                    if_else(gt(OV("X"), V("X")), [set_var("iMove", -1)], [set_var("iMove", 1)]),
                    set_var("lent", 0.4),
                    set_var("iJump", 0),
                    # au contact : plus de tir (sinon c'est du tir dans la figure), juste des poings
                    if_(lt(var("dist"), 70), [set_var("iKick", 0)]),
                ]),
                if_(and_(gt(var("dist"), 140), lt(var("dist"), 300)), [
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
        # talents défensifs : dégâts subis réduits de talParry %
        if_(and_(gt(V("Hit"), 0), gt(var("talParry"), 0)), [
            setV("Hit", mathop("ceiling", mul(V("Hit"), sub(1, div(var("talParry"), 100))))),
            if_(lt(V("Hit"), 1), [setV("Hit", 0)]),
        ]),
        # esquive : la touche est annulée pendant les images d'invulnérabilité
        if_(and_(gt(V("Hit"), 0), gt(var("invT"), 0)), [
            set_var("fxType", "ring"), set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 50)),
            create_clone("FX"),
            setV("Hit", 0),
        ]),
        if_(and_(gt(V("Hit"), 0), gt(var("bulleT"), 0)), [
            # le bouclier encaisse : 30 % des dégâts passent
            setV("Hit", mathop("ceiling", mul(V("Hit"), 0.3))),
            set_var("fxType", "ring"), set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 45)),
            create_clone("FX"),
            if_(lt(V("Hit"), 1), [setV("Hit", 0)]),
        ]),
        if_(and_(gt(V("Hit"), 0), eq(var("invT"), 0)), [
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
                    set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 60)), set_var("fxFort", 2),
                    broadcast("fxImpact"),
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
            ] + hit_fx + [
                # éclat : étoile sur un coup lourd (charge / smash), étincelle sinon — la diffusion
                # passe par le sprite FX, dont le clone recopie les variables locales au bon moment
                set_var("fxFort", 0),
                if_(or_(eq(V("HitType"), "charge"), eq(V("HitType"), "smash")), [set_var("fxFort", 1)]),
                broadcast("fxImpact"),
            ]),
            if_(gt(V("Special"), 100), [setV("Special", 100)]),
            if_(lt(V("HP"), 0), [setV("HP", 0)]),
            setV("Hit", 0),
        ]),
    ]

    # ----- démarrage d'actions
    def bulle_action():
        """Bouclier personnel : ~3 s de protection à -70 % de dégâts, puis 5 s de recharge."""
        return if_(and_(eq(var("iBulle"), 1), eq(var("bulleCd"), 0)), [
            set_var("bulleT", add(BULLE_DUREE, mul(var("talBulle"), 6))),
            set_var("bulleCd", BULLE_CD),
            set_var("fxVie", add(BULLE_DUREE, mul(var("talBulle"), 6))),
            set_var("fxWho", 1 if is_player else 2),
            # diffusion dédiée : le clone lit fxType une image trop tard (les autres effets nés dans la
            # même image l'écrasent). Ici le FX se clone lui-même : son type est figé à la création.
            broadcast("fxBulle"),
            play_sound("special"),
            set_var("flash", 2),
        ])

    speed = add(var("P1Vitesse"), var("talVit")) if is_player else var("BotVitesse")
    start_actions = [
        bulle_action(),
        if_(st_is("idle", "walk", "block"), [
            if_else(eq(var("iBlock"), 1), [
                if_(and_(not_(eq(state, "block")), gt(V("Y"), GROUND)), [
                    # garde aérienne : propulsion vers l'arrière
                    set_var("vx", mul(V("Dir"), -0.09)),
                    set_var("vy", 3),
                    set_var("fxType", "ring"), set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 40)), create_clone("FX"),
                ]),
                setV("State", "block"),
                # en garde au sol on avance au ralenti (indispensable face à l'arc)
                if_(eq(V("Y"), GROUND), [set_var("vx", mul(var("iMove"), mul(speed, 0.5)))]),
            ], [
                if_(eq(state, "block"), [setV("State", "idle")]),
                if_else(eq(var("iPunch"), 1), [
                    set_var("aTotal", item("armeTotP", V("Arme"))),
                    set_var("dmg", add(add(add(PUNCH["dmg"], item("armeDmgP", V("Arme"))), BOOST("armeIncP")), var("talDmg"))),
                    set_var("portee", add(add(add(PUNCH["range"], item("armePortee", V("Arme"))), BOOST("armeIncR")), var("talRange"))),
                    set_var("aStart", add(PUNCH["start"], sub(var("aTotal"), PUNCH["total"]))),
                    set_var("aEnd", add(PUNCH["end"], sub(var("aTotal"), PUNCH["total"]))),
                    setV("State", "punch"), set_var("timer", var("aTotal")), set_var("hitDone", 0),
                ], [
                    if_else(and_(eq(var("iKick"), 1),
                                 or_(not_(eq(item("armeProj", V("Arme")), 1)), eq(var("recharge"), 0))), [
                        set_var("aTotal", item("armeTotK", V("Arme"))),
                        set_var("dmg", add(add(KICK["dmg"], item("armeDmgK", V("Arme"))), BOOST("armeIncK"))),
                        set_var("portee", add(add(add(KICK["range"], item("armePortee", V("Arme"))), BOOST("armeIncR")), var("talRange"))),
                        set_var("aStart", add(KICK["start"], sub(var("aTotal"), KICK["total"]))),
                        set_var("aEnd", add(KICK["end"], sub(var("aTotal"), KICK["total"]))),
                        setV("State", "kick"), set_var("timer", var("aTotal")), set_var("hitDone", 0),
                    ], [
                        if_else(and_(eq(var("iSpecial"), 1), eq(V("Special"), 100)), [
                            set_var("aTotal", item("armeSpeTot", V("Arme"))),
                            set_var("dmg", add(add(item("armeSpeDmg", V("Arme")), BOOST("armeIncS")), var("talSpe"))),
                            set_var("portee", add(add(item("armeSpePortee", V("Arme")), BOOST("armeIncR")), var("talRange"))),
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
                            set_var("vx", mul(var("iMove"), mul(speed, var("lent")))),
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

    def tirer(hauteur=56):
        """Tire une flèche : le sprite Fleche (clone) gère le vol et la collision."""
        return [
            set_var("recharge", sub(RECHARGE_TIR, var("talCut"))),
            if_(lt(var("recharge"), 12), [set_var("recharge", 12)]),
            set_var("flX", add(V("X"), mul(30, div(V("Dir"), 90)))),
            set_var("flY", add(V("Y"), hauteur)),
            set_var("flDir", V("Dir")),
            set_var("flWho", 1 if is_player else 2),
            set_var("flDmg", var("dmg")),
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
                if_(and_(eq(var("hitDone"), 0), and_(ge(var("f"), var("aStart")), lt(var("f"), var("aEnd")))),
                    [set_var("hitDone", 1)] + tirer()),
            ], [
                if_else(and_(eq(item("armeProj", V("Arme")), 1), eq(name, "special")), [
                    # 3 flèches espacées de 8 images : la fenêtre du spécial (20 images) en contient bien 3
                    if_(and_(lt(var("tirFait"), 3), ge(var("f"), add(var("aStart"), mul(var("tirFait"), 8)))), [
                        set_var("tirFait", add(var("tirFait"), 1)),
                        *tirer(),
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

    # ----- physique
    physics = [
        # esquive : on glisse d'un coup, sans être repoussé par l'adversaire
        if_(gt(var("dashT"), 0), [
            chV("X", var("dashVx")), change_var("dashT", -1), set_var("vx", 0),
            set_var("fxType", "dot"), set_var("fxX", V("X")), set_var("fxY", add(V("Y"), 30)),
            create_clone("FX"), create_clone("FX"),
        ]),
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
        if_(gt(V("X"), 205), [setV("X", 205), set_var("dashT", 0)]),
        if_(lt(V("X"), -205), [setV("X", -205), set_var("dashT", 0)]),
        # repousser les corps (sauf pendant une esquive : on traverse)
        set_var("dx", sub(OV("X"), V("X"))),
        if_(and_(eq(var("dashT"), 0), and_(lt(abs_(var("dx")), 34), and_(not_(eq(state, "ko")), not_(eq(OV("State"), "ko"))))), [
            if_else(gt(var("dx"), 0), [chV("X", -2)], [chV("X", 2)]),
            if_(eq(var("dx"), 0), [chV("X", -2 if is_player else 2)]),
        ]),
        # orientation
        if_(st_is("idle", "walk"), [
            if_(gt(var("dx"), 0), [setV("Dir", 90)]),
            if_(lt(var("dx"), 0), [setV("Dir", -90)]),
        ]),
        # rechargement de l'arc et fin de l'invulnérabilité d'esquive
        if_(gt(var("recharge"), 0), [change_var("recharge", -1)]),
        if_(gt(var("invT"), 0), [change_var("invT", -1)]),
        if_(gt(var("bulleT"), 0), [change_var("bulleT", -1)]),
        if_(gt(var("bulleCd"), 0), [change_var("bulleCd", -1)]),
        # miroir HUD (les variables de combattant sont locales à la cible)
        *([set_var("P1BulleT", var("bulleT")), set_var("P1BulleCd", var("bulleCd"))] if is_player else []),
        # régénération (voie "Regain" du bouclier)
        if_(gt(var("talRegen"), 0), [
            change_var("regenT", 1),
            if_(ge(var("regenT"), 25), [
                set_var("regenT", 0),
                chV("HP", var("talRegen")),
                if_(gt(V("HP"), V("Max")), [setV("HP", V("Max"))]),
            ]),
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
        if_(gt(var("dashT"), 0), [COS("walk2"), set_effect("GHOST", 30)]),
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
                if_(and_(eq(var("scene"), "shop"), gt(var("shopPage"), 1)), [hide(), setV("Vis", 0)]),
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

    # garde-fou (bots) : un numéro d'adversaire hors bornes donnerait un niveau d'arme négatif
    garde_niveau = [] if is_player else [
        if_(or_(lt(var("niveau"), 1), gt(var("niveau"), len(BOTS))), [set_var("niveau", 1)]),
    ]
    t.script(
        when_flag(),
        set_rotation_style("left-right"),
        setV("Hit", 0), setV("State", "idle"),
        set_var("anim", 0),
        forever([
            *garde_niveau,
            if_(eq(var("scene"), "fight"), [show(), setV("Vis", 1)] + ([setV("Size", 85)] if is_player else [])),
            if_(eq(var("scene"), "result"), [hide(), setV("Vis", 0)]),
            if_(eq(var("scene"), "fight"), [
                if_(and_(eq(var("phase"), "fight"), eq(var("hitStop"), 0)), [
                    set_var("nivArme", NIV()),
                    *take_hit,
                    *intents,
                    *start_actions,
                    *attacks,
                ]),
                if_(and_(eq(var("phase"), "intro"), eq(var("hitStop"), 0)), [
                    if_(gt(var("timer"), 0), [set_var("timer", 0)]),
                    # touché juste avant le début du round : sans ça le combattant reste sonné
                    # pour toujours (le décompte du timer ne repart jamais)
                    if_(eq(state, "hurt"), [setV("State", "idle")]),
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
fx.add_var("who", 1)
fx.add_var("typeActuel", "")
fx.add_var("typeFx", "")
fx.add_var("estClone", 0)
fx.script(when_flag(), hide())
fx.script(*([when_broadcast("fxImpact"),
    # un clone reçoit lui aussi les diffusions : seul l'original fabrique les effets
    if_(eq(var("estClone"), 0), [
    set_var("typeActuel", "spark"),
    if_(eq(var("fxFort"), 1), [set_var("typeActuel", "etoile")]),
    if_(eq(var("fxFort"), 2), [set_var("typeActuel", "eclair")]),
    set_var("fxVie", 16),
    create_clone("FX"),
    set_var("typeActuel", "dot"), set_var("fxVie", 40),
] + [create_clone("FX")] * 6 + [set_var("typeActuel", "")]),
    ]))
fx.script(
    when_broadcast("fxBulle"),
    # la variable locale est recopiée dans le clone au moment du clonage : le bulle est identifiable
    set_var("typeActuel", "bulle"), create_clone("FX"), set_var("typeActuel", ""),
)
fx.script(
    when_clone_start(),
    set_var("estClone", 1),
    if_else(eq(var("typeActuel"), "bulle"), [
        switch_costume("bulle"),
        set_var("life", var("fxVie")),
        set_var("who", var("fxWho")),
        goto_xy(var("fxX"), var("fxY")),
        clear_effects(), go_front(),
        set_size(70), point_dir(90), set_effect("GHOST", 12), show(),
        repeat_until(lt(var("life"), 1), [
            if_else(eq(var("who"), 1), [goto_xy(var("P1X"), add(var("P1Y"), 45))],
                                       [goto_xy(var("BotX"), add(var("BotY"), 45))]),
            change_size(2), change_effect("GHOST", 1), change_var("life", -1),
        ]),
        delete_clone(),
    ], [
    # typeActuel est posé juste avant la création du clone (donc propre à lui), fxType est le
    # type par défaut : plusieurs clones créés la même image ne se mélangent plus.
    set_var("typeFx", var("fxType")),
    if_(not_(eq(var("typeActuel"), "")), [set_var("typeFx", var("typeActuel"))]),
    switch_costume(var("typeFx")),
    set_var("life", var("fxVie")),
    goto_xy(var("fxX"), var("fxY")),
    clear_effects(),
    go_front(),
    if_(eq(var("typeFx"), "spark"), [
        set_size(60), point_dir(random(-180, 180)), show(),
        repeat(7, [change_size(14), change_effect("GHOST", 14), Blk("motion_turnright", {"DEGREES": 12})]),
    ]),
    if_(eq(var("typeFx"), "ring"), [
        set_size(30), point_dir(90), set_effect("COLOR", 100), show(),
        repeat(8, [change_size(18), change_effect("GHOST", 12)]),
    ]),
    if_(eq(var("typeFx"), "dot"), [
        set_size(random(40, 90)), point_dir(90), set_effect("COLOR", var("fxTeinte")), show(),
        set_var("vx", random(-8, 8)), set_var("vy", random(2, 10)),
        repeat(14, [
            change_x(var("vx")), change_y(var("vy")), change_var("vy", -0.9), change_effect("GHOST", 7), change_size(-4),
        ]),
    ]),
    if_(eq(var("typeFx"), "bolt"), [
        set_size(random(60, 110)), point_dir(90), show(),
        change_x(random(-40, 40)), change_y(random(-10, 40)),
        repeat(10, [change_y(6), change_effect("GHOST", 10)]),
    ]),
    # étoile : gros coup (charge / smash) — elle tourne et grossit en s'effaçant
    if_(eq(var("typeFx"), "etoile"), [
        set_size(40), point_dir(90), show(),
        repeat(9, [change_size(12), change_effect("GHOST", 11), Blk("motion_turnright", {"DEGREES": 9})]),
    ]),
    # éclair : garde brisée par le marteau
    if_(eq(var("typeFx"), "eclair"), [
        set_size(70), point_dir(90), show(),
        repeat(8, [change_size(10), change_effect("GHOST", 13)]),
    ]),
    # poussière : retombée au sol (le clone suit son porteur grâce à fxWho)
    if_(eq(var("typeFx"), "poussiere"), [
        set_size(60), point_dir(90), set_effect("GHOST", 20), show(),
        repeat(10, [change_size(9), change_effect("GHOST", 8), change_y(-1.5)]),
    ]),
    delete_clone(),
    ]),
)

# ================================================================== FLÈCHES
for v, d in [("x", 0), ("y", 0), ("vx", 0), ("who", 1), ("dmg", 0), ("life", 0), ("dist", 0), ("mchute", 1)]:
    fleche.add_var(v, d)
fleche.script(when_flag(), hide())
fleche.script(when_broadcast("resetRound"), delete_clone())
fleche.script(
    when_clone_start(),
    set_var("x", var("flX")), set_var("y", var("flY")),
    set_var("vx", mul(div(var("flDir"), 90), FLECHE_VITESSE)),
    set_var("who", var("flWho")), set_var("dmg", var("flDmg")), set_var("life", FLECHE_VIE),
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
                set_var("mchute", 1),
                set_var("dist", mul(abs_(var("vx")), sub(FLECHE_VIE, var("life")))),
                if_(gt(var("dist"), 150), [set_var("mchute", 0.85)]),
                if_(gt(var("dist"), 300), [set_var("mchute", 0.7)]),
                set_var("BotHit", mul(var("dmg"), var("mchute"))), set_var("BotHitType", "fleche"),
                if_else(gt(var("vx"), 0), [set_var("BotHitDir", 1)], [set_var("BotHitDir", -1)]),
                set_var("life", 0),
            ]),
        ], [
            if_(and_(lt(abs_(sub(var("x"), var("P1X"))), 36),
                     lt(abs_(sub(var("y"), add(var("P1Y"), 55))), 70)), [
                set_var("mchute", 1),
                set_var("dist", mul(abs_(var("vx")), sub(FLECHE_VIE, var("life")))),
                if_(gt(var("dist"), 150), [set_var("mchute", 0.85)]),
                if_(gt(var("dist"), 300), [set_var("mchute", 0.7)]),
                set_var("P1Hit", mul(var("dmg"), var("mchute"))), set_var("P1HitType", "fleche"),
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
