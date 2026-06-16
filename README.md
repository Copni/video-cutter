# Video Cutter

Application desktop Python pour découper rapidement des fichiers MP4 à partir de marqueurs placés frame par frame.

## Prérequis

- Python 3.10 ou plus récent
- FFmpeg installé et disponible dans le `PATH`

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
python main.py
```

## Utilisation

1. Cliquez sur `Choisir dossier`.
2. Sélectionnez un dossier contenant des fichiers `.mp4`.
3. Choisissez une vidéo dans la liste de gauche.
4. Naviguez avec lecture/pause, frame précédente et frame suivante.
5. Placez un ou plusieurs marqueurs sur la frame courante.
6. Sélectionnez un marqueur sur la timeline si vous voulez le supprimer.
7. Cliquez sur `Valider` pour générer les segments.

Les fichiers générés utilisent le même préfixe que la vidéo source et les prochains indices disponibles, sans écraser les fichiers existants.

## Raccourcis par défaut

- `Espace` : lecture / pause
- `Q` : frame précédente
- `D` : frame suivante
- maintenir `Q` ou `D` : défilement continu frame par frame
- `A` : vidéo précédente
- `E` : vidéo suivante
- `Entrée` : valider le découpage
- `M` : placer un marqueur
- `Retour arrière` : supprimer le marqueur sélectionné

Le bouton `Menu`, dans la barre latérale droite, permet de réattribuer les touches.
