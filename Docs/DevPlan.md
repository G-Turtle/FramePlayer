# Frame Player — 개발 실행 계획 (DevPlan)

> 이 문서는 [Planning.md](./Planning.md)를 기반으로 한 단계별 개발 실행 계획입니다.
> 각 단계는 **목표 / 작업 / 검증 / 산출물**로 구성되며, 한 단계가 검증을 통과한 후 다음 단계로 진행합니다.
> Claude Code가 다른 컨텍스트에서 이 문서만 읽고도 작업을 이어갈 수 있도록 작성되었습니다.

## 작업 원칙

- **한 번에 하나의 단계만** 구현하고 즉시 검증한다 (버그 조기 발견).
- 각 단계는 **독립 실행 가능한 상태**로 끝낸다 (항상 실행되는 앱 유지).
- 기능 추가 시 **기존 동작을 깨지 않았는지** 매번 확인한다.
- 커밋은 단계(또는 하위 단계) 단위로 작게 나눈다.
- 실행/테스트는 항상 `.venv\Scripts\python.exe` 사용.

## 진행 상황 추적

각 단계 완료 시 아래 체크박스를 갱신한다.

- [x] Phase 0: 프로젝트 구조 및 기반 설정
- [x] Phase 1: VLC 연동 최소 재생 검증 (UI 없음)
- [x] Phase 2: PyQt6 기본 윈도우 + 영상 출력
- [x] Phase 3: 재생 컨트롤 (재생/일시정지/정지)
- [x] Phase 4: 재생바(Seek bar) — 진행 표시 + 드래그 초 단위 이동
- [x] Phase 5: 프레임 단위 앞/뒤 이동
- [ ] Phase 6: CLI 인자로 파일 경로 받기 (파일 연결 대비)
- [ ] Phase 7: UX 보강 (단축키, 볼륨, 시간 표시, 풀스크린)
- [ ] Phase 8: PyInstaller 폴더 빌드 (VLC 런타임 번들 포함)
- [ ] Phase 9: Inno Setup 인스톨러 + 레지스트리 파일 연결
- [ ] Phase 10: GitHub Releases 배포 + 앱 내 업데이트 체크

---

## 핵심 기술 주의사항 (버그 예방용 — 반드시 숙지)

이 프로젝트에서 가장 사고가 나기 쉬운 지점들이다. 구현 전에 읽어둔다.

1. **영상 출력 임베딩 (Windows)**
   - VLC 영상을 PyQt 위젯에 그리려면 위젯의 윈도우 핸들을 VLC에 넘겨야 한다:
     `media_player.set_hwnd(int(video_widget.winId()))`
   - `winId()`는 위젯이 실제로 화면에 생성된(`show()` 이후) 시점에 유효하다. 너무 일찍 호출하면 검은 화면이 된다.

2. **프레임 단위 "뒤로" 이동은 VLC에 직접 API가 없다**
   - libVLC는 `next_frame()`(한 프레임 전진)만 제공한다. **뒤로 한 프레임 API는 없다.**
   - 뒤로 이동은 **현재 시간에서 (1/fps)초만큼 빼서 `set_time()`** 으로 직접 seek 하여 구현한다.
   - FPS는 `media_player.get_fps()`로 얻되, **재생이 시작되어 미디어가 파싱된 후에야 유효**하다. 0이 나오면 트랙 정보(`media.get_tracks()` 또는 미디어 파싱)로 보완하고, 그래도 없으면 기본값(예: 30fps)으로 폴백한다.

3. **seek 정밀도 / 일시정지 상태에서의 화면 갱신**
   - `set_time()` 후 정지 상태에서 화면이 즉시 갱신되지 않을 수 있다. 프레임 이동 시 일시정지 상태를 유지하면서 화면을 갱신하려면 짧은 재생/정지 토글 또는 `next_frame()` 활용이 필요할 수 있다 — Phase 5에서 실제 동작을 보며 조정한다.

4. **슬라이더 드래그 중 위치 갱신 충돌**
   - 타이머가 재생 위치로 슬라이더를 갱신하는 동시에 사용자가 드래그하면 값이 튄다.
   - 사용자가 드래그 중(`sliderPressed`~`sliderReleased`)에는 **타이머의 슬라이더 갱신을 중단**하고, 놓는 순간에만 seek 한다.

5. **VLC 이벤트 콜백에서 Qt UI를 직접 만지지 말 것**
   - VLC 이벤트는 별도 스레드에서 온다. UI 갱신은 `QTimer`로 메인 스레드에서 폴링하거나 Qt 시그널로 넘긴다.

6. **PyInstaller 배포 시 VLC 런타임 번들**
   - python-vlc는 시스템에 설치된 VLC의 `libvlc.dll`을 찾는다. 배포 PC에 VLC가 없을 수 있으므로 **`libvlc.dll`, `libvlccore.dll`, `plugins/` 폴더**를 함께 번들해야 한다. (Phase 8에서 상세)

---

## Phase 0 — 프로젝트 구조 및 기반 설정

**목표**: 코드 작성 전 폴더/파일 골격과 의존성 고정.

**작업**
- 폴더 구조 생성:
  ```
  FramePlayer/
  ├── src/
  │   ├── __init__.py
  │   ├── main.py          # 진입점 (QApplication 실행)
  │   ├── main_window.py   # 메인 윈도우(UI 조립)
  │   ├── player_core.py   # VLC 래퍼 (재생 로직)
  │   └── widgets/         # 커스텀 위젯 (seek bar 등)
  │       └── __init__.py
  ├── assets/
  │   └── (icon.ico 추후)
  ├── Docs/
  ├── requirements.txt
  ├── README.md
  └── .gitignore
  ```
- `requirements.txt` 작성: 설치된 정확한 버전 고정 (`pip freeze` 결과 중 PyQt6, python-vlc 명시).

**검증**
- 폴더/파일이 위 구조대로 존재.
- `requirements.txt`에 PyQt6, python-vlc 버전이 박혀 있음.

**산출물**: 빈 골격 + requirements.txt. 커밋: `chore: scaffold project structure`.

---

## Phase 1 — VLC 연동 최소 재생 검증 (UI 없음)

**목표**: PyQt 이전에, python-vlc만으로 영상이 열리고 재생되는지 먼저 확인 (문제 분리).

**작업**
- `src/player_core.py`에 최소 VLC 래퍼 작성:
  - `vlc.Instance()` 생성, `media_player_new()`.
  - `load(path)`, `play()`, `pause()`, `stop()`, `get_time()`, `get_length()`, `set_time(ms)`.
- 임시 스크립트(`scratch_play.py` 또는 `if __name__ == "__main__"`)로 샘플 mp4를 VLC 자체 창에서 재생.

**검증**
- 샘플 mp4가 재생되고 콘솔에 `get_length()`, `get_time()` 값이 출력됨.
- (이 단계는 VLC 자체 팝업 창으로 재생되어도 OK — 임베딩은 Phase 2.)

**산출물**: 검증된 `player_core.py`. 커밋: `feat: minimal VLC playback wrapper`.

> 준비물: 테스트용 샘플 mp4 1개 경로를 정해둔다 (예: 짧은 클립). 단계 진행 시 사용자에게 경로를 요청.

---

## Phase 2 — PyQt6 기본 윈도우 + 영상 출력

**목표**: 앱 윈도우 안에 VLC 영상이 임베딩되어 나온다.

**작업**
- `src/main.py`: `QApplication` 생성 → `MainWindow` 표시.
- `src/main_window.py`:
  - `QMainWindow` 기반, 중앙에 영상 출력용 `QFrame`(또는 `QWidget`) 배치.
  - 윈도우 `show()` 이후 `player_core`에 `set_hwnd(int(video_frame.winId()))` 연결.
  - 메뉴 또는 버튼으로 "파일 열기"(`QFileDialog`) → 선택 파일 재생.

**검증**
- 앱 실행 → 파일 열기 → **앱 창 내부**에 영상이 표시되고 재생됨 (검은 화면 아님).

**산출물**: 영상이 나오는 앱. 커밋: `feat: embed VLC video in PyQt window`.

---

## Phase 3 — 재생 컨트롤 (재생 / 일시정지 / 정지)

**목표**: 기본 재생 조작 버튼.

**작업**
- 하단 컨트롤 바 레이아웃 추가.
- 재생/일시정지 토글 버튼, 정지 버튼.
- 상태에 따라 버튼 아이콘/텍스트 갱신 (재생 중 ↔ 일시정지).

**검증**
- 버튼으로 재생/일시정지/정지가 정확히 동작하고 상태 표시가 일치.

**산출물**: 커밋: `feat: playback controls`.

---

## Phase 4 — 재생바(Seek bar): 진행 표시 + 드래그 초 단위 이동

**목표**: 핵심 기능 ①. 재생 위치를 표시하고, 드래그로 초 단위 정밀 이동.

**작업**
- `QSlider`(가로) 추가. 범위는 0~길이(ms) 또는 0~1000 정규화 중 택1 (ms 권장: 정밀).
- `QTimer`(예: 100~200ms 간격)로 `get_time()` 폴링 → 슬라이더/시간 라벨 갱신.
- **드래그 충돌 방지** (주의사항 4):
  - `sliderPressed` → 타이머의 슬라이더 갱신 일시 중지(플래그).
  - `sliderMoved` → 시간 라벨만 미리보기 갱신(선택).
  - `sliderReleased` → 해당 위치로 `set_time()`, 갱신 재개.
- 현재시간/총시간 라벨 (`HH:MM:SS`).

**검증**
- 재생 중 슬라이더가 부드럽게 진행.
- 드래그해서 놓으면 그 지점으로 정확히 이동(초 단위), 드래그 중 값 튐 없음.

**산출물**: 커밋: `feat: seek bar with drag-to-seek`.

---

## Phase 5 — 프레임 단위 앞/뒤 이동

**목표**: 핵심 기능 ②. 한 프레임씩 전진/후진.

**작업**
- FPS 확보 로직 (주의사항 2): `get_fps()` → 0이면 폴백(미디어 파싱 후 재시도 → 그래도 없으면 30fps 가정, 상태바에 표시).
- **앞으로 한 프레임**: `next_frame()` 사용 (재생이 일시정지 상태일 때 동작이 자연스러움).
- **뒤로 한 프레임**: `set_time(get_time() - round(1000/fps))` 로 직접 seek.
- 버튼 2개(◀프레임 / 프레임▶) + (Phase 7에서 단축키 `,` `.` 연결 예정).
- 프레임 이동은 **일시정지 상태에서** 수행하도록 유도 (이동 전 자동 pause 옵션 고려).

**검증**
- 일시정지 상태에서 한 프레임씩 앞/뒤로 이동하며 화면이 갱신됨.
- 뒤로 이동이 누적되어도 시간이 음수로 가지 않음(0 하한 처리).

**산출물**: 커밋: `feat: frame-by-frame stepping`.

> 이 단계에서 화면 갱신 지연(주의사항 3)이 보이면, 프레임 이동 후 강제 갱신 방법(짧은 play/pause, 또는 `next_frame()` 조합)을 실험하여 확정하고 코드 주석으로 남긴다.

---

## Phase 6 — CLI 인자로 파일 경로 받기 (파일 연결 대비)

**목표**: `FramePlayer.exe "D:\video.mp4"` 처럼 인자로 받은 파일을 자동 재생. (더블클릭/우클릭 연결의 토대)

**작업**
- `main.py`에서 `sys.argv[1]`이 있으면 시작 시 해당 파일 로드·재생.
- 경로에 공백/유니코드가 있어도 정상 처리 확인.
- 잘못된 경로/미지원 파일일 때 에러 메시지(다이얼로그) 후 정상 동작.

**검증**
- 터미널에서 `python src/main.py "샘플경로.mp4"` 실행 시 자동 재생.
- 공백 포함 경로 정상 동작.

**산출물**: 커밋: `feat: open file from CLI argument`.

---

## Phase 7 — UX 보강 (단축키 / 볼륨 / 시간 표시 / 풀스크린)

**목표**: 실사용 편의 기능. (배포 전 완성도)

**작업** (각 항목은 작은 커밋으로 분리)
- 단축키: `Space`(재생/일시정지), `←/→`(설정 초만큼 점프), `,`/`.`(프레임 뒤/앞), `F`(풀스크린), `Esc`(풀스크린 해제).
- 점프 간격(초) 사용자 설정값 (기본 5초) — 일단 상수로 두고 추후 설정 UI.
- 볼륨 슬라이더 + 음소거.
- 풀스크린 토글 (더블클릭으로도).
- 창 제목에 현재 파일명 표시.

**검증**
- 모든 단축키가 의도대로 동작, 충돌 없음.
- 풀스크린 진입/해제 시 영상 정상 표시.

**산출물**: 커밋들: `feat: shortcuts`, `feat: volume`, `feat: fullscreen` 등.

---

## Phase 8 — PyInstaller 폴더 빌드 (VLC 런타임 번들 포함)

**목표**: 배포 PC에 VLC가 없어도 단독 실행되는 폴더 빌드 산출.

**작업**
- 앱 아이콘 `assets/icon.ico` 준비.
- `.spec` 파일 작성 또는 명령으로 빌드:
  - `--onedir --windowed --icon=assets/icon.ico --name FramePlayer`
- **VLC 런타임 번들** (주의사항 6):
  - `C:\Program Files\VideoLAN\VLC\libvlc.dll`, `libvlccore.dll` → 출력 폴더에 포함.
  - `C:\Program Files\VideoLAN\VLC\plugins\` 폴더 전체 → 출력 폴더의 `plugins\` 로 포함.
  - `.spec`의 `datas`/`binaries`에 추가하거나 빌드 후 복사 스크립트로 처리.
  - 코드에서 필요 시 `vlc.Instance()`에 plugins 경로를 명시(`--plugin-path` 또는 환경변수 `VLC_PLUGIN_PATH`)하여 번들 플러그인을 찾게 한다.
- 빌드 자동화용 스크립트(`build.ps1` 또는 `build.bat`)로 정리.

**검증**
- **VLC를 설치하지 않은(또는 PATH에서 가린) 환경**에서 `dist\FramePlayer\FramePlayer.exe` 실행 → 영상 재생 성공.
- 모든 기능(seek, 프레임 이동, CLI 인자) 정상.

**산출물**: `dist\FramePlayer\` 폴더 빌드. 커밋: `build: PyInstaller onedir with bundled VLC`.

> 빌드 산출물(`dist/`, `build/`, `*.spec`)은 `.gitignore` 대상. 단, `.spec`을 빌드 재현용으로 버전관리하려면 ignore에서 예외 처리할지 이 단계에서 결정.

---

## Phase 9 — Inno Setup 인스톨러 + 레지스트리 파일 연결

**목표**: 설치 파일(.exe) 제작 + Windows "연결 프로그램" 등록.

**작업**
- Inno Setup 설치(개발 PC).
- `installer/FramePlayer.iss` 스크립트 작성:
  - `dist\FramePlayer\` 전체를 `{autopf}\FramePlayer` 등에 설치.
  - 시작 메뉴 바로가기, (선택) 바탕화면 바로가기.
  - **레지스트리 등록** (Planning.md 4절):
    - `HKCU\Software\Classes\FramePlayer\shell\open\command` → `"{app}\FramePlayer.exe" "%1"`
    - `HKCU\Software\Classes\FramePlayer\DefaultIcon`
    - `HKCU\Software\Classes\.mp4\OpenWithProgids` → `FramePlayer`
    - `HKCU\Software\RegisteredApplications` → `FramePlayer`
    - `Capabilities`(앱 표시 이름, FileAssociations) 등록 → "연결 프로그램" 목록 노출.
  - 제거 시 레지스트리/파일 정리.

**검증**
- 인스톨러로 설치 후:
  - mp4 우클릭 → "연결 프로그램"에 **Frame Player** 표시.
  - "항상 이 앱으로 열기"로 지정 → 더블클릭 시 Frame Player로 자동 재생.
  - 제거 시 항목이 깔끔히 사라짐.

**산출물**: `installer/FramePlayer.iss`, 설치 파일. 커밋: `build: Inno Setup installer with file association`.

> 주의: mp4 기본 연결 변경은 OS가 사용자 선택 UI를 통해 확정하는 부분이 있어, 인스톨러가 강제로 기본값을 빼앗지 않도록 "연결 프로그램 목록 노출 + 사용자가 선택"하는 방식으로 설계한다.

---

## Phase 10 — GitHub Releases 배포 + 앱 내 업데이트 체크

**목표**: 배포 채널 확립 + 자동 업데이트 알림.

**작업**
- 버전 체계 정립: `src`에 `__version__` 상수 (예: `0.1.0`), 태그와 일치.
- GitHub Releases에 설치 파일 업로드 (수동 또는 후에 Actions 자동화).
- 앱 내 업데이트 체크:
  - 시작 시(또는 메뉴) GitHub Releases API(`/repos/G-Turtle/FramePlayer/releases/latest`) 호출.
  - 최신 태그 > 현재 버전이면 알림 다이얼로그 + Releases 링크 안내.
  - 네트워크 실패 시 조용히 무시(앱 동작에 영향 없음).

**검증**
- 현재 버전보다 높은 더미 릴리스로 알림이 뜨는지 확인.
- 오프라인에서도 앱이 정상 실행.

**산출물**: 릴리스 1건 + 업데이트 체크 코드. 커밋: `feat: update check via GitHub releases`.

---

## 단계 간 공통 체크리스트 (매 단계 종료 시)

- [ ] `.venv` 파이썬으로 앱이 정상 실행되는가?
- [ ] 이번 단계 이전 기능이 그대로 동작하는가(회귀 없음)?
- [ ] 변경이 요청 범위로 한정되었는가(불필요한 리팩터 없음)?
- [ ] 커밋 메시지가 단계 내용을 정확히 설명하는가?
- [ ] (해당 시) Planning.md / DevPlan.md 체크박스 갱신.

## 향후 확장 (배포 후, 우선순위 낮음)

- 스킵 간격 사용자 설정 UI
- 재생 속도 조절 (0.25x~4x)
- 자막 트랙 선택 / 오디오 트랙 선택
- 재생 목록 / 최근 파일
- 캡처(스크린샷) 기능
