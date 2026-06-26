"""mpv(libmpv) 재생 로직 래퍼.

VLC 대신 libmpv를 사용한다. libmpv는 일시정지 상태에서 프레임 단위 스텝
(frame-step / frame-back-step)과 정밀(hr-seek) 탐색을 지원하므로, 화면에
보이는 프레임을 기준으로 정확한 프레임 이동이 가능하다.

(VLC는 일시정지 시 get_time이 화면 프레임보다 몇 프레임 뒤처지고, 화면에 멈춘
프레임을 정밀하게 주소지정할 수 없어 프레임 단위 이동에서 점프가 발생했다.)
"""

import mpv


class PlayerCore:
    """libmpv를 감싼 재생 제어 래퍼."""

    def __init__(self):
        # mpv는 임베딩 창 핸들(wid)을 인스턴스 생성 시점에 알아야 하므로,
        # 실제 MPV 객체는 set_hwnd에서 만든다.
        self._player = None
        self._loaded = False

    def set_hwnd(self, hwnd: int) -> None:
        """영상을 그릴 윈도우 핸들을 지정하며 MPV 인스턴스를 생성한다.

        주의: 위젯이 화면에 생성된(show() 이후) 시점의 winId()를 넘겨야 한다.
        """
        self._player = mpv.MPV(
            wid=str(int(hwnd)),
            vo="gpu",
            hr_seek="yes",            # 프레임 정확 탐색
            keep_open="yes",          # 끝에서 자동 종료하지 않고 마지막 프레임 유지
            input_default_bindings=False,
            input_vo_keyboard=False,  # 키 입력은 Qt 단축키가 처리하도록 mpv가 가로채지 않게
            input_cursor=False,
            cursor_autohide="no",
        )

    def load(self, path: str) -> None:
        """파일을 로드하고 재생을 시작한다."""
        self._player.play(path)
        self._loaded = True

    def play(self) -> None:
        if self._player:
            self._player.pause = False

    def pause(self) -> None:
        """일시정지한다."""
        if self._player:
            self._player.pause = True

    def resume(self) -> None:
        self.play()

    def stop(self) -> None:
        if self._player:
            self._player.command("stop")
        self._loaded = False

    def is_loaded(self) -> bool:
        """재생할 파일이 로드되어 있는지."""
        return self._loaded

    def is_playing(self) -> bool:
        if not self._player or not self._loaded:
            return False
        return not bool(self._player.pause) and not bool(self._player.eof_reached)

    def get_time(self) -> int:
        """현재 재생 위치 (밀리초). 아직 준비 안 됐으면 -1."""
        if not self._player:
            return -1
        t = self._player.time_pos
        return int(t * 1000) if t is not None else -1

    def get_length(self) -> int:
        """전체 길이 (밀리초). 아직 파싱 안 됐으면 0."""
        if not self._player:
            return 0
        d = self._player.duration
        return int(d * 1000) if d is not None else 0

    def set_time(self, ms: int) -> None:
        """지정한 위치(밀리초)로 정밀(hr-seek) 이동."""
        if self._player:
            self._player.seek(max(0, ms) / 1000.0, reference="absolute", precision="exact")

    def seek_relative(self, seconds: float) -> None:
        """현재 위치에서 지정한 초만큼 정밀 이동."""
        if self._player:
            self._player.seek(seconds, reference="relative", precision="exact")

    def frame_step(self) -> None:
        """일시정지 상태에서 정확히 한 프레임 앞으로."""
        if self._player:
            self._player.frame_step()

    def frame_back_step(self) -> None:
        """일시정지 상태에서 정확히 한 프레임 뒤로."""
        if self._player:
            self._player.frame_back_step()

    def get_fps(self) -> float:
        """컨테이너 프레임레이트. 파싱 전에는 0이 나올 수 있다."""
        if not self._player:
            return 0.0
        fps = self._player.container_fps
        return float(fps) if fps else 0.0

    def has_ended(self) -> bool:
        """재생이 끝까지 가서 종료(EOF) 상태인지."""
        if not self._player:
            return False
        return bool(self._player.eof_reached)

    def set_volume(self, volume: int) -> None:
        """볼륨을 0~100으로 설정한다."""
        if self._player:
            self._player.volume = int(volume)

    def get_volume(self) -> int:
        if not self._player:
            return 100
        v = self._player.volume
        return int(v) if v is not None else 100

    def set_mute(self, muted: bool) -> None:
        if self._player:
            self._player.mute = bool(muted)

    def release(self) -> None:
        """libmpv 리소스를 정리한다. 앱 종료 시 호출한다."""
        if self._player:
            self._player.terminate()
            self._player = None
