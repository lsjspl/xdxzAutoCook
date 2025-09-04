# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['cook/cookGui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('common', 'common'),  # 包含common模块
        ('cook/foods', 'foods'),  # 包含食物图片目录
        ('btns', 'btns'),  # 包含按钮图片
    ],
    hiddenimports=[
        'common.isAdmin',  # 明确包含common.isAdmin模块
        'cook',  # 包含cook模块
        'cook_mumu',  # 包含cook_mumu模块
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
        'cv2',
        'numpy',
        'PIL',
        'keyboard',
        'pyautogui',
        'win32gui',
        'win32con',
        'win32com.client',
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
    [],
    exclude_binaries=True,
    name='CookApp',
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
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CookApp',
)
