# MacroEverything

> 🇫🇷 [English Version](README.md)

---

Application de création de macros automatisées avancé facile d'utilisation. 

### Lancement rapide

1. **Double-cliquez** sur `run.bat` (si Python est déjà installé)
2. **Ou** double-cliquez sur `install_and_run.bat` (installe Python + Pillow automatiquement si absent)

### Types de nœuds disponibles

| Catégorie  | Nœud                       | Description                                              |
|------------|----------------------------|----------------------------------------------------------|
| Action     | 🖱️ Clic souris             | Clic gauche/droit/milieu à une position                  |
| Action     | ➡️ Déplacer souris         | Déplace le curseur vers une position                     |
| Action     | 🖱️ Scroll                  | Molette haut/bas                                         |
| Action     | ⌨️ Touche clavier          | Raccourcis clavier (ctrl+c, F5, enter…)                  |
| Action     | 📝 Saisir texte            | Tape du texte dans la fenêtre active                     |
| Action     | ⏱️ Attendre                | Pause en millisecondes                                   |
| Action     | ▶️ Lancer programme        | Ouvre un fichier ou une commande shell                   |
| Action     | 🔍 Focus fenêtre           | Active une fenêtre par titre                             |
| Action     | ⏺ Enregistrer/Rejouer     | Enregistre des actions clavier/souris et les rejoue      |
| Condition  | 📸 Si écran contient       | Détection d'image par capture d'écran                    |
| Condition  | 🎨 Si pixel = couleur      | Vérifie la couleur d'un pixel à l'écran                  |
| Condition  | 📊 Si variable             | Compare une variable à une valeur                        |
| Condition  | 🔗 Groupe de conditions    | Combine plusieurs conditions (AND / OR / NAND / NOR)     |
| Boucle     | 🔁 Répéter N fois          | Boucle simple avec compteur                              |
| Boucle     | 🔄 Tant que (écran)        | Boucle conditionnelle basée sur capture d'écran          |
| Boucle     | 🔁 Tant que (variable)     | Boucle conditionnelle basée sur une variable             |
| Variable   | 📦 Définir variable        | Assigne une valeur numérique à une variable              |
| Variable   | ➕ Modifier variable       | Ajoute un delta à une variable                           |
| Contrôle   | 🏷️ Étiquette               | Point de repère nommé                                    |
| Contrôle   | ↩️ Aller à étiquette       | Saut inconditionnel vers une étiquette                   |
| Contrôle   | 📞 Appeler une macro       | Appelle une autre macro du même fichier                  |
| Contrôle   | ⏹️ Arrêter / Retourner     | Stoppe la macro et retourne Vrai ou Faux                 |

### Enregistrement / Rejeu

Le nœud **Enregistrer/Rejouer** permet de capturer une séquence d'actions en temps réel :
- Choisissez une touche de déclenchement (ex. F8)
- Appuyez sur la touche → l'enregistrement démarre (rouge)
- Appuyez de nouveau → l'enregistrement s'arrête et les actions sont sauvegardées
- À l'exécution de la macro, la séquence est rejouée fidèlement
- Options : clics souris, molette, mouvements, frappe clavier, mode absolu/relatif

### Interface

- **Arbre visuel** — chaque nœud s'affiche avec ses paramètres résumés
- **Clic droit** sur un nœud → menu contextuel (modifier, déplacer, dupliquer, supprimer, copier/coller l'image)
- **Double-clic** sur un nœud → ouvre l'éditeur de paramètres
- **Panneau droit** → propriétés détaillées du nœud sélectionné
- **Sélecteur de coordonnées** → overlay couvrant tous les moniteurs pour pointer visuellement
- **Capture de région** → sélection rectangulaire de zone sur tous les moniteurs
- **Raccourcis clavier globaux** → lancer/arrêter/pause même en arrière-plan
- **Panneau Paramètres** → activation/désactivation de l'overlay de debug (détection d'image)
- **Mise à l'échelle de résolution** — les coordonnées sont automatiquement adaptées si la résolution de lecture diffère de celle d'enregistrement
- Interface bilingue **FR / EN** (Ajout de nouvelle langue facile via fichier json)
- Sauvegarde en `.macros` (JSON lisible)

### Détection d'image (Si écran contient / Tant que écran)

La détection s'effectue en 3 passes, toutes les opérations lourdes sont exécutées en C via PIL (pas de boucle Python sur les pixels) :

1. **Scan thumbnail** — le template et le screenshot sont réduits à ≤ 16 px. Le thumbnail glisse sur l'écran avec un pas de 4 px (~3 000 positions). Score = SAD couleur via histogramme PIL. Les 15 meilleures zones sont conservées.
2. **Scan grossier pleine résolution** — SAD en niveaux de gris autour de chacune des 15 zones, pas = template / 8. Identifie le meilleur candidat.
3. **Raffinement pixel-précis** — scan exhaustif au pas de 1 px dans une fenêtre ±step2 autour du candidat. Garantit une précision pixel sans re-scanner tout l'écran.

Si l'overlay de debug est activé (Paramètres), un rectangle coloré s'affiche autour du meilleur résultat après chaque vérification : vert = trouvé, orange = proche, rouge = non trouvé; pour que vous puissiez changer le taux de correspondance en fonction.

### Dépendances

- Python 3.8+
- Pillow (`pip install pillow`) — captures d'écran et détection d'image

### Structure des fichiers

```
MacroEverything/
├── main.py                    ← Point d'entrée de l'application
├── Lancer.bat                 ← Lancement rapide
├── install_and_run.bat        ← Installation automatique + lancement
├── settings.json              ← Paramètres (langue, raccourcis…)
├── locales/
│   ├── en.json                ← Traductions anglaises
│   ├── fr.json                ← Traductions françaises
│   └── langs.json             ← Liste des langues disponibles
├── macros/                    ← Dossier des fichiers de macros (.macros)
└── macro_app/
    ├── constants.py           ← Couleurs, polices, types de nœuds
    ├── engine.py              ← Moteur d'exécution des macros
    ├── hotkeys.py             ← Gestionnaire de raccourcis globaux
    ├── i18n.py                ← Système de traduction
    ├── models.py              ← Modèles de données
    ├── settings.py            ← Lecture/écriture des paramètres
    ├── utils.py               ← Utilitaires système
    └── ui/
        ├── app.py             ← Fenêtre principale
        ├── dialogs.py         ← Éditeurs de nœuds et overlays
        ├── panels.py          ← Panneau de propriétés
        └── tree_canvas.py     ← Rendu de l'arbre de nœuds
```
