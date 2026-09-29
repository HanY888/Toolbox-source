from pathlib import Path
import shutil
import sys
from toolbox.desktop import VERSION
import zipfile
import hashlib
import importlib.metadata as metadata

root=Path(__file__).parent
release=root/'release'/f'v{VERSION}';release.mkdir(parents=True,exist_ok=True)

def checksums():
    files=sorted(p for p in release.iterdir() if p.suffix in ('.exe','.zip'))
    (release/'SHA256.txt').write_text('\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}' for p in files)+'\n',encoding='utf-8')

if '--checksums-only' in sys.argv:
    checksums();sys.exit(0)
licenses=release/'licenses';licenses.mkdir(exist_ok=True)
for name in ['pillow','pymupdf','tkinterdnd2','pyinstaller','pystray','six']:
    dist=metadata.distribution(name)
    for item in dist.files or []:
        if any(t in item.name.lower() for t in ['license','copying','notice']):
            p=Path(dist.locate_file(item))
            if p.is_file():
                target=licenses/name/Path(str(item));target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
for candidate in (Path(__import__('sys').base_prefix)/'tcl').rglob('license.terms'):
    target=licenses/'tcl-tk'/candidate.parent.name/'license.terms';target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(candidate,target)
python_license=Path(__import__('sys').base_prefix)/'LICENSE.txt'
if python_license.exists():shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
shutil.copy2(root/'dist/Toolbox.exe',release/'Toolbox.exe')
shutil.copy2(root/'README.md',release/'使用说明.md')
shutil.copy2(root/'LICENSE',release/'LICENSE')
source=release/'github-source';source.mkdir(exist_ok=True)
files=[root/name for name in ['app.py','build.py','package_release.py','requirements.txt','README.md','LICENSE','.gitignore']]
for folder in ['toolbox','tests','assets','installer','docs','.github']:
    files.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for p in files:
    target=source/p.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
shutil.copytree(licenses,source/'licenses',dirs_exist_ok=True)
for p in source.rglob('*'):
    if p.is_file() and p.suffix in ('.py','.md','.yml','.iss','.isl','.txt'):
        content=p.read_text(encoding='utf-8',errors='ignore')
        if str(root) in content:
            raise RuntimeError(f'Local path found: {p.relative_to(source)}')
with zipfile.ZipFile(release/'Toolbox-source.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(source.rglob('*')):
        if p.is_file():z.write(p,p.relative_to(source))
with zipfile.ZipFile(release/f'Toolbox-Portable-{VERSION}-x64.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in ['Toolbox.exe','使用说明.md','LICENSE','Toolbox-source.zip']:z.write(release/name,name)
    for p in licenses.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(release))
checksums();print(f'Release prepared: {release}')
