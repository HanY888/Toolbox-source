import sys
import os
import json
import queue
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
from toolbox.engine import OPS, IMAGE_EXTS, run, Cancelled

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))

from toolbox.studio import StudioUI
from toolbox.desktop import VERSION

class App(StudioUI, TkinterDnD.Tk):
    def __init__(self, broker=None, tray=False):
        super().__init__()
        self.broker=broker;self.tray_icon=None;self.tray_ready=False;self.pending_paths=[];self.exiting=False
        self.title(f'Toolbox {VERSION}')
        self.configure(bg='#edf2f7')
        if (BASE / 'assets/app.ico').exists(): self.iconbitmap(str(BASE / 'assets/app.ico'))
        self.files = []; self.busy = False; self.events = queue.Queue(); self.cancel = threading.Event(); self.last_out = None
        self.build_ui()
        self.after(100,self.poll); self.protocol('WM_DELETE_WINDOW',self.close)
        self.add([a for a in sys.argv[1:] if not a.startswith('--')])
        if tray:self.start_tray()
        if broker:self.after(200,self.poll_instance)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i,p in enumerate(self.files):
            try: size=f'{p.stat().st_size/1024:,.1f} KB'
            except OSError: size='不可访问'
            self.tree.insert('', 'end',iid=str(i),values=(p.name,p.suffix.upper().lstrip('.'),size,str(p.parent)))
        if not self.busy:self.status.set(f'已添加 {len(self.files)} 个文件')
        self.file_count.set(f'素材 · {len(self.files)}');self.schedule_preview()
    def add(self, paths):
        if self.busy:
            self.pending_paths.extend(paths);self.status.set(f'任务进行中，新导入的 {len(self.pending_paths)} 个文件将在结束后加入。');return
        added=[]
        for item in paths:
            p=Path(item).resolve()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS|{'.pdf'} and p not in self.files:self.files.append(p);added.append(p)
        if added:
            self.home.place_forget()
            if all(p.suffix.lower()=='.pdf' for p in added) and not OPS[self.op.get()].startswith('pdf_'):self.select_tool('PDF 编辑')
            elif all(p.suffix.lower() in IMAGE_EXTS for p in added) and OPS[self.op.get()].startswith('pdf_'):self.select_tool('多图拼接')
        self.refresh()
        if OPS[self.op.get()]=='pdf_edit':
            pdfs=[p for p in added if p.suffix.lower()=='.pdf']
            if pdfs:self.pdf_editor.open(pdfs[0])
    def add_dialog(self):self.add(filedialog.askopenfilenames(filetypes=[('图片和 PDF','*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.pdf')]))
    def clear(self):
        if not self.busy:self.files.clear();self.refresh()
    def remove(self):
        if self.busy:return
        selected={int(x) for x in self.tree.selection()}; self.files=[p for i,p in enumerate(self.files) if i not in selected]; self.refresh()
    def move(self,step):
        if self.busy:return
        selection=self.tree.selection()
        if len(selection)!=1:return
        i=int(selection[0]); j=i+step
        if 0<=j<len(self.files):self.files[i],self.files[j]=self.files[j],self.files[i];self.refresh();self.tree.selection_set(str(j))
    def choose_output(self):
        p=filedialog.askdirectory()
        if p:self.output.set(p)
    def open_output(self):
        p=self.last_out or Path(self.output.get())
        if p.exists():os.startfile(p)
    def open_print(self):
        if self.last_out:
            pdfs=list(self.last_out.glob('*.pdf'))
            if pdfs:os.startfile(pdfs[0]);return
        messagebox.showinfo('打印','先使用“图片转 PDF / 多图打印”生成文件，再打开打印。')
    def start(self):
        if self.busy:return
        op=OPS[self.op.get()]
        if op=='pdf_edit':self.pdf_editor.save();return
        want_pdf=op.startswith('pdf_')
        files=[p for p in self.files if (p.suffix.lower()=='.pdf')==want_pdf]
        if not files:messagebox.showinfo('添加文件','请添加适用于当前功能的文件。');return
        try:
            opts=self.read_options()
            if not self.output.get().strip():raise ValueError('请选择输出目录')
            out=Path(self.output.get())/datetime.now().strftime('%Y%m%d_%H%M%S_%f'); out.mkdir(parents=True,exist_ok=False)
        except Exception as e:messagebox.showerror('设置有误',str(e));return
        self.progress.pack(fill='x',pady=(8,4));self.last_out=out;self.busy=True;self.cancel.clear();self.start_button.configure(state='disabled');self.progress['value']=0
        self.status.set(f'正在处理 {len(files)} 个文件；忽略不适用文件 {len(self.files)-len(files)} 个')
        def work():
            try:
                outputs,errors=run(files,op,out,opts,lambda a,b,c:self.events.put(('progress',a,b,c)),self.cancel)
                report={'operation':self.op_name,'inputs':[str(f) for f in files],'outputs':[str(p) for p in outputs],'errors':errors}
                (out/'处理报告.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                self.events.put(('done',len(outputs),errors))
            except Cancelled:self.events.put(('cancelled',))
            except Exception as e:self.events.put(('error',str(e)))
        self.op_name=self.op.get(); threading.Thread(target=work,daemon=True).start()
    def poll(self):
        try:
            while True:
                event=self.events.get_nowait()
                if event[0]=='tray_show':self.show_window();continue
                if event[0]=='tray_exit':
                    self.request_exit()
                    if self.exiting:return
                    continue
                if event[0]=='tray_ready':
                    self.tray_ready=True
                    if '--background' in sys.argv:self.withdraw()
                    continue
                if event[0]=='tray_error':self.show_window();self.status.set('托盘启动失败，窗口保持打开。');continue
                if event[0] in ('preview','preview_error','pdf_preview'):
                    self.accept_preview(event);continue
                if event[0]=='progress':self.progress['value']=event[1]*100/max(1,event[2]);self.status.set(f'{event[1]}/{event[2]} · {event[3]}')
                else:
                    self.busy=False;self.progress.pack_forget();self.start_button.configure(state='normal')
                    if event[0]=='done':
                        self.progress['value']=100;self.status.set(f'完成：生成 {event[1]} 个文件，失败 {len(event[2])} 个')
                        if event[2]:messagebox.showwarning('部分文件未完成','\n'.join(event[2][:8])+'\n完整记录见输出目录中的处理报告。')
                    elif event[0]=='cancelled':self.status.set('已取消；已经生成的文件保留在输出目录。')
                    else:self.status.set('任务未完成');messagebox.showerror('处理失败',event[1])
        except queue.Empty:pass
        if not self.busy and self.pending_paths:
            pending=self.pending_paths;self.pending_paths=[];self.add(pending)
        self.after(100,self.poll)
    def menu_settings(self):
        if not getattr(sys,'frozen',False):messagebox.showinfo('右键菜单','请在打包后的 EXE 中设置右键菜单。');return
        from toolbox import shell_menu
        win=tk.Toplevel(self);win.title('右键菜单 · 检测与修复');win.geometry('620x530');win.minsize(620,530)
        frame=ttk.Frame(win,padding=22);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='文件右键入口',font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Windows 11：右键图片或 PDF → 显示更多选项 → 使用 Toolbox 打开\n也可选中文件后按 Shift + F10。请不要右键文件夹或空白处。',wraplength=565).pack(anchor='w',pady=(12,8))
        ttk.Label(frame,text='多选文件也可通过“发送到 → Toolbox”一次导入。\n只修改当前用户的菜单，不改变文件默认打开方式。',wraplength=565,foreground='#6c7f90').pack(anchor='w',pady=(0,14))
        status=tk.StringVar()
        ttk.Label(frame,textvariable=status,wraplength=565,foreground='#138b80').pack(anchor='w',pady=8)
        ttk.Label(frame,text='当前程序位置',foreground='#6c7f90').pack(anchor='w',pady=(8,4))
        path=ttk.Entry(frame);path.insert(0,sys.executable);path.configure(state='readonly');path.pack(fill='x')
        ttk.Label(frame,text='先将 EXE 放到固定文件夹再添加入口。移动后请重新修复。\n修复后关闭已有右键菜单并重新打开；必要时重新打开资源管理器窗口。',wraplength=565,foreground='#6c7f90').pack(anchor='w',pady=10)
        def refresh():
            try:status.set(shell_menu.diagnose(sys.executable)[1])
            except Exception as e:status.set(f'无法完成检测：{e}')
        def change(install):
            try:
                if install:shell_menu.install(sys.executable)
                else:shell_menu.uninstall()
                refresh()
            except Exception as e:messagebox.showerror('设置未完成',str(e),parent=win);refresh()
        row=ttk.Frame(frame);row.pack(fill='x',pady=8)
        ttk.Button(row,text='添加 / 修复入口',command=lambda:change(True)).pack(side='left')
        ttk.Button(row,text='重新检测',command=refresh).pack(side='left',padx=10)
        ttk.Button(row,text='移除入口',command=lambda:change(False)).pack(side='right')
        refresh()
        from toolbox.desktop import autostart_enabled,set_autostart
        startup=tk.BooleanVar(value=autostart_enabled(sys.executable))
        def toggle_startup():
            try:set_autostart(sys.executable,startup.get())
            except Exception as e:startup.set(not startup.get());messagebox.showerror('设置未完成',str(e),parent=win)
        ttk.Checkbutton(frame,text='登录 Windows 后在托盘中启动',variable=startup,command=toggle_startup).pack(anchor='w',pady=(12,4))
        ttk.Label(frame,text='关闭主窗口会收起到托盘；彻底退出请使用托盘菜单。',foreground='#6c7f90').pack(anchor='w')
    def start_tray(self):
        try:
            import pystray
            from PIL import Image
            icon_image=Image.open(BASE/'assets/app.ico').copy()
            self.tray_icon=pystray.Icon('ShiguangToolbox',icon_image,'Toolbox',menu=pystray.Menu(
                pystray.MenuItem('打开工具箱',lambda:self.events.put(('tray_show',)),default=True),
                pystray.MenuItem('退出',lambda:self.events.put(('tray_exit',)))))
            def ready(icon):
                try:icon.visible=True;self.events.put(('tray_ready',))
                except Exception:self.events.put(('tray_error',))
            self.tray_icon.run_detached(setup=ready)
        except Exception:self.events.put(('tray_error',))
    def show_window(self):
        self.deiconify();self.lift()
        try:self.focus_force()
        except tk.TclError:pass
    def poll_instance(self):
        if self.exiting:return
        for message in self.broker.drain():
            if message['action']=='quit_target':
                if message.get('target')==str(Path(sys.executable).resolve()):self.request_exit()
            elif message['action']=='quit':self.request_exit()
            else:self.add(message['paths']);self.show_window()
            if self.exiting:return
        if not self.exiting:self.after(200,self.poll_instance)
    def close(self):
        if self.tray_ready:
            self.withdraw()
            return
        self.request_exit()
    def request_exit(self):
        if not self.pdf_editor.confirm_discard():return
        if self.busy:
            if messagebox.askyesno('任务进行中','取消任务并在处理停止后关闭？'):
                self.cancel.set();self.wait_close()
        else:self.destroy()
    def wait_close(self):
        if self.busy:self.after(150,self.wait_close)
        else:self.destroy()

    def destroy(self):
        self.exiting=True
        if self.tray_icon:
            self.tray_icon.stop();self.tray_icon=None
        if self.pdf_editor.model:self.pdf_editor.model.close();self.pdf_editor.model=None
        super().destroy()
        if self.broker:self.broker.close();self.broker=None

if __name__=='__main__':
    if '--smoke-test' in sys.argv:
        app=App();app.update();app.after(500,app.destroy);app.mainloop()
    elif '--register-menu' in sys.argv or '--unregister-menu' in sys.argv:
        from toolbox import shell_menu
        if '--register-menu' in sys.argv:shell_menu.install(sys.executable)
        else:shell_menu.uninstall()
    else:
        from toolbox.desktop import InstanceBroker
        broker=InstanceBroker()
        if '--quit' in sys.argv:
            if not broker.primary:broker.send(action='quit_target',target=sys.executable)
            broker.close()
        elif not broker.primary:
            broker.send([a for a in sys.argv[1:] if not a.startswith('--')]);broker.close()
        else:
            try:
                app=App(broker=broker,tray=True);app.mainloop()
            finally:broker.close()
