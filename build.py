from pathlib import Path
import subprocess
import sys
from PIL import Image,ImageDraw

root=Path(__file__).parent
(root/'assets').mkdir(exist_ok=True)
im=Image.new('RGBA',(256,256),(0,0,0,0));d=ImageDraw.Draw(im)
d.rounded_rectangle((8,8,248,248),radius=54,fill='#173c65')
d.rounded_rectangle((48,48,178,204),radius=15,fill='#f6fafc')
d.rounded_rectangle((88,82,214,189),radius=14,fill='#28b8a3')
d.ellipse((153,99,179,125),fill='#fff1b8');d.polygon([(97,173),(130,130),(155,155),(177,137),(205,173)],fill='white')
im.save(root/'assets/app.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--name','Toolbox','--icon',str(root/'assets/app.ico'),'--add-data',str(root/'assets')+';assets','--collect-all','tkinterdnd2','--collect-all','pymupdf',str(root/'app.py')],check=True,cwd=root)
