# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['fish/FishApp.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('common', 'common'),  # 包含common模块
        ('fish/configs', 'configs'),  # 包含配置文件目录
        ('fish/logs', 'logs'),  # 包含日志目录
        ('btns', 'btns'),  # 包含按钮图片
    ],
    hiddenimports=[
        'common.isAdmin',  # 明确包含common.isAdmin模块
        'fishing_ui',  # 包含fishing_ui模块
        'fishing_business',  # 包含fishing_business模块
        'fishing_worker',  # 包含fishing_worker模块
        'image_detector',  # 包含image_detector模块
        'screen_cropper',  # 包含screen_cropper模块
        'config_manager',  # 包含config_manager模块
        'PyQt5.QtCore',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'cv2',
        'numpy',
        'PIL',
        'keyboard',
        'pyautogui',
        'paddleocr',
        'easyocr',
        'torch',
        'torchvision',
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
    name='FishApp',
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
    name='FishApp',
)
