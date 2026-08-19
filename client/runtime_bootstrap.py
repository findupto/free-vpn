from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

def runtime_dir() -> Path:
    return Path(sys._MEIPASS) / 'runtime' if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent / 'runtime'

def install_bundled_drivers() -> bool:
    if os.name != 'nt': return True
    root = runtime_dir()
    infs = list(root.rglob('*.inf')) if root.exists() else []
    if not infs: return False
    ok = False
    for inf in infs:
        try:
            cp = subprocess.run(['pnputil.exe','/add-driver',str(inf),'/install'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            ok = ok or cp.returncode == 0
        except Exception:
            continue
    return ok
