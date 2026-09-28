import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser
from pathlib import Path
from PIL import Image, ImageTk, ImageColor
from .engine import OPS, IMAGE_EXTS
from .imaging import render_collage, render_single

BG='#f1f5f8'; INK='#18314c'; MUTED='#6c7f90'; TEAL='#138b80'; NAV='#132d46'

FIELDS={
    'compress':['quality','target_kb'], 'convert':['format','quality','dpi'],
    'resize':['width','height','dpi','format'],
    'watermark':['text','watermark_path','font_size','opacity','position','format'],
    'crop':['crop','format'], 'rotate_image':['angle','format'], 'rename':['text'],
    'stitch':['layout','columns','width','gap','margin','background','format','quality'],
    'images_pdf':['quality'], 'pdf_compress':['pdf_mode','quality','dpi'],
    'pdf_images':['pages','dpi'], 'pdf_split':['pages'], 'pdf_extract':['pages'],
    'pdf_delete':['pages'], 'pdf_rotate':['pages','angle'], 'pdf_merge':[]}
DEFAULTS={'quality':'85','target_kb':'0','format':'JPG','width':'0','height':'0','dpi':'150',
          'text':'','font_size':'36','opacity':'60','position':'右下角','watermark_path':'',
          'crop':'0,0,800,600','angle':'90','pages':'','layout':'宫格',
          'pdf_mode':'无损压缩（保留文字）','columns':'0','gap':'24','margin':'32','background':'#ffffff'}
LABELS={'quality':'图片质量 · 10–95','target_kb':'目标大小 KB · 0 不限制','format':'输出格式',
        'width':'宽度 px · 0 自动','height':'高度 px · 0 自动','dpi':'DPI · 72–600',
        'text':'文字 / 重命名前缀','font_size':'文字字号','opacity':'水印不透明度 %',
        'position':'水印位置','watermark_path':'水印图片（可选）','crop':'裁剪 · 左,上,右,下',
        'angle':'顺时针旋转','pages':'页码 · 空白为全部','layout':'排列方式',
        'pdf_mode':'压缩方式','columns':'宫格列数 · 0 自动','gap':'图片间距 px',
        'margin':'外边距 px','background':'背景颜色'}
CHOICES={'format':['JPG','PNG','WEBP','BMP','TIFF'],'angle':['90','180','270'],
         'position':['右下角','居中'],'layout':['纵向','横向','宫格'],
         'pdf_mode':['无损压缩（保留文字）','扫描件压缩（页面转图片）']}
SHORT=['压缩图片','转换格式','尺寸与 DPI','文字与水印','裁剪图片','旋转图片','批量重命名',
       '多图拼接','图片转 PDF / 打印','压缩 PDF','PDF 转图片','合并 PDF','拆分 PDF','提取页面','删除页面','旋转页面']

class RoundButton(tk.Canvas):
    def __init__(self, parent, text, command, width=120, height=38, fill=TEAL, fg='white', bg='white'):
        super().__init__(parent,width=width,height=height,bg=bg,highlightthickness=0,bd=0,cursor='hand2',takefocus=1)
        self.label=text;self.command=command;self.fill=fill;self.fg=fg;self.enabled=True
        self.bind('<Configure>',lambda e:self.draw())
        self.bind('<Button-1>',lambda e:self.command() if self.enabled else None)
        self.bind('<Return>',lambda e:self.command() if self.enabled else None)
        self.bind('<space>',lambda e:self.command() if self.enabled else None)
        self.bind('<FocusIn>',lambda e:self.draw());self.bind('<FocusOut>',lambda e:self.draw())
    def draw(self):
        self.delete('all');w=self.winfo_width();h=self.winfo_height();r=12
        fill=self.fill if self.enabled else '#a4b5bc'
        self.create_polygon(1+r,1,w-r,1,w-1,1,w-1,1+r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1,smooth=True,fill=fill)
        self.create_text(w/2,h/2,text=self.label,fill=self.fg,font=('Microsoft YaHei UI',10,'bold'))
        if self.focus_get()==self:self.create_rectangle(4,4,w-4,h-4,outline='#72d9ca',dash=(3,2))
    def configure(self, **kw):
        if 'state' in kw:self.enabled=kw.pop('state')!='disabled'
        if 'text' in kw:self.label=kw.pop('text')
        result=super().configure(**kw);self.draw();return result

class StudioUI:
    def build_ui(self):
        self.geometry('1360x900');self.minsize(1120,760);self.configure(bg=BG)
        self.preview_revision=0;self.preview_timer=None;self.preview_image=None;self.preview_photo=None
        self.preview_requests=queue.Queue(maxsize=1);self.preview_stop=threading.Event();self.zoom=None
        self.preview_meta=tk.StringVar(value='预览会随设置自动更新')
        style=ttk.Style(self);style.theme_use('clam')
        style.configure('.',font=('Microsoft YaHei UI',10),foreground=INK)
        style.configure('TFrame',background='white');style.configure('TLabel',background='white')
        style.configure('TButton',padding=(10,6),background='#edf3f6',borderwidth=0)
        style.map('TButton',background=[('active','#dcebe9')])
        style.configure('TEntry',fieldbackground='#f6f8fa',padding=7,bordercolor='#e3eaf0',lightcolor='#e3eaf0',darkcolor='#e3eaf0')
        style.configure('TCombobox',padding=6,fieldbackground='#f6f8fa',background='#edf3f6')
        style.map('TCombobox',fieldbackground=[('readonly','#f6f8fa')])
        style.configure('TCheckbutton',background='white')
        style.configure('Treeview',rowheight=31,background='white',fieldbackground='white',borderwidth=0)
        style.configure('Treeview.Heading',background='#f3f7f9',padding=7,borderwidth=0)
        style.map('Treeview',background=[('selected','#d4eee9')],foreground=[('selected',INK)])
        style.configure('Horizontal.TProgressbar',background=TEAL,troughcolor='#e9f0f3',borderwidth=0)
        self.op=tk.StringVar(value='多图拼接')
        sidebar=tk.Frame(self,bg=NAV,width=192);sidebar.pack(side='left',fill='y');sidebar.pack_propagate(False)
        tk.Label(sidebar,text='拾光  /  STUDIO',bg=NAV,fg='white',font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w',padx=18,pady=(25,4))
        tk.Label(sidebar,text='本地图片与 PDF 工作台',bg=NAV,fg='#8ea8bc',font=('Microsoft YaHei UI',9)).pack(anchor='w',padx=18,pady=(0,20))
        self.nav_buttons={}
        for i,(title,op) in enumerate(OPS.items()):
            if i in (0,9):tk.Label(sidebar,text='图片工具' if i==0 else 'PDF 工具',bg=NAV,fg='#7c98ae',font=('Microsoft YaHei UI',9)).pack(anchor='w',padx=20,pady=(6,5))
            btn=RoundButton(sidebar,SHORT[i],lambda title=title:self.select_tool(title),width=170,height=28,fill=NAV,fg='#d4e0e9',bg=NAV)
            btn.pack(fill='x',padx=10,pady=1);self.nav_buttons[title]=btn
        tk.Label(sidebar,text='●  完全本地 · 原文件保留',bg=NAV,fg='#79cdbf',font=('Microsoft YaHei UI',9)).pack(side='bottom',pady=16)
        ttk.Button(sidebar,text='应用与右键设置',command=self.menu_settings).pack(side='bottom',fill='x',padx=14,pady=4)

        shell=tk.Frame(self,bg=BG);shell.pack(side='left',fill='both',expand=True,padx=20,pady=18)
        header=tk.Frame(shell,bg=BG);header.pack(fill='x',pady=(0,16))
        self.heading=tk.Label(header,text='多图拼接',bg=BG,fg=INK,font=('Microsoft YaHei UI',22,'bold'));self.heading.pack(side='left')
        tk.Label(header,text='先看效果，再安心导出',bg=BG,fg=MUTED,font=('Microsoft YaHei UI',10)).pack(side='left',padx=18,pady=(8,0))
        RoundButton(header,'＋ 添加文件',self.add_dialog,width=126,bg=BG).pack(side='right')
        body=tk.Frame(shell,bg=BG);body.pack(fill='both',expand=True)
        right=tk.Frame(body,bg='white',width=286,highlightbackground='#e3eaf0',highlightthickness=1);right.pack(side='right',fill='y',padx=(16,0));right.pack_propagate(False)
        center=tk.Frame(body,bg=BG);center.pack(side='left',fill='both',expand=True)

        card=tk.Frame(center,bg='white',highlightbackground='#e3eaf0',highlightthickness=1);card.pack(fill='both',expand=True)
        bar=tk.Frame(card,bg='white');bar.pack(fill='x',padx=16,pady=12)
        tk.Label(bar,text='效果预览',bg='white',fg=INK,font=('Microsoft YaHei UI',11,'bold')).pack(side='left')
        self.zoom_text=tk.StringVar(value='适应窗口')
        ttk.Button(bar,text='适应',command=self.fit_preview).pack(side='right')
        ttk.Button(bar,text='＋',width=3,command=lambda:self.change_zoom(1.25)).pack(side='right',padx=(3,6))
        ttk.Label(bar,textvariable=self.zoom_text,width=9,anchor='center').pack(side='right')
        ttk.Button(bar,text='－',width=3,command=lambda:self.change_zoom(.8)).pack(side='right',padx=3)
        area=tk.Frame(card,bg='#e8eef2');area.pack(fill='both',expand=True,padx=12)
        self.preview_canvas=tk.Canvas(area,bg='#e8eef2',highlightthickness=0,cursor='fleur')
        self.preview_canvas.grid(row=0,column=0,sticky='nsew');area.rowconfigure(0,weight=1);area.columnconfigure(0,weight=1)
        vs=ttk.Scrollbar(area,orient='vertical',command=self.preview_canvas.yview);vs.grid(row=0,column=1,sticky='ns')
        hs=ttk.Scrollbar(area,orient='horizontal',command=self.preview_canvas.xview);hs.grid(row=1,column=0,sticky='ew')
        self.preview_canvas.configure(xscrollcommand=hs.set,yscrollcommand=vs.set)
        self.preview_canvas.bind('<Configure>',lambda e:self.draw_preview())
        self.preview_canvas.bind('<MouseWheel>',lambda e:self.change_zoom(1.15 if e.delta>0 else 1/1.15))
        self.preview_canvas.bind('<ButtonPress-1>',lambda e:self.preview_canvas.scan_mark(e.x,e.y))
        self.preview_canvas.bind('<B1-Motion>',lambda e:self.preview_canvas.scan_dragto(e.x,e.y,gain=1))
        self.preview_canvas.drop_target_register('DND_Files');self.preview_canvas.dnd_bind('<<Drop>>',lambda e:self.add(self.tk.splitlist(e.data)))
        ttk.Label(card,textvariable=self.preview_meta,foreground=MUTED,wraplength=600).pack(anchor='w',padx=16,pady=10)

        files_card=tk.Frame(center,bg='white',highlightbackground='#e3eaf0',highlightthickness=1);files_card.pack(fill='x',pady=(14,0))
        toolbar=tk.Frame(files_card,bg='white');toolbar.pack(fill='x',padx=10,pady=9)
        self.file_count=tk.StringVar(value='素材 · 0')
        ttk.Label(toolbar,textvariable=self.file_count,font=('Microsoft YaHei UI',10,'bold')).pack(side='left',padx=4)
        for text,fn in [('清空',self.clear),('移除',self.remove),('下移',lambda:self.move(1)),('上移',lambda:self.move(-1))]:
            ttk.Button(toolbar,text=text,width=5,command=fn).pack(side='right',padx=2)
        self.tree=ttk.Treeview(files_card,columns=('name','kind','size','path'),show='headings',height=4,displaycolumns=('name','kind','size'))
        for key,title,width in [('name','文件 · 点击切换预览',230),('kind','格式',70),('size','大小',100),('path','路径',200)]:
            self.tree.heading(key,text=title);self.tree.column(key,width=width,minwidth=45,stretch=key=='name')
        self.tree.pack(side='left',fill='x',expand=True,padx=(8,0),pady=(0,8))
        scroll=ttk.Scrollbar(files_card,orient='vertical',command=self.tree.yview);scroll.pack(side='right',fill='y',pady=(0,8));self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<<TreeviewSelect>>',lambda e:self.schedule_preview())
        self.tree.drop_target_register('DND_Files');self.tree.dnd_bind('<<Drop>>',lambda e:self.add(self.tk.splitlist(e.data)))

        ttk.Label(right,text='调整与导出',font=('Microsoft YaHei UI',13,'bold')).pack(anchor='w',padx=18,pady=(18,12))
        # Export controls remain visible even when parameters need scrolling.
        export=tk.Frame(right,bg='white');export.pack(side='bottom',fill='x',padx=14,pady=14)
        self.hint=ttk.Label(export,text='',foreground=MUTED,wraplength=245,font=('Microsoft YaHei UI',9));self.hint.pack(anchor='w',pady=(0,12))
        ttk.Separator(export).pack(fill='x',pady=(0,12))
        ttk.Label(export,text='输出到',foreground=MUTED).pack(anchor='w')
        self.output=tk.StringVar(value=str(Path.home()/'Documents'/'拾光工具箱输出'))
        ttk.Entry(export,textvariable=self.output).pack(fill='x',pady=6)
        output_row=ttk.Frame(export);output_row.pack(fill='x')
        ttk.Button(output_row,text='选择目录',command=self.choose_output).pack(side='left')
        ttk.Button(output_row,text='打开结果',command=self.open_output).pack(side='right')
        self.start_button=RoundButton(export,'导出到本地',self.start,height=42);self.start_button.pack(fill='x',pady=(12,6))
        other=ttk.Frame(export);other.pack(fill='x')
        ttk.Button(other,text='取消任务',command=self.cancel.set).pack(side='left')
        ttk.Button(other,text='打开打印 PDF',command=self.open_print).pack(side='right')
        param_area=ttk.Frame(right);param_area.pack(fill='both',expand=True,padx=12)
        self.param_canvas=tk.Canvas(param_area,bg='white',highlightthickness=0,width=244)
        self.param_canvas.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(param_area,orient='vertical',command=self.param_canvas.yview);scroll.pack(side='right',fill='y')
        self.param_canvas.configure(yscrollcommand=scroll.set)
        self.params=ttk.Frame(self.param_canvas);self.param_window=self.param_canvas.create_window((0,0),window=self.params,anchor='nw')
        self.params.bind('<Configure>',lambda e:self.param_canvas.configure(scrollregion=self.param_canvas.bbox('all')))
        self.param_canvas.bind('<Configure>',lambda e:self.param_canvas.itemconfigure(self.param_window,width=e.width))
        self.vars={};self.widgets={}
        for k,value in DEFAULTS.items():
            var=tk.StringVar(value=value);self.vars[k]=var
            box=ttk.Frame(self.params);ttk.Label(box,text=LABELS[k],foreground=MUTED,font=('Microsoft YaHei UI',9)).pack(anchor='w',pady=(0,5))
            row=ttk.Frame(box);row.pack(fill='x')
            field=ttk.Combobox(row,textvariable=var,values=CHOICES[k],state='readonly',width=8) if k in CHOICES else ttk.Entry(row,textvariable=var,width=8)
            field.pack(side='left',fill='x',expand=True)
            if k=='background':ttk.Button(row,text='选色',width=4,command=self.pick_color).pack(side='right',padx=(4,0))
            if k=='watermark_path':ttk.Button(row,text='选择',width=4,command=self.pick_watermark).pack(side='right',padx=(4,0))
            self.widgets[k]=box;var.trace_add('write',self.schedule_preview)
            for control in (box,row,field):control.bind('<MouseWheel>',self.scroll_params)
        self.keep_ratio=tk.BooleanVar(value=True);self.keep_ratio.trace_add('write',self.schedule_preview)
        self.ratio_widget=ttk.Checkbutton(self.params,text='保持宽高比例',variable=self.keep_ratio)
        self.status=tk.StringVar(value='准备就绪')
        self.progress=ttk.Progressbar(shell,mode='determinate');self.progress.pack(fill='x',pady=(14,6))
        tk.Label(shell,textvariable=self.status,bg=BG,fg=MUTED,anchor='w',font=('Microsoft YaHei UI',9)).pack(fill='x')
        threading.Thread(target=self.preview_loop,daemon=True).start()
        self.bind('<Destroy>',lambda e:self.preview_stop.set() if e.widget is self else None)
        self.update_fields()

    def select_tool(self,title):
        self.op.set(title);self.update_fields()
    def scroll_params(self,event):
        self.param_canvas.yview_scroll(-1 if event.delta>0 else 1,'units');return 'break'
    def update_fields(self,*_):
        op=OPS[self.op.get()];self.heading.configure(text=self.op.get())
        for title,btn in self.nav_buttons.items():
            btn.fill=TEAL if title==self.op.get() else NAV;btn.fg='white' if title==self.op.get() else '#d4e0e9';btn.draw()
        for w in self.widgets.values():w.grid_forget()
        self.ratio_widget.grid_forget()
        groups={'stitch':[['layout'],['columns','width'],['gap','margin'],['background'],['format','quality']],
                'resize':[['width','height'],['dpi','format']],
                'watermark':[['text'],['watermark_path'],['font_size','opacity'],['position','format']]}.get(op,[[key] for key in FIELDS[op]])
        for row,keys in enumerate(groups):
            for col,key in enumerate(keys):self.widgets[key].grid(row=row,column=col,columnspan=2 if len(keys)==1 else 1,sticky='ew',padx=3,pady=(0,12))
        self.params.columnconfigure(0,weight=1,uniform='settings');self.params.columnconfigure(1,weight=1,uniform='settings')
        if op=='resize':self.ratio_widget.grid(row=len(groups),column=0,columnspan=2,sticky='w',pady=5)
        hints={'stitch':'全部图片按列表顺序拼接。间距、外边距按导出像素计；透明区域使用所选背景色。',
               'compress':'压缩预览仅展示原图构图。指定大小可能降低清晰度和尺寸，以导出结果为准。',
               'pdf_compress':'扫描件模式将页面转为图片，会移除文字层、链接和表单。无损模式不保证变小。',
               'images_pdf':'每张图片生成一页 A4，导出后在 PDF 阅读器中确认打印。',
               'watermark':'选择图片水印后优先使用图片。预览使用缩略图，文字边缘以导出为准。'}
        self.hint.configure(text=hints.get(op,'每次导出创建独立目录，保留原文件。图片预览跟随列表选中项。'))
        self.param_canvas.yview_moveto(0);self.zoom=None;self.schedule_preview()
    def pick_color(self):
        result=colorchooser.askcolor(parent=self,color=self.vars['background'].get() if self.valid_color() else '#ffffff',title='拼图背景颜色')
        if result[1]:self.vars['background'].set(result[1])
    def valid_color(self):
        try:ImageColor.getrgb(self.vars['background'].get());return True
        except ValueError:return False
    def pick_watermark(self):
        path=filedialog.askopenfilename(filetypes=[('图片','*.png *.jpg *.jpeg *.webp *.bmp')])
        if path:self.vars['watermark_path'].set(path)
    def read_options(self):
        opts=dict(DEFAULTS);opts.update({k:v.get().strip() for k,v in self.vars.items()})
        active=set(FIELDS[OPS[self.op.get()]])
        bounds={'quality':(10,95),'target_kb':(0,1048576),'width':(0,30000),'height':(0,30000),'dpi':(72,600),'font_size':(8,500),'opacity':(0,100),'angle':(90,270),'columns':(0,50),'gap':(0,2000),'margin':(0,5000)}
        for key,(lo,hi) in bounds.items():
            try:value=int(opts[key])
            except ValueError:
                if key in active:raise ValueError(f'请为“{LABELS[key]}”输入整数')
                value=int(DEFAULTS[key])
            if not lo<=value<=hi:
                if key in active:raise ValueError(f'{LABELS[key]}：允许 {lo}–{hi}')
                value=int(DEFAULTS[key])
            opts[key]=value
        if 'background' in active:
            try:ImageColor.getrgb(opts['background'])
            except ValueError:raise ValueError('请选择有效背景色，例如 #ffffff')
        opts['keep_ratio']=self.keep_ratio.get();return opts
    def schedule_preview(self,*_):
        self.preview_revision+=1
        if self.preview_timer:self.after_cancel(self.preview_timer)
        self.preview_meta.set('正在更新预览…')
        self.preview_timer=self.after(250,self.request_preview)
    def request_preview(self):
        self.preview_timer=None;op=OPS[self.op.get()]
        if op.startswith('pdf_') or op=='images_pdf':
            self.preview_image=None;self.empty_message='PDF 工具已就绪\n添加文件并设置参数，即可导出到本地'
            self.preview_meta.set('本次新增预览适用于图片工具；PDF 不显示页面预览。');self.draw_preview();return
        files=[p for p in self.files if p.suffix.lower() in IMAGE_EXTS]
        if not files:
            self.preview_image=None;self.empty_message='把图片拖到这里\n从一张图片，开始你的创作'
            self.preview_meta.set('支持 JPG、PNG、WEBP、BMP、TIFF · 可拖入多张');self.draw_preview();return
        if op!='stitch':
            selected=self.tree.selection()
            chosen=self.files[int(selected[0])] if selected else files[0]
            files=[chosen if chosen in files else files[0]]
        try:opts=self.read_options()
        except Exception as e:
            self.preview_image=None;self.empty_message='请完成右侧设置';self.preview_meta.set(str(e));self.draw_preview();return
        request=(self.preview_revision,files,op,opts)
        try:self.preview_requests.get_nowait()
        except queue.Empty:pass
        self.preview_requests.put_nowait(request)
    def preview_loop(self):
        while not self.preview_stop.is_set():
            try:revision,files,op,opts=self.preview_requests.get(timeout=.3)
            except queue.Empty:continue
            try:
                if op=='stitch':im,size=render_collage(files,opts,preview_limit=1800)
                else:
                    im,size=render_single(files[0],op,opts,preview_limit=1800)
                    if op=='compress' or (op!='rename' and opts['format'] in ('JPG','BMP')):
                        from .engine import rgb
                        im=rgb(im)
                self.events.put(('preview',revision,im,size,f'{len(files)} 张图片' if op=='stitch' else files[0].name,op))
            except Exception as e:self.events.put(('preview_error',revision,str(e)))
    def accept_preview(self,event):
        if event[1]!=self.preview_revision:
            if event[0]=='preview':event[2].close()
            return
        if self.preview_image is not None:self.preview_image.close()
        if event[0]=='preview_error':
            self.preview_image=None;self.empty_message='暂时无法预览';self.preview_meta.set(event[2])
        else:
            self.preview_image=event[2];self.preview_size=event[3]
            note='构图参考 · 压缩后的尺寸以实际导出为准' if event[5]=='compress' else '导出尺寸'
            self.preview_meta.set(f'{event[4]}  ·  {note} {event[3][0]:,} × {event[3][1]:,} px  ·  滚轮缩放 / 拖动平移')
        self.draw_preview()
    def fit_preview(self):self.zoom=None;self.draw_preview();self.preview_canvas.xview_moveto(0);self.preview_canvas.yview_moveto(0)
    def change_zoom(self,factor):
        if self.preview_image is None:return
        current=self.display_scale if self.zoom is None else self.zoom
        self.zoom=max(.05,min(3,current*factor));self.draw_preview()
    def draw_preview(self):
        canvas=self.preview_canvas;canvas.delete('all');w=max(1,canvas.winfo_width());h=max(1,canvas.winfo_height())
        if self.preview_image is None:
            canvas.configure(scrollregion=(0,0,w,h))
            canvas.create_text(w/2,h/2-45,text='▧',fill='#9aafb9',font=('Segoe UI',42))
            canvas.create_text(w/2,h/2+22,text=getattr(self,'empty_message','把图片拖到这里\n从一张图片，开始你的创作'),fill=MUTED,font=('Microsoft YaHei UI',12),justify='center',width=max(50,w-40))
            self.preview_photo=None;self.zoom_text.set('适应窗口');return
        im=self.preview_image;fit=min(max(1,w-50)/im.width,max(1,h-50)/im.height)
        self.display_scale=fit if self.zoom is None else self.zoom
        # Bound the display bitmap even under large monitors or high zoom.
        self.display_scale=min(self.display_scale,4096/max(im.size))
        dw=max(1,round(im.width*self.display_scale));dh=max(1,round(im.height*self.display_scale))
        sw=max(w,dw+48);sh=max(h,dh+48);x=(sw-dw)//2;y=(sh-dh)//2
        canvas.configure(scrollregion=(0,0,sw,sh))
        canvas.create_rectangle(x+5,y+6,x+dw+5,y+dh+6,fill='#d4dfe5',outline='')
        # Neutral checkerboard makes alpha visible for PNG / WEBP previews.
        image=im.convert('RGBA').resize((dw,dh),Image.Resampling.LANCZOS)
        if image.getextrema()[3][0]<255:
            base=Image.new('RGBA',(dw,dh),'#ffffff')
            from PIL import ImageDraw
            draw=ImageDraw.Draw(base)
            for yy in range(0,dh,16):
                for xx in range(0,dw,16):
                    if (xx//16+yy//16)%2:draw.rectangle((xx,yy,xx+15,yy+15),fill='#e8edef')
            base.alpha_composite(image);self.preview_photo=ImageTk.PhotoImage(base)
        else:self.preview_photo=ImageTk.PhotoImage(image)
        canvas.create_image(x,y,image=self.preview_photo,anchor='nw')
        self.zoom_text.set('适应窗口' if self.zoom is None else f'{round(self.display_scale*100)}%')
