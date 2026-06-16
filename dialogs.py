from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from shortcuts import ACTION_LABELS, key_name, normalized_key


class KeyCaptureEdit(QLineEdit):
    keyChanged = Signal(int)

    def __init__(self, key):
        super().__init__()
        self.key = key
        self.setReadOnly(True)
        self.setText(key_name(key))
        self.setPlaceholderText("Appuyez sur une touche")

    def keyPressEvent(self, event: QKeyEvent):
        key = normalized_key(event)
        if key in (Qt.Key_unknown, Qt.Key_Escape):
            return
        self.key = key
        self.setText(key_name(key))
        self.keyChanged.emit(key)


class ShortcutDialog(QDialog):
    def __init__(self, shortcuts, delete_original_after_cut, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Menu")
        self.shortcuts = dict(shortcuts)
        self.delete_original_after_cut = delete_original_after_cut
        self.edits = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        for action, label in ACTION_LABELS.items():
            edit = KeyCaptureEdit(self.shortcuts[action])
            edit.keyChanged.connect(lambda key, name=action: self._set_shortcut(name, key))
            self.edits[action] = edit
            form.addRow(label, edit)

        settings_title = QLabel("Paramètres")
        settings_title.setStyleSheet("font-weight: 600; margin-top: 10px;")
        layout.addWidget(settings_title)

        self.delete_original_btn = QPushButton()
        self.delete_original_btn.setCheckable(True)
        self.delete_original_btn.setChecked(self.delete_original_after_cut)
        self.delete_original_btn.clicked.connect(self._set_delete_original_after_cut)
        self._update_delete_original_button()
        layout.addWidget(self.delete_original_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_shortcut(self, action, key):
        self.shortcuts[action] = key

    def _set_delete_original_after_cut(self, checked):
        self.delete_original_after_cut = checked
        self._update_delete_original_button()

    def _update_delete_original_button(self):
        state = "ON" if self.delete_original_after_cut else "OFF"
        self.delete_original_btn.setText(f"Suppression de la vidéo d'origine : {state}")

    def accept(self):
        keys = list(self.shortcuts.values())
        if len(keys) != len(set(keys)):
            QMessageBox.warning(self, "Raccourcis", "Chaque action doit avoir une touche différente.")
            return
        super().accept()
