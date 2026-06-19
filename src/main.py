"""Frame Player 진입점."""

import sys

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
