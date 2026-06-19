"""Frame Player 진입점."""

import os
import sys

# 동결(PyInstaller 빌드) 실행 시 번들된 VLC 런타임을 사용하도록 경로를 지정한다.
# python-vlc가 이 환경변수를 우선 사용하므로, 대상 PC에 VLC가 없어도 동작한다.
# 반드시 vlc 모듈이 import되기 전(= main_window import 전)에 설정해야 한다.
if getattr(sys, "frozen", False):
    _base = sys._MEIPASS
    os.environ.setdefault("PYTHON_VLC_LIB_PATH", os.path.join(_base, "libvlc.dll"))
    os.environ.setdefault("PYTHON_VLC_MODULE_PATH", os.path.join(_base, "plugins"))

from PyQt6.QtWidgets import QApplication

from main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    # CLI 인자로 파일 경로가 오면 자동 재생한다 (파일 더블클릭/연결 프로그램용).
    # show() 이후에 호출해야 영상 출력 핸들(winId)이 유효하다.
    if len(sys.argv) >= 2:
        window.open_file(sys.argv[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
