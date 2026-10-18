# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import psutil
from pathlib import Path
import os

# Replacing a live distribution can remove assets before Windows blocks DLLs.
target = (Path(DISTPATH) / 'EntreTerras' / 'EntreTerras.exe').resolve()
if any((p.info['name'] or '').casefold() == 'entreterras.exe'
       and (not p.info['exe'] or Path(p.info['exe']).resolve() == target)
       for p in psutil.process_iter(['name', 'exe'])):
    raise SystemExit('Encerre o Entre Terras pela bandeja antes de gerar o executavel.')

datas = [('entre_terras/assets', 'entre_terras/assets'), ('LICENSE', '.')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('atomics')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pystray')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['elden_ring_tracker.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='EntreTerras',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    uac_admin=True,
    version=os.environ.get('ENTRE_TERRAS_VERSION_FILE'),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['entre_terras/assets/entre-terras.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EntreTerras',
)
