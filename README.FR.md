# MacroEverything

> 🇫🇷 [English Version](README.md)

---

Application de création de macros automatisées avancée et facile d'utilisation.

### Lancement rapide

| Option | Comment |
|--------|---------|
| **Autonome (recommandé)** | Lancez `MacroEverything.exe` — A récupérer via la section 'Release' |
| **Depuis les sources (Python installé)** | Lancez sur `run.bat` |
| **Depuis les sources (sans Python)** | Lancez sur `install_and_run.bat` — installe Python(Pourrait ne pas fonctionner ; si cela arrive, installer Python manuellement) + Pillow automatiquement |

### Types de nœuds disponibles

| Catégorie  | Nœud                           | Description                                              |
|------------|--------------------------------|----------------------------------------------------------|
| Action     | 🖱️ Clic souris                | Clic gauche/droit/milieu à une position                  |
| Action     | ➡️ Déplacer souris            | Déplace le curseur vers une position                     |
| Action     | 🖱️ Scroll                     | Molette haut/bas                                         |
| Action     | ⌨️ Touche clavier             | Raccourcis clavier (ctrl+c, F5, enter…)                  |
| Action     | 📝 Saisir texte               | Tape du texte dans la fenêtre active                     |
| Action     | ⏱️ Attendre                   | Pause en millisecondes                                   |
| Action     | ▶️ Lancer programme           | Ouvre un fichier ou une commande shell                   |
| Action     | 🔍 Focus fenêtre              | Active une fenêtre par titre                             |
| Action     | 🔍 Cliquer sur image          | Recherche une image à l'écran et clique dessus           |
| Action     | ❖ Disposition fenêtre         | Positionne et/ou redimensionne une fenêtre par titre     |
| Action     | ⏺ Enregistrer/Rejouer        | Enregistre des actions clavier/souris et les rejoue      |
| Condition  | 📸 Si écran contient          | Détection d'image par capture d'écran                    |
| Condition  | 🎨 Si pixel = couleur         | Vérifie la couleur d'un pixel à l'écran                  |
| Condition  | 📊 Si variable                | Compare une variable à une valeur                        |
| Condition  | ⋇ Groupe de conditions        | Combine plusieurs conditions (AND / OR / NAND / NOR)     |
| Condition  | ⊟ Switch variable             | Branchement multiple selon la valeur d'une variable      |
| Boucle     | 🔁 Répéter N fois             | Boucle simple avec compteur                              |
| Boucle     | 🔄 Tant que (écran)           | Boucle conditionnelle basée sur capture d'écran          |
| Boucle     | ∞ Tant que (variable)         | Boucle conditionnelle basée sur une variable             |
| Variable   | 📦 Définir variable           | Assigne une valeur numérique à une variable              |
| Variable   | ➕ Modifier variable          | Ajoute un delta à une variable                           |
| Contrôle   | 🏷️ Étiquette                  | Point de repère nommé                                    |
| Contrôle   | ↩️ Aller à étiquette          | Saut inconditionnel vers une étiquette                   |
| Contrôle   | ↳ Appeler une macro           | Appelle une autre macro du même fichier                  |
| Contrôle   | ↵ Arrêter / Retourner         | Stoppe la macro et retourne Vrai ou Faux                 |

### Switch variable

Le nœud **Switch variable** dirige l'exécution vers différentes branches selon la valeur d'une variable — comme un `switch/case` :
- Définissez la variable à tester
- Ajoutez une valeur de cas par branche (comparaison numérique ou textuelle)
- La dernière branche est toujours le **Défaut** (exécutée si aucun cas ne correspond)
- N cas → N+1 branches dans l'arbre

### Cliquer sur image

Le nœud **Cliquer sur image** recherche une image de référence à l'écran et clique dessus si trouvée :
- Capturez une zone de référence dans l'éditeur de nœud
- Définissez optionnellement une **zone de recherche restreinte** (plus rapide, évite les faux positifs)
- Configurez la position du clic : centre de l'image trouvée, ou décalage en pixels personnalisé
- Seuil de correspondance réglable (0.0 → 1.0)

### Enregistrement / Rejeu

Le nœud **Enregistrer/Rejouer** capture une séquence d'actions en temps réel :
- Choisissez une touche de déclenchement (ex. F8)
- Appuyez sur la touche → l'enregistrement démarre (indicateur rouge)
- Appuyez de nouveau → l'enregistrement s'arrête et les actions sont sauvegardées
- À l'exécution de la macro, la séquence est rejouée fidèlement
- Options : clics souris, molette, mouvements, frappe clavier, mode absolu/relatif

### Interface

- **Arbre visuel** — chaque nœud s'affiche avec ses paramètres résumés et un badge de type coloré
- **Clic droit** sur un nœud → menu contextuel (modifier, déplacer, dupliquer, supprimer, copier/coller l'image)
- **Double-clic** sur un nœud → ouvre l'éditeur de paramètres
- **Panneau Propriétés** → vue détaillée du nœud sélectionné avec :
  - **Minimap de coordonnées** — affiche où l'action se produit sur un aperçu à l'échelle (nœuds clic, déplacement, scroll, pixel)
  - **Vignette d'image** — aperçu de l'image de référence capturée (nœuds de recherche d'image)
  - **Overlay écran** — viseur flottant transparent indiquant la position réelle à l'écran après mise à l'échelle
  - **Overlay de zone** — rectangle flottant délimitant la zone de recherche aux coordonnées réelles
- **Sélecteur de coordonnées** → overlay plein écran pour pointer visuellement sur tous les moniteurs
- **Sélecteur de région** → glisser pour définir une zone rectangulaire sur tous les moniteurs
- **Raccourcis clavier globaux** → lancer/arrêter/pause même en arrière-plan (configurables)
- **Panneau Paramètres** → activation de l'overlay de debug (visualisation de la détection d'image)
- **Mise à l'échelle de résolution** — les coordonnées sont automatiquement adaptées si la résolution de lecture diffère de celle d'enregistrement
- Interface bilingue **FR / EN** (ajout de nouvelles langues facile via fichier JSON)
- Sauvegarde en `.macros` (JSON lisible)

### Détection d'image (Si écran contient / Tant que écran / Cliquer sur image)

La détection s'effectue en 3 passes, toutes les opérations lourdes sont exécutées en C via PIL (pas de boucle Python sur les pixels) :

1. **Scan thumbnail** — le template et le screenshot sont réduits à ≤ 16 px. Le thumbnail glisse sur l'écran avec un pas de 4 px (~3 000 positions). Score = SAD couleur via histogramme PIL. Les 15 meilleures zones sont conservées.
2. **Scan grossier pleine résolution** — SAD en niveaux de gris autour de chacune des 15 zones, pas = template / 8. Identifie le meilleur candidat.
3. **Raffinement pixel-précis** — scan exhaustif au pas de 1 px dans une fenêtre ±step2 autour du candidat. Garantit une précision pixel sans re-scanner tout l'écran.

Si l'overlay de debug est activé (Paramètres), un rectangle coloré s'affiche autour du meilleur résultat après chaque vérification : vert = trouvé, orange = proche, rouge = non trouvé.

# User Data
Tout est sauvegardé localement dans '%localappdata%/RunFaster/MacroEverything'

### Dépendances

- Python 3.10+ (uniquement pour l'exécution depuis les sources)
- Pillow (`pip install pillow`) — captures d'écran et détection d'image

### Structure des fichiers

```
MacroEverything/
├── main.py                    ← Point d'entrée de l'application
├── run.bat                    ← Lancement rapide (Python requis)
├── install_and_run.bat        ← Installation automatique + lancement
├── MacroEverything.spec       ← Configuration PyInstaller
├── version_info.txt           ← Métadonnées de l'exécutable Windows
├── locales/
│   ├── en.json                ← Traductions anglaises
│   ├── fr.json                ← Traductions françaises
│   └── langs.json             ← Liste des langues disponibles
├── macros/                    ← Dossier des fichiers de macros (.macros) — mode dev
└── macro_app/
    ├── constants.py           ← Couleurs, polices, types de nœuds
    ├── engine.py              ← Moteur d'exécution des macros
    ├── hotkeys.py             ← Gestionnaire de raccourcis globaux
    ├── i18n.py                ← Système de traduction
    ├── models.py              ← Modèles de données
    ├── paths.py               ← Résolution des chemins (dev vs .exe)
    ├── settings.py            ← Lecture/écriture des paramètres
    ├── utils.py               ← Utilitaires système
    └── ui/
        ├── app.py             ← Fenêtre principale
        ├── dialogs.py         ← Éditeurs de nœuds et sélecteur de région
        ├── panels.py          ← Panneau de propriétés avec aperçus
        └── tree_canvas.py     ← Rendu de l'arbre de nœuds
```
