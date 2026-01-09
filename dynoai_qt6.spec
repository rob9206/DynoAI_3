# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for DynoAI Qt6 Desktop Application
"""

import sys
from pathlib import Path

block_cipher = None

# Collect all data files
added_files = [
    ('config', 'config'),
    ('docs', 'docs'),
]

# Analysis
a = Analysis(
    ['dynoai_qt6.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        # PyQt6
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        
        # Core DynoAI
        'dynoai',
        'dynoai.core',
        'dynoai.core.ve_math',
        'dynoai.core.io_contracts',
        'dynoai.gui',
        'dynoai.gui.analysis_tab',
        'dynoai.gui.jetdrive_tab',
        'dynoai.gui.results_tab',
        'dynoai.gui.settings_tab',
        
        # API services (backend)
        'api',
        'api.services',
        'api.services.autotune_workflow',
        'api.services.dyno_simulator',
        'api.services.jetdrive_client',
        
        # Data processing
        'pandas',
        'numpy',
        'scipy',
        'scipy.interpolate',
        'scipy.signal',
        
        # Utilities
        'json',
        'csv',
        'uuid',
        'hashlib',
        'threading',
        'queue',
        'logging',
        'datetime',
        'pathlib',
        'shutil',
        'subprocess',
        
        # Additional dependencies
        'dotenv',
        'python_dotenv',
        'yaml',
        'jsonschema',
        'requests',
        'certifi',
        'urllib3',
        'charset_normalizer',
        'idna',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude web-related packages
        'flask',
        'flask_cors',
        'werkzeug',
        'jinja2',
        'flask_limiter',
        'flasgger',
        'prometheus_client',
        'prometheus_flask_exporter',
        
        # Exclude development/testing packages
        'pytest',
        'pytest_cov',
        'black',
        'ruff',
        'mypy',
        'pre_commit',
        
        # Exclude other GUI frameworks
        'tkinter',
        
        # Exclude large unused packages
        'matplotlib',
        'PIL',
        'pillow',
        'pytesseract',
        'reportlab',
        'qrcode',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Create PYZ archive
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Create the executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DynoAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # TODO: Add icon: icon='assets/dynoai.ico'
    version=None,
)
