# -*- mode: python ; coding: utf-8 -*-
"""
DynoAI PyInstaller Spec File
Builds a standalone Windows executable
"""

import os
from pathlib import Path

# Get the project root
PROJECT_ROOT = Path(SPECPATH)

# Analysis configuration
a = Analysis(
    ['dynoai_standalone.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # Include the built React frontend
        ('frontend/dist', 'frontend/dist'),
        # Include API modules
        ('api', 'api'),
        # Include dynoai core modules
        ('dynoai', 'dynoai'),
        # Include configuration files
        ('config', 'config'),
        # Include tools (tuning wizards, etc.)
        ('tools/tuning_wizards.py', 'tools'),
        ('tools/tables', 'tools/tables'),
        # Include the main toolkit script
        ('tools/ai_tuner_toolkit_dyno_v1_2.py', 'tools'),
    ],
    hiddenimports=[
        # Flask and extensions
        'flask',
        'flask_cors',
        'flask_limiter',
        'flasgger',
        'waitress',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.middleware',
        'werkzeug.middleware.proxy_fix',
        'jinja2',
        'jinja2.ext',
        'markupsafe',
        'itsdangerous',
        'click',
        'blinker',
        
        # Data processing
        'numpy',
        'pandas',
        'pandas.io.formats.style',
        
        # Database
        'sqlalchemy',
        'sqlalchemy.sql.default_comparator',
        'alembic',
        
        # API modules
        'api',
        'api.app',
        'api.auth',
        'api.config',
        'api.docs',
        'api.errors',
        'api.health',
        'api.metrics',
        'api.middleware',
        'api.rate_limit',
        'api.reliability_agent',
        'api.reliability_helpers',
        'api.reliability_integration',
        
        # API routes
        'api.routes',
        'api.routes.jetstream',
        'api.routes.jetdrive',
        'api.routes.timeline',
        'api.routes.wizards',
        'api.routes.powercore',
        'api.routes.transient',
        'api.routes.virtual_tune',
        
        # API services
        'api.services',
        'api.services.database',
        'api.services.run_manager',
        'api.services.session_logger',
        'api.services.jetdrive_client',
        'api.services.autotune_workflow',
        
        # Jetstream
        'api.jetstream',
        'api.jetstream.models',
        'api.jetstream.poller',
        'api.jetstream.stub_data',
        
        # DynoAI core
        'dynoai',
        'dynoai.core',
        'dynoai.core.ve_operations',
        'dynoai.constants',
        
        # Scientific computing
        'scipy',
        'scipy.ndimage',
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
        
        # Prometheus metrics (optional)
        'prometheus_client',
        'prometheus_flask_exporter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude development/testing packages
        'pytest',
        'pytest_cov',
        'black',
        'ruff',
        'mypy',
        'pre_commit',
        # Exclude Qt (not needed for web app)
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        # Exclude other large packages not needed
        'tkinter',
        'PIL',
        'pillow',
        'pytesseract',
        'reportlab',
        'qrcode',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Create PYZ archive
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

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
    console=True,  # Show console for debugging; set to False for release
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here: icon='assets/dynoai.ico'
    version=None,  # Add version info file here if desired
)
