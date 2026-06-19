"""VLC 재생 로직 래퍼.

Phase 1: UI 없이 python-vlc만으로 재생이 되는지 검증하기 위한 최소 구현.
영상 임베딩(set_hwnd)은 Phase 2에서 추가한다.
"""

import vlc


class PlayerCore:
    """libVLC를 감싼 재생 제어 래퍼."""

    def __init__(self):
        self._instance = vlc.Instance()
        self._player = self._instance.media_player_new()
        self._media = None

    def set_hwnd(self, hwnd: int) -> None:
        """영상을 그릴 윈도우 핸들을 지정한다. (Windows 전용)

        주의: 위젯이 화면에 생성된(show() 이후) 시점의 winId()를 넘겨야 한다.
        """
        self._player.set_hwnd(hwnd)

    def load(self, path: str) -> None:
        """파일 경로를 미디어로 로드한다."""
        self._media = self._instance.media_new(path)
        self._player.set_media(self._media)

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        """재생/일시정지 토글이 아닌 '일시정지'. (토글은 set_pause 사용)"""
        self._player.set_pause(1)

    def resume(self) -> None:
        self._player.set_pause(0)

    def stop(self) -> None:
        self._player.stop()

    def is_playing(self) -> bool:
        return bool(self._player.is_playing())

    def get_time(self) -> int:
        """현재 재생 위치 (밀리초). 아직 준비 안 됐으면 -1."""
        return self._player.get_time()

    def get_length(self) -> int:
        """전체 길이 (밀리초). 아직 파싱 안 됐으면 0 또는 -1."""
        return self._player.get_length()

    def set_time(self, ms: int) -> None:
        """지정한 위치(밀리초)로 이동."""
        self._player.set_time(int(ms))

    def get_fps(self) -> float:
        """프레임레이트. 재생/파싱 전에는 0이 나올 수 있다."""
        return self._player.get_fps()


def _format_ms(ms: int) -> str:
    if ms < 0:
        return "--:--"
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


if __name__ == "__main__":
    # Phase 1 검증용 스크립트.
    # 사용법: python src/player_core.py "<영상경로>"
    # 경로를 생략하면 TestFile 폴더의 샘플을 사용한다.
    import sys
    import time
    from pathlib import Path

    if len(sys.argv) >= 2:
        video_path = sys.argv[1]
    else:
        # 프로젝트 루트 기준 기본 샘플
        root = Path(__file__).resolve().parent.parent
        sample = root / "TestFile" / "2026.04.04.mp4"
        video_path = str(sample)

    print(f"[load] {video_path}")
    core = PlayerCore()
    core.load(video_path)
    core.play()

    # 미디어 파싱에 약간의 시간이 필요하므로 잠시 대기 후 정보 출력.
    time.sleep(1.0)
    print(f"[length] {core.get_length()} ms ({_format_ms(core.get_length())})")
    print(f"[fps]    {core.get_fps()}")

    # 5초간 0.5초 간격으로 재생 위치를 출력한다.
    for _ in range(10):
        print(f"[time] {core.get_time()} ms ({_format_ms(core.get_time())})  playing={core.is_playing()}")
        time.sleep(0.5)

    core.stop()
    print("[done] Phase 1 검증 종료")
