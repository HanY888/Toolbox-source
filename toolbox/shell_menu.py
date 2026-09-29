"""Per-user classic Explorer menu registration and diagnosis."""
import ctypes
from pathlib import Path
import winreg

EXTENSIONS=('.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff','.pdf')
VERB='ShiguangToolbox'
RELATIVE=rf'*\shell\{VERB}'
KEY=rf'Software\Classes\{RELATIVE}'
LABEL='使用 Toolbox 打开'
APPLIES_TO=' OR '.join(f'System.FileExtension:="{ext}"' for ext in EXTENSIONS)

def command_for(exe):
    exe=Path(exe).resolve()
    if not exe.is_file() or exe.suffix.lower()!='.exe':
        raise ValueError('未找到可运行的 EXE，请先解压软件并放在固定目录。')
    return f'"{exe}" "%1"'

def notify_shell():
    notify=ctypes.WinDLL('shell32',use_last_error=True).SHChangeNotify
    notify.argtypes=[ctypes.c_long,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p]
    notify.restype=None
    notify(0x08000000,0,None,None)  # SHCNE_ASSOCCHANGED / SHCNF_IDLIST

def read_values(hive,key):
    try:
        with winreg.OpenKey(hive,key) as handle:
            values={}
            for i in range(winreg.QueryInfoKey(handle)[1]):
                name,value,_=winreg.EnumValue(handle,i);values[name]=value
            return values
    except FileNotFoundError:return None

def delete_owned_key(key):
    # Only the known command child and our own verb; never remove shell/association parents.
    for suffix in ('\\command',''):
        try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key+suffix)
        except FileNotFoundError:pass

def legacy_keys():
    return [rf'Software\Classes\SystemFileAssociations\{ext}\shell\{VERB}' for ext in EXTENSIONS]

def diagnose(exe):
    expected=command_for(exe)
    values=read_values(winreg.HKEY_CURRENT_USER,KEY)
    command=read_values(winreg.HKEY_CURRENT_USER,KEY+'\\command')
    merged=read_values(winreg.HKEY_CLASSES_ROOT,RELATIVE+'\\command')
    legacy=any(read_values(winreg.HKEY_CURRENT_USER,key) is not None for key in legacy_keys())
    if values is None:
        return False,('检测到旧版注册，点击“添加 / 修复入口”升级。' if legacy else '当前 Windows 用户尚未注册右键入口。')
    if not command or command.get('')!=expected:
        return False,'入口指向另一份程序，或 EXE 已移动。点击“添加 / 修复入口”更新路径。'
    if not merged or merged.get('')!=expected:
        return False,'已写入当前用户设置，但系统关联视图未匹配。请使用同一 Windows 账户重新修复。'
    if values.get('AppliesTo')!=APPLIES_TO or values.get('MultiSelectModel')!='Player':
        return False,'注册参数不完整，请点击“添加 / 修复入口”。'
    return True,'注册检查通过，路径有效。请右键图片或 PDF，并展开“显示更多选项”。'

def install(exe):
    command=command_for(exe)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,KEY) as handle:
        for name,value in {'':LABEL,'MUIVerb':LABEL,'Icon':f'"{Path(exe).resolve()}",0',
                           'MultiSelectModel':'Player','AppliesTo':APPLIES_TO,'Position':'Top'}.items():
            winreg.SetValueEx(handle,name,0,winreg.REG_SZ,value)
        for name in ('Extended','LegacyDisable','ProgrammaticAccessOnly'):
            try:winreg.DeleteValue(handle,name)
            except FileNotFoundError:pass
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,KEY+'\\command') as handle:
        winreg.SetValueEx(handle,'',0,winreg.REG_SZ,command)
    for old in legacy_keys():delete_owned_key(old)
    notify_shell()
    success,detail=diagnose(exe)
    if not success:raise OSError(detail)
    return detail

def uninstall():
    delete_owned_key(KEY)
    for old in legacy_keys():delete_owned_key(old)
    notify_shell()
