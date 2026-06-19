"""메인 윈도우 (UI 조립).

Phase 2: 앱 창 안에 VLC 영상을 임베딩하고, '파일 열기'로 선택한 영상을 재생한다.
Phase 3: 하단 컨트롤 바(재생/일시정지/정지)를 추가한다.
Phase 4: 재생바(seek bar) — 진행 표시 + 드래그로 초 단위 이동, 시간 라벨.
"""

import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QPalette, QColor
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QLabel,
)

from player_core import PlayerCore


def format_time(ms: int) -> str:
    """밀리초를 MM:SS 또는 H:MM:SS 문자열로 변환한다."""
    if ms < 0:
        ms = 0
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Frame Player")
        self.resize(960, 540)

        self.player = PlayerCore()
        self._hwnd_attached = False

        # 재생바 상태
        self._user_dragging = False   # 사용자가 슬라이더를 잡고 있는 동안 True
        self._duration_ms = 0         # 알려진 영상 길이 (슬라이더 범위 설정용)

        # 프레임 이동용 FPS 캐시 (재생 후에야 유효, 없으면 기본 30fps)
        self._cached_fps = 0.0
        self._default_fps = 30.0

        self._build_ui()
        self._build_menu()

        # 재생 위치를 주기적으로 폴링해 슬라이더/시간 라벨 갱신
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

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

        # 재생바 (시간 라벨 + 슬라이더)
        layout.addLayout(self._build_seek_bar())

        # 컨트롤 바
        layout.addLayout(self._build_control_bar())

        self.setCentralWidget(central)

    def _build_seek_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 0)

        self.current_label = QLabel("00:00")
        self.total_label = QLabel("00:00")

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        # 드래그 충돌 방지: 누르는 동안 타이머 갱신 중단, 놓을 때만 seek
        self.seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self.seek_slider.sliderReleased.connect(self._on_slider_released)
        self.seek_slider.sliderMoved.connect(self._on_slider_moved)

        bar.addWidget(self.current_label)
        bar.addWidget(self.seek_slider, stretch=1)
        bar.addWidget(self.total_label)
        return bar

    def _build_control_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 4)

        self.play_button = QPushButton("▶ 재생")
        self.play_button.clicked.connect(self.toggle_play)

        self.stop_button = QPushButton("⏹ 정지")
        self.stop_button.clicked.connect(self.stop)

        self.prev_frame_button = QPushButton("◀ 프레임")
        self.prev_frame_button.clicked.connect(self.step_backward)

        self.next_frame_button = QPushButton("프레임 ▶")
        self.next_frame_button.clicked.connect(self.step_forward)

        bar.addWidget(self.play_button)
        bar.addWidget(self.stop_button)
        bar.addWidget(self.prev_frame_button)
        bar.addWidget(self.next_frame_button)
        bar.addStretch(1)
        return bar

    def _build_menu(self):
        open_action = QAction("열기(&O)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file_dialog)

        file_menu = self.menuBar().addMenu("파일(&F)")
        file_menu.addAction(open_action)

    def closeEvent(self, event):
        """앱 종료 시 VLC 리소스를 정리한 뒤 닫는다."""
        self.player.release()
        super().closeEvent(event)

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

        # 새 파일이므로 재생바/FPS 상태 초기화 (길이·FPS는 타이머가 파싱 후 채운다)
        self._duration_ms = 0
        self._cached_fps = 0.0
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setValue(0)
        self.current_label.setText("00:00")
        self.total_label.setText("00:00")

    def _on_tick(self):
        """주기적으로 재생 위치를 읽어 슬라이더/시간 라벨을 갱신한다."""
        length = self.player.get_length()
        if length > 0 and length != self._duration_ms:
            self._duration_ms = length
            self.seek_slider.setRange(0, length)
            self.total_label.setText(format_time(length))

        # FPS는 재생이 시작된 후에야 유효하므로 유효값을 한 번 캐시한다
        if self._cached_fps <= 0:
            fps = self.player.get_fps()
            if fps and fps > 0:
                self._cached_fps = fps

        # 사용자가 드래그 중이면 슬라이더 위치를 건드리지 않는다 (값 튐 방지)
        if not self._user_dragging:
            t = self.player.get_time()
            if t >= 0:
                self.seek_slider.setValue(t)
                self.current_label.setText(format_time(t))

    def _on_slider_pressed(self):
        self._user_dragging = True

    def _on_slider_moved(self, value: int):
        # 드래그 중에는 미리보기로 현재시간 라벨만 갱신
        self.current_label.setText(format_time(value))

    def _on_slider_released(self):
        # 놓는 순간에만 실제 seek 수행
        self.player.set_time(self.seek_slider.value())
        self._user_dragging = False

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

    def _effective_fps(self) -> float:
        """프레임 이동 계산에 쓸 FPS. 캐시값이 없으면 기본값으로 폴백."""
        return self._cached_fps if self._cached_fps > 0 else self._default_fps

    def _pause_for_stepping(self):
        """프레임 이동은 일시정지 상태에서 수행한다. 재생 중이면 멈춘다."""
        if self.player.is_playing():
            self.player.pause()
            self.play_button.setText("▶ 재생")

    def step_forward(self):
        """한 프레임 앞으로."""
        self._pause_for_stepping()
        self.player.next_frame()

    def step_backward(self):
        """한 프레임 뒤로. (VLC 후진 API가 없어 시간 계산으로 seek)"""
        self._pause_for_stepping()
        frame_ms = round(1000.0 / self._effective_fps())
        new_time = max(0, self.player.get_time() - frame_ms)
        self.player.set_time(new_time)
