# ⚔️ Arena Clash — jeu de combat 2D pour Scratch 3

Un jeu de combat complet en **un seul fichier `.sb3`**, généré par script (Python → JSON Scratch),
avec des graphismes 100 % vectoriels, dessinés procéduralement.

![Aperçu](preview.png)

## ▶️ Jouer

1. Télécharge **[`dist/ArenaClash.sb3`](dist/ArenaClash.sb3)**.
2. Va sur <https://scratch.mit.edu/projects/editor/> (ou ouvre l'appli Scratch 3 / TurboWarp).
3. **Fichier → Charger depuis votre ordinateur** → choisis `ArenaClash.sb3`.
4. Clique sur le drapeau vert 🟩.

> Fonctionne aussi dans TurboWarp (plus fluide) : <https://turbowarp.org/editor>

## 🎮 Commandes

| Touche | Action |
|---|---|
| ← / → | Se déplacer |
| ↑ | Sauter |
| ↓ | Garde (12 % des dégâts subis, remplit la jauge spéciale) |
| ↓ **en l'air** | Garde aérienne : petit recul vers l'arrière. Résiste au coup de poing, mais **se brise sur un coup de pied / spécial / charge** (moitié des dégâts + éjection) |
| J / K / L **en l'air** | Attaques aériennes (l'élan du saut est conservé) |
| **J** | Coup de poing (rapide) |
| **K** | Coup de pied (plus lent, plus de portée) — **avec l'arc : tire une flèche** |
| **L** | **SPÉCIAL** (barre bleue pleine) — l'effet dépend de l'arme en main |

Un combat se joue **en 2 rounds gagnants** (max 3), 60 s par round. Au temps écoulé, celui qui a le plus de PV gagne le round.

## 🗡️ Armes : six façons de se battre

Les armes ne sont **pas** des cosmétiques : chacune change les dégâts, l'allonge, la vitesse,
la garde et **le spécial**. Les effets sont lisibles dans le bandeau du bas pendant le combat.

| Arme | Prix | Ce que ça change vraiment |
|---|---|---|
| **Poings** | offert | Référence : poing 7, pied 11, spécial 24 |
| **Épée** | 200 | Allonge **+48 px**, poing 9, pied 13, estoc (spécial 26 qui avance) — récupération plus lente |
| **Lance** | 240 | Allonge **+72 px** (la plus grande), poing 6, pied 11, **CHARGE 30** qui fonce et éjecte |
| **Marteau** | 280 | Lent et punissable (52 images) mais **brise la garde : 60 % des dégâts passent**, smash 34 qui sonne |
| **Arc** | 260 | Combat à distance : **K tire une flèche (13)**, spécial = **salve de 3 flèches (3x10)** |
| **Bouclier** | 220 | **Garde à 0 dégât** (au lieu de 12 %), garde brisée à 20 % (au lieu de 50 %), allonge réduite |

- **Armes au sol** : à chaque round, deux armes apparaissent sur l'arène (dont une en hauteur,
  à attraper en sautant). Un combattant **à mains nues** les ramasse en passant dessus ; une arme
  ramassée remplace celle de départ et repousse 4 s plus tard sur un autre emplacement libre.
- Les **bots s'en servent aussi** : ils vont chercher l'arme au sol, s'écartent pour tirer à l'arc,
  et les derniers adversaires arrivent déjà équipés (Cyan-X au bouclier, Rosa à l'arc, Ombre à
  l'épée, Le Champion au marteau).
- **Boutique page ARMES** (onglet `ARMES`) : aperçu du combattant avec l'arme survolée + description
  des effets ; on achète, puis on clique une arme possédée pour l'équiper.
- L'arme choisie est **dessinée dans les 12 poses** de chaque personnage (elle suit la main),
  visible aussi sur le HUD : `TOI : Épée` / `Le Champion : Marteau`.


## 🧩 Contenu

- **Menu** complet : Jouer / Boutique / Commandes, aperçu de ton combattant, pièces et progression.
- **8 bots de plus en plus forts** (PV, vitesse, agressivité, garde et temps de réaction croissants), chacun avec son look et son accessoire :
  `Kid Bleu → Verdo → Sunny → Violette → Cyan-X → Rosa → Ombre → Le Champion`.
  Chaque victoire débloque le suivant ; les bots verrouillés s'affichent « ????? ».
- **4 arènes** : Dojo, Toits de nuit, Volcan, Cyber.
- **Boutique** en deux onglets : **LOOK** (8 accessoires de tête + 6 couleurs) et **ARMES** (6 armes qui changent le gameplay). Les accessoires suivent la tête sur **toutes** les animations.
- **Sauvegarde de progression** : bouton *SAUVER* → code du type `5-01234-001-01-9-4-17-4-11` (niveau max, pièces, cosmétiques **et armes** achetés/équipés, avec somme de contrôle) ; *CHARGER* → colle le code. Les codes invalides sont refusés, et les anciens codes à 15 chiffres restent acceptés.
- **Économie** : 100 pièces au départ, `40 + 30 × niveau` par victoire, 10 en cas de défaite.
- **Feeling de combat** : hit-stop, flash écran au K.O., étincelles, particules, effet de garde, combo compteur, anim. de victoire / K.O., 12 sons synthétisés (dont le claquement de corde de l'arc).
- **Moteur de texte vectoriel** : la police (DejaVu Sans Bold, accents inclus) est embarquée sous forme de costumes SVG et tamponnée au stylo → texte net et aligné dans tous les menus.

## 🛠 Régénérer le projet

```bash
pip install fonttools
python3 scratch-game/build.py      # -> scratch-game/dist/ArenaClash.sb3
```

| Fichier | Rôle |
|---|---|
| `sb3lib.py` | mini-DSL Python → blocs Scratch 3 (`if_`, `repeat`, `define`/`call`, stylo, etc.) et assemblage du `.sb3` |
| `assets.py` | génération des SVG (combattant en 12 poses **pour chacune des 6 armes**, par cinématique directe ; accessoires, armes, décors, FX) et des sons WAV |
| `build.py` | tout le gameplay : machine d'états des combattants, armes (stats, projectiles, ramassage), IA des bots, HUD, menus, boutique, sauvegarde |
| `tools/` | harnais de test headless : `cd tools && npm i && bash test.sh` rejoue tous les scénarios dans la vraie VM Scratch, mesure les dégâts par arme et capture les écrans dans `tools/out/` |

Pour ajouter un bot, une arme ou un cosmétique, il suffit d'ajouter une ligne dans `BOTS`, `ARMES`, `ACCS` ou `SKINS`
dans `build.py` (les listes Scratch, la boutique, les sauvegardes et les descriptions suivent automatiquement).

## ✅ Vérifications faites

- Le `.sb3` passe la validation officielle de `scratch-vm` (schéma SB3) et s'exécute sans erreur.
- Parcours testés en headless : menu → sélection → combat → K.O. → round 2 → victoire → pièces → déblocage → boutique (achat, équipement, « pas assez de pièces ») → commandes, ainsi que la défaite et la garde.
- Armes testées une par une : dégâts de chaque attaque avec chaque arme, allonge (l'épée touche à 120 px,
  les poings non), marteau qui perce la garde (60 %), bouclier qui annule les dégâts bloqués,
  arc (flèche 13, salve 3 x 10), ramassage au sol + réapparition, sauvegarde/rechargement d'arme,
  compatibilité des anciens codes ; 600 images de combat réel avec Le Champion au marteau :
  aucun gel de combattant, aucune fuite de clones.
- Coût : ≈ 0,7–1,8 ms par image en combat et 3–6 ms dans les menus (Scratch en autorise 33).
