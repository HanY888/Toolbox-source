"""PDF editing model. All PyMuPDF access is serialized across preview/export."""
from contextlib import contextmanager
from pathlib import Path
import os
import tempfile
import threading
import uuid
import pymupdf as fitz
from PIL import Image

PDF_LOCK=threading.RLock()

def raster(page,limit=1500):
    scale=min(3,limit/max(page.rect.width,page.rect.height))
    pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
    return Image.frombytes('RGB',(pix.width,pix.height),pix.samples)

def preview_file(path,index=0,limit=1500):
    with PDF_LOCK,fitz.open(path) as doc:
        if doc.needs_pass:raise ValueError('请先解密 PDF')
        if not len(doc):raise ValueError('PDF 没有页面')
        index=max(0,min(index,len(doc)-1));page=doc[index]
        return raster(page,limit),(round(page.rect.width),round(page.rect.height)),index,len(doc)

class PDFDocument:
    def __init__(self,path):
        self.path=Path(path).resolve();self.inputs={self.path};self.history=[];self.future=[]
        with PDF_LOCK:
            self.doc=fitz.open(self.path)
            if self.doc.needs_pass:
                self.doc.close();raise ValueError('请先解密 PDF')
            if not len(self.doc):self.doc.close();raise ValueError('PDF 没有页面')
        self.state=uuid.uuid4().hex;self.saved_state=self.state
    @property
    def dirty(self):return self.state!=self.saved_state
    def __len__(self):return len(self.doc)
    @contextmanager
    def change(self):
        with PDF_LOCK:
            before=self.doc.tobytes();old_state=self.state
            try:yield
            except Exception:
                self.doc.close();self.doc=fitz.open(stream=before,filetype='pdf');raise
            else:
                self.future.clear();self.history.append((before,old_state));self.state=uuid.uuid4().hex
                while len(self.history)>20 or (len(self.history)>1 and sum(len(b) for b,_ in self.history)>128_000_000):self.history.pop(0)
    def undo(self):
        with PDF_LOCK:
            if not self.history:return
            self.future.append((self.doc.tobytes(),self.state))
            data,self.state=self.history.pop();self.doc.close();self.doc=fitz.open(stream=data,filetype='pdf')
    def redo(self):
        with PDF_LOCK:
            if not self.future:return
            self.history.append((self.doc.tobytes(),self.state))
            data,self.state=self.future.pop();self.doc.close();self.doc=fitz.open(stream=data,filetype='pdf')
    def objects(self,index):
        with PDF_LOCK:
            page=self.doc[index];items=[]
            for block in page.get_text('dict')['blocks']:
                if block['type']!=0:continue
                for line in block['lines']:
                    for span in line['spans']:
                        if span['text'].strip():items.append(dict(span,kind='text',direction=line['dir'],rect=tuple(fitz.Rect(span['bbox'])*page.rotation_matrix)))
            for info in page.get_image_info(xrefs=True):
                if info['xref'] and max(info['width'],info['height'])>1:items.append(dict(info,kind='image',rect=tuple(fitz.Rect(info['bbox'])*page.rotation_matrix)))
            return items
    def search(self,query):
        with PDF_LOCK:
            return [(i,tuple(r*page.rotation_matrix)) for i,page in enumerate(self.doc) for r in page.search_for(query)] if query.strip() else []
    def replace_text(self,index,item,text,font='自动匹配',size=None,color=None,position=None):
        if item['kind']!='text':raise ValueError('请选择文字')
        if not any(o['kind']=='text' and o['bbox']==item['bbox'] and o['text']==item['text'] for o in self.objects(index)):raise ValueError('内容已改变，请重新选择文字')
        if tuple(item['direction'])!=(1.0,0.0) or self.doc[index].rotation:raise ValueError('此文字带有旋转，请先使用常规水平文字进行编辑')
        size=float(size or item['size'])
        if not 4<=size<=200:raise ValueError('字号应为 4–200')
        old=fitz.Rect(item['bbox']);origin=fitz.Point(item['origin'])
        if position:origin=fitz.Point(float(position[0]),float(position[1]))
        if color is None:
            c=item['color'];color=tuple(((c>>s)&255)/255 for s in (16,8,0))
        with self.change():
            page=self.doc[index]
            if list(page.annots(types=[fitz.PDF_ANNOT_REDACT])):raise ValueError('请先处理文档中已有的脱敏标记')
            name='china-s';fontfile=None
            fonts={'微软雅黑':'msyh.ttc','宋体':'simsun.ttc','黑体':'simhei.ttf','Arial':'arial.ttf','Arial Bold':'arialbd.ttf','Arial Italic':'ariali.ttf','Times New Roman':'times.ttf','Courier New':'cour.ttf'}
            if font in fonts:
                fontfile=str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/fonts[font]);name='tb'+fonts[font].split('.')[0]
                if not Path(fontfile).exists():raise ValueError('此电脑未安装所选字体')
                metric=fitz.Font(fontfile=fontfile)
            elif font=='自动匹配':
                metric=None
                for entry in page.get_fonts():
                    if entry[3].split('+')[-1]==item['font'].split('+')[-1]:
                        data=self.doc.extract_font(entry[0])[3]
                        if data:
                            candidate=fitz.Font(fontbuffer=data)
                            if all(ch.isspace() or candidate.has_glyph(ord(ch)) for ch in text):
                                name='tb'+str(entry[0]);page.insert_font(fontname=name,fontbuffer=data);metric=candidate;break
                if metric is None:
                    basic={'Helvetica':'helv','Helvetica-Bold':'hebo','Helvetica-Oblique':'heit','Times-Roman':'tiro','Courier':'cour'}
                    name=basic.get(item['font'],'china-s');metric=fitz.Font(name)
                if any(not ch.isspace() and not metric.has_glyph(ord(ch)) for ch in text):name='china-s';metric=fitz.Font(name)
            else:raise ValueError('请选择支持的字体')
            if any(not ch.isspace() and not metric.has_glyph(ord(ch)) for ch in text):raise ValueError('所选字体不包含部分文字，请选择微软雅黑或宋体')
            if '\n' in text:raise ValueError('当前按文字片段编辑，请保持单行；多行可分段编辑')
            width=metric.text_length(text,fontsize=size)
            newbox=fitz.Rect(origin.x,origin.y-size*metric.ascender,origin.x+width,origin.y-size*metric.descender)
            if text and (newbox.x0<0 or newbox.y0<0 or newbox.x1>page.rect.width or newbox.y1>page.rect.height):raise ValueError('文字超出页面，请缩小字号或调整位置')
            others=[o for o in self.objects(index) if o['kind']=='text']
            for position_index,other in enumerate(others):
                if other['bbox']==item['bbox'] and other['text']==item['text']:
                    others.pop(position_index);break
            # Use a narrow band through the selected glyphs; reject overlapping text.
            removal=fitz.Rect(old.x0+.05,old.y0+old.height*.45,old.x1-.05,old.y0+old.height*.55)
            if any(removal.intersects(fitz.Rect(o['bbox'])) for o in others):raise ValueError('文字与其他内容重叠，无法可靠单独编辑')
            if text and any(newbox.intersects(fitz.Rect(o['bbox'])) for o in others):raise ValueError('修改后的文字会与其他文字重叠，请缩小字号或调整位置')
            page.add_redact_annot(removal,fill=False,cross_out=False)
            page.apply_redactions(images=0,graphics=0,text=0)
            if text:page.insert_text(origin,text,fontsize=size,fontname=name,fontfile=fontfile,color=color)
    def edit_image(self,index,item,rect=None,replacement=None,delete=False):
        if not any(o['kind']=='image' and o['xref']==item['xref'] and o['bbox']==item['bbox'] for o in self.objects(index)):raise ValueError('内容已改变，请重新选择图片')
        with self.change():
            page=self.doc[index];xref=item['xref']
            occurrences=sum(len(p.get_image_rects(xref)) for p in self.doc)
            if occurrences!=1:raise ValueError('图片在文档中被重复使用，暂不支持单独修改')
            if page.rotation:raise ValueError('请先在未旋转页面编辑图片')
            data=self.doc.extract_image(xref)['image']
            page.delete_image(xref)
            if not delete:
                box=fitz.Rect(rect or item['bbox'])
                if box.is_empty or not page.rect.contains(box):raise ValueError('图片范围应在页面内')
                if replacement:page.insert_image(box,filename=str(replacement))
                else:page.insert_image(box,stream=data)
    def annotate(self,index,rect,kind,text=''):
        with self.change():
            page=self.doc[index];box=fitz.Rect(rect)*page.derotation_matrix
            if kind in ('highlight','underline','strike'):
                words=[fitz.Rect(w[:4]) for w in page.get_text('words') if box.intersects(fitz.Rect(w[:4]))]
                if not words:raise ValueError('选区中没有可标注的文字')
                method={'highlight':page.add_highlight_annot,'underline':page.add_underline_annot,'strike':page.add_strikeout_annot}[kind]
                annot=method(words)
            elif kind=='note':annot=page.add_text_annot(box.tl,text)
            elif kind=='rectangle':annot=page.add_rect_annot(box)
            elif kind=='arrow':
                annot=page.add_line_annot(box.tl,box.br);annot.set_line_ends(0,5)
            else:raise ValueError('未知标注类型')
            annot.update()
    def pages_action(self,indices,action):
        indices=sorted(set(indices))
        if not indices:return
        if action=='delete' and len(indices)>=len(self):raise ValueError('至少保留一页')
        with self.change():
            if action=='delete':
                for i in reversed(indices):self.doc.delete_page(i)
            elif action=='rotate':
                for i in indices:self.doc[i].set_rotation((self.doc[i].rotation+90)%360)
    def extract(self,indices,path):
        if Path(path).resolve() in self.inputs:raise ValueError('不能覆盖导入文件')
        with PDF_LOCK,fitz.open() as result:
            for i in sorted(set(indices)):result.insert_pdf(self.doc,from_page=i,to_page=i)
            result.save(path,garbage=4,deflate=True)
    def render(self,index,limit=1500):
        with PDF_LOCK:
            page=self.doc[index];return raster(page,limit),(page.rect.width,page.rect.height)
    def rotate(self,index):
        with self.change():
            page=self.doc[index];page.set_rotation((page.rotation+90)%360)
    def delete(self,index):
        if len(self)==1:raise ValueError('至少保留一页')
        with self.change():self.doc.delete_page(index)
    def move(self,index,target):
        if index==target:return
        if not 0<=target<len(self):raise ValueError('目标页码超出范围')
        destination=target if target<index else (-1 if target==len(self)-1 else target+1)
        with self.change():self.doc.move_page(index,destination)
    def insert(self,paths,after):
        count=0
        with self.change():
            for path in paths:
                path=Path(path).resolve()
                if path.suffix.lower()=='.pdf':
                    with fitz.open(path) as src:
                        if src.needs_pass:raise ValueError(f'{path.name} 已加密')
                        self.doc.insert_pdf(src,start_at=after+1+count);count+=len(src)
                else:
                    from .imaging import load_image
                    from io import BytesIO
                    with load_image(path) as image:
                        data=BytesIO();image.save(data,'PNG')
                    page=self.doc.new_page(pno=after+1+count,width=595,height=842)
                    page.insert_image(fitz.Rect(24,24,571,818),stream=data.getvalue());count+=1
                self.inputs.add(path)
        return count
    def overlay(self,index,rect,kind,*,text='',font_size=20,color=(0,0,0),image=None):
        with self.change():
            page=self.doc[index]
            # Normalize page rotation without rasterizing, preserving displayed coordinates.
            if page.rotation:page.remove_rotation();page=self.doc[index]
            box=fitz.Rect(rect)&page.rect
            if box.is_empty or box.width<2 or box.height<2:raise ValueError('请拖出更大的区域')
            if kind=='text':
                if not text.strip():raise ValueError('请输入文字')
                if not 6<=font_size<=200:raise ValueError('字号应为 6–200')
                left=page.insert_textbox(box,text,fontsize=font_size,fontname='china-s',color=color)
                if left<0:raise ValueError('文字放不下，请扩大区域或缩小字号')
            elif kind=='image':page.insert_image(box,filename=str(image),keep_proportion=True)
            elif kind=='cover':page.draw_rect(box,color=color,fill=color,overlay=True)
            else:raise ValueError('未知编辑类型')
    def save(self,path):
        path=Path(path).resolve()
        if path in self.inputs:raise ValueError('请选择不同文件名，不能覆盖导入的原文件')
        if path.suffix.lower()!='.pdf':raise ValueError('请使用 .pdf 文件扩展名')
        path.parent.mkdir(parents=True,exist_ok=True)
        fd,temporary=tempfile.mkstemp(suffix='.pdf',dir=path.parent);os.close(fd)
        try:
            with PDF_LOCK:self.doc.save(temporary,garbage=4,deflate=True)
            os.replace(temporary,path);self.saved_state=self.state
        finally:
            if os.path.exists(temporary):os.unlink(temporary)
    def close(self):
        with PDF_LOCK:self.doc.close()
