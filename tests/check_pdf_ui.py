import sys,time,hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pymupdf as fitz
from app import App
from window_capture import capture_window

root=Path(__file__).resolve().parents[1]/'verification';root.mkdir(exist_ok=True)
source=root/'项目说明.pdf'
with fitz.open() as doc:
    for i in range(3):
        page=doc.new_page(width=595,height=842)
        page.draw_rect((0,0,595,130),fill=(.07,.18,.28),color=None)
        page.insert_text((44,70),'TOOLBOX',fontsize=32,color=(1,1,1))
        page.insert_text((44,105),f'PROJECT NOTES / 0{i+1}',fontsize=12,color=(.4,.8,.7))
        page.insert_text((44,190),'项目说明与页面编辑',fontname='china-s',fontsize=23,color=(.1,.2,.3))
        page.insert_textbox((44,225,550,350),'这是一份用于验证 PDF 预览与编辑的示例文档。\n可以添加文字、插入图片、调整页面顺序。',fontname='china-s',fontsize=15,color=(.25,.3,.35))
        page.draw_rect((44,390,550,570),color=None,fill=(.92,.96,.95))
        page.insert_text((60,425),'Review / Design / Export',fontsize=18,color=(.05,.45,.4))
        page.insert_text((44,790),f'{i+1} / 3',fontsize=11)
    doc.save(source)
original=hashlib.sha256(source.read_bytes()).hexdigest()
def wait(app,predicate,timeout=20):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        app.update()
        if predicate():return
        time.sleep(.03)
    raise AssertionError('PDF UI timed out')
app=App();app.add([source]);app.select_tool('PDF 压缩')
wait(app,lambda:app.pdf_total==3 and app.preview_image is not None)
app.turn_pdf(1);wait(app,lambda:app.pdf_page_text.get()=='2 / 3')
app.edit_preview_pdf();editor=app.pdf_editor
wait(app,lambda:editor.model is not None and hasattr(editor,'photo'))
assert editor.index==1
editor.go(-1);wait(app,lambda:editor.page_label.get()=='1 / 3')
editor.mode.set('text');editor.choose_tool();editor.render()
ox,oy=editor.origin;dw,dh=editor.display_size
x0=ox+dw*.1;y0=oy+dh*.68;x1=ox+dw*.88;y1=oy+dh*.78
editor.press(SimpleNamespace(x=x0,y=y0))
with patch('tkinter.simpledialog.askstring',return_value='已审核 · Toolbox'):
    editor.release(SimpleNamespace(x=x1,y=y1))
assert 'Toolbox' in editor.model.doc[0].get_text()
editor.model.move(0,2);editor.index=2;editor.refresh();wait(app,lambda:editor.page_label.get()=='3 / 3')
editor.undo();assert len(editor.model)==3
target=root/'Toolbox-PDF编辑验证.pdf'
with patch('toolbox.pdf_editor.filedialog.asksaveasfilename',return_value=str(target)):assert editor.save()
assert hashlib.sha256(source.read_bytes()).hexdigest()==original
for size in ['1120x760','1360x900']:
    app.geometry(size);app.update();editor.fit();wait(app,lambda:editor.render_job is None)
    capture_window(app,root/f'Toolbox-PDF-{size}.png')
app.destroy();print('PDF UI preview, paging, canvas text placement, reorder, undo, save, layout PASS')
