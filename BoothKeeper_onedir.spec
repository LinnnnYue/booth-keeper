# -*- mode: python ; coding: utf-8 -*-
# BoothKeeper onedir spec (for zip portable distribution)
a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    # R8 修复：assets/ 包含应用图标源 + 微信收款码 + 主题 SVG 资源，必须捆绑进 exe
    datas=[('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BoothKeeper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'D:\Lin_Agent\WB-WorkSpace\BoothKeeper\assets\art\scene-reimu-egg-icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BoothKeeper',
)