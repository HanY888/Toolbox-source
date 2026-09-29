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
        self.path=Path(path).resolve();self.inputs={self.path};self.history=[]
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
                self.history.append((before,old_state));self.state=uuid.uuid4().hex
                while len(self.history)>20 or (len(self.history)>1 and sum(len(b) for b,_ in self.history)>128_000_000):self.history.pop(0)
    def undo(self):
        with PDF_LOCK:
            if not self.history:return
            data,self.state=self.history.pop();self.doc.close();self.doc=fitz.open(stream=data,filetype='pdf')
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
