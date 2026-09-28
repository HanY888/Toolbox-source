"""Windows lifecycle: per-user single instance, local mailbox, and autostart."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid
import winreg

VERSION='0.3.0'
RUN_KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME='ShiguangToolbox'

class InstanceBroker:
    def __init__(self,directory=None,name=None):
        self.directory=Path(directory or Path(os.environ['LOCALAPPDATA'])/'ShiguangToolbox'/'inbox')
        self.directory.mkdir(parents=True,exist_ok=True)
        identity=hashlib.sha256(str(self.directory.resolve()).lower().encode()).hexdigest()[:24]
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
        self.kernel.CreateMutexW.restype=wintypes.HANDLE
        self.kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        self.handle=self.kernel.CreateMutexW(None,False,name or 'Local\\ShiguangToolbox_'+identity)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        self.primary=ctypes.get_last_error()!=183
    def send(self,paths=(),action='show'):
        if action not in ('show','quit'):raise ValueError('Invalid action')
        payload={'action':action,'paths':[str(Path(p).resolve()) for p in paths][:1000],'time':time.time()}
        target=self.directory/(uuid.uuid4().hex+'.json');temporary=target.with_suffix('.tmp')
        temporary.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8');temporary.replace(target)
    def drain(self):
        messages=[]
        for path in sorted(self.directory.glob('*.json'),key=lambda p:p.name):
            if not re.fullmatch(r'[0-9a-f]{32}\.json',path.name):continue
            try:
                if path.stat().st_size>2_000_000:continue
                data=json.loads(path.read_text(encoding='utf-8'))
                if (data.get('action') in ('show','quit') and isinstance(data.get('paths'),list)
                    and all(isinstance(p,str) for p in data['paths']) and time.time()-float(data.get('time',0))<300):
                    messages.append(data)
            except (OSError,ValueError,TypeError,AttributeError):pass
            finally:
                try:path.unlink()
                except FileNotFoundError:pass
        return messages
    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None

def autostart_enabled(exe):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:
            return winreg.QueryValueEx(key,RUN_NAME)[0]==f'"{Path(exe).resolve()}" --background'
    except FileNotFoundError:return False

def set_autostart(exe,enabled):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:
        if enabled:
            if not Path(exe).is_file():raise ValueError('程序路径无效')
            winreg.SetValueEx(key,RUN_NAME,0,winreg.REG_SZ,f'"{Path(exe).resolve()}" --background')
        else:
            try:winreg.DeleteValue(key,RUN_NAME)
            except FileNotFoundError:pass
