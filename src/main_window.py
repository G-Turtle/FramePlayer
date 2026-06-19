"""메인 윈도우 (UI 조립).

Phase 2: 앱 창 안에 VLC 영상을 임베딩하고, '파일 열기'로 선택한 영상을 재생한다.
Phase 3: 하단 컨트롤 바(재생/일시정지/정지)를 추가한다.
Phase 4: 재생바(seek bar) — 진행 표시 + 드래그로 초 단위 이동, 시간 라벨.
"""

import os

from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtGui import QAction, QPalette, QColor, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QLabel,
    QMessageBox,
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

        # 직접 추적하는 현재 위치(ms, float).
        # next_frame() 후 get_time()이 갱신되지 않으므로 프레임 이동의 기준값으로 사용한다.
        self._position_ms = 0.0

        # 프레임 이동용 FPS 캐시 (재생 후에야 유효, 없으면 기본 30fps)
        self._cached_fps = 0.0
        self._default_fps = 30.0

        # ←/→ 점프 간격(초)
        self._jump_seconds = 5

        # 음소거 상태
        self._muted = False

        self._build_ui()
        self._build_menu()
        self._build_shortcuts()

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
        # 영상 더블클릭으로 풀스크린 토글 (VLC 마우스 입력을 꺼서 이벤트가 Qt로 전달됨)
        self.video_widget.installEventFilter(self)
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

        self.mute_button = QPushButton("🔊")
        self.mute_button.clicked.connect(self.toggle_mute)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

        # 버튼이 키보드 포커스를 가져가면 Space가 버튼을 누르므로 포커스를 받지 않게 한다
        for btn in (self.play_button, self.stop_button,
                    self.prev_frame_button, self.next_frame_button):
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            bar.addWidget(btn)
        bar.addStretch(1)
        self.mute_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.volume_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        bar.addWidget(self.mute_button)
        bar.addWidget(self.volume_slider)
        return bar

    def _build_menu(self):
        open_action = QAction("열기(&O)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file_dialog)

        file_menu = self.menuBar().addMenu("파일(&F)")
        file_menu.addAction(open_action)

    def _build_shortcuts(self):
        """키보드 단축키를 등록한다.

        VLC가 입력을 가로채지 않도록 set_hwnd에서 video_set_key_input(False)를
        호출했으므로, 영상에 포커스가 있어도 이 단축키들이 동작한다.
        """
        def add(key, handler):
            QShortcut(QKeySequence(key), self, activated=handler)

        add(Qt.Key.Key_Space, self.toggle_play)
        add(Qt.Key.Key_Left, lambda: self.jump(-self._jump_seconds))
        add(Qt.Key.Key_Right, lambda: self.jump(self._jump_seconds))
        add(Qt.Key.Key_Comma, self.step_backward)    # ',' 한 프레임 뒤로
        add(Qt.Key.Key_Period, self.step_forward)    # '.' 한 프레임 앞으로
        add(Qt.Key.Key_F, self.toggle_fullscreen)
        add(Qt.Key.Key_Escape, self.exit_fullscreen)

    def eventFilter(self, obj, event):
        """영상 위젯 더블클릭 시 풀스크린을 토글한다."""
        if obj is self.video_widget and event.type() == QEvent.Type.MouseButtonDblClick:
            self.toggle_fullscreen()
            return True
        return super().eventFilter(obj, event)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.menuBar().hide()
            self.showFullScreen()

    def exit_fullscreen(self):
        # 풀스크린일 때만 동작 (Esc를 일반 상태에서 눌러도 영향 없게)
        if self.isFullScreen():
            self.menuBar().show()
            self.showNormal()

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
        """파일을 로드하고 재생한다. 경로가 유효하지 않으면 경고 후 무시한다."""
        if not os.path.isfile(path):
            QMessageBox.warning(
                self,
                "파일 열기 실패",
                f"파일을 찾을 수 없습니다:\n{path}",
            )
            return

        self.player.load(path)
        self.player.play()
        self.player.set_volume(self.volume_slider.value())
        self.player.set_mute(self._muted)
        self.setWindowTitle(f"Frame Player - {os.path.basename(path)}")
        self.play_button.setText("⏸ 일시정지")

        # 새 파일이므로 재생바/FPS 상태 초기화 (길이·FPS는 타이머가 파싱 후 채운다)
        self._duration_ms = 0
        self._cached_fps = 0.0
        self._position_ms = 0.0
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

        # 재생 중일 때만 get_time()으로 위치를 동기화한다.
        # (일시정지 중에는 프레임 이동/seek 메서드가 _position_ms와 UI를 직접 갱신한다.)
        if self.player.is_playing() and not self._user_dragging:
            t = self.player.get_time()
            if t >= 0:
                self._position_ms = float(t)
                self._update_seek_ui(t)

        # 끝까지 재생되어 종료되면 버튼을 '재생'으로 되돌린다
        if self.player.has_ended() and self.play_button.text() != "▶ 재생":
            self.play_button.setText("▶ 재생")

    def _update_seek_ui(self, ms: int):
        """슬라이더와 현재시간 라벨을 주어진 위치(ms)로 갱신한다."""
        self.seek_slider.setValue(int(ms))
        self.current_label.setText(format_time(int(ms)))

    def _on_slider_pressed(self):
        self._user_dragging = True

    def _on_slider_moved(self, value: int):
        # 드래그 중에는 미리보기로 현재시간 라벨만 갱신
        self.current_label.setText(format_time(value))

    def _on_slider_released(self):
        # 놓는 순간에만 실제 seek 수행
        value = self.seek_slider.value()
        self.player.set_time(value)
        self._position_ms = float(value)   # 추적 위치도 동기화
        self._user_dragging = False

    def toggle_play(self):
        # play()/pause() 직후의 is_playing()은 상태 반영이 지연되므로,
        # 동작 전 상태로 분기하고 버튼 라벨은 수행한 동작 기준으로 직접 설정한다.
        if self.player.is_playing():
            self._pause()
        else:
            # 끝까지 재생되어 종료된 상태면 stop으로 리셋 후 처음부터 재생한다
            if self.player.has_ended():
                self.player.stop()
            self.player.play()
            self.play_button.setText("⏸ 일시정지")

    def _pause(self):
        """일시정지하고, 이 순간의 정확한 get_time()으로 추적 위치를 동기화한다.

        일시정지 시점에 _position_ms를 맞춰 두면 이후 프레임 이동의 기준이 정확해진다.
        (next_frame()을 쓰지 않으므로 get_time()은 항상 신뢰 가능하다.)
        """
        self.player.pause()
        self.play_button.setText("▶ 재생")
        t = self.player.get_time()
        if t >= 0:
            self._position_ms = float(t)

    def stop(self):
        self.player.stop()
        self.play_button.setText("▶ 재생")

    def toggle_mute(self):
        self._muted = not self._muted
        self.player.set_mute(self._muted)
        self.mute_button.setText("🔇" if self._muted else "🔊")

    def _on_volume_changed(self, value: int):
        self.player.set_volume(value)
        # 볼륨을 올리면 음소거를 자동 해제한다
        if self._muted and value > 0:
            self._muted = False
            self.player.set_mute(False)
            self.mute_button.setText("🔊")

    def _effective_fps(self) -> float:
        """프레임 이동 계산에 쓸 FPS. 캐시값이 없으면 기본값으로 폴백."""
        return self._cached_fps if self._cached_fps > 0 else self._default_fps

    def _pause_for_stepping(self):
        """프레임 이동은 일시정지 상태에서 수행한다. 재생 중이면 멈춘다."""
        if self.player.is_playing():
            self._pause()

    def _current_ms(self) -> int:
        """현재 재생 위치(ms). 재생 중이면 get_time(), 아니면 추적 위치."""
        if self.player.is_playing():
            t = self.player.get_time()
            if t >= 0:
                return t
        return round(self._position_ms)

    def seek_to(self, ms: int):
        """주어진 위치(ms)로 이동한다. 범위를 벗어나면 양끝으로 보정한다."""
        ms = max(0, ms)
        if self._duration_ms > 0:
            ms = min(ms, self._duration_ms)
        self.player.set_time(ms)
        self._position_ms = float(ms)
        self._update_seek_ui(ms)

    def jump(self, seconds: float):
        """현재 위치에서 지정한 초만큼 앞/뒤로 점프한다."""
        self.seek_to(self._current_ms() + int(seconds * 1000))

    def step_forward(self):
        """한 프레임 앞으로."""
        self._step_frame(+1)

    def step_backward(self):
        """한 프레임 뒤로."""
        self._step_frame(-1)

    def _step_frame(self, direction: int):
        """프레임 이동을 set_time으로 통일 구현한다.

        next_frame()은 이후 set_time을 깨뜨리는 특수 상태를 만들므로 사용하지 않고,
        추적 위치(_position_ms)에서 ±1프레임 한 지점으로 직접 seek 한다.
        set_time은 일시정지 상태에서 프레임 단위로 정확하다.
        """
        self._pause_for_stepping()
        frame_ms = 1000.0 / self._effective_fps()
        self._position_ms += direction * frame_ms
        self._position_ms = max(0.0, self._position_ms)
        if self._duration_ms > 0:
            self._position_ms = min(self._position_ms, float(self._duration_ms))
        self.player.set_time(round(self._position_ms))
        self._update_seek_ui(round(self._position_ms))
