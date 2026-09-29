"""Round-trip 0.3 -> 0.4 upgrade with existing user shell settings restored."""
import sys,os,subprocess,winreg,atexit
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from toolbox.shell_menu import KEY,legacy_keys,read_values,notify_shell
from toolbox.desktop import InstanceBroker

root=Path(__file__).resolve().parents[1];target=root/'verification/upgrade-test'
uninstall=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{C1B10776-C1D5-4B13-BE8E-75D1D3ECA906}_is1'
assert read_values(winreg.HKEY_CURRENT_USER,uninstall) is None,'Existing installation: test refused'
# The test never starts its installation as a normal instance. The new uninstaller
# sends a path-targeted quit request, which cannot close another portable copy.
def snapshot(key):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as h:
            children,values,_=winreg.QueryInfoKey(h)
            return ([winreg.EnumValue(h,i) for i in range(values)],{winreg.EnumKey(h,i):snapshot(key+'\\'+winreg.EnumKey(h,i)) for i in range(children)})
    except FileNotFoundError:return None
def restore(key,state):
    if state is None:return
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key) as h:
        for name,value,kind in state[0]:winreg.SetValueEx(h,name,0,kind,value)
    for name,child in state[1].items():restore(key+'\\'+name,child)
previous={key:snapshot(key) for key in [KEY,*legacy_keys()]}
run_key=r'Software\Microsoft\Windows\CurrentVersion\Run'
startup=read_values(winreg.HKEY_CURRENT_USER,run_key) or {}
folders=read_values(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders')
shortcuts=[]
for name in ('拾光工具箱','Toolbox'):
    shortcuts.extend([Path(folders['Desktop'])/(name+'.lnk'),Path(folders['SendTo'])/(name+'.lnk'),Path(folders['Programs'])/name/(name+'.lnk'),Path(folders['Programs'])/name/('卸载'+name+'.lnk')])
copies={p:p.read_bytes() if p.exists() else None for p in shortcuts}
def restore_user():
    for key,state in previous.items():restore(key,state)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,run_key) as h:
        for name in ('ShiguangToolbox','Toolbox'):
            if name in startup:winreg.SetValueEx(h,name,0,winreg.REG_SZ,startup[name])
            else:
                try:winreg.DeleteValue(h,name)
                except FileNotFoundError:pass
    for path,data in copies.items():
        if data is not None:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    notify_shell()
atexit.register(restore_user)
installed=False
try:
    old=root/'release/v0.3.0/ShiguangToolbox-Setup-0.3.0-x64.exe'
    new=root/'release/v0.5.0/Toolbox-Setup-0.5.0-x64.exe'
    args=['/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LANG=chinesesimp','/TASKS=desktopicon,contextmenu,autostart']
    subprocess.run([str(old),*args,f'/DIR={target}'],check=True,timeout=90);installed=True
    assert read_values(winreg.HKEY_CURRENT_USER,uninstall)['DisplayName']=='拾光工具箱'
    intermediate=root/'release/v0.4.0/Toolbox-Setup-0.4.0-x64.exe'
    if intermediate.exists():subprocess.run([str(intermediate),*args],check=True,timeout=90)
    subprocess.run([str(new),*args],check=True,timeout=90)
    registration=read_values(winreg.HKEY_CURRENT_USER,uninstall)
    assert registration['DisplayName']=='Toolbox' and registration['DisplayVersion']=='0.5.0'
    assert Path(registration['InstallLocation']).resolve()==target.resolve()
    assert (target/'Toolbox.exe').is_file() and not (target/'ShiguangToolbox.exe').exists()
    assert read_values(winreg.HKEY_CURRENT_USER,KEY)['MUIVerb']=='使用 Toolbox 打开'
    startup_now=read_values(winreg.HKEY_CURRENT_USER,run_key)
    assert 'ShiguangToolbox' not in startup_now and str(target/'Toolbox.exe') in startup_now['Toolbox']
    for name in ('Desktop','SendTo'):
        assert (Path(folders[name])/'Toolbox.lnk').exists()
        assert not (Path(folders[name])/'拾光工具箱.lnk').exists()
    subprocess.run([str(target/'Toolbox.exe'),'--smoke-test'],timeout=40,check=True)
    print('Upgrade PASS: same installation path/AppId, Toolbox name/version, shortcuts, autorun, shell menu, EXE startup')
finally:
    if installed:subprocess.run([str(target/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=90)
assert read_values(winreg.HKEY_CURRENT_USER,uninstall) is None
assert read_values(winreg.HKEY_CURRENT_USER,KEY) is None
assert not (target/'Toolbox.exe').exists()
print('Upgraded installation uninstalled; prior user settings restored on exit')
