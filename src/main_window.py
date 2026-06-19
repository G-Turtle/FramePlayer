"""메인 윈도우 (UI 조립).

Phase 2: 앱 창 안에 VLC 영상을 임베딩하고, '파일 열기'로 선택한 영상을 재생한다.
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QPalette, QColor
from PyQt6.QtWidgets import QMainWindow, QWidget, QFileDialog

from player_core import PlayerCore


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Frame Player")
        self.resize(960, 540)

        self.player = PlayerCore()
        self._hwnd_attached = False

        # 영상 출력 영역 (검은 배경)
        self.video_widget = QWidget(self)
        self.video_widget.setAutoFillBackground(True)
        palette = self.video_widget.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        self.video_widget.setPalette(palette)
        self.setCentralWidget(self.video_widget)

        self._build_menu()

    def _build_menu(self):
        open_action = QAction("열기(&O)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file_dialog)

        file_menu = self.menuBar().addMenu("파일(&F)")
        file_menu.addAction(open_action)

    def showEvent(self, event):
        """창이 화면에 표시된 후 영상 출력 핸들을 연결한다.

        winId()는 위젯이 실제 생성된 이후에만 유효하므로 여기서 한 번만 연결한다.
        """
        super().showEvent(event)
        if not self._hwnd_attached:
            self.player.set_hwnd(int(self.video_widget.winId()))
            self._hwnd_attached = True

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "동영상 열기",
            "",
            "동영상 파일 (*.mp4 *.mkv *.avi *.mov *.wmv);;모든 파일 (*.*)",
        )
        if path:
            self.open_file(path)

    def open_file(self, path: str):
        """파일을 로드하고 재생한다."""
        self.player.load(path)
        self.player.play()
        self.setWindowTitle(f"Frame Player - {os.path.basename(path)}")
