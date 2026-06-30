"""메인 윈도우 (UI 조립).

Phase 2: 앱 창 안에 영상을 임베딩하고, '파일 열기'로 선택한 영상을 재생한다.
Phase 3: 하단 컨트롤 바(재생/일시정지/정지)를 추가한다.
Phase 4: 재생바(seek bar) — 진행 표시 + 드래그로 초 단위 이동, 시간 라벨.
"""

import os
import subprocess
import tempfile
import time

from PyQt6.QtCore import Qt, QTimer, QEvent, QPoint, QPointF, QRectF, QSettings
from PyQt6.QtGui import (
    QActionGroup,
    QPalette,
    QColor,
    QShortcut,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFileDialog,
    QMenu,
    QVBoxLayout,
    QHBoxLayout,
    QSlider,
    QLabel,
    QPushButton,
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


class PlayPauseButton(QPushButton):
    """재생/일시정지 아이콘을 QPainter로 직접 그리는 둥근 토글 버튼.

    이모지·텍스트 대신 벡터로 그려 어떤 크기에서도 선명하며,
    마우스 호버 시 원형 배경이 살짝 밝아진다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._playing = False
        self.setFixedSize(44, 44)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_playing(self, playing: bool):
        """재생 상태를 바꾸고 모양이 달라졌을 때만 다시 그린다."""
        if playing != self._playing:
            self._playing = playing
            self.update()

    def enterEvent(self, event):
        self.update()   # 호버 배경 갱신
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        side = min(self.width(), self.height())
        cx, cy = self.width() / 2, self.height() / 2

        # 원형 배경 (호버 시 더 밝게)
        painter.setBrush(QColor(255, 255, 255, 40 if self.underMouse() else 22))
        r = side / 2
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # 흰색 아이콘
        painter.setBrush(QColor(255, 255, 255))
        icon = side * 0.42
        if self._playing:
            # 일시정지: 둥근 모서리 세로 막대 2개
            bar_w = icon * 0.32
            gap = icon * 0.30
            top = cy - icon / 2
            radius = bar_w * 0.35
            painter.drawRoundedRect(
                QRectF(cx - gap / 2 - bar_w, top, bar_w, icon), radius, radius
            )
            painter.drawRoundedRect(
                QRectF(cx + gap / 2, top, bar_w, icon), radius, radius
            )
        else:
            # 재생: 오른쪽을 가리키는 삼각형 (시각적 중심 보정으로 살짝 오른쪽)
            w = icon * 0.9
            left = cx - w / 2 + w * 0.12
            path = QPainterPath()
            path.moveTo(left, cy - icon / 2)
            path.lineTo(left, cy + icon / 2)
            path.lineTo(left + w, cy)
            path.closeSubpath()
            painter.drawPath(path)

        painter.end()


class MenuButton(QPushButton):
    """옵션(메뉴) 아이콘을 QPainter로 직접 그리는 둥근 버튼.

    재생 버튼과 동일한 크기·호버 배경을 사용해 같은 행에서 통일감을 준다.
    아이콘은 수평으로 나란한 둥근 줄 3개(햄버거 메뉴)로 그린다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(33, 33)   # 재생 버튼(44)의 75% 크기
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event):
        self.update()   # 호버 배경 갱신
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        side = min(self.width(), self.height())
        cx, cy = self.width() / 2, self.height() / 2

        # 원형 배경 (호버 시 더 밝게) — 재생 버튼과 동일
        painter.setBrush(QColor(255, 255, 255, 40 if self.underMouse() else 22))
        r = side / 2
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # 햄버거 메뉴 (흰색): 수평으로 나란한 둥근 줄 3개
        painter.setBrush(QColor(255, 255, 255))
        bar_w = side * 0.44
        bar_h = max(2.0, side * 0.072)
        gap = side * 0.15
        radius = bar_h / 2
        for dy in (-gap, 0.0, gap):
            painter.drawRoundedRect(
                QRectF(cx - bar_w / 2, cy + dy - bar_h / 2, bar_w, bar_h),
                radius,
                radius,
            )

        painter.end()


class VolumeButton(QPushButton):
    """볼륨(스피커/음소거) 아이콘을 QPainter로 직접 그리는 둥근 버튼.

    옵션 버튼과 동일한 크기·호버 배경을 사용한다.
    음소거(볼륨 0)면 스피커 옆에 X를, 아니면 음파를 그린다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._muted = True   # 시작 시 음소거(볼륨 0)
        self.setFixedSize(33, 33)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_muted(self, muted: bool):
        """음소거 상태를 바꾸고 모양이 달라졌을 때만 다시 그린다."""
        if muted != self._muted:
            self._muted = muted
            self.update()

    def enterEvent(self, event):
        self.update()   # 호버 배경 갱신
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        side = min(self.width(), self.height())
        cx, cy = self.width() / 2, self.height() / 2

        # 원형 배경 (호버 시 더 밝게) — 다른 버튼과 동일
        painter.setBrush(QColor(255, 255, 255, 40 if self.underMouse() else 22))
        r = side / 2
        painter.drawEllipse(QPointF(cx, cy), r, r)

        painter.translate(cx, cy)
        white = QColor(255, 255, 255)

        # 스피커 본체: 뒤쪽 사각형 + 앞쪽으로 벌어지는 원뿔(콘)
        painter.setBrush(white)
        box_l, box_r = -0.26 * side, -0.08 * side
        box_h = 0.09 * side
        cone_x = 0.07 * side
        cone_h = 0.22 * side
        speaker = QPainterPath()
        speaker.moveTo(box_l, -box_h)
        speaker.lineTo(box_r, -box_h)
        speaker.lineTo(cone_x, -cone_h)
        speaker.lineTo(cone_x, cone_h)
        speaker.lineTo(box_r, box_h)
        speaker.lineTo(box_l, box_h)
        speaker.closeSubpath()
        painter.drawPath(speaker)

        # 음파(재생) 또는 X(음소거)는 선으로 그린다.
        pen = QPen(white, max(1.5, side * 0.06))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self._muted:
            d = 0.085 * side
            x0 = 0.21 * side
            painter.drawLine(QPointF(x0 - d, -d), QPointF(x0 + d, d))
            painter.drawLine(QPointF(x0 - d, d), QPointF(x0 + d, -d))
        else:
            # 오른쪽으로 열린 두 개의 호 (-45°~+45°)
            for rad in (0.16 * side, 0.26 * side):
                rect = QRectF(0.04 * side - rad, -rad, 2 * rad, 2 * rad)
                painter.drawArc(rect, -45 * 16, 90 * 16)

        painter.end()


class SeekButton(QPushButton):
    """되감기/넘기기 버튼. 홑겹 화살표(< / >)를 QPainter로 그린다.

    스피커 버튼과 동일한 크기·호버 배경을 사용한다.
    forward=True면 오른쪽('>', 넘기기), False면 왼쪽('<', 되감기)을 가리킨다.
    """

    def __init__(self, forward: bool, parent=None):
        super().__init__(parent)
        self._forward = forward
        self.setFixedSize(33, 33)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event):
        self.update()   # 호버 배경 갱신
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        side = min(self.width(), self.height())
        cx, cy = self.width() / 2, self.height() / 2

        # 원형 배경 (호버 시 더 밝게) — 다른 버튼과 동일
        painter.setBrush(QColor(255, 255, 255, 40 if self.underMouse() else 22))
        r = side / 2
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # 홑겹 화살표 (흰색 선). forward면 '>', 아니면 '<' 방향으로 그린다.
        painter.translate(cx, cy)
        pen = QPen(QColor(255, 255, 255), max(2.0, side * 0.09))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        d = 1.0 if self._forward else -1.0   # '>'는 +, '<'는 -
        w = 0.16 * side    # 화살표 가로 절반
        h = 0.24 * side    # 화살표 세로 절반
        path = QPainterPath()
        path.moveTo(-w * d, -h)
        path.lineTo(w * d, 0.0)
        path.lineTo(-w * d, h)
        painter.drawPath(path)

        painter.end()


class SpeedButton(QPushButton):
    """배속 버튼. 넘기기(forward) 버튼과 똑같은 더블 삼각형(►►)을 QPainter로 그린다.

    옵션·되감기/넘기기 버튼과 동일한 크기·호버 배경을 사용한다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(33, 33)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event):
        self.update()   # 호버 배경 갱신
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        side = min(self.width(), self.height())
        cx, cy = self.width() / 2, self.height() / 2

        # 원형 배경 (호버 시 더 밝게) — 다른 버튼과 동일
        painter.setBrush(QColor(255, 255, 255, 40 if self.underMouse() else 22))
        r = side / 2
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # 더블 삼각형 (흰색) — 넘기기 버튼(오른쪽)과 동일하게 그린다.
        painter.translate(cx, cy)
        painter.setBrush(QColor(255, 255, 255))
        w = 0.22 * side
        h = 0.34 * side
        path = QPainterPath()
        for back_x in (-0.22 * side, 0.0):
            path.moveTo(back_x, -h / 2)
            path.lineTo(back_x, h / 2)
            path.lineTo(back_x + w, 0.0)
            path.closeSubpath()
        painter.drawPath(path)

        painter.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Frame Player")
        self.resize(1280, 720)

        self.player = PlayerCore()
        self._hwnd_attached = False

        # 재생바 상태
        self._user_dragging = False   # 사용자가 슬라이더를 잡고 있는 동안 True
        self._duration_ms = 0         # 알려진 영상 길이 (슬라이더 범위 설정용)
        self._resume_after_drag = False  # 드래그 시작 시 재생 중이었으면 종료 후 재개
        self._last_drag_seek = 0.0    # 드래그 중 실시간 seek throttle용 마지막 실행 시각
        self._drag_seek_interval = 0.02  # 실시간 seek 최소 간격(초) = 20ms

        # 화살표를 누르고 있을 때 프레임/초 이동을 제한할 최소 간격(초)
        self._step_interval = 0.1

        # 넘기기/되감기 버튼의 단위 시간(초). 메뉴에서 변경하면 영구 저장된다.
        self._settings = QSettings("FramePlayer", "FramePlayer")
        self._skip_seconds = self._settings.value("skip_seconds", 10, type=int)

        # 재생 배속 — 시작 시 항상 1배속으로 둔다(저장하지 않음).
        self._speed = 1.0

        # 볼륨 상태 — 마지막에 설정한 값을 불러온다(최초 실행 시 음소거 0).
        self._volume = self._settings.value("volume", 0, type=int)
        self._volume_popup = None        # 수직 사운드 패널 (lazy 생성)
        self._volume_closed_at = 0.0     # Popup이 바깥 클릭으로 닫힌 시각 (버튼 재오픈 디바운스용)

        self._build_ui()
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

        # 재생/일시정지 버튼 (재생바 영역 중앙 하단)
        layout.addLayout(self._build_play_controls())

        self.setCentralWidget(central)

    def _build_seek_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        # 위 여백을 최소화해 슬라이더와 시간 텍스트를 회색 영역 위쪽에 둔다.
        # (남는 아래 공간에는 재생/일시정지 버튼 행이 들어간다)
        bar.setContentsMargins(6, 6, 6, 6)

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

    def _build_play_controls(self) -> QHBoxLayout:
        """재생바 영역 중앙 하단에 재생/일시정지 토글 버튼을 배치한다."""
        row = QHBoxLayout()
        row.setContentsMargins(6, 0, 6, 12)

        self.option_button = MenuButton()
        self.option_button.clicked.connect(self._open_options)

        # 배속 버튼 — 메뉴 버튼 바로 오른쪽
        self.speed_button = SpeedButton()
        self.speed_button.clicked.connect(self._open_speed_menu)

        # 재생 버튼 양옆의 되감기/넘기기 (스피커 버튼과 같은 크기)
        self.rewind_button = SeekButton(forward=False)
        self.rewind_button.clicked.connect(lambda: self._skip(-self._skip_seconds))

        self.play_button = PlayPauseButton()
        self.play_button.clicked.connect(self.toggle_play)

        self.forward_button = SeekButton(forward=True)
        self.forward_button.clicked.connect(lambda: self._skip(self._skip_seconds))

        # 볼륨 버튼 — 옵션 버튼과 같은 크기로 우측에 고정 (좌우 대칭 → 재생 버튼 중앙 유지)
        self.volume_button = VolumeButton()
        self.volume_button.clicked.connect(self._toggle_volume_popup)

        row.addWidget(self.option_button)
        row.addSpacing(8)
        row.addWidget(self.speed_button)
        row.addStretch(1)
        row.addWidget(self.rewind_button)
        row.addSpacing(20)
        row.addWidget(self.play_button)
        row.addSpacing(20)
        row.addWidget(self.forward_button)
        row.addStretch(1)
        row.addWidget(self.volume_button)
        return row

    def _skip(self, seconds: float):
        """현재 재생 상태를 유지한 채 지정한 초만큼 이동한다(되감기/넘기기).

        영상을 불러오지 않은 상태에서는 아무 동작도 하지 않는다.
        """
        if not self.player.is_loaded():
            return
        self.player.seek_relative(seconds)
        self._sync_position()

    def _open_options(self):
        """메뉴 버튼 클릭 시 옵션 리스트를 연다.

        - 파일 열기: 상단 '파일 > 열기'와 동일
        - 넘기기 시간 조절: 5/10/15/30초 (선택 항목에 체크 표시)
        - 업데이트 확인: 상단 '업데이트 확인'과 동일
        """
        menu = QMenu(self)
        menu.addAction("파일 열기", self.open_file_dialog)

        skip_menu = menu.addMenu("넘기기 시간 조절")
        group = QActionGroup(skip_menu)
        group.setExclusive(True)
        for sec in (5, 10, 15, 30):
            act = skip_menu.addAction(f"{sec}초")
            act.setCheckable(True)
            act.setChecked(sec == self._skip_seconds)
            act.triggered.connect(lambda _checked, s=sec: self._set_skip_seconds(s))
            group.addAction(act)

        menu.addAction("업데이트 확인", self.check_for_update)

        # 메뉴 버튼은 창 하단에 있으므로 버튼 위쪽으로 띄운다.
        btn = self.option_button
        top_left = btn.mapToGlobal(btn.rect().topLeft())
        menu.exec(QPoint(top_left.x(), top_left.y() - menu.sizeHint().height()))

    def _set_skip_seconds(self, seconds: int):
        """넘기기/되감기 버튼의 단위 시간(초)을 설정하고 영구 저장한다."""
        self._skip_seconds = seconds
        self._settings.setValue("skip_seconds", seconds)

    def _open_speed_menu(self):
        """배속 버튼 클릭 시 배속 선택지(x0.25 ~ x2)를 연다.

        현재 선택된 배속에 체크 표시를 한다 (넘기기 시간 조절과 동일).
        """
        menu = QMenu(self)
        group = QActionGroup(menu)
        group.setExclusive(True)
        for speed in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
            act = menu.addAction(f"x{speed:g}")
            act.setCheckable(True)
            act.setChecked(speed == self._speed)
            act.triggered.connect(lambda _checked, s=speed: self._set_speed(s))
            group.addAction(act)

        # 배속 버튼은 창 하단에 있으므로 버튼 위쪽으로 띄운다.
        btn = self.speed_button
        top_left = btn.mapToGlobal(btn.rect().topLeft())
        menu.exec(QPoint(top_left.x(), top_left.y() - menu.sizeHint().height()))

    def _set_speed(self, speed: float):
        """재생 배속을 설정한다."""
        self._speed = speed
        self.player.set_speed(speed)

    def _update_play_icon(self):
        """현재 재생 상태에 맞춰 버튼 아이콘을 갱신한다."""
        self.play_button.set_playing(self.player.is_playing())

    # ----- 볼륨 (사운드 패널) -----

    def _build_volume_popup(self) -> QWidget:
        """버튼 위로 떠오르는 수직 사운드 패널을 생성한다.

        Qt.Popup으로 만들어 영상(네이티브 HWND) 위에 확실히 표시되고,
        바깥 클릭·창 비활성화(포커스 이동) 시 자동으로 닫힌다.
        """
        popup = QWidget(self, Qt.WindowType.Popup)
        popup.setFixedSize(40, 140)

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(8, 10, 8, 10)

        slider = QSlider(Qt.Orientation.Vertical, popup)
        slider.setRange(0, 100)
        slider.setValue(self._volume)
        slider.valueChanged.connect(self._on_volume_changed)
        layout.addWidget(slider, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 패널이 닫히는 시각을 기록해 버튼 재오픈 디바운스에 쓴다.
        # (바깥 클릭이 버튼이었던 경우 곧바로 다시 열리는 것을 막음)
        popup.installEventFilter(self)

        self._volume_slider = slider
        return popup

    def _toggle_volume_popup(self):
        """사운드 패널을 열거나 닫는다.

        패널이 바깥 클릭으로 막 닫힌 경우(버튼 클릭이 그 바깥 클릭이었던 경우)
        곧바로 다시 열리지 않도록 짧게 디바운스한다.
        """
        if self._volume_popup is None:
            self._volume_popup = self._build_volume_popup()

        if self._volume_popup.isVisible():
            self._volume_popup.hide()
            return

        # 방금(150ms 이내) 바깥 클릭으로 닫혔다면 재오픈하지 않는다.
        if time.monotonic() - self._volume_closed_at < 0.15:
            return

        self._volume_slider.setValue(self._volume)

        # 버튼 바로 위, 가로 중앙에 맞춰 배치한다.
        popup = self._volume_popup
        btn = self.volume_button
        top_left = btn.mapToGlobal(btn.rect().topLeft())
        x = top_left.x() + (btn.width() - popup.width()) // 2
        y = top_left.y() - popup.height()
        popup.move(x, y)
        popup.show()

    def _on_volume_changed(self, value: int):
        """슬라이더 값으로 볼륨을 설정·저장하고 버튼 아이콘을 갱신한다. (0 = 음소거)"""
        self._volume = value
        self.player.set_volume(value)
        self._settings.setValue("volume", value)
        self._update_volume_icon()

    def _update_volume_icon(self):
        self.volume_button.set_muted(self._volume == 0)

    def changeEvent(self, event):
        """창이 비활성화(포커스 이동)되면 사운드 패널을 닫는다. (Popup 보강)"""
        if event.type() == QEvent.Type.WindowDeactivate and self._volume_popup is not None:
            if self._volume_popup.isVisible():
                self._volume_closed_at = time.monotonic()
                self._volume_popup.hide()
        super().changeEvent(event)

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
        add("Shift+Left", self._throttled(lambda: self._skip(-self._skip_seconds)))   # Shift+← 되감기
        add("Shift+Right", self._throttled(lambda: self._skip(self._skip_seconds)))    # Shift+→ 넘기기
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
        """영상 위젯 더블클릭 시 풀스크린을 토글하고,
        사운드 패널이 닫히는 시각을 기록한다(버튼 재오픈 디바운스용)."""
        if obj is self.video_widget and event.type() == QEvent.Type.MouseButtonDblClick:
            self.toggle_fullscreen()
            return True
        if obj is self._volume_popup and event.type() == QEvent.Type.Hide:
            self._volume_closed_at = time.monotonic()
        return super().eventFilter(obj, event)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.showFullScreen()

    def exit_fullscreen(self):
        # 풀스크린일 때만 동작 (Esc를 일반 상태에서 눌러도 영향 없게)
        if self.isFullScreen():
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
            # 마지막에 저장된 볼륨을 적용하고 버튼 아이콘도 동기화한다.
            self.player.set_volume(self._volume)
            self._update_volume_icon()
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

        # 재생/일시정지 버튼 아이콘을 현재 상태와 동기화한다.
        self._update_play_icon()

    def _update_seek_ui(self, ms: int):
        """슬라이더와 현재시간 라벨을 주어진 위치(ms)로 갱신한다."""
        self.seek_slider.setValue(int(ms))
        self.current_label.setText(format_time(int(ms)))

    def _on_slider_pressed(self):
        # 드래그 시작: 재생 중이었는지 기억하고 일시정지한다.
        # (종료 후 이전 상태로 복원하기 위함)
        self._resume_after_drag = self.player.is_playing()
        self.player.pause()
        self._user_dragging = True
        self._last_drag_seek = 0.0

    def _on_slider_moved(self, value: int):
        # 드래그 중: 현재시간 라벨을 갱신하고, 화면을 드래그 위치에 실시간 동기화한다.
        # sliderMoved는 매우 자주 발생하므로 20ms 간격으로 seek를 제한해 mpv 부하를 막는다.
        self.current_label.setText(format_time(value))
        now = time.monotonic()
        if now - self._last_drag_seek >= self._drag_seek_interval:
            self._last_drag_seek = now
            self.player.set_time(value)

    def _on_slider_released(self):
        # 놓는 순간 최종 위치로 정확히 이동(throttle로 건너뛴 마지막 위치 보정).
        value = self.seek_slider.value()
        self.player.set_time(value)
        self._user_dragging = False
        # 드래그 전 재생 중이었다면 재개한다.
        if self._resume_after_drag:
            self.player.play()
            self._resume_after_drag = False

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
        """현재 재생 상태(재생/일시정지)를 유지한 채 지정한 초만큼 정밀 이동한다."""
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
        self._checker = UpdateChecker()
        self._checker.succeeded.connect(self._on_check_result)
        self._checker.failed.connect(self._on_check_failed)
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
            "설치 완료 후 자동으로 다시 시작됩니다. 잠시 기다려주세요.",
        )
        # 설치 파일을 조용히 실행한 뒤 앱을 종료한다.
        # (설치 파일이 실행 중인 앱을 닫고 파일을 교체하며, 완료 후 자동 재시작한다)
        subprocess.Popen([path, "/SILENT"])
        self.close()

    def _on_download_failed(self, message: str):
        self._progress.close()
        QMessageBox.warning(self, "업데이트 실패", f"다운로드에 실패했습니다.\n{message}")
