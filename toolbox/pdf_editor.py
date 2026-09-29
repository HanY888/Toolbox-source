import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from PIL import ImageTk
from .pdf_document import PDFDocument
from .pdf_workspace import WorkspaceTools, TOOLS

class PDFEditor(WorkspaceTools,ttk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent);self.app=app;self.model=None;self.index=0;self.photos={};self.tool='select';self.drag=None;self.zoom=None;self.render_job=None
        self.caption=tk.StringVar(value='打开 PDF')
        ttk.Label(self,textvariable=self.caption,font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w',padx=10,pady=10)
        toolbar=ttk.Frame(self);toolbar.pack(fill='x',padx=8,pady=(0,7))
        for label,fn in [('页面管理',self.organize),('插入页面',self.insert_pages),('撤销',self.undo),('重做',self.redo)]:ttk.Button(toolbar,text=label,command=fn).pack(side='left',padx=2)
        self.mode=tk.StringVar(value='select');self.font_size=tk.StringVar(value='20');self.color=tk.StringVar(value='黑色')
        self.tool_label=tk.StringVar(value='选择 / 编辑')
        picker=ttk.Combobox(toolbar,textvariable=self.tool_label,values=list(TOOLS),state='readonly',width=12);picker.pack(side='left',padx=5)
        picker.bind('<<ComboboxSelected>>',lambda e:(self.mode.set(TOOLS[self.tool_label.get()]),self.choose_tool()))
        search=ttk.Frame(self);search.pack(fill='x',padx=10,pady=(0,8))
        self.search_var=tk.StringVar();self.search_count=tk.StringVar()
        self.search_entry=ttk.Entry(search,textvariable=self.search_var,width=22);self.search_entry.pack(side='left');self.search_entry.bind('<Return>',self.find_text)
        for label,fn in [('查找',self.find_text),('‹',lambda:self.next_hit(-1)),('›',self.next_hit)]:ttk.Button(search,text=label,width=4,command=fn).pack(side='left',padx=2)
        ttk.Label(search,textvariable=self.search_count,foreground='#667085').pack(side='left',padx=6)
        self.app.bind('<Control-f>',self.focus_search)
        self.app.bind('<Control-s>',lambda e:self.save() if self.winfo_ismapped() else None)
        body=ttk.Frame(self);body.pack(fill='both',expand=True)
        left=ttk.Frame(body,width=110);left.pack(side='left',fill='y');left.pack_propagate(False)
        ttk.Style(self).configure('Pages.Treeview',rowheight=118)
        self.pages=ttk.Treeview(left,show='tree',style='Pages.Treeview',selectmode='browse');self.pages.column('#0',width=86,stretch=False)
        scroll=ttk.Scrollbar(left,orient='vertical',command=lambda *a:(self.pages.yview(*a),self.thumbnails()))
        self.pages.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        self.pages.configure(yscrollcommand=scroll.set)
        self.pages.bind('<<TreeviewSelect>>',self.page_selected)
        self.pages.bind('<ButtonPress-1>',lambda e:setattr(self,'drag_page',self.pages.identify_row(e.y)))
        self.pages.bind('<ButtonRelease-1>',self.drop_page)
        self.pages.bind('<MouseWheel>',lambda e:self.after(80,self.thumbnails),add='+')
        pane=ttk.Frame(body);pane.pack(side='left',fill='both',expand=True)
        nav=ttk.Frame(pane);nav.pack(fill='x',padx=4,pady=4)
        for text,fn in [('‹',lambda:self.go(-1)),('›',lambda:self.go(1)),('－',lambda:self.magnify(.8)),('＋',lambda:self.magnify(1.25)),('适应',self.fit)]:ttk.Button(nav,text=text,width=4,command=fn).pack(side='left',padx=2)
        self.page_label=tk.StringVar(value='');ttk.Label(nav,textvariable=self.page_label).pack(side='right',padx=8)
        area=ttk.Frame(pane);area.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(area,bg='#e9ebef',highlightthickness=0)
        self.canvas.grid(row=0,column=0,sticky='nsew');area.columnconfigure(0,weight=1);area.rowconfigure(0,weight=1)
        vs=ttk.Scrollbar(area,orient='vertical',command=self.canvas.yview);vs.grid(row=0,column=1,sticky='ns')
        hs=ttk.Scrollbar(area,orient='horizontal',command=self.canvas.xview);hs.grid(row=1,column=0,sticky='ew');self.canvas.configure(xscrollcommand=hs.set,yscrollcommand=vs.set)
        self.canvas.bind('<Configure>',lambda e:self.schedule_render());self.canvas.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-3 if e.delta>0 else 3,'units'));self.canvas.bind('<Control-MouseWheel>',lambda e:self.magnify(1.15 if e.delta>0 else 1/1.15))
        self.canvas.bind('<ButtonPress-1>',self.press);self.canvas.bind('<B1-Motion>',self.motion);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.note=tk.StringVar(value='');ttk.Label(self,textvariable=self.note,wraplength=620,foreground='#6c7f90').pack(anchor='w',padx=8,pady=8)
    def move_current(self,delta):
        if not self.model or self.app.busy:return
        target=self.index+delta
        if 0<=target<len(self.model):self.model.move(self.index,target);self.index=target;self.refresh()
    def confirm_discard(self):
        if self.model and self.model.dirty:
            answer=messagebox.askyesnocancel('未保存的编辑','是否先保存当前 PDF？',parent=self)
            if answer is None:return False
            if answer:return self.save()
        return True
    def open_dialog(self):
        path=filedialog.askopenfilename(filetypes=[('PDF','*.pdf')])
        if path:self.open(path)
    def open(self,path):
        if self.model and self.model.path==Path(path).resolve():return True
        if not self.confirm_discard():return False
        try:new=PDFDocument(path)
        except Exception as e:messagebox.showerror('无法打开 PDF',str(e),parent=self);return False
        if self.model:self.model.close()
        self.model=new;self.index=0;self.zoom=None;self.refresh();return True
    def refresh(self):
        self.selected=None;self.update_properties();self.search_hits=[];self.search_count.set('');self.photos.clear();self.pages.delete(*self.pages.get_children())
        if not self.model:return
        self.index=max(0,min(self.index,len(self.model)-1))
        for i in range(len(self.model)):self.pages.insert('','end',iid=str(i),text=str(i+1))
        self.pages.selection_set(str(self.index));self.pages.see(str(self.index));self.schedule_render();self.after(50,self.thumbnails)
        self.caption.set(self.model.path.name+('  • 未保存' if self.model.dirty else ''))
    def thumbnails(self):
        if not self.model or self.app.busy:return
        start=max(0,int(self.pages.yview()[0]*len(self.model))-1)
        for i in range(start,min(len(self.model),start+9)):
            if i not in self.photos:
                from PIL import Image,ImageDraw
                im,_=self.model.render(i,92);im.thumbnail((76,92))
                tile=Image.new('RGB',(82,112),'white');tile.paste(im,((82-im.width)//2,3))
                ImageDraw.Draw(tile).text((41,104),str(i+1),fill='#18314c',anchor='mm')
                self.photos[i]=ImageTk.PhotoImage(tile);self.pages.item(str(i),image=self.photos[i],text='')
        for i in list(self.photos):
            if abs(i-start)>18:self.pages.item(str(i),image='');del self.photos[i]
    def page_selected(self,*_):
        selection=self.pages.selection()
        if selection:
            new_index=int(selection[0])
            if new_index!=self.index:self.selected=None;self.update_properties()
            self.index=new_index;self.schedule_render()
    def drop_page(self,event):
        target=self.pages.identify_row(event.y);source=getattr(self,'drag_page','')
        if not self.model or not source or not target or source==target:return
        if self.app.busy:return
        try:self.model.move(int(source),int(target));self.index=int(target);self.refresh()
        except Exception as e:messagebox.showerror('排序失败',str(e),parent=self)
    def go(self,delta):
        if self.model:self.select_object(None);self.index=max(0,min(self.index+delta,len(self.model)-1));self.pages.selection_set(str(self.index));self.pages.see(str(self.index));self.schedule_render();self.thumbnails()
    def edit(self,operation):
        if not self.model or self.app.busy:return
        if operation=='delete' and not messagebox.askyesno('删除页面',f'删除第 {self.index+1} 页？',parent=self):return
        try:getattr(self.model,operation)(self.index);self.refresh()
        except Exception as e:messagebox.showerror('编辑失败',str(e),parent=self)
    def undo(self):
        if self.model and not self.app.busy:self.model.undo();self.refresh()
    def insert_pages(self):
        if not self.model or self.app.busy:return
        paths=filedialog.askopenfilenames(filetypes=[('PDF 和图片','*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff')])
        if not paths:return
        try:self.model.insert(paths,self.index);self.index+=1;self.refresh()
        except Exception as e:messagebox.showerror('插入失败',str(e),parent=self)
    def choose_tool(self):
        self.tool=self.mode.get();self.tool_label.set(next((label for label,key in TOOLS.items() if key==self.tool),'选择 / 编辑'));self.selected=None;self.update_properties();self.draw_selection();self.canvas.configure(cursor='fleur' if self.tool=='hand' else 'crosshair')
        self.note.set('拖出添加区域' if self.tool in ('text','image') else '遮盖仅改变外观，底层文字仍可提取；不用于敏感信息脱敏。' if self.tool=='cover' else '')
        if self.tool=='select':self.note.set('点击原有文字或图片，在右侧修改属性')
        elif self.tool in ('highlight','underline','strike','note','rectangle','arrow'):self.note.set('拖动框选需要标注的区域')
    def schedule_render(self):
        if self.render_job:self.after_cancel(self.render_job)
        self.render_job=self.after(100,self.render)
    def render(self):
        self.render_job=None
        if self.app.busy:self.schedule_render();return
        c=self.canvas;c.delete('all')
        if not self.model:
            c.create_text(max(1,c.winfo_width())/2,max(1,c.winfo_height())/2,text='打开 PDF 开始编辑',fill='#6c7f90',font=('Microsoft YaHei UI',13));return
        im,self.page_size=self.model.render(self.index,1800)
        fit=min(max(1,c.winfo_width()-40)/im.width,max(1,c.winfo_height()-40)/im.height)
        factor=fit if self.zoom is None else self.zoom;factor=min(factor,3500/max(im.size));self.factor=factor
        w,h=max(1,round(im.width*factor)),max(1,round(im.height*factor))
        self.photo=ImageTk.PhotoImage(im.resize((w,h)))
        sw,sh=max(c.winfo_width(),w+40),max(c.winfo_height(),h+40)
        self.origin=((sw-w)/2,(sh-h)/2);self.display_size=(w,h)
        c.configure(scrollregion=(0,0,sw,sh));c.create_image(*self.origin,image=self.photo,anchor='nw')
        self.page_label.set(f'{self.index+1} / {len(self.model)}');self.draw_selection();self.paint_hits()
    def fit(self):self.zoom=None;self.schedule_render();self.canvas.xview_moveto(0);self.canvas.yview_moveto(0)
    def magnify(self,factor):
        if self.model:self.zoom=max(.05,min(3,(self.factor if self.zoom is None else self.zoom)*factor));self.schedule_render()
    def point(self,event):return (self.canvas.canvasx(event.x),self.canvas.canvasy(event.y))
    def press(self,event):
        if not self.model or self.app.busy:return
        if self.tool=='select':self.hit_object(event);return
        if self.tool=='hand':self.canvas.scan_mark(event.x,event.y)
        else:self.drag=self.point(event)
    def motion(self,event):
        if self.tool=='hand':self.canvas.scan_dragto(event.x,event.y,gain=1)
        elif self.drag:self.canvas.delete('selection');self.canvas.create_rectangle(*self.drag,*self.point(event),outline='#138b80',width=2,dash=(4,3),tags='selection')
    def release(self,event):
        if not self.drag or not self.model:return
        a=self.drag;b=self.point(event);self.drag=None;self.canvas.delete('selection')
        ox,oy=self.origin;dw,dh=self.display_size;pw,ph=self.page_size
        rect=((min(a[0],b[0])-ox)*pw/dw,(min(a[1],b[1])-oy)*ph/dh,(max(a[0],b[0])-ox)*pw/dw,(max(a[1],b[1])-oy)*ph/dh)
        if rect[2]-rect[0]<3 or rect[3]-rect[1]<3:return
        options={};kind=self.tool
        if kind in ('highlight','underline','strike','note','rectangle','arrow'):
            text=''
            if kind=='note':
                from tkinter import simpledialog
                text=simpledialog.askstring('便签','批注内容：',parent=self)
                if not text:return
            try:self.model.annotate(self.index,rect,kind,text);self.refresh()
            except Exception as e:messagebox.showerror('无法标注',str(e),parent=self)
            return
        if kind=='text':
            from tkinter import simpledialog
            text=simpledialog.askstring('添加文字','输入文字：',parent=self)
            if text is None:return
            try:options={'text':text,'font_size':int(self.font_size.get())}
            except ValueError:messagebox.showerror('字号','请输入整数字号',parent=self);return
        elif kind=='image':
            image=filedialog.askopenfilename(filetypes=[('图片','*.png *.jpg *.jpeg *.webp *.bmp')])
            if not image:return
            options={'image':image}
        colors={'黑色':(0,0,0),'白色':(1,1,1),'红色':(.85,.1,.1),'蓝色':(.1,.3,.8)}
        try:self.model.overlay(self.index,rect,kind,color=colors[self.color.get()],**options);self.refresh()
        except Exception as e:messagebox.showerror('无法添加',str(e),parent=self)
    def save(self):
        if not self.model:return False
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.pdf',initialdir=self.app.output.get() if Path(self.app.output.get()).is_dir() else str(self.model.path.parent),initialfile=self.model.path.stem+'_编辑.pdf',filetypes=[('PDF','*.pdf')])
        if not path:return False
        try:self.model.save(path);self.app.last_out=Path(path).parent;self.app.status.set(f'已保存：{Path(path).name}');self.refresh();return True
        except Exception as e:messagebox.showerror('保存失败',str(e),parent=self);return False
