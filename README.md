# AI-improves-itself
AI improves itself comme le nom l'indique le concepte est simple : L'AI s'améliore d'elle meme.

--- 

Nous utilisons des clées de fournisseurs qui propose des offres gratuites. Et des solutions d'hébergement gratuite.
Ce projet et avant tout pour la recherche et répondre a la question : Ou pourra allez l'AI si nous lui donnons assez d'outils pour entre guillemet modifier le code et les
informations qu'elles connaissent. 

---  


Le projet et un mono-repo, contenant 2 partie (en cours de construction) actuellement : 

La première l'interface général du site, page contibuteur, l'AI, prompt system, ensemble des redirections vers les data. (Site render static)

La 2ème la partie recherche web et informations mise a jour dans les infrastructures AI possibilité d'utiliser Google Colab (Note : Pour google Colab, l'Api key (AI) devra etre
rentré manuellement par l'utilisateur, les scriptes scrapera une grosse partie web étape par étape pour ensuite les envoyer pour etre étudier au sites principal qui modifiera
lui meme l'infrastructure. (Web service render capacité minimum 512Mo de Ram, choisir la Session le nombre d'heures minutes) 

---

#Comment l'ai modifira t-elle structure et ensemble ? 

J'ai découpé ça en en plusieurs parties :

- Prompt systeme
- Skill
- Base de données & recherche
- 

Prompt système :
L'AI a la possibilité de modifier le Prompt Système actuel notamment lors de l'analyse de ses propres réponses.
Nous avons fournis un prompt système a l'AI de base. Avec comment intéragir avec ci et ça. Des descriptions dans l'ensemble de a quoi ressemble sont interface la clée et
qu'elle peut le modifier selon ces réponses a elle. Imaginons elle veut changez de noms elle le fait sans problème. Bref c'est un exemple mais aussi par exemple,
elle veut piocher quelque chose dans la base de donnée. Par exemple une information sur le dernier jeu Zelda et là l'AI nous sort la première ligne de la base de donnée le jeu
Zelda le plus vieux... Qu'elle a ingnorer l'informations de date. Et bien elle peut modifier elle meme le prompt système pour faire attentions a la Date. Et aussi le prompt
système peut etre brancher a une partie précise en gros pour le code : telle prompt. Et crée des "garde-fou" qui vont choisir quelle prompt selon certains mots clées.


Skill :

L'ai doit etre capable de modifier ses propres skill pour ça une page /request existe ici l'Ai peut envoyer des requetes au dévloppeur du projet pour des fonctionnalité utile et
des modification UI et autres.

Base de données & recherche : 

C'est un repo github qui fait office de base de données pour le moment nous le gardons privé. 


