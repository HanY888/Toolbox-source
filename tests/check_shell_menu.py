"""Temporary, isolated registry integration test; never alters the installed verb."""
import sys
import uuid
import json
import os
import subprocess
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import winreg
from PIL import Image
import pymupdf
from toolbox import shell_menu as menu

menu.VERB='ShiguangToolbox_Test_'+uuid.uuid4().hex
menu.RELATIVE=rf'*\shell\{menu.VERB}'
menu.KEY=rf'Software\Classes\{menu.RELATIVE}'
menu.LABEL='Shiguang test '+menu.VERB
exe=Path(__file__).resolve().parents[1]/'dist/ShiguangToolbox.exe'

try:
    assert not menu.diagnose(exe)[0]
    # Simulate an old-style registration and hidden flags, then repair.
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,menu.legacy_keys()[0]) as key:
        winreg.SetValueEx(key,'',0,winreg.REG_SZ,'old test registration')
    assert '旧版' in menu.diagnose(exe)[1]
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,menu.KEY) as key:
        winreg.SetValueEx(key,'LegacyDisable',0,winreg.REG_SZ,'')
    menu.install(exe);menu.install(exe)
    assert menu.diagnose(exe)[0]
    assert menu.read_values(winreg.HKEY_CURRENT_USER,menu.legacy_keys()[0]) is None
    assert 'LegacyDisable' not in menu.read_values(winreg.HKEY_CURRENT_USER,menu.KEY)
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);Image.new('RGB',(20,20),'red').save(root/'test.png')
        with pymupdf.open() as doc:doc.new_page();doc.save(root/'test.pdf')
        (root/'test.txt').write_text('not an image');(root/'subfolder').mkdir()
        script='''$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace($env:MENU_TEST_FOLDER)
$result = @{}
foreach ($name in @('test.png','test.pdf','test.txt','subfolder')) {
    $item = $folder.ParseName($name)
    $result[$name] = @($item.Verbs() | ForEach-Object { $_.Name })
}
$result | ConvertTo-Json -Compress
'''
        env=dict(os.environ,MENU_TEST_FOLDER=folder)
        output=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,capture_output=True,timeout=30,check=True)
        data=json.loads(output.stdout.decode('utf-8',errors='replace'))
        for name in ['test.png','test.pdf']:
            assert menu.LABEL in data[name],f'{name}: test verb missing: {data[name]}'
        for name in ['test.txt','subfolder']:
            assert menu.LABEL not in data[name],f'{name}: unexpected verb'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,menu.KEY+'\\command') as key:
        winreg.SetValueEx(key,'',0,winreg.REG_SZ,'"C:\\missing\\Toolbox.exe" "%1"')
    assert not menu.diagnose(exe)[0]
    menu.install(exe);assert menu.diagnose(exe)[0]
    menu.uninstall();assert not menu.diagnose(exe)[0]
    print('Shell integration passed: real PNG/PDF verbs visible, TXT/folder excluded; repair, path detection, migration, removal verified.')
finally:
    menu.uninstall()
