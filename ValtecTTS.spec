# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = [('src', 'src'), ('valtec_tts', 'valtec_tts')]
binaries = []
hiddenimports = ['src', 'src.models.synthesizer', 'src.text.symbols', 'src.vietnamese.text_processor', 'src.vietnamese.phonemizer', 'src.text', 'src.nn.commons', 'src.nn.mel_processing', 'src.utils.helpers', 'valtec_tts', 'infer']

# Collect customtkinter data
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Collect underthesea data files (corpus, models)
underthesea_datas = collect_data_files('underthesea', include_py_files=False)
datas += underthesea_datas
hiddenimports += ['underthesea', 'underthesea_core', 'viphoneme', 'vinorm']


a = Analysis(
    ['gui_app_modern.py'],
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
    a.binaries,
    a.datas,
    [],
    name='ValtecTTS',
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
