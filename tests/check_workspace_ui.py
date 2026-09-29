import sys,time,hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pymupdf as fitz
from PIL import Image
from app import App
from toolbox.comparison import CompressionComparison
from window_capture import capture_window

root=Path(__file__).resolve().parents[1]/'verification';root.mkdir(exist_ok=True)
source=root/'content-edit-demo.pdf'
with fitz.open() as doc:
    for i in range(3):
        p=doc.new_page(width=595,height=842)
        p.insert_text((48,72),'PROJECT REVIEW',fontsize=25,color=(.12,.17,.25))
        p.insert_text((48,110),'Toolbox / Design notes / September 2026',fontsize=11,color=(.4,.45,.5))
        p.draw_line((48,135),(547,135),color=(.2,.4,.85))
        p.insert_text((48,180),'Editable document content',fontsize=18)
        p.insert_text((48,218),'Select any text to update its font, size and color.',fontsize=12)
        p.insert_text((48,244),'All changes can be reviewed before saving.',fontsize=12)
        p.insert_text((48,310),'Notes and review',fontsize=18)
        p.insert_text((48,348),'Use annotations to highlight the important details.',fontsize=12)
        p.insert_text((48,780),f'Page {i+1}',fontsize=10)
    doc.save(source)
digest=hashlib.sha256(source.read_bytes()).hexdigest()
def wait(app,predicate,timeout=30):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        app.update()
        if predicate():return
        time.sleep(.03)
    raise AssertionError('UI timed out')
def fail(*args,**kwargs):raise AssertionError(str(args))
app=App();errors=[];app.report_callback_exception=lambda *args:errors.append(args)
try:
    app.update();capture_window(app,root/'Toolbox-0.5-home.png')
    for category in ('PDF','图片','批处理','首页'):app.show_category(category);app.update()
    app.add([source]);editor=app.pdf_editor
    wait(app,lambda:hasattr(editor,'photo'))
    item=next(o for o in editor.model.objects(0) if o.get('text')=='Editable document content')
    editor.render();rect=editor.canvas_rect(item['rect']);x=(rect[0]+rect[2])/2;y=(rect[1]+rect[3])/2
    editor.press(SimpleNamespace(x=x,y=y));assert editor.selected['text']=='Editable document content'
    editor.text_value.set('Updated project content');editor.font_family.set('Arial Bold');editor.font_size.set('19');editor.color_hex='#2563eb'
    with patch('toolbox.pdf_workspace.messagebox.showerror',side_effect=fail):editor.apply_object()
    text=editor.model.doc[0].get_text().replace('\xa0',' ')
    assert 'Updated project content' in text and 'Editable document content' not in text
    editor.undo();assert 'Editable document content' in editor.model.doc[0].get_text();editor.redo()
    editor.search_var.set('important');editor.find_text();assert len(editor.search_hits)==3
    editor.next_hit();wait(app,lambda:editor.page_label.get()=='2 / 3')
    editor.go(-1);editor.fit();wait(app,lambda:editor.render_job is None)
    editor.select_object(next(o for o in editor.model.objects(0) if 'Updated' in o.get('text','')))
    for size in ('1120x760','1360x900'):
        app.geometry(size);app.update();editor.fit();wait(app,lambda:editor.render_job is None)
        capture_window(app,root/f'Toolbox-0.5-editor-{size}.png')
    editor.model.annotate(0,(45,332,340,350),'highlight');editor.refresh()
    editor.organize();app.update()
    windows=[w for w in editor.winfo_children() if w.winfo_class()=='Toplevel']
    assert windows;wait(app,lambda:windows[-1].winfo_viewable());time.sleep(.2);app.update();capture_window(windows[-1],root/'Toolbox-0.5-pages.png');windows[-1].destroy()
    output=root/'Toolbox-0.5-edited.pdf'
    with patch('toolbox.pdf_editor.filedialog.asksaveasfilename',return_value=str(output)):assert editor.save()
    app.select_tool('PDF 压缩');opts=app.read_options();comparison=CompressionComparison(app,source,'pdf_compress',opts)
    wait(app,lambda:comparison.result is not None and len(comparison.images)==2)
    assert comparison.total==3;comparison.turn(1);assert comparison.page==1
    comparison.zoom(1.4);comparison.fit();app.update();capture_window(comparison,root/'Toolbox-0.5-compare.png')
    comparison.close();assert not app.busy
    image_path=root/'comparison-image.png';Image.effect_noise((1000,700),60).convert('RGB').save(image_path)
    app.add([image_path]);app.select_tool('图片压缩 / 指定大小')
    comparison=CompressionComparison(app,image_path,'compress',app.read_options())
    wait(app,lambda:comparison.result is not None and len(comparison.images)==2)
    image_output=root/'comparison-export.jpg'
    expected=comparison.result.read_bytes()
    with patch('toolbox.comparison.filedialog.asksaveasfilename',return_value=str(image_output)):comparison.export()
    assert image_output.read_bytes()==expected
    comparison.close();assert not app.busy
    assert digest==hashlib.sha256(source.read_bytes()).hexdigest()
    assert not errors,errors
finally:app.destroy()
print('Workspace UI: categories, selection, font/content edit, undo/redo, search, page grid, save, compression comparison and layouts PASS')
