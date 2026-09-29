import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser
from pathlib import Path
from PIL import Image, ImageTk, ImageColor
from .engine import OPS, IMAGE_EXTS
from .imaging import render_collage, render_single

BG='#f5f6f8'; INK='#20242c'; MUTED='#667085'; TEAL='#2563eb'; NAV='#ffffff'

FIELDS={
    'compress':['quality','target_kb'], 'convert':['format','quality','dpi'],
    'resize':['width','height','dpi','format'],
    'watermark':['text','watermark_path','font_size','opacity','position','format'],
    'crop':['crop','format'], 'rotate_image':['angle','format'], 'rename':['text'],
    'stitch':['layout','columns','width','gap','margin','background','format','quality'],
    'images_pdf':['quality'], 'pdf_compress':['pdf_mode','quality','dpi'],
    'pdf_images':['pages','dpi'], 'pdf_split':['pages'], 'pdf_extract':['pages'],
    'pdf_delete':['pages'], 'pdf_rotate':['pages','angle'], 'pdf_merge':[], 'pdf_edit':[]}
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
       '多图拼接','图片转 PDF / 打印','压缩 PDF','PDF 转图片','合并 PDF','拆分 PDF','提取页面','删除页面','旋转页面','编辑 PDF']

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
        style.configure('TButton',padding=(10,6),background='#f1f3f6',borderwidth=0)
        style.map('TButton',background=[('active','#e8eefc')])
        style.configure('TEntry',fieldbackground='#f6f8fa',padding=7,bordercolor='#e3eaf0',lightcolor='#e3eaf0',darkcolor='#e3eaf0')
        style.configure('TCombobox',padding=6,fieldbackground='#f6f8fa',background='#f1f3f6')
        style.map('TCombobox',fieldbackground=[('readonly','#f6f8fa')])
        style.configure('TCheckbutton',background='white');style.configure('TRadiobutton',background='white')
        style.configure('Accent.TButton',background=TEAL,foreground='white');style.map('Accent.TButton',background=[('active','#1d4ed8')])
        style.configure('TScrollbar',background='#d0d5dd',troughcolor='#f5f6f8',borderwidth=0,arrowsize=12)
        style.configure('Treeview',rowheight=31,background='white',fieldbackground='white',borderwidth=0)
        style.configure('Treeview.Heading',background='#f3f7f9',padding=7,borderwidth=0)
        style.map('Treeview',background=[('selected','#e8efff')],foreground=[('selected',INK)])
        style.configure('Horizontal.TProgressbar',background=TEAL,troughcolor='#e9f0f3',borderwidth=0)
        self.op=tk.StringVar(value='多图拼接');self.active_title='多图拼接'
        sidebar=tk.Frame(self,bg=NAV,width=156);sidebar.pack(side='left',fill='y');sidebar.pack_propagate(False)
        tk.Label(sidebar,text='Toolbox',bg=NAV,fg=INK,font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w',padx=18,pady=(25,4))
        tk.Label(sidebar,text='文件工作台',bg=NAV,fg=MUTED,font=('Microsoft YaHei UI',9)).pack(anchor='w',padx=18,pady=(0,20))
        self.nav_buttons={};self.category_buttons={}
        for label in ('首页','PDF','图片','批处理'):
            button=RoundButton(sidebar,label,lambda name=label:self.show_category(name),width=132,height=40,fill=NAV,fg=MUTED,bg=NAV)
            button.pack(fill='x',padx=12,pady=4);self.category_buttons[label]=button
        ttk.Button(sidebar,text='应用与右键设置',command=self.menu_settings).pack(side='bottom',fill='x',padx=14,pady=4)

        shell=tk.Frame(self,bg=BG);shell.pack(side='left',fill='both',expand=True,padx=18,pady=18)
        header=tk.Frame(shell,bg=BG);header.pack(fill='x',pady=(0,16))
        self.heading=tk.Label(header,text='多图拼接',bg=BG,fg=INK,font=('Microsoft YaHei UI',22,'bold'));self.heading.pack(side='left')
        self.add_button=RoundButton(header,'打开文件',self.open_current,width=112,bg=BG);self.add_button.pack(side='right')
        self.tool_picker=ttk.Combobox(header,textvariable=self.op,values=list(OPS),state='readonly',width=21);self.tool_picker.pack(side='right',padx=12);self.tool_picker.bind('<<ComboboxSelected>>',lambda e:self.select_tool(self.op.get()))
        body=tk.Frame(shell,bg=BG);body.pack(fill='both',expand=True);self.work_body=body
        right=tk.Frame(body,bg='white',width=286,highlightbackground='#e3eaf0',highlightthickness=1);right.pack(side='right',fill='y',padx=(16,0));right.pack_propagate(False)
        center=tk.Frame(body,bg=BG);center.pack(side='left',fill='both',expand=True)
        from .pdf_editor import PDFEditor
        self.pdf_editor=PDFEditor(center,self)

        card=tk.Frame(center,bg='white',highlightbackground='#e3eaf0',highlightthickness=1);card.pack(fill='both',expand=True)
        self.preview_card=card
        bar=tk.Frame(card,bg='white');bar.pack(fill='x',padx=16,pady=12)
        tk.Label(bar,text='效果预览',bg='white',fg=INK,font=('Microsoft YaHei UI',11,'bold')).pack(side='left')
        self.zoom_text=tk.StringVar(value='适应窗口')
        ttk.Button(bar,text='适应',command=self.fit_preview).pack(side='right')
        ttk.Button(bar,text='＋',width=3,command=lambda:self.change_zoom(1.25)).pack(side='right',padx=(3,6))
        ttk.Label(bar,textvariable=self.zoom_text,width=9,anchor='center').pack(side='right')
        ttk.Button(bar,text='－',width=3,command=lambda:self.change_zoom(.8)).pack(side='right',padx=3)
        self.pdf_page=0;self.pdf_total=0;self.pdf_preview_path=None
        self.compare_button=ttk.Button(bar,text='压缩对比',command=self.open_comparison)
        self.pdf_nav=ttk.Frame(card);self.pdf_page_text=tk.StringVar(value='')
        ttk.Button(self.pdf_nav,text='上一页',command=lambda:self.turn_pdf(-1)).pack(side='left',padx=4)
        ttk.Label(self.pdf_nav,textvariable=self.pdf_page_text).pack(side='left',padx=10)
        ttk.Button(self.pdf_nav,text='下一页',command=lambda:self.turn_pdf(1)).pack(side='left',padx=4)
        ttk.Button(self.pdf_nav,text='编辑此 PDF',command=self.edit_preview_pdf).pack(side='right',padx=4)
        area=tk.Frame(card,bg='#e9ebef');area.pack(fill='both',expand=True,padx=12)
        self.preview_canvas=tk.Canvas(area,bg='#e9ebef',highlightthickness=0,cursor='fleur')
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
        self.files_card=files_card
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

        self.right_title=ttk.Label(right,text='调整与导出',font=('Microsoft YaHei UI',12,'bold'));self.right_title.pack(anchor='w',padx=18,pady=(18,12))
        # Export controls remain visible even when parameters need scrolling.
        export=tk.Frame(right,bg='white');export.pack(side='bottom',fill='x',padx=14,pady=14)
        self.hint=ttk.Label(export,text='',foreground=MUTED,wraplength=245,font=('Microsoft YaHei UI',9));self.hint.pack(anchor='w',pady=(0,12))
        ttk.Separator(export).pack(fill='x',pady=(0,12))
        self.output_controls=ttk.Frame(export);self.output_controls.pack(fill='x')
        ttk.Label(self.output_controls,text='输出到',foreground=MUTED).pack(anchor='w')
        self.output=tk.StringVar(value=str(Path.home()/'Documents'/'Toolbox输出'))
        ttk.Entry(self.output_controls,textvariable=self.output).pack(fill='x',pady=6)
        output_row=ttk.Frame(self.output_controls);output_row.pack(fill='x')
        ttk.Button(output_row,text='选择目录',command=self.choose_output).pack(side='left')
        ttk.Button(output_row,text='打开结果',command=self.open_output).pack(side='right')
        self.start_button=RoundButton(export,'导出',self.start,height=42);self.start_button.pack(fill='x',pady=(12,6))
        other=ttk.Frame(export);other.pack(fill='x');self.export_other=other
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
        self.pdf_settings=self.pdf_editor.build_controls(self.params)
        self.status=tk.StringVar(value='准备就绪')
        self.progress=ttk.Progressbar(shell,mode='determinate');self.progress.pack(fill='x',pady=(14,6));self.progress.pack_forget()
        tk.Label(shell,textvariable=self.status,bg=BG,fg=MUTED,anchor='w',font=('Microsoft YaHei UI',9)).pack(fill='x')
        threading.Thread(target=self.preview_loop,daemon=True).start()
        self.bind('<Destroy>',lambda e:self.preview_stop.set() if e.widget is self else None)
        self.update_fields()
        self.build_home(shell)
        self.show_category('首页')

    def select_tool(self,title):
        if self.busy:self.op.set(self.active_title);return
        self.active_title=title
        if title not in self.tool_picker['values']:self.tool_picker.configure(values=[name for name,code in OPS.items() if code.startswith('pdf_')==OPS[title].startswith('pdf_')])
        if hasattr(self,'home'):self.home.place_forget()
        if not self.tool_picker.winfo_manager():self.tool_picker.pack(side='right',padx=12)
        self.op.set(title);self.update_fields()
    def scroll_params(self,event):
        self.param_canvas.yview_scroll(-1 if event.delta>0 else 1,'units');return 'break'
    def update_fields(self,*_):
        op=OPS[self.op.get()];self.heading.configure(text=self.op.get())
        category='PDF' if op.startswith('pdf_') else '图片'
        for label,button in self.category_buttons.items():
            button.fill='#e8efff' if label==category else NAV;button.fg=TEAL if label==category else MUTED;button.draw()
        self.right_title.configure(text='内容属性' if op=='pdf_edit' else '调整与导出')
        self.add_button.configure(text='打开 PDF' if op=='pdf_edit' else '添加文件')
        if op=='pdf_edit':self.output_controls.pack_forget()
        elif not self.output_controls.winfo_manager():self.output_controls.pack(fill='x',before=self.start_button)

        if op=='pdf_edit':
            self.preview_card.pack_forget();self.files_card.pack_forget();self.pdf_editor.pack(fill='both',expand=True)
            if self.pdf_editor.model is None:
                pdfs=[p for p in self.files if p.suffix.lower()=='.pdf']
                if pdfs:self.pdf_editor.open(pdfs[0])
        else:
            self.pdf_editor.pack_forget()
            self.preview_card.pack(fill='both',expand=True);self.files_card.pack(fill='x',pady=(14,0))
        self.start_button.configure(text='另存 PDF' if op=='pdf_edit' else '导出')
        self.compare_button.pack_forget()
        if op in ('compress','pdf_compress'):self.compare_button.pack(side='left',padx=14)
        self.pdf_nav.pack_forget()
        if op.startswith('pdf_') and op!='pdf_edit':self.pdf_nav.pack(fill='x',before=self.preview_canvas.master,padx=12,pady=(0,6))
        for title,btn in self.nav_buttons.items():
            btn.fill=TEAL if title==self.op.get() else NAV;btn.fg='white' if title==self.op.get() else '#d4e0e9';btn.draw()
        for w in self.widgets.values():w.grid_forget()
        self.ratio_widget.grid_forget();self.pdf_settings.grid_forget()
        if op=='pdf_edit':self.pdf_settings.grid(row=0,column=0,columnspan=2,sticky='ew',padx=5);self.export_other.pack_forget()
        else:self.export_other.pack(fill='x')
        groups={'stitch':[['layout'],['columns','width'],['gap','margin'],['background'],['format','quality']],
                'resize':[['width','height'],['dpi','format']],
                'watermark':[['text'],['watermark_path'],['font_size','opacity'],['position','format']]}.get(op,[[key] for key in FIELDS[op]])
        for row,keys in enumerate(groups):
            for col,key in enumerate(keys):self.widgets[key].grid(row=row,column=col,columnspan=2 if len(keys)==1 else 1,sticky='ew',padx=3,pady=(0,12))
        self.params.columnconfigure(0,weight=1,uniform='settings');self.params.columnconfigure(1,weight=1,uniform='settings')
        if op=='resize':self.ratio_widget.grid(row=len(groups),column=0,columnspan=2,sticky='w',pady=5)
        hints={'stitch':'间距和外边距以像素计。',
               'compress':'压缩预览仅展示原图构图。指定大小可能降低清晰度和尺寸，以导出结果为准。',
               'pdf_compress':'扫描件模式将页面转为图片，会移除文字层、链接和表单。无损模式不保证变小。',
               'images_pdf':'每张图片生成一页 A4，导出后在 PDF 阅读器中确认打印。',
               'watermark':'选择图片水印后优先使用图片。'}
        self.hint.configure(text=hints.get(op,''))
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
        if op=='pdf_edit':return
        if op.startswith('pdf_'):
            files=[p for p in self.files if p.suffix.lower()=='.pdf']
            if not files:
                self.preview_image=None;self.empty_message='添加 PDF';self.preview_meta.set('');self.draw_preview();return
            selected=self.tree.selection()
            chosen=self.files[int(selected[0])] if selected else files[0]
            chosen=chosen if chosen in files else files[0]
            if chosen!=self.pdf_preview_path:self.pdf_page=0;self.pdf_preview_path=chosen
            request=(self.preview_revision,[chosen],op,{'_pdf_page':self.pdf_page})
            try:self.preview_requests.get_nowait()
            except queue.Empty:pass
            self.preview_requests.put_nowait(request);return
        files=[p for p in self.files if p.suffix.lower() in IMAGE_EXTS]
        if not files:
            self.preview_image=None;self.empty_message='拖入文件或点击添加'
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
                if op.startswith('pdf_'):
                    from .pdf_document import preview_file
                    im,size,index,total=preview_file(files[0],opts['_pdf_page'])
                    self.events.put(('pdf_preview',revision,im,size,files[0].name,index,total));continue
                if op=='stitch':im,size=render_collage(files,opts,preview_limit=1800)
                else:
                    im,size=render_single(files[0],op,opts,preview_limit=1800)
                    if op=='compress' or (op!='rename' and opts['format'] in ('JPG','BMP')):
                        from .engine import rgb
                        im=rgb(im)
                self.events.put(('preview',revision,im,size,f'{len(files)} 张图片' if op=='stitch' else files[0].name,op))
            except Exception as e:self.events.put(('preview_error',revision,str(e)))
    def turn_pdf(self,step):
        self.pdf_page=max(0,min(self.pdf_page+step,self.pdf_total-1));self.schedule_preview()
    def edit_preview_pdf(self):
        if self.pdf_preview_path:
            if self.pdf_editor.open(self.pdf_preview_path):
                self.pdf_editor.index=min(self.pdf_page,len(self.pdf_editor.model)-1)
                self.pdf_editor.refresh();self.select_tool('PDF 编辑')
    def accept_preview(self,event):
        if event[0]=='pdf_preview':
            if event[1]!=self.preview_revision:event[2].close();return
            self.pdf_page=event[5];self.pdf_total=event[6];self.pdf_page_text.set(f'{event[5]+1} / {event[6]}')
            event=('preview',event[1],event[2],event[3],event[4],'pdf_page')
        if event[1]!=self.preview_revision:
            if event[0]=='preview':event[2].close()
            return
        if self.preview_image is not None:self.preview_image.close()
        if event[0]=='preview_error':
            self.preview_image=None;self.empty_message='暂时无法预览';self.preview_meta.set(event[2])
        else:
            self.preview_image=event[2];self.preview_size=event[3]
            if event[5]=='pdf_page':
                self.preview_meta.set(f'{event[4]} · 第 {self.pdf_page+1} 页');self.draw_preview();return
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
            canvas.create_text(w/2,h/2+22,text=getattr(self,'empty_message','拖入文件或点击添加'),fill=MUTED,font=('Microsoft YaHei UI',12),justify='center',width=max(50,w-40))
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

    def open_current(self):
        if self.busy:return
        if self.home.winfo_ismapped():self.add_dialog();return
        if OPS[self.op.get()]=='pdf_edit':self.pdf_editor.open_dialog()
        else:self.add_dialog()
    def show_category(self,name):
        if self.busy:return
        if name=='首页':
            for label,button in self.category_buttons.items():
                button.fill='#e8efff' if label==name else NAV;button.fg=TEAL if label==name else MUTED;button.draw()
            self.tool_picker.pack_forget()
            self.home.place(in_=self.work_body,x=0,y=0,relwidth=1,relheight=1);self.home.lift();self.heading.configure(text='工作台');self.add_button.configure(text='打开文件');return
        self.home.place_forget()
        titles=[title for title,code in OPS.items() if (code.startswith('pdf_') if name=='PDF' else not code.startswith('pdf_'))]
        if name=='批处理':titles=[title for title,code in OPS.items() if code!='pdf_edit']
        self.tool_picker.configure(values=titles)
        self.select_tool('PDF 编辑' if name=='PDF' else '多图拼接' if name=='图片' else '图片压缩 / 指定大小')
        for label,button in self.category_buttons.items():
            button.fill='#e8efff' if label==name else NAV;button.fg=TEAL if label==name else MUTED;button.draw()
    def build_home(self,shell):
        self.home=tk.Frame(shell,bg=BG)
        tk.Label(self.home,text='开始处理文件',bg=BG,fg=INK,font=('Microsoft YaHei UI',24,'bold')).pack(anchor='w',pady=(32,8),padx=24)
        tk.Label(self.home,text='选择工具，或打开 PDF 进入编辑工作区',bg=BG,fg=MUTED,font=('Microsoft YaHei UI',11)).pack(anchor='w',padx=24,pady=(0,24))
        cards=tk.Frame(self.home,bg=BG);cards.pack(fill='x',padx=16)
        for i,(label,detail,title) in enumerate([('编辑 PDF','修改文字、图片与页面','PDF 编辑'),('压缩 PDF','预览压缩效果与文件大小','PDF 压缩'),('多图拼接','实时预览布局与间距','多图拼接'),('图片压缩','控制清晰度与目标大小','图片压缩 / 指定大小'),('合并 PDF','整理多个文档','PDF 合并'),('转换图片','调整格式、尺寸与 DPI','图片格式转换')]):
            card=tk.Frame(cards,bg='white',highlightbackground='#e4e7ec',highlightthickness=1);card.grid(row=i//3,column=i%3,sticky='nsew',padx=8,pady=8,ipady=16);cards.columnconfigure(i%3,weight=1)
            icon=tk.Canvas(card,width=42,height=42,bg='white',highlightthickness=0);icon.pack(anchor='w',padx=20,pady=(0,12))
            icon.create_rectangle(2,2,40,40,fill='#e8efff',outline='')
            if i in (0,1,4):
                icon.create_rectangle(13,9,29,32,outline=TEAL,width=2)
                for yy in (16,21,26):icon.create_line(17,yy,25,yy,fill=TEAL,width=2)
            else:
                icon.create_rectangle(9,11,33,31,outline=TEAL,width=2);icon.create_line(10,29,19,19,25,25,29,21,33,26,fill=TEAL,width=2)
            title_widget=tk.Label(card,text=label,bg='white',fg=INK,font=('Microsoft YaHei UI',13,'bold'),anchor='w');title_widget.pack(fill='x',padx=20)
            detail_widget=tk.Label(card,text=detail,bg='white',fg=MUTED,font=('Microsoft YaHei UI',10),anchor='w');detail_widget.pack(fill='x',padx=20,pady=(8,0))
            for widget in (card,icon,title_widget,detail_widget):widget.configure(cursor='hand2');widget.bind('<Button-1>',lambda e,t=title:self.select_tool(t))
        drop=tk.Canvas(self.home,bg=BG,height=115,highlightthickness=0);drop.pack(fill='x',padx=24,pady=28)
        def draw_drop(e):
            drop.delete('all');drop.create_rectangle(1,1,e.width-2,110,outline='#c7ced8',dash=(5,4));drop.create_text(e.width/2,45,text='拖入图片或 PDF，开始处理',fill=INK,font=('Microsoft YaHei UI',12));drop.create_text(e.width/2,78,text='也可以点击右上角打开文件',fill=MUTED,font=('Microsoft YaHei UI',10))
        drop.bind('<Configure>',draw_drop);drop.drop_target_register('DND_Files');drop.dnd_bind('<<Drop>>',lambda e:self.add(self.tk.splitlist(e.data)))
    def open_comparison(self):
        if self.busy:return
        from .comparison import CompressionComparison
        op=OPS[self.op.get()];files=[p for p in self.files if (p.suffix.lower()=='.pdf')==(op=='pdf_compress')]
        if not files:
            from tkinter import messagebox
            messagebox.showinfo('压缩对比','请先添加文件');return
        selected=self.tree.selection();path=self.files[int(selected[0])] if selected else files[0]
        if path not in files:path=files[0]
        try:CompressionComparison(self,path,op,self.read_options())
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror('无法对比',str(e))
