# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 명세 (폴더 빌드 / --onedir).

libmpv 런타임(libmpv-2.dll)을 함께 번들하여 대상 PC에 mpv가 설치되지
않아도 실행되게 한다. libmpv-2.dll은 프로젝트 루트의 libs/ 폴더에 둔다
(대용량 바이너리라 git에는 포함하지 않음 — README/requirements 참고).
"""

import os

# libmpv-2.dll은 번들 루트(_internal)에 둔다 → main.py가 _MEIPASS에서 찾는다
binaries = [
    (os.path.join("libs", "libmpv-2.dll"), "."),
]
datas = []

# 아이콘이 있으면 사용 (없으면 기본 아이콘)
icon_path = "assets/icon.ico" if os.path.exists("assets/icon.ico") else None

# 런타임 창/팝업/작업 표시줄 아이콘으로 쓸 icon.ico를 번들 루트(_internal)에 포함한다.
if icon_path:
    datas.append((icon_path, "."))


a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FramePlayer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # --windowed: 콘솔 창 없음
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FramePlayer",
)
