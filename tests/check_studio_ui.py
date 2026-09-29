"""Desktop integration checks; run directly on Windows, outside unittest discovery."""
import sys
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw
from app import App

root=Path(__file__).resolve().parents[1]/'verification';root.mkdir(exist_ok=True)
files=[]
for i,(color,title) in enumerate([('#257477','SHORE'),('#d4a46b','SAND'),('#65867a','FOREST')]):
    im=Image.new('RGB',(900,650),color);d=ImageDraw.Draw(im)
    d.ellipse((450,-170,1080,460),fill='#eadbc1')
    d.polygon([(0,490),(260,200),(560,650),(0,650)],fill='#25474f')
    d.polygon([(250,650),(620,270),(900,650)],fill='#52746c')
    d.text((40,40),title,fill='white',font_size=50)
    p=root/f'studio-{i+1}.png';im.save(p);files.append(p)

def wait(app,predicate,timeout=20):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        app.update()
        if predicate():return
        time.sleep(.03)
    raise AssertionError('Timed out waiting for desktop preview')

from window_capture import capture_window

app=App();app.add(files);app.output.set(str(root/'studio-output'))
wait(app,lambda:app.preview_image is not None and not app.preview_meta.get().startswith('正在'))
initial=app.preview_size
app.vars['layout'].set('横向');app.vars['gap'].set('50');app.vars['margin'].set('60');app.vars['background'].set('#e9dfcd')
wait(app,lambda:app.preview_size!=initial and not app.preview_meta.get().startswith('正在'))
assert app.preview_size==(2920,770),app.preview_size
app.tree.selection_set('0');app.move(1)
wait(app,lambda:not app.preview_meta.get().startswith('正在'))
assert app.files[1]==files[0]
app.change_zoom(1.25);assert app.zoom is not None
app.fit_preview();assert app.zoom is None
app.vars['layout'].set('宫格');app.vars['columns'].set('2');app.vars['format'].set('PNG')
wait(app,lambda:not app.preview_meta.get().startswith('正在'))
app.start();wait(app,lambda:not app.busy)
out=list(app.last_out.glob('*.png'));assert out
with Image.open(out[0]) as im:assert im.size==app.preview_size
for geometry in ['1120x760','1360x900']:
    app.geometry(geometry);app.update()
    assert app.preview_canvas.winfo_width()>300
    assert app.preview_canvas.winfo_height()>200
    assert app.start_button.winfo_rooty()+app.start_button.winfo_height() < app.winfo_rooty()+app.winfo_height()
    assert all(button.winfo_ismapped() for button in app.nav_buttons.values())
    try:capture_window(app,root/f'studio-{geometry}.png')
    except OSError as e:print(e)
app.vars['gap'].set('invalid');wait(app,lambda:app.preview_image is None)
assert '整数' in app.preview_meta.get()
app.vars['gap'].set('24');wait(app,lambda:app.preview_image is not None)
app.select_tool('图片旋转');wait(app,lambda:'studio-' in app.preview_meta.get() and not app.preview_meta.get().startswith('正在'))
assert app.preview_size==(650,900)
app.select_tool('PDF 合并');wait(app,lambda:app.preview_image is None)
app.clear();app.select_tool('多图拼接');wait(app,lambda:'可拖入' in app.preview_meta.get())
app.destroy();print('Studio preview, edit, reorder, zoom, export and layout checks passed')
