"""Install/uninstall round trip, refuses to overwrite an existing installation."""
import sys
import os
import time
import subprocess
import ctypes
import winreg
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from toolbox.desktop import InstanceBroker
from toolbox.shell_menu import KEY,read_values,legacy_keys,notify_shell

root=Path(__file__).resolve().parents[1]
installer=root/'release/v0.3.0/ShiguangToolbox-Setup-0.3.0-x64.exe'
target=root/'verification/installed-0.3.0'
uninstall_key=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{C1B10776-C1D5-4B13-BE8E-75D1D3ECA906}_is1'
assert read_values(winreg.HKEY_CURRENT_USER,uninstall_key) is None,'Existing installation: do not modify'
def snapshot(key):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as h:
            count,values,_=winreg.QueryInfoKey(h)
            return ([winreg.EnumValue(h,i) for i in range(values)],{winreg.EnumKey(h,i):snapshot(key+'\\'+winreg.EnumKey(h,i)) for i in range(count)})
    except FileNotFoundError:return None
def restore(key,state):
    if state is None:return
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key) as h:
        for name,value,kind in state[0]:winreg.SetValueEx(h,name,0,kind,value)
    for name,child in state[1].items():restore(key+'\\'+name,child)
prior={key:snapshot(key) for key in [KEY,*legacy_keys()]}
run_key=r'Software\Microsoft\Windows\CurrentVersion\Run'
old_run=(read_values(winreg.HKEY_CURRENT_USER,run_key) or {}).get('ShiguangToolbox')
sendto=Path(os.environ['APPDATA'])/'Microsoft/Windows/SendTo/拾光工具箱.lnk'
old_sendto=sendto.read_bytes() if sendto.exists() else None
guard=InstanceBroker()
assert guard.primary,'Application already running: do not modify'
guard.close()
target.parent.mkdir(exist_ok=True)
retained=target.parent/'user-output-retained.txt';retained.write_text('preserve user outputs')
import atexit
def restore_user_settings():
    for key,state in prior.items():restore(key,state)
    if old_run is not None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,run_key) as h:winreg.SetValueEx(h,'ShiguangToolbox',0,winreg.REG_SZ,old_run)
    if old_sendto is not None:sendto.write_bytes(old_sendto)
    notify_shell()
    print('Existing user menu/autorun/Send To settings restored')
atexit.register(restore_user_settings)
installed=False;process=None
try:
    subprocess.run([str(installer),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LANG=chinesesimp',f'/DIR={target}','/TASKS=contextmenu,autostart',f'/LOG={root / "verification/install.log"}'],timeout=90,check=True)
    installed=True
    values=read_values(winreg.HKEY_CURRENT_USER,uninstall_key)
    assert values and values['DisplayName']=='拾光工具箱',values
    assert (target/'ShiguangToolbox.exe').is_file()
    assert (target/'ShiguangToolbox-source.zip').is_file()
    assert read_values(winreg.HKEY_CURRENT_USER,KEY+'\\command')['']==f'"{target / "ShiguangToolbox.exe"}" "%1"'
    run=read_values(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run')
    assert run['ShiguangToolbox'].endswith('--background')
    sendto=Path(os.environ['APPDATA'])/'Microsoft/Windows/SendTo/拾光工具箱.lnk'
    assert sendto.exists()
    exe=target/'ShiguangToolbox.exe'
    process=subprocess.Popen([str(exe),'--background'])
    user=ctypes.WinDLL('user32');user.FindWindowW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p];user.FindWindowW.restype=ctypes.c_void_p
    user.IsWindowVisible.argtypes=[ctypes.c_void_p];user.IsWindowVisible.restype=ctypes.c_bool
    user.PostMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
    title='拾光工具箱 Studio 0.3.0 · 图片 & PDF'
    def wait(predicate,timeout=25):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if predicate():return
            time.sleep(.1)
        raise AssertionError('Timed out waiting for installed app')
    wait(lambda:user.FindWindowW(None,title))
    hwnd=user.FindWindowW(None,title)
    wait(lambda:not user.IsWindowVisible(hwnd))
    subprocess.run([str(exe)],timeout=30,check=True)
    wait(lambda:user.IsWindowVisible(hwnd))
    user.PostMessageW(hwnd,0x10,0,0)
    wait(lambda:not user.IsWindowVisible(hwnd))
    assert process.poll() is None,'Closing window terminated tray app'
    subprocess.run([str(exe),'--quit'],timeout=30,check=True)
    process.wait(timeout=20);assert process.returncode==0
    print('Installed EXE: background tray, second launch wake, close-to-tray, clean quit PASS')
finally:
    if process and process.poll() is None:
        subprocess.run([str(target/'ShiguangToolbox.exe'),'--quit'],timeout=30)
        process.wait(timeout=20)
    if installed:
        subprocess.run([str(target/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',f'/LOG={root / "verification/uninstall.log"}'],timeout=90,check=True)
assert read_values(winreg.HKEY_CURRENT_USER,uninstall_key) is None
assert read_values(winreg.HKEY_CURRENT_USER,KEY) is None
assert not (target/'ShiguangToolbox.exe').exists()
assert not sendto.exists()
run=read_values(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') or {}
assert 'ShiguangToolbox' not in run
assert retained.read_text()=='preserve user outputs'
print('Installer: app list, files, source, shell menu, Send To, autorun and uninstall cleanup PASS')

