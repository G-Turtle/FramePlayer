# Frame Player — 프로젝트 계획

## 1. 개요

Windows 10/11용 동영상(mp4) 재생 프로그램. Windows 기본 Media Player에 없는 정밀 탐색 기능을 추가하는 것이 목표.

- **프로그램 이름**: Frame Player
- **대상 OS**: Windows 10, 11 (64비트)
- **프로젝트 경로**: `C:\null\80_ai\01_ClaudeCode\FramePlayer`

## 2. 개발 환경

| 구성 요소 | 선택 | 비고 |
|---|---|---|
| 언어 | Python 3.11.9 | 가상환경 `.venv` 사용 |
| UI 프레임워크 | PyQt6 | 커스텀 위젯 자유도 |
| 미디어 백엔드 | python-vlc (libVLC) | 프레임 단위 접근, 정밀 seek |
| 패키징 | PyInstaller 6.21.0 | 폴더 빌드(`--onedir`) |
| 인스톨러 | Inno Setup | 레지스트리 등록 + 설치 파일 |
| 배포 | GitHub Releases | 업데이트/배포 |

### 설치 완료 상태
- Python 3.11.9 (`C:\Users\vkdld\AppData\Local\Programs\Python\Python311`)
- 가상환경: `C:\null\80_ai\01_ClaudeCode\FramePlayer\.venv`
- VLC Media Player 3.0.23 win64 (`C:\Program Files\VideoLAN\VLC`, libvlc.dll 확인됨)
- 패키지: PyQt6, python-vlc, pyinstaller(6.21.0) — 모두 `.venv`에 설치 완료
- VLC 설치 시 "파일 형식 연결"은 해제함 (Frame Player를 기본 플레이어로 등록할 예정)

## 3. 주요 부가 기능

1. **재생바 드래그로 초 단위 이동** — 슬라이더 드래그 시 실시간 초/밀리초 단위 seek
2. **프레임 단위 앞/뒤 이동** — libVLC `next_frame()` 등 활용한 프레임 단위 탐색
3. (확장 예정) 스킵 간격 사용자 지정, 재생 속도 조절, 자막 트랙 선택 등

## 4. 배포 / 업데이트 전략

```
소스코드(Python)
  → PyInstaller 폴더 빌드(--onedir)
  → Inno Setup 인스톨러(.exe) — 레지스트리 등록 포함
  → GitHub Releases 업로드
  → 앱 내 버전 체크(GitHub API)로 업데이트 알림
```

### Windows 파일 연결 (레지스트리 등록)
설치 시 인스톨러가 등록, 제거 시 삭제. 관리자 권한 불필요한 `HKEY_CURRENT_USER` 권장.

```
HKCU\Software\Classes\FramePlayer\shell\open\command
  → "<설치경로>\FramePlayer.exe" "%1"
HKCU\Software\Classes\.mp4\OpenWithProgids → FramePlayer
HKCU\Software\RegisteredApplications → FramePlayer
```
- 우클릭 → "연결 프로그램" 목록에 표시
- "항상 이 앱으로 열기"로 기본 플레이어 지정 가능

## 5. 향후 작업 순서 (TODO)

- [ ] GitHub 저장소 생성 및 연결
- [ ] 프로젝트 구조 설계 (소스 폴더, requirements.txt, .gitignore 등)
- [ ] PyQt6 + python-vlc 기본 재생 창 뼈대 작성
- [ ] 재생바 드래그 초 단위 seek 구현
- [ ] 프레임 단위 앞/뒤 이동 구현
- [ ] CLI 인자(`%1`)로 파일 경로 받아 재생 (파일 연결용)
- [ ] PyInstaller 폴더 빌드 스크립트
- [ ] Inno Setup 인스톨러 스크립트 (레지스트리 등록 포함)
- [ ] GitHub Releases 배포 + 앱 내 업데이트 체크

## 6. 참고 사항

- VS Code에서 Python 인터프리터를 `.venv\Scripts\python.exe`로 선택해야 함
- pip 설치 시 반드시 `.venv`의 pip 사용 (`.venv\Scripts\pip.exe`)
