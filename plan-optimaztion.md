# Frame Player 최적화 작업 계획

실측 분석(2026-07-03)을 토대로 한 용량·성능 최적화 작업 목록과 단계별 실행 계획.

## 현재 상태 (기준값)

| 항목 | 실측값 |
|---|---|
| 설치 파일(Setup exe) | 59 MB |
| 신규 설치 폴더 | ~198 MB |
| 업그레이드 누적 설치 폴더(현 PC) | 337 MB (VLC 잔여물 136MB 포함) |
| 대기 메모리 | 76 MB |
| 재생 중 메모리 | 183 MB |
| 재생 중 CPU | ~1~2% (1코어 기준, SW 디코딩) |
| 캐시/데이터 폴더 | 생성 안 함 (설정은 레지스트리 QSettings) |

작업은 **위험도가 낮고 독립적인 것부터** 순서대로 진행한다. 각 단계는 빌드가 필요 없는 것(코드)과 필요한 것(spec/iss)으로 나뉜다.

---

## Phase 1 — 빌드 산출물 감량 (build-time, `FramePlayer.spec`)

세 항목 모두 `Analysis`의 `excludes`/후처리로 처리하며, 서로 독립적이라 한 번에 적용한다.

### 1. PIL(Pillow) 제거 — 약 −11MB
- **원인**: venv에 Pillow가 설치돼 있어 PyInstaller 훅이 자동 수집. 소스 어디에서도 `import PIL` 없음(확인 완료).
- **변경**: `FramePlayer.spec`의 `Analysis(..., excludes=[...])`에 `"PIL"` 추가.
- **검증**: 재빌드 후 `dist/FramePlayer/_internal/PIL` 폴더가 없어야 함. 앱 실행·영상 재생 정상.

### 2. Qt 번역 파일 제외 — 약 −6MB
- **원인**: `PyQt6/Qt6/translations`는 Qt 자체 UI 문자열의 다국어 번역. 이 앱은 자체 한국어 문자열만 사용.
- **변경**: `Analysis` 이후 `a.datas`에서 `Qt6/translations` 경로 항목을 필터링해서 제거하거나, `excludes`/`Tree` 조정. (spec에서 `a.datas = [d for d in a.datas if "translations" not in d[0].lower()]`)
- **검증**: 재빌드 후 `_internal/PyQt6/Qt6/translations`가 비거나 없어야 함. UI 텍스트(한국어) 정상 표시.

### 3. Qt6Pdf.dll 제외 — 약 −4.5MB
- **원인**: PDF 이미지 플러그인 훅이 딸려옴. 앱은 PDF를 다루지 않음.
- **변경**: `a.binaries`에서 `Qt6Pdf.dll`(및 관련 `QtPdf.pyd`가 있으면) 항목을 필터링 제거.
- **검증**: 재빌드 후 해당 DLL 부재. 앱 실행·재생 정상.
- **참고(선택)**: `Qt6Network.dll`(−1.7MB)도 업데이트가 `urllib` 기반이라 불필요할 수 있으나, 이번 목록에는 없으므로 제외하지 않음. 별도 검토 대상으로만 남김.

**Phase 1 예상 결과**: 신규 설치 198MB → 약 175MB, Setup exe 59MB → 약 52MB.

---

## Phase 2 — 설치/임시 파일 정리 (item 4)

### 4-A. 업그레이드 잔여물 제거 (`installer/FramePlayer.iss`)
- **원인**: Inno Setup은 이전 빌드에만 있던 파일을 자동 삭제하지 않음 → VLC 기반 구버전의 `plugins\`(133MB), `libvlccore.dll`(2.7MB)이 업데이트 사용자 PC에 잔존.
- **변경**: `[InstallDelete]` 섹션 추가로 설치 직전 구 파일 정리.
  ```
  [InstallDelete]
  Type: filesandordirs; Name: "{app}\_internal\plugins"
  Type: files; Name: "{app}\_internal\libvlccore.dll"
  ```
  (필요 시 구버전 잔재 목록을 실제 설치 폴더와 대조해 보강)
- **검증**: 잔여물 있는 PC에 새 Setup 설치 → `_internal\plugins` 삭제 확인, 설치 폴더 용량이 신규 설치 수준으로 감소. 앱 정상 실행.
- **주의**: `plugins`가 현행 빌드에서 실제로 쓰이지 않는지 재확인(mpv 전환 후 미사용 확인됨). 현행 빌드가 만드는 파일과 이름 충돌이 없어야 함.

### 4-B. 업데이트 임시 파일 삭제 (`src/main.py` 또는 `MainWindow`)
- **원인**: 업데이트 시 `%TEMP%\FramePlayer-Setup-update.exe`(~59MB)가 실행 후 삭제되지 않고 잔존.
- **변경**: 앱 시작 시 해당 경로 파일이 있으면 삭제. `updater`가 쓰는 경로와 동일한 `os.path.join(tempfile.gettempdir(), "FramePlayer-Setup-update.exe")`를 재사용. 삭제는 실패해도 무시(try/except) — 방금 종료된 설치 프로세스가 잠시 잡고 있을 수 있음.
- **위치**: `main()` 초기(창 생성 전) 또는 `MainWindow.__init__`. 실행 중인 설치 파일과 경합하지 않도록 시작 시점 1회.
- **검증**: 임시 파일을 수동 배치 후 앱 실행 → 시작 직후 삭제 확인. 파일이 없을 때 예외 없이 정상 실행.

---

## Phase 3 — 재생 성능 (런타임, 코드만, 빌드 불필요)

### 5. 하드웨어 디코딩 활성화 (`src/player_core.py`)
- **원인**: `mpv.MPV(...)` 생성 시 `hwdec` 미설정 = 소프트웨어 디코딩. 고해상도(4K 등)에서 CPU 부담.
- **변경**: `set_hwnd`의 MPV 생성 인자에 `hwdec="auto-safe"` 추가. 지원 안 되면 자동 SW 폴백이라 안전.
- **검증**: 고해상도 mp4 재생 중 CPU 사용량이 기존 대비 감소(작업 관리자/PowerShell). 프레임 스텝(frame-step/back-step) 정확도 유지 확인 — hwdec가 프레임 정확도를 해치지 않는지가 핵심 확인 포인트(문제 시 `auto-safe`→`no` 폴백 판단).
- **위험도**: 중. 프레임 단위 정확 탐색이 이 앱의 핵심 기능이므로 회귀 테스트 필수.

### 6. 드래그 스크럽 최적화 (`src/main_window.py`)
- **원인**: 슬라이더 드래그 중 20ms마다 `precision="exact"` seek → 매번 키프레임부터 재디코딩(긴 GOP에서 버벅임).
- **변경**:
  - 드래그 중(`_on_slider_moved`): `precision="keyframes"`로 빠르게 미리보기.
  - 놓는 순간(`_on_slider_released`): `precision="exact"`로 최종 위치 정밀 보정(현행 유지).
  - `PlayerCore.set_time`에 `precision` 인자를 받도록 확장하거나, keyframe용 메서드 분리.
- **검증**: 긴 GOP 영상에서 드래그 시 반응이 부드러움. 놓았을 때 최종 위치가 프레임 정확. 짧은 영상/키프레임 많은 영상에서도 회귀 없음.
- **위험도**: 낮~중.

### 7. 폴링 → 이벤트 방식 (`src/main_window.py`, `src/player_core.py`)
- **원인**: 200ms `QTimer`가 매 틱 `get_length`/`get_time`/`is_playing` 등 libmpv 속성을 반복 조회.
- **변경(단계적)**:
  1. **1차(간단, 저위험)**: 영상 미로드 상태에서는 타이머를 멈추고, 로드 시 재개 → 유휴 wakeup 감소.
  2. **2차(선택, 구조 변경)**: mpv `observe_property`로 `time-pos`/`duration`/`pause`를 구독해 값 변화 시에만 UI 갱신. 슬라이더 드래그 로직(`_user_dragging`)과 충돌하지 않게 콜백에서 가드.
- **검증**: 재생/일시정지/드래그/프레임스텝 시 슬라이더·시간 라벨이 기존과 동일하게 갱신. 유휴 시 CPU wakeup 감소(선택 측정).
- **위험도**: 2차는 중(콜백은 mpv 스레드에서 올 수 있어 Qt 시그널로 메인 스레드 마샬링 필요). 우선 1차만 적용하고 2차는 여력에 따라 결정.

---

## 실행 순서 요약

| 순서 | 항목 | 파일 | 빌드 필요 | 위험도 |
|---|---|---|---|---|
| 1 | PIL 제외 | FramePlayer.spec | O | 낮음 |
| 2 | Qt translations 제외 | FramePlayer.spec | O | 낮음 |
| 3 | Qt6Pdf.dll 제외 | FramePlayer.spec | O | 낮음 |
| 4-A | 업그레이드 잔여물 정리 | installer/FramePlayer.iss | O(재빌드+재설치) | 낮음 |
| 4-B | 임시 파일 삭제 | src/main.py | X | 낮음 |
| 5 | 하드웨어 디코딩 | src/player_core.py | X | 중 |
| 6 | 드래그 스크럽 | src/main_window.py, player_core.py | X | 낮~중 |
| 7 | 폴링→이벤트 | src/main_window.py, player_core.py | X | 1차 낮음 / 2차 중 |

- **1~3**은 한 번의 spec 수정 + 1회 재빌드로 함께 검증.
- **4-B, 5, 6, 7(1차)**는 코드만 바꾸면 되므로 개발 환경(`python src/main.py`)에서 즉시 검증 가능.
- **4-A**는 재빌드 후 실제 설치로만 검증 가능하므로 Phase 1 재빌드에 묶어서 진행.
- 각 항목은 독립적이므로 문제가 생기면 해당 항목만 되돌릴 수 있게 커밋을 분리한다.

## 예상 최종 효과

- 신규 설치: 198MB → **약 175MB**
- 업그레이드 설치 폴더: 337MB → **약 175MB**(잔여물 제거)
- 재생 CPU: 고해상도에서 hwdec로 유의미 감소
- 스크럽 반응성·유휴 효율 개선
- 기능 변화 없음
