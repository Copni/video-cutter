from PySide6.QtCore import Qt


ACTION_LABELS = {
    "toggle_playback": "Lecture / pause",
    "previous_frame": "Frame précédente",
    "next_frame": "Frame suivante",
    "previous_video": "Vidéo précédente",
    "next_video": "Vidéo suivante",
    "validate": "Valider",
    "delete_video": "Supprimer la vidéo",
    "add_marker": "Placer marqueur",
    "delete_marker": "Supprimer marqueur",
}


DEFAULT_SHORTCUTS = {
    "toggle_playback": Qt.Key_Space,
    "previous_frame": Qt.Key_Q,
    "next_frame": Qt.Key_D,
    "previous_video": Qt.Key_A,
    "next_video": Qt.Key_E,
    "validate": Qt.Key_Return,
    "delete_video": Qt.Key_F,
    "add_marker": Qt.Key_M,
    "delete_marker": Qt.Key_Backspace,
}


def normalized_key(event):
    key = event.key()
    if key == Qt.Key_Enter:
        return Qt.Key_Return
    return key


def key_name(key):
    names = {
        Qt.Key_Space: "Espace",
        Qt.Key_Return: "Entrée",
        Qt.Key_Backspace: "Retour arrière",
        Qt.Key_Delete: "Suppr",
    }
    if key in names:
        return names[key]
    return chr(key).upper() if 32 <= key <= 126 else str(int(key))
