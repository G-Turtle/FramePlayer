"""메인 윈도우 (UI 조립).

Phase 2: 앱 창 안에 VLC 영상을 임베딩하고, '파일 열기'로 선택한 영상을 재생한다.
Phase 3: 하단 컨트롤 바(재생/일시정지/정지)를 추가한다.
"""

import os

from PyQt6.QtGui import QAction, QPalette, QColor
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)

from player_core import PlayerCore


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Frame Player")
        self.resize(960, 540)

        self.player = PlayerCore()
        self._hwnd_attached = False

        self._build_ui()
        self._build_menu()

    def _build_ui(self):
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 영상 출력 영역 (검은 배경)
        self.video_widget = QWidget(self)
        self.video_widget.setAutoFillBackground(True)
        palette = self.video_widget.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        self.video_widget.setPalette(palette)
        layout.addWidget(self.video_widget, stretch=1)

        # 컨트롤 바
        layout.addLayout(self._build_control_bar())

        self.setCentralWidget(central)

    def _build_control_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 4)

        self.play_button = QPushButton("▶ 재생")
        self.play_button.clicked.connect(self.toggle_play)

        self.stop_button = QPushButton("⏹ 정지")
        self.stop_button.clicked.connect(self.stop)

        bar.addWidget(self.play_button)
        bar.addWidget(self.stop_button)
        bar.addStretch(1)
        return bar

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
        self.play_button.setText("⏸ 일시정지")

    def toggle_play(self):
        # play()/pause() 직후의 is_playing()은 상태 반영이 지연되므로,
        # 동작 전 상태로 분기하고 버튼 라벨은 수행한 동작 기준으로 직접 설정한다.
        if self.player.is_playing():
            self.player.pause()
            self.play_button.setText("▶ 재생")
        else:
            self.player.play()
            self.play_button.setText("⏸ 일시정지")

    def stop(self):
        self.player.stop()
        self.play_button.setText("▶ 재생")
