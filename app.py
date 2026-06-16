import shutil
import subprocess
from pathlib import Path

import cv2
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QAction, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dialogs import ShortcutDialog
from shortcuts import ACTION_LABELS, DEFAULT_SHORTCUTS, key_name, normalized_key
from video_files import next_output_paths, run_ffmpeg, temporary_output_path, video_prefix
from widgets import TimelineSlider


class VideoCutter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Cutter")
        self.resize(1250, 740)

        self.work_dir = None
        self.video_files = []
        self.current_path = None
        self.cap = None
        self.fps = 0.0
        self.total_frames = 0
        self.current_frame = 0
        self.markers = []
        self.selected_marker = None
        self.is_playing = False
        self.shortcuts = dict(DEFAULT_SHORTCUTS)
        self.delete_original_after_cut = True
        self.held_action = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)

        self.hold_timer = QTimer(self)
        self.hold_timer.setInterval(35)
        self.hold_timer.timeout.connect(self._repeat_held_action)

        self._build_ui()
        self._set_video_controls_enabled(False)
        self.update_info()
        QApplication.instance().installEventFilter(self)

    def _build_ui(self):
        open_action = QAction("Choisir dossier", self)
        open_action.triggered.connect(self.choose_folder)
        menu_action = QAction("Menu", self)
        menu_action.triggered.connect(self.open_shortcut_menu)
        self.toolbar = self.addToolBar("Actions")
        self.toolbar.addAction(open_action)
        self.toolbar.addAction(menu_action)

        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        left_panel = QVBoxLayout()
        main_layout.addLayout(left_panel)

        self.video_list = QListWidget()
        self.video_list.setFixedWidth(280)
        self.video_list.currentRowChanged.connect(self.load_selected_video)
        left_panel.addWidget(self.video_list, 1)

        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(0, 4, 0, 0)
        controls_layout.setSpacing(6)

        nav_controls = QGridLayout()
        nav_controls.setSpacing(6)
        controls_layout.addLayout(nav_controls)

        self.prev_video_btn = QPushButton("Vidéo précédente")
        self.prev_video_btn.clicked.connect(self.previous_video)
        nav_controls.addWidget(self.prev_video_btn, 0, 0)

        self.prev_btn = QPushButton("Frame précédente")
        self.prev_btn.clicked.connect(self.previous_frame)
        nav_controls.addWidget(self.prev_btn, 0, 1)

        self.play_btn = QPushButton("Lecture")
        self.play_btn.clicked.connect(self.toggle_playback)
        nav_controls.addWidget(self.play_btn, 0, 2)

        self.next_btn = QPushButton("Frame suivante")
        self.next_btn.clicked.connect(self.next_frame)
        nav_controls.addWidget(self.next_btn, 0, 3)

        self.next_video_btn = QPushButton("Vidéo suivante")
        self.next_video_btn.clicked.connect(self.next_video)
        nav_controls.addWidget(self.next_video_btn, 0, 4)

        marker_controls = QHBoxLayout()
        marker_controls.setSpacing(6)
        controls_layout.addLayout(marker_controls)

        self.add_marker_btn = QPushButton("Placer marqueur")
        self.add_marker_btn.clicked.connect(self.add_marker)
        marker_controls.addWidget(self.add_marker_btn)

        self.delete_marker_btn = QPushButton("Supprimer marqueur")
        self.delete_marker_btn.clicked.connect(self.delete_selected_marker)
        marker_controls.addWidget(self.delete_marker_btn)

        self.validate_btn = QPushButton("Valider")
        self.validate_btn.clicked.connect(self.cut_video)
        marker_controls.addWidget(self.validate_btn)

        self.delete_video_btn = QPushButton("Supprimer la vidéo")
        self.delete_video_btn.clicked.connect(self.delete_current_video)
        marker_controls.addWidget(self.delete_video_btn)

        center = QVBoxLayout()
        main_layout.addLayout(center, 1)

        self.file_label = QLabel("Aucune vidéo sélectionnée")
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setStyleSheet("font-weight: 600;")
        center.addWidget(self.file_label)

        self.video_label = QLabel("Choisissez un dossier contenant des fichiers MP4")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(560, 360)
        self.video_label.setStyleSheet("background: #111; color: #ddd;")
        center.addWidget(self.video_label, 1)

        self.timeline = TimelineSlider()
        self.timeline.valueChanged.connect(self.seek_frame)
        self.timeline.markerClicked.connect(self.marker_selected)
        center.addWidget(self.timeline)
        center.addWidget(controls_panel, 0, Qt.AlignHCenter)

        right_panel = QVBoxLayout()
        main_layout.addLayout(right_panel)

        self.info_box = QFrame()
        self.info_box.setFrameShape(QFrame.StyledPanel)
        self.info_box.setFixedWidth(240)
        info_layout = QVBoxLayout(self.info_box)
        right_panel.addWidget(self.info_box)

        info_title = QLabel("Informations vidéo")
        info_title.setStyleSheet("font-weight: 600;")
        info_layout.addWidget(info_title)

        self.info_file_label = QLabel("-")
        self.info_folder_label = QLabel("-")
        self.info_frame_label = QLabel("Frame: 0 / 0")
        self.info_fps_label = QLabel("FPS: -")
        self.info_duration_label = QLabel("Durée: -")
        self.info_marker_label = QLabel("Marqueurs: 0")
        self.info_selected_marker_label = QLabel("Marqueur sélectionné: -")

        for label in (
            self.info_file_label,
            self.info_folder_label,
            self.info_frame_label,
            self.info_fps_label,
            self.info_duration_label,
            self.info_marker_label,
            self.info_selected_marker_label,
        ):
            label.setWordWrap(True)
            info_layout.addWidget(label)

        shortcut_title = QLabel("Raccourcis")
        shortcut_title.setStyleSheet("font-weight: 600; margin-top: 10px;")
        info_layout.addWidget(shortcut_title)

        self.shortcut_label = QLabel()
        self.shortcut_label.setWordWrap(True)
        info_layout.addWidget(self.shortcut_label)
        right_panel.addStretch(1)

        self.statusBar().showMessage("Prêt")

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choisir un dossier de travail")
        if not folder:
            self.show_warning("Aucun dossier sélectionné.")
            return

        self.work_dir = Path(folder)
        self.video_files = sorted(self.work_dir.glob("*.mp4"), key=lambda p: p.name.lower())
        self.video_list.clear()

        if not self.video_files:
            self.release_video()
            self._set_video_controls_enabled(False)
            self.show_warning("Ce dossier ne contient aucun fichier MP4.")
            return

        for video in self.video_files:
            self.video_list.addItem(video.name)
        self.video_list.setCurrentRow(0)
        self.statusBar().showMessage(f"{len(self.video_files)} fichier(s) MP4 trouvé(s)")
        self.update_navigation_buttons()

    def load_selected_video(self, row):
        if row < 0 or row >= len(self.video_files):
            return
        self.load_video(self.video_files[row])

    def load_video(self, path):
        self.release_video()
        self.current_path = path
        self.cap = cv2.VideoCapture(str(path))

        if not self.cap.isOpened():
            self.release_video()
            self.show_error("Vidéo illisible.")
            return

        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if self.fps <= 0 or self.total_frames <= 0:
            self.release_video()
            self.show_error("FPS invalide ou nombre de frames inconnu.")
            return

        self.current_frame = 0
        self.markers = []
        self.selected_marker = None
        self.timeline.blockSignals(True)
        self.timeline.setMaximum(max(0, self.total_frames - 1))
        self.timeline.setValue(0)
        self.timeline.blockSignals(False)
        self.file_label.setText(path.name)
        self._set_video_controls_enabled(True)
        self.show_frame(0)
        self.update_navigation_buttons()

    def release_video(self):
        self.timer.stop()
        self.hold_timer.stop()
        self.held_action = None
        self.is_playing = False
        if self.cap is not None:
            self.cap.release()
        self.cap = None
        self.current_path = None
        self.fps = 0.0
        self.total_frames = 0
        self.current_frame = 0
        self.markers = []
        self.selected_marker = None
        self.play_btn.setText("Lecture")
        self.update_info()

    def show_frame(self, frame_number):
        if self.cap is None:
            return

        frame_number = max(0, min(int(frame_number), self.total_frames - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, frame = self.cap.read()
        if not ok:
            self.show_error("Impossible de lire cette frame.")
            return

        self.current_frame = frame_number
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channel = rgb.shape
        image = QImage(rgb.data, width, height, channel * width, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image).scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(pixmap)

        self.timeline.blockSignals(True)
        self.timeline.setValue(frame_number)
        self.timeline.blockSignals(False)
        self.update_info()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.cap is not None:
            self.show_frame(self.current_frame)

    def eventFilter(self, watched, event):
        if not self.isActiveWindow():
            return super().eventFilter(watched, event)
        if event.type() == QEvent.KeyPress and self.handle_key_press(event):
            return True
        if event.type() == QEvent.KeyRelease and self.handle_key_release(event):
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if self.handle_key_press(event):
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self.handle_key_release(event):
            return
        super().keyReleaseEvent(event)

    def handle_key_press(self, event):
        if event.isAutoRepeat():
            return True

        action = self.action_for_key(normalized_key(event))
        if action is None:
            return False

        self.run_shortcut_action(action)
        if action in ("previous_frame", "next_frame"):
            self.held_action = action
            self.hold_timer.start()
        return True

    def handle_key_release(self, event):
        if event.isAutoRepeat():
            return True
        action = self.action_for_key(normalized_key(event))
        if action == self.held_action:
            self.hold_timer.stop()
            self.held_action = None
            return True
        else:
            return action is not None

    def action_for_key(self, key):
        for action, shortcut_key in self.shortcuts.items():
            if shortcut_key == key:
                return action
        return None

    def run_shortcut_action(self, action):
        actions = {
            "toggle_playback": self.toggle_playback,
            "previous_frame": self.previous_frame,
            "next_frame": self.next_frame,
            "previous_video": self.previous_video,
            "next_video": self.next_video,
            "validate": self.cut_video,
            "delete_video": self.delete_current_video,
            "add_marker": self.add_marker,
            "delete_marker": self.delete_selected_marker,
        }
        actions[action]()

    def _repeat_held_action(self):
        if self.held_action in ("previous_frame", "next_frame"):
            self.run_shortcut_action(self.held_action)

    def seek_frame(self, frame_number):
        if self.cap is not None:
            self.show_frame(frame_number)

    def toggle_playback(self):
        if self.cap is None:
            return
        if self.is_playing:
            self.timer.stop()
            self.is_playing = False
            self.play_btn.setText("Lecture")
            return

        interval = max(1, int(1000 / self.fps))
        self.timer.start(interval)
        self.is_playing = True
        self.play_btn.setText("Pause")

    def previous_frame(self):
        if self.cap is not None:
            self.show_frame(self.current_frame - 1)

    def next_frame(self):
        if self.cap is None:
            return
        if self.current_frame >= self.total_frames - 1:
            self.timer.stop()
            self.is_playing = False
            self.play_btn.setText("Lecture")
            return
        self.show_frame(self.current_frame + 1)

    def previous_video(self):
        row = self.video_list.currentRow()
        if row > 0:
            self.video_list.setCurrentRow(row - 1)

    def next_video(self):
        row = self.video_list.currentRow()
        if 0 <= row < self.video_list.count() - 1:
            self.video_list.setCurrentRow(row + 1)

    def add_marker(self):
        if self.cap is None:
            return
        if self.current_frame <= 0 or self.current_frame >= self.total_frames - 1:
            self.show_warning("Un marqueur à la frame 0 ou à la dernière frame est inutile.")
            return
        if self.current_frame in self.markers:
            self.show_warning("Un marqueur existe déjà sur cette frame.")
            return

        self.markers.append(self.current_frame)
        self.markers.sort()
        self.selected_marker = self.current_frame
        self.update_info()

    def marker_selected(self, marker):
        self.selected_marker = marker
        self.show_frame(marker)
        self.update_info()

    def delete_selected_marker(self):
        if self.selected_marker is None:
            self.show_warning("Aucun marqueur sélectionné.")
            return
        self.markers = [m for m in self.markers if m != self.selected_marker]
        self.selected_marker = None
        self.update_info()

    def cut_video(self):
        if self.current_path is None or self.work_dir is None:
            self.show_warning("Aucune vidéo sélectionnée.")
            return
        if not self.markers:
            self.show_warning("Aucun marqueur placé.")
            return
        if shutil.which("ffmpeg") is None:
            self.show_error("FFmpeg n'est pas installé ou n'est pas disponible dans le PATH.")
            return

        points = [0] + sorted(self.markers) + [self.total_frames]
        if any(points[i] >= points[i + 1] for i in range(len(points) - 1)):
            self.show_error("Marqueurs invalides.")
            return

        source_path = self.current_path
        delete_original = self.delete_original_after_cut
        prefix = video_prefix(source_path)
        outputs = next_output_paths(
            self.work_dir,
            prefix,
            len(points) - 1,
            ignored_path=source_path if delete_original else None,
        )
        ffmpeg_outputs = []
        temporary_outputs = []
        for output_path in outputs:
            ffmpeg_output = output_path
            if delete_original and output_path == source_path:
                ffmpeg_output = temporary_output_path(output_path)
                temporary_outputs.append((ffmpeg_output, output_path))
            ffmpeg_outputs.append(ffmpeg_output)

        try:
            for index, output_path in enumerate(ffmpeg_outputs):
                start_frame = points[index]
                end_frame = points[index + 1]
                start = start_frame / self.fps
                end = end_frame / self.fps
                run_ffmpeg(source_path, start, end, output_path)
            if delete_original:
                self.release_video()
                source_path.unlink()
                for temporary_path, final_path in temporary_outputs:
                    if final_path.exists():
                        raise FileExistsError(f"Le fichier existe déjà : {final_path.name}")
                    temporary_path.replace(final_path)
        except PermissionError:
            self.show_error("Problème de permission fichier.")
            return
        except FileExistsError as exc:
            self.show_error(str(exc))
            return
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() if exc.stderr else "Découpage échoué."
            self.show_error(message)
            return

        self.statusBar().showMessage(f"{len(outputs)} segment(s) généré(s)")
        QMessageBox.information(
            self,
            "Découpage terminé",
            "Fichiers générés :\n" + "\n".join(path.name for path in outputs),
        )
        self.refresh_video_list(keep_path=outputs[0] if delete_original else source_path)

    def delete_current_video(self):
        if self.current_path is None:
            self.show_warning("Aucune vidéo sélectionnée.")
            return

        path = self.current_path
        reply = QMessageBox.question(
            self,
            "Supprimer la vidéo",
            f"Supprimer définitivement cette vidéo ?\n{path.name}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        row = self.video_list.currentRow()
        self.release_video()
        try:
            path.unlink()
        except OSError as exc:
            self.show_error(f"Impossible de supprimer la vidéo : {exc}")
            self.refresh_video_list()
            return

        self.statusBar().showMessage(f"Vidéo supprimée : {path.name}")
        self.refresh_video_list()
        if self.video_files:
            self.video_list.setCurrentRow(min(row, len(self.video_files) - 1))
        else:
            self._set_video_controls_enabled(False)
            self.file_label.setText("Aucune vidéo sélectionnée")
            self.video_label.setText("Choisissez un dossier contenant des fichiers MP4")

    def refresh_video_list(self, keep_path=None):
        if self.work_dir is None:
            return
        self.video_files = sorted(self.work_dir.glob("*.mp4"), key=lambda p: p.name.lower())
        self.video_list.blockSignals(True)
        self.video_list.clear()
        for video in self.video_files:
            self.video_list.addItem(video.name)
        self.video_list.blockSignals(False)
        if keep_path in self.video_files:
            self.video_list.setCurrentRow(self.video_files.index(keep_path))
        self.update_navigation_buttons()

    def update_info(self):
        total = max(0, self.total_frames - 1)
        self.timeline.set_markers(self.markers, self.selected_marker)

        file_name = self.current_path.name if self.current_path else "-"
        folder = str(self.work_dir) if self.work_dir else "-"
        duration = self.total_frames / self.fps if self.fps > 0 else 0
        selected = str(self.selected_marker) if self.selected_marker is not None else "-"

        self.info_file_label.setText(f"Fichier: {file_name}")
        self.info_folder_label.setText(f"Dossier: {folder}")
        self.info_frame_label.setText(f"Frame: {self.current_frame} / {total}")
        self.info_fps_label.setText(f"FPS: {self.fps:.3f}" if self.fps else "FPS: -")
        self.info_duration_label.setText(
            f"Durée: {duration:.2f} s" if duration else "Durée: -"
        )
        self.info_marker_label.setText(f"Marqueurs: {len(self.markers)}")
        self.info_selected_marker_label.setText(f"Marqueur sélectionné: {selected}")
        self.shortcut_label.setText(self.shortcut_summary())

    def shortcut_summary(self):
        lines = []
        for action, label in ACTION_LABELS.items():
            lines.append(f"{label}: {key_name(self.shortcuts[action])}")
        return "\n".join(lines)

    def update_navigation_buttons(self):
        row = self.video_list.currentRow()
        has_video = self.cap is not None
        self.prev_video_btn.setEnabled(has_video and row > 0)
        self.next_video_btn.setEnabled(has_video and row < self.video_list.count() - 1)

    def _set_video_controls_enabled(self, enabled):
        for widget in (
            self.prev_video_btn,
            self.prev_btn,
            self.play_btn,
            self.next_btn,
            self.next_video_btn,
            self.add_marker_btn,
            self.delete_marker_btn,
            self.validate_btn,
            self.delete_video_btn,
            self.timeline,
        ):
            widget.setEnabled(enabled)
        self.update_navigation_buttons()

    def open_shortcut_menu(self):
        dialog = ShortcutDialog(self.shortcuts, self.delete_original_after_cut, self)
        if dialog.exec() == QDialog.Accepted:
            self.shortcuts = dict(dialog.shortcuts)
            self.delete_original_after_cut = dialog.delete_original_after_cut
            self.update_info()

    def show_warning(self, message):
        self.statusBar().showMessage(message)
        QMessageBox.warning(self, "Attention", message)

    def show_error(self, message):
        self.statusBar().showMessage(message)
        QMessageBox.critical(self, "Erreur", message)
