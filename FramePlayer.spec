# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 명세 (폴더 빌드 / --onedir).

VLC 런타임(libvlc.dll, libvlccore.dll, plugins/)을 함께 번들하여
대상 PC에 VLC가 설치되지 않아도 실행되게 한다.
빌드 PC에는 VLC가 설치되어 있어야 한다(아래 VLC_DIR 경로 참조).
"""

import os

# 빌드 PC의 VLC 설치 경로 (64비트)
VLC_DIR = r"C:\Program Files\VideoLAN\VLC"

# libvlc 본체 DLL은 번들 루트(_internal)에 둔다 → main.py가 PYTHON_VLC_LIB_PATH로 참조
binaries = [
    (os.path.join(VLC_DIR, "libvlc.dll"), "."),
    (os.path.join(VLC_DIR, "libvlccore.dll"), "."),
]
# 플러그인 폴더 전체 → _internal/plugins (main.py가 PYTHON_VLC_MODULE_PATH로 참조)
datas = [
    (os.path.join(VLC_DIR, "plugins"), "plugins"),
]

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
