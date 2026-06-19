"""메인 윈도우 (UI 조립).

Phase 2: 앱 창 안에 영상을 임베딩하고, '파일 열기'로 선택한 영상을 재생한다.
Phase 3: 하단 컨트롤 바(재생/일시정지/정지)를 추가한다.
Phase 4: 재생바(seek bar) — 진행 표시 + 드래그로 초 단위 이동, 시간 라벨.
"""

import os
import subprocess
import tempfile
import time

from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtGui import QAction, QPalette, QColor, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSlider,
    QLabel,
    QMessageBox,
    QProgressDialog,
)

from player_core import PlayerCore
from version import __version__
from updater import UpdateChecker, Downloader, is_newer


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

        # 화살표를 누르고 있을 때 프레임/초 이동을 제한할 최소 간격(초)
        self._step_interval = 0.1

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
        # mpv가 임베딩할 수 있도록 네이티브 윈도우로 만든다 (winId 유효화)
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.video_widget.setAutoFillBackground(True)
        palette = self.video_widget.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        self.video_widget.setPalette(palette)
        # 영상 더블클릭으로 풀스크린 토글 (mpv 마우스 입력을 꺼서 이벤트가 Qt로 전달됨)
        self.video_widget.installEventFilter(self)
        layout.addWidget(self.video_widget, stretch=1)

        # 재생바 (시간 라벨 + 슬라이더)
        layout.addLayout(self._build_seek_bar())

        self.setCentralWidget(central)

    def _build_seek_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        # 위·아래 여백을 대칭으로 줘서 재생바 영역을 넓히고,
        # 슬라이더와 시간 텍스트가 그 안에서 세로 중앙에 같은 높이로 정렬되게 한다.
        bar.setContentsMargins(6, 14, 6, 14)

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

    def _build_menu(self):
        open_action = QAction("열기(&O)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file_dialog)

        file_menu = self.menuBar().addMenu("파일(&F)")
        file_menu.addAction(open_action)

        # 파일 메뉴 오른쪽에 '업데이트 확인' 버튼 (드롭다운 없이 바로 실행)
        self.update_action = self.menuBar().addAction("업데이트 확인")
        self.update_action.triggered.connect(self.check_for_update)

    def _build_shortcuts(self):
        """키보드 단축키를 등록한다.

        mpv가 입력을 가로채지 않도록 set_hwnd에서 input_vo_keyboard=False로
        생성했으므로, 영상에 포커스가 있어도 이 단축키들이 동작한다.
        """
        def add(key, handler):
            QShortcut(QKeySequence(key), self, activated=handler)

        add(Qt.Key.Key_Space, self.toggle_play)
        add(Qt.Key.Key_Left, self._throttled(self.step_backward))            # ← 1프레임 뒤로
        add(Qt.Key.Key_Right, self._throttled(self.step_forward))            # → 1프레임 앞으로
        add("Ctrl+Left", self._throttled(lambda: self._step_seconds(-1)))    # Ctrl+← 1초 뒤로
        add("Ctrl+Right", self._throttled(lambda: self._step_seconds(1)))    # Ctrl+→ 1초 앞으로
        add(Qt.Key.Key_F, self.toggle_fullscreen)
        add(Qt.Key.Key_Escape, self.exit_fullscreen)

    def _throttled(self, handler):
        """단축키를 누르고 있을 때 자동반복으로 핸들러가 폭주하지 않도록,
        직전 실행으로부터 _step_interval(0.1초)이 지난 경우에만 실행한다.

        키마다 독립된 마지막 실행 시각을 클로저로 갖는다.
        (←를 누르고 있어도 → 첫 입력은 즉시 반응)
        """
        last = 0.0

        def wrapped():
            nonlocal last
            now = time.monotonic()
            if now - last < self._step_interval:
                return
            last = now
            handler()

        return wrapped

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
        """앱 종료 시 재생 리소스를 정리한 뒤 닫는다."""
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
        self.setWindowTitle(f"Frame Player - {os.path.basename(path)}")

        # 새 파일이므로 재생바 상태 초기화 (길이는 타이머가 파싱 후 채운다)
        self._duration_ms = 0
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

        # 재생 중이든 일시정지(프레임 이동) 중이든 항상 현재 위치로 동기화한다.
        # (mpv의 time_pos는 일시정지·프레임 스텝 이후에도 유효하다.)
        if not self._user_dragging:
            t = self.player.get_time()
            if t >= 0:
                self._update_seek_ui(t)

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
        self._user_dragging = False

    def toggle_play(self):
        # play()/pause() 직후의 is_playing()은 상태 반영이 지연되므로 동작 전 상태로 분기한다.
        if self.player.is_playing():
            self.player.pause()
        else:
            # 끝까지 재생되어 종료된 상태면 처음으로 되감은 뒤 재생한다
            if self.player.has_ended():
                self.player.set_time(0)
            self.player.play()

    def _pause_for_stepping(self):
        """프레임 이동은 일시정지 상태에서 수행한다. 재생 중이면 멈춘다."""
        if self.player.is_playing():
            self.player.pause()

    def _step_seconds(self, seconds: float):
        """재생 중이면 먼저 일시정지한 뒤, 지정한 초만큼 정밀 이동한다. (일시정지 유지)"""
        self._pause_for_stepping()
        self.player.seek_relative(seconds)
        self._sync_position()

    def step_forward(self):
        """한 프레임 앞으로 (mpv frame-step, 화면 프레임 기준 정확)."""
        self._pause_for_stepping()
        self.player.frame_step()
        self._sync_position()

    def step_backward(self):
        """한 프레임 뒤로 (mpv frame-back-step, 화면 프레임 기준 정확)."""
        self._pause_for_stepping()
        self.player.frame_back_step()
        self._sync_position()

    def _sync_position(self):
        """프레임 이동/seek 직후 슬라이더·시간 라벨을 현재 위치로 갱신한다."""
        t = self.player.get_time()
        if t >= 0:
            self._update_seek_ui(t)

    # ----- 업데이트 (Phase 10) -----

    def check_for_update(self):
        """GitHub 최신 릴리스를 확인한다 (백그라운드 스레드)."""
        self.update_action.setEnabled(False)
        self._checker = UpdateChecker()
        self._checker.succeeded.connect(self._on_check_result)
        self._checker.failed.connect(self._on_check_failed)
        self._checker.finished.connect(lambda: self.update_action.setEnabled(True))
        self._checker.start()

    def _on_check_result(self, info: dict):
        latest = info.get("version")
        url = info.get("download_url")

        if not latest:
            QMessageBox.information(self, "업데이트 확인", "현재 사용 가능한 업데이트가 없습니다.")
            return

        if not is_newer(latest, __version__):
            QMessageBox.information(
                self, "업데이트 확인", f"현재 최신 버전입니다. (버전 {__version__})"
            )
            return

        if not url:
            QMessageBox.warning(
                self,
                "업데이트",
                f"새 버전 {latest}이(가) 있으나 설치 파일을 찾지 못했습니다.\n"
                "GitHub 릴리스 페이지에서 직접 받아주세요.",
            )
            return

        ret = QMessageBox.question(
            self,
            "업데이트",
            f"새 버전 {latest}이(가) 있습니다. (현재 {__version__})\n업데이트를 하시겠습니까?",
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._start_download(url)

    def _on_check_failed(self, message: str):
        QMessageBox.warning(
            self, "업데이트 확인 실패", f"업데이트 정보를 확인할 수 없습니다.\n{message}"
        )

    def _start_download(self, url: str):
        dest = os.path.join(tempfile.gettempdir(), "FramePlayer-Setup-update.exe")
        self._progress = QProgressDialog("업데이트를 다운로드하는 중...", "취소", 0, 100, self)
        self._progress.setWindowTitle("업데이트")
        self._progress.setMinimumDuration(0)
        self._progress.setAutoClose(False)
        self._progress.setAutoReset(False)

        self._downloader = Downloader(url, dest)
        self._downloader.progress.connect(self._progress.setValue)
        self._downloader.succeeded.connect(self._on_download_done)
        self._downloader.failed.connect(self._on_download_failed)
        self._progress.canceled.connect(self._downloader.requestInterruption)
        self._downloader.start()

    def _on_download_done(self, path: str):
        self._progress.close()
        QMessageBox.information(
            self,
            "업데이트",
            "다운로드가 완료되었습니다. 업데이트를 설치하면 앱이 종료되었다가\n"
            "설치 완료 후 자동으로 다시 시작됩니다.",
        )
        # 설치 파일을 조용히 실행한 뒤 앱을 종료한다.
        # (설치 파일이 실행 중인 앱을 닫고 파일을 교체하며, 완료 후 자동 재시작한다)
        subprocess.Popen([path, "/SILENT"])
        self.close()

    def _on_download_failed(self, message: str):
        self._progress.close()
        QMessageBox.warning(self, "업데이트 실패", f"다운로드에 실패했습니다.\n{message}")
