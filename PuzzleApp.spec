# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['pintu/PuzzleApp.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('common', 'common'),  # 包含common模块
#        ('pintu/configs', 'configs'),  # 包含配置文件目录
    ],
    hiddenimports=[
        'common.isAdmin',  # 明确包含common.isAdmin模块
        'mapping_overlay',  # 包含mapping_overlay模块
        'screen_cropper',  # 包含screen_cropper模块
    ],
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
    a.binaries,
    a.datas,
    [],
    name='PuzzleApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
