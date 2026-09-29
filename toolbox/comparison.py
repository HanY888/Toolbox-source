"""Compare the actual compression output, then export those exact bytes."""
from pathlib import Path
import queue
import threading
import tempfile
import shutil
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from PIL import Image,ImageTk
from .engine import run,Cancelled
from .pdf_document import preview_file

class CompressionComparison(tk.Toplevel):
    def __init__(self,app,path,operation,options):
        super().__init__(app);self.title('压缩效果对比');self.geometry('1060x760');self.minsize(850,600)
        self.transient(app);self.grab_set();self.path=Path(path);self.app=app;self.operation=operation;self.page=0;self.total=1;self.scale=1
        self.temp=tempfile.TemporaryDirectory(prefix='toolbox_compare_');self.cancel=app.cancel;self.cancel.clear();app.busy=True;self.queue=queue.Queue();self.result=None;self.closed=False;self.images=[];self.photos=[]
        self.protocol('WM_DELETE_WINDOW',self.close)
        bar=ttk.Frame(self,padding=14);bar.pack(fill='x')
        self.status=tk.StringVar(value='正在生成实际压缩结果…');ttk.Label(bar,textvariable=self.status).pack(side='left')
        self.save_button=ttk.Button(bar,text='导出此结果',style='Accent.TButton',command=self.export,state='disabled');self.save_button.pack(side='right')
        nav=ttk.Frame(self,padding=(14,0,14,10));nav.pack(fill='x')
        for label,fn in [('上一页',lambda:self.turn(-1)),('下一页',lambda:self.turn(1)),('放大',lambda:self.zoom(1.4)),('缩小',lambda:self.zoom(1/1.4)),('适应',self.fit)]:ttk.Button(nav,text=label,command=fn).pack(side='left',padx=3)
        self.page_label=tk.StringVar();ttk.Label(nav,textvariable=self.page_label).pack(side='right')
        area=ttk.Frame(self);area.pack(fill='both',expand=True);self.canvases=[]
        for i,label in enumerate(('原文件','压缩结果')):
            pane=ttk.Frame(area,padding=8);pane.pack(side='left',fill='both',expand=True);ttk.Label(pane,text=label,font=('Microsoft YaHei UI',11,'bold')).pack(pady=6)
            c=tk.Canvas(pane,bg='#e9ebef',highlightthickness=0,width=450);c.pack(fill='both',expand=True);self.canvases.append(c)
            c.bind('<ButtonPress-1>',lambda e:self.mark(e));c.bind('<B1-Motion>',lambda e:self.pan(e));c.bind('<Configure>',lambda e:self.draw())
        def worker():
            try:
                files,errors=run([self.path],operation,Path(self.temp.name),options,lambda *a:None,self.cancel)
                if errors:raise ValueError(errors[0])
                self.queue.put(('done',files[0]))
            except Exception as e:self.queue.put(('error',str(e)))
        self.thread=threading.Thread(target=worker,daemon=True);self.thread.start();self.after(100,self.poll)
    def poll(self):
        if self.closed:return
        try:event,value=self.queue.get_nowait()
        except queue.Empty:self.after(100,self.poll);return
        self.app.busy=False
        if event=='error':self.status.set('未生成结果：'+value);return
        self.result=value;before=self.path.stat().st_size;after=value.stat().st_size
        change=(1-after/max(1,before))*100
        self.status.set(f'{before/1024:,.1f} KB → {after/1024:,.1f} KB · '+(f'减少 {change:.1f}%' if change>=0 else f'增大 {-change:.1f}%'))
        self.save_button.configure(state='normal');self.load()
    def load(self):
        for im in self.images:im.close()
        self.images=[]
        try:
            for path in (self.path,self.result):
                if self.operation=='pdf_compress':
                    im,_,self.page,self.total=preview_file(path,self.page,2200)
                else:
                    with Image.open(path) as source:im=source.convert('RGB');im.thumbnail((2400,2400))
                self.images.append(im)
            self.page_label.set(f'{self.page+1} / {self.total} · 拖动可同步查看局部');self.draw()
        except Exception as e:self.status.set(str(e))
    def draw(self):
        if len(self.images)!=2:return
        self.photos=[]
        for c,im in zip(self.canvases,self.images):
            w,h=max(1,c.winfo_width()),max(1,c.winfo_height());factor=min((w-24)/im.width,(h-24)/im.height)*self.scale
            factor=max(.02,min(factor,5000/max(im.size)));dw,dh=max(1,int(im.width*factor)),max(1,int(im.height*factor))
            photo=ImageTk.PhotoImage(im.resize((dw,dh),Image.Resampling.LANCZOS));self.photos.append(photo)
            c.delete('all');sw,sh=max(w,dw+24),max(h,dh+24);c.configure(scrollregion=(0,0,sw,sh));c.create_image(sw/2,sh/2,image=photo)
    def mark(self,event):
        for c in self.canvases:c.scan_mark(event.x,event.y)
    def pan(self,event):
        for c in self.canvases:c.scan_dragto(event.x,event.y,gain=1)
    def zoom(self,factor):self.scale=max(1,min(8,self.scale*factor));self.draw()
    def fit(self):
        self.scale=1;self.draw()
        for c in self.canvases:c.xview_moveto(0);c.yview_moveto(0)
    def turn(self,delta):
        if not self.result:return
        self.page=max(0,min(self.total-1,self.page+delta));self.load()
    def export(self):
        if not self.result:return
        path=filedialog.asksaveasfilename(parent=self,initialfile=self.result.name,defaultextension=self.result.suffix)
        if not path:return
        if Path(path).resolve()==self.path.resolve():messagebox.showerror('导出','请选择不同文件名',parent=self);return
        try:shutil.copy2(self.result,path);self.app.last_out=Path(path).parent;self.status.set('已导出：'+Path(path).name)
        except Exception as e:messagebox.showerror('导出失败',str(e),parent=self)
    def close(self):
        self.closed=True;self.cancel.set()
        def cleanup():
            if self.thread.is_alive():self.app.after(100,cleanup);return
            self.app.busy=False;self.temp.cleanup()
        cleanup()
        for im in self.images:im.close()
        self.destroy()
        # Release Tcl-owned objects on the UI thread, not during worker GC.
        self.status=None;self.page_label=None;self.photos.clear();self.images.clear();self.canvases.clear()
