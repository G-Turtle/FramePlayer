"""Frame Player 진입점."""

import os
import sys

# libmpv-2.dll 위치를 DLL 검색 경로에 추가한다. python-mpv가 이 경로에서
# libmpv-2.dll을 찾으므로, 대상 PC에 mpv가 설치돼 있지 않아도 동작한다.
# 반드시 mpv 모듈이 import되기 전(= main_window import 전)에 설정해야 한다.
if getattr(sys, "frozen", False):
    _libdir = sys._MEIPASS
else:
    # 개발 환경: 프로젝트 루트의 libs/ 폴더 (이 파일은 src/ 안에 있음)
    _libdir = os.path.join(os.path.dirname(__file__), "..", "libs")
_libdir = os.path.abspath(_libdir)
if os.path.isdir(_libdir):
    os.add_dll_directory(_libdir)
    os.environ["PATH"] = _libdir + os.pathsep + os.environ.get("PATH", "")

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from main_window import MainWindow


def _icon_path() -> str:
    """아이콘 파일 경로를 반환한다 (동결 빌드/개발 환경 모두 대응)."""
    if getattr(sys, "frozen", False):
        # 스펙의 datas로 번들 루트(_internal)에 포함된 icon.ico
        return os.path.join(sys._MEIPASS, "icon.ico")
    # 개발 환경: 프로젝트 루트의 assets/icon.ico (이 파일은 src/ 안에 있음)
    return os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")


def main():
    # Windows 작업 표시줄이 python.exe가 아닌 이 앱의 아이콘으로 표시되도록
    # 명시적 AppUserModelID를 지정한다 (창 생성 전에 호출).
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FramePlayer")

    app = QApplication(sys.argv)
    # 앱 전역 아이콘. 모든 최상위 창과 팝업(파일 열기, 업데이트, 진행률)에 상속된다.
    app.setWindowIcon(QIcon(_icon_path()))
    window = MainWindow()
    window.show()

    # CLI 인자로 파일 경로가 오면 자동 재생한다 (파일 더블클릭/연결 프로그램용).
    # show() 이후에 호출해야 영상 출력 핸들(winId)이 유효하다.
    if len(sys.argv) >= 2:
        window.open_file(sys.argv[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
