"""GitHub Releases 기반 업데이트 확인/다운로드.

네트워크 작업은 UI를 멈추지 않도록 QThread에서 수행하고 시그널로 결과를 전달한다.
"""

import json
import re
import urllib.request
import urllib.error

from PyQt6.QtCore import QThread, pyqtSignal

# 대상 저장소의 최신 릴리스 API
GITHUB_API = "https://api.github.com/repos/G-Turtle/FramePlayer/releases/latest"
_HEADERS = {"User-Agent": "FramePlayer", "Accept": "application/vnd.github+json"}


def parse_version(s: str) -> tuple:
    """'v0.1.2' / '0.1.2' 같은 문자열을 (0,1,2) 튜플로 변환한다."""
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums) if nums else (0,)


def is_newer(latest: str, current: str) -> bool:
    """latest가 current보다 높은 버전이면 True."""
    return parse_version(latest) > parse_version(current)


class UpdateChecker(QThread):
    """최신 릴리스 정보를 조회한다.

    succeeded: {'version': str|None, 'download_url': str|None}
               version이 None이면 릴리스가 없는 것으로 간주.
    failed:    오류 메시지(str)
    """

    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        try:
            req = urllib.request.Request(GITHUB_API, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # 아직 릴리스가 없음 → 업데이트 없음으로 처리
                self.succeeded.emit({"version": None, "download_url": None})
            else:
                self.failed.emit(f"서버 응답 오류 (HTTP {e.code})")
            return
        except Exception as e:
            self.failed.emit(str(e))
            return

        version = data.get("tag_name") or ""
        download_url = None
        for asset in data.get("assets", []):
            name = (asset.get("name") or "").lower()
            if name.endswith(".exe") and "setup" in name:
                download_url = asset.get("browser_download_url")
                break
        self.succeeded.emit({"version": version, "download_url": download_url})


class Downloader(QThread):
    """설치 파일을 다운로드한다.

    progress:  0~100 정수
    succeeded: 저장된 파일 경로(str)
    failed:    오류 메시지(str)
    """

    progress = pyqtSignal(int)
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, url: str, dest: str):
        super().__init__()
        self._url = url
        self._dest = dest

    def run(self):
        try:
            req = urllib.request.Request(self._url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(self._dest, "wb") as f:
                    while True:
                        if self.isInterruptionRequested():
                            self.failed.emit("취소되었습니다.")
                            return
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self.progress.emit(int(downloaded * 100 / total))
            self.succeeded.emit(self._dest)
        except Exception as e:
            self.failed.emit(str(e))
