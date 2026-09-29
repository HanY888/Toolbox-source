import ctypes
from ctypes import wintypes
from PIL import Image

def capture_window(app,path):
    user=ctypes.windll.user32;gdi=ctypes.windll.gdi32
    user.GetDC.argtypes=[wintypes.HWND];user.GetDC.restype=wintypes.HDC
    user.ReleaseDC.argtypes=[wintypes.HWND,wintypes.HDC]
    user.PrintWindow.argtypes=[wintypes.HWND,wintypes.HDC,wintypes.UINT]
    gdi.CreateCompatibleDC.argtypes=[wintypes.HDC];gdi.CreateCompatibleDC.restype=wintypes.HDC
    gdi.CreateCompatibleBitmap.argtypes=[wintypes.HDC,ctypes.c_int,ctypes.c_int];gdi.CreateCompatibleBitmap.restype=wintypes.HBITMAP
    gdi.SelectObject.argtypes=[wintypes.HDC,wintypes.HGDIOBJ];gdi.SelectObject.restype=wintypes.HGDIOBJ
    gdi.DeleteObject.argtypes=[wintypes.HGDIOBJ];gdi.DeleteDC.argtypes=[wintypes.HDC]
    class Header(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('width',wintypes.LONG),('height',wintypes.LONG),('planes',wintypes.WORD),('bits',wintypes.WORD),('compression',wintypes.DWORD),('image_size',wintypes.DWORD),('x',wintypes.LONG),('y',wintypes.LONG),('used',wintypes.DWORD),('important',wintypes.DWORD)]
    gdi.GetDIBits.argtypes=[wintypes.HDC,wintypes.HBITMAP,wintypes.UINT,wintypes.UINT,ctypes.c_void_p,ctypes.POINTER(Header),wintypes.UINT]
    user.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT];user.GetAncestor.restype=wintypes.HWND
    hwnd=user.GetAncestor(app.winfo_id(),2);w,h=app.winfo_width(),app.winfo_height();dc=user.GetDC(hwnd);memory=gdi.CreateCompatibleDC(dc);bitmap=gdi.CreateCompatibleBitmap(dc,w,h);old=gdi.SelectObject(memory,bitmap)
    try:
        if not user.PrintWindow(hwnd,memory,3):raise OSError('PrintWindow unavailable')
        header=Header();header.size=ctypes.sizeof(Header);header.width=w;header.height=-h;header.planes=1;header.bits=32
        gdi.SelectObject(memory,old)
        data=ctypes.create_string_buffer(w*h*4)
        if not gdi.GetDIBits(memory,bitmap,0,h,data,ctypes.byref(header),0):raise OSError('GetDIBits unavailable')
        im=Image.frombuffer('RGB',(w,h),data,'raw','BGRX',0,1)
        if not im.getbbox():raise OSError('Window capture is blank')
        im.save(path)
    finally:
        gdi.SelectObject(memory,old);gdi.DeleteObject(bitmap);gdi.DeleteDC(memory);user.ReleaseDC(hwnd,dc)
