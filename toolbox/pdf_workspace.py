"""Object properties, search and page organizer for the PDF workspace."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
from PIL import ImageTk

TOOLS={'选择 / 编辑':'select','平移视图':'hand','添加文字':'text','添加图片':'image','高亮':'highlight','下划线':'underline','删除线':'strike','便签':'note','矩形':'rectangle','箭头':'arrow'}
FONTS=['自动匹配','微软雅黑','宋体','黑体','Arial','Arial Bold','Arial Italic','Times New Roman','Courier New']

class WorkspaceTools:
    def build_controls(self,parent):
        panel=ttk.Frame(parent);self.property_panel=panel;self.selected=None
        self.object_label=tk.StringVar(value='点击页面中的文字或图片')
        ttk.Label(panel,textvariable=self.object_label,wraplength=235,foreground='#667085').pack(fill='x',pady=(5,16))
        self.property_body=ttk.Frame(panel);self.property_body.pack(fill='x')
        self.text_value=tk.StringVar();self.font_family=tk.StringVar(value='自动匹配');self.color_hex='#202124'
        self.coords={key:tk.StringVar() for key in ('x','y','w','h')}
        self.update_properties()
        return panel
    def update_properties(self):
        if not hasattr(self,'property_body'):return
        for child in self.property_body.winfo_children():child.destroy()
        body=self.property_body;item=self.selected
        if not item:
            self.object_label.set('选择文字可修改内容与字体；选择图片可调整位置和大小。')
            if self.tool=='text':
                self.object_label.set('在页面上拖出文字区域')
                ttk.Label(body,text='字号').pack(anchor='w',pady=8)
                ttk.Entry(body,textvariable=self.font_size).pack(fill='x')
                ttk.Label(body,text='颜色').pack(anchor='w',pady=8)
                ttk.Combobox(body,textvariable=self.color,values=['黑色','白色','红色','蓝色'],state='readonly').pack(fill='x')
            else:
                ttk.Separator(body).pack(fill='x',pady=12)
                ttk.Label(body,text='快捷操作',font=('Microsoft YaHei UI',10,'bold')).pack(anchor='w',pady=8)
                ttk.Label(body,text='Ctrl + F    查找文字\nCtrl + S    另存文档\nCtrl + 滚轮    缩放页面',foreground='#667085',justify='left').pack(anchor='w',pady=8)
            return
        self.object_label.set('文字属性' if item['kind']=='text' else '图片属性')
        def field(label,var,values=None):
            ttk.Label(body,text=label,foreground='#667085').pack(anchor='w',pady=(10,4))
            widget=ttk.Combobox(body,textvariable=var,values=values,state='readonly') if values else ttk.Entry(body,textvariable=var)
            widget.pack(fill='x');return widget
        if item['kind']=='text':
            field('内容',self.text_value)
            field('字体',self.font_family,FONTS)
            ttk.Label(body,text='原字体：'+item['font'],wraplength=235,foreground='#667085',font=('Microsoft YaHei UI',8)).pack(anchor='w',pady=3)
            field('字号',self.font_size)
            ttk.Button(body,text='文字颜色',command=self.pick_text_color).pack(fill='x',pady=8)
        row=ttk.Frame(body);row.pack(fill='x',pady=8)
        for col,key in enumerate(('x','y')):
            ttk.Label(row,text=key.upper()+' · pt').grid(row=0,column=col,sticky='w')
            ttk.Entry(row,textvariable=self.coords[key],width=9).grid(row=1,column=col,sticky='ew',padx=(0,6));row.columnconfigure(col,weight=1)
        if item['kind']=='image':
            field('宽度 · pt',self.coords['w']);field('高度 · pt',self.coords['h'])
            ttk.Button(body,text='替换图片…',command=self.replace_selected_image).pack(fill='x',pady=8)
        ttk.Button(body,text='应用修改',style='Accent.TButton',command=self.apply_object).pack(fill='x',pady=(12,6))
        ttk.Button(body,text='删除选中内容',command=self.delete_object).pack(fill='x',pady=4)
        def bind_scroll(widget):
            widget.bind('<MouseWheel>',self.app.scroll_params)
            for child in widget.winfo_children():bind_scroll(child)
        bind_scroll(body)
    def pick_text_color(self):
        color=colorchooser.askcolor(self.color_hex,parent=self)[1]
        if color:self.color_hex=color
    def select_object(self,item):
        self.selected=item;self.selection_index=self.index
        if item:
            x,y,x1,y1=item['rect']
            if item['kind']=='text':
                x,y=item['origin'];self.text_value.set(item['text']);self.font_size.set(f"{item['size']:.2f}");self.font_family.set('自动匹配');self.color_hex=f"#{item['color']:06x}"
            for key,value in zip(('x','y','w','h'),(x,y,x1-item['rect'][0],y1-item['rect'][1])):self.coords[key].set(f'{value:.2f}')
        self.update_properties();self.draw_selection()
    def canvas_rect(self,rect):
        ox,oy=self.origin;dw,dh=self.display_size;pw,ph=self.page_size
        x0,y0,x1,y1=rect;return (ox+x0*dw/pw,oy+y0*dh/ph,ox+x1*dw/pw,oy+y1*dh/ph)
    def draw_selection(self):
        self.canvas.delete('object')
        if self.selected and hasattr(self,'origin'):self.canvas.create_rectangle(*self.canvas_rect(self.selected['rect']),outline='#2563eb',width=2,tags='object')
    def hit_object(self,event):
        if not hasattr(self,'origin'):return
        x,y=self.point(event);ox,oy=self.origin;dw,dh=self.display_size;pw,ph=self.page_size
        x=(x-ox)*pw/dw;y=(y-oy)*ph/dh
        matches=[o for o in self.model.objects(self.index) if o['rect'][0]<=x<=o['rect'][2] and o['rect'][1]<=y<=o['rect'][3]]
        matches.sort(key=lambda o:(o['kind']!='text',(o['rect'][2]-o['rect'][0])*(o['rect'][3]-o['rect'][1])))
        self.select_object(matches[0] if matches else None)
        if not matches:self.note.set('未选中内容。扫描图片中的文字需 OCR 后才能识别。')
    def apply_object(self,delete=False,replacement=None):
        if not self.selected or self.app.busy:return
        if self.selection_index!=self.index:self.select_object(None);return
        try:
            item=self.selected
            if item['kind']=='text':
                color=tuple(int(self.color_hex[i:i+2],16)/255 for i in (1,3,5))
                self.model.replace_text(self.index,item,'' if delete else self.text_value.get(),self.font_family.get(),float(self.font_size.get()),color,tuple(float(self.coords[k].get()) for k in ('x','y')))
            else:
                x,y,w,h=(float(self.coords[k].get()) for k in ('x','y','w','h'))
                self.model.edit_image(self.index,item,(x,y,x+w,y+h),replacement,delete)
            self.selected=None;self.refresh();self.update_properties();self.note.set('修改已应用，可撤销')
        except Exception as e:messagebox.showerror('无法应用修改',str(e),parent=self)
    def delete_object(self):
        if self.selected and messagebox.askyesno('删除内容','删除选中的内容？',parent=self):self.apply_object(delete=True)
    def replace_selected_image(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('图片','*.png *.jpg *.jpeg *.bmp')])
        if path:self.apply_object(replacement=path)
    def redo(self):
        if self.model and not self.app.busy:self.model.redo();self.refresh()
    def find_text(self,*_):
        if not self.model or self.app.busy:return
        self.search_hits=self.model.search(self.search_var.get());self.hit_index=-1
        self.next_hit()
    def next_hit(self,delta=1):
        if not getattr(self,'search_hits',[]):self.search_count.set('无结果');self.schedule_render();return
        self.select_object(None)
        self.hit_index=(self.hit_index+delta)%len(self.search_hits)
        self.index=self.search_hits[self.hit_index][0];self.pages.selection_set(str(self.index));self.pages.see(str(self.index));self.schedule_render()
        self.search_count.set(f'{self.hit_index+1} / {len(self.search_hits)}')
    def paint_hits(self):
        for index,rect in getattr(self,'search_hits',[]):
            if index==self.index:self.canvas.create_rectangle(*self.canvas_rect(rect),outline='#d99a16',fill='#ffdf75',stipple='gray50',tags='search')
        if getattr(self,'search_hits',[]) and self.hit_index>=0:
            index,rect=self.search_hits[self.hit_index]
            if index==self.index:
                x0,y0,x1,y1=self.canvas_rect(rect)
                self.canvas.create_rectangle(x0,y0,x1,y1,outline='#d48806',width=2,tags='search')
                region=self.canvas.bbox('all')
                if region:
                    sw=max(self.canvas.winfo_width(),region[2]);sh=max(self.canvas.winfo_height(),region[3])
                    self.canvas.xview_moveto(max(0,(x0-30)/sw));self.canvas.yview_moveto(max(0,(y0-80)/sh))
    def focus_search(self,event=None):
        if self.winfo_ismapped():self.search_entry.focus_set();self.search_entry.selection_range(0,'end');return 'break'
    def organize(self):
        if not self.model or self.app.busy:return
        win=tk.Toplevel(self);win.title('页面管理');win.geometry('820x660');win.transient(self);win.grab_set()
        bar=ttk.Frame(win,padding=12);bar.pack(fill='x')
        ttk.Label(bar,text='多选页面进行批量操作 · 拖动页面调整顺序').pack(side='left')
        canvas=tk.Canvas(win,bg='#f5f6f8',highlightthickness=0);canvas.pack(fill='both',expand=True,side='left')
        scroll=ttk.Scrollbar(win,orient='vertical',command=canvas.yview);scroll.pack(side='right',fill='y');canvas.configure(yscrollcommand=scroll.set)
        grid=ttk.Frame(canvas);canvas.create_window(0,0,window=grid,anchor='nw');grid.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        selected=set();photos=[];drag=[None];offset=[0];page_text=tk.StringVar()
        def dispose(event):
            nonlocal page_text
            if event.widget is win:page_text=None;photos.clear()
        win.bind('<Destroy>',dispose)
        footer=ttk.Frame(bar);footer.pack(side='right')
        def refresh():
            for child in grid.winfo_children():child.destroy()
            photos.clear();selected.clear();offset[0]=min(offset[0],max(0,((len(self.model)-1)//24)*24))
            page_text.set(f'{offset[0]+1}–{min(offset[0]+24,len(self.model))} / {len(self.model)}')
            for local,i in enumerate(range(offset[0],min(offset[0]+24,len(self.model)))):
                tile=tk.Frame(grid,bg='white',highlightthickness=2,highlightbackground='#e4e7ec');tile.grid(row=local//4,column=local%4,padx=12,pady=12)
                im,_=self.model.render(i,165);photo=ImageTk.PhotoImage(im);photos.append(photo)
                label=tk.Label(tile,image=photo,bg='white',width=160,height=175);label.pack();tk.Label(tile,text=f'第 {i+1} 页',bg='white').pack(pady=6)
                def down(e,i=i):drag[0]=i
                def up(e,i=i,tile=tile):
                    target=win.winfo_containing(e.x_root,e.y_root);destination=getattr(target,'page_index',i)
                    if drag[0] is not None and destination!=drag[0]:self.model.move(drag[0],destination);self.index=destination;self.refresh();refresh();return
                    if i in selected:selected.remove(i)
                    else:selected.add(i)
                    tile.configure(highlightbackground='#2563eb' if i in selected else '#e4e7ec')
                label.page_index=i;label.bind('<ButtonPress-1>',down);label.bind('<ButtonRelease-1>',up)
        def act(action):
            if not selected:return
            if action=='delete' and not messagebox.askyesno('删除页面',f'删除选中的 {len(selected)} 页？',parent=win):return
            try:
                if action=='extract':
                    path=filedialog.asksaveasfilename(parent=win,defaultextension='.pdf',filetypes=[('PDF','*.pdf')])
                    if path:self.model.extract(selected,path)
                    return
                self.model.pages_action(selected,action);self.refresh();refresh()
            except Exception as e:messagebox.showerror('页面操作失败',str(e),parent=win)
        for label,key in [('旋转','rotate'),('删除','delete'),('提取','extract')]:ttk.Button(footer,text=label,width=4,command=lambda k=key:act(k)).pack(side='left',padx=2)
        paging=ttk.Frame(grid)
        def turn(delta):offset[0]=max(0,min(((len(self.model)-1)//24)*24,offset[0]+delta*24));refresh()
        ttk.Button(bar,text='‹',width=2,command=lambda:turn(-1)).pack(side='left');ttk.Label(bar,textvariable=page_text).pack(side='left');ttk.Button(bar,text='›',width=2,command=lambda:turn(1)).pack(side='left')
        refresh()
