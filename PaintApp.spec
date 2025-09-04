# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['paint/PaintApp.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('common', 'common'),
        ('paint/paint_configs', 'paint_configs'),
        ('paint/icon','icon'),
        ('paint/icon/icon_multi.ico', '.'),
    ],
    hiddenimports=[
        'common.isAdmin',
        'paint_ui',
        'paint_business', 
        'paint_worker',
        'image_detector',
        'image_processor',
        'screen_cropper',
        'click_utils',
        'config_manager',
        'pixel_overlay',
        'PyQt5.QtCore',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'cv2',
        'numpy',
        'PIL',
        'keyboard', 
        'pyautogui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'paddleocr', 'easyocr',
        'matplotlib', 'seaborn', 'pandas', 'tensorflow', 'keras',
        'sklearn.neighbors', 'sklearn.svm', 'sklearn.ensemble', 'sklearn.tree',
        'sklearn.metrics', 'sklearn.preprocessing', 'sklearn.decomposition',
        'sklearn.linear_model', 'sklearn.model_selection', 'sklearn.feature_extraction',
        'sklearn.datasets', 'sklearn.externals',
        'sklearn._isotonic', 'sklearn._lib', 'sklearn._loss', 'sklearn._openmp_helpers',
        'sklearn._random', 'sklearn._testing', 'sklearn.calibration',
        'sklearn.compose', 'sklearn.covariance', 'sklearn.cross_decomposition',
        'sklearn.discriminant_analysis', 'sklearn.dummy', 'sklearn.feature_selection',
        'sklearn.gaussian_process', 'sklearn.impute', 'sklearn.inspection',
        'sklearn.isotonic', 'sklearn.kernel_approximation', 'sklearn.kernel_ridge',
        'sklearn.manifold', 'sklearn.mixture', 'sklearn.multiclass', 'sklearn.multioutput',
        'sklearn.naive_bayes', 'sklearn.neural_network', 'sklearn.pipeline',
        'sklearn.random_projection', 'sklearn.semi_supervised'
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PaintApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 改为True以便查看错误信息
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'paint\icon\icon_multi.ico',  # 图标文件路径
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PaintApp',
)
