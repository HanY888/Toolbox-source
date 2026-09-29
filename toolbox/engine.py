from pathlib import Path
from contextlib import nullcontext
from io import BytesIO
import math
import os
import pymupdf as fitz
from PIL import Image, ImageOps, ImageDraw, ImageFont
from .imaging import render_collage, render_single

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}
OPS = {
    '图片压缩 / 指定大小': 'compress', '图片格式转换': 'convert',
    '图片调整尺寸 / DPI': 'resize', '图片文字 / 水印': 'watermark',
    '图片裁剪': 'crop', '图片旋转': 'rotate_image', '图片批量重命名': 'rename',
    '多图拼接': 'stitch', '图片转 PDF / 多图打印': 'images_pdf',
    'PDF 压缩': 'pdf_compress', 'PDF 转图片': 'pdf_images',
    'PDF 合并': 'pdf_merge', 'PDF 拆分': 'pdf_split',
    'PDF 提取页面': 'pdf_extract', 'PDF 删除页面': 'pdf_delete', 'PDF 页面旋转': 'pdf_rotate', 'PDF 编辑': 'pdf_edit',
}

class Cancelled(Exception):
    pass

def pages(spec, count):
    if not spec.strip():
        return list(range(count))
    result = []
    for token in spec.replace('，', ',').split(','):
        pair = token.strip().split('-')
        if len(pair) > 2:
            raise ValueError('页码格式应为 1,3-5')
        a = int(pair[0]); b = int(pair[-1])
        if not 1 <= a <= b <= count:
            raise ValueError(f'页码必须在 1 到 {count} 之间，且范围不能倒序')
        for p in range(a - 1, b):
            if p not in result:
                result.append(p)
    return result

def rgb(im):
    out = Image.new('RGB', im.size, 'white')
    if im.mode in ('RGBA', 'LA') or 'transparency' in im.info:
        rgba = im.convert('RGBA'); out.paste(rgba, mask=rgba.getchannel('A'))
    else:
        out.paste(im.convert('RGB'))
    return out

def read_image(path):
    with Image.open(path) as source:
        return ImageOps.exif_transpose(source).copy()

def save_image(im, path, opts):
    suffix = path.suffix.lower()
    if suffix in ('.jpg', '.jpeg', '.bmp'):
        im = rgb(im)
    im.save(path, quality=opts['quality'], optimize=True, dpi=(opts['dpi'], opts['dpi']))

def jpeg_bytes(im, quality):
    buff = BytesIO(); rgb(im).save(buff, 'JPEG', quality=quality, optimize=True)
    return buff.getvalue()

def compress_image(im, target, quality):
    data = jpeg_bytes(im, quality)
    if target <= 0 or len(data) <= target:
        return data
    for _ in range(30):
        lo, hi, best = 10, quality, None
        while lo <= hi:
            q = (lo + hi) // 2; current = jpeg_bytes(im, q)
            if len(current) <= target:
                best = current; lo = q + 1
            else:
                hi = q - 1
        if best is not None:
            return best
        if min(im.size) <= 1:
            break
        im = im.resize((max(1, int(im.width * .8)), max(1, int(im.height * .8))), Image.Resampling.LANCZOS)
    raise ValueError('目标大小太小，无法生成有效图片，请提高目标大小')

def save_pdf(doc, path):
    doc.save(path, garbage=4, deflate=True)

def run(files, op, out, opts, progress, cancel):
    from .pdf_document import PDF_LOCK
    if op.startswith('pdf_') or op=='images_pdf':
        with PDF_LOCK:return _run(files,op,out,opts,progress,cancel)
    return _run(files,op,out,opts,progress,cancel)

def _run(files, op, out, opts, progress, cancel):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    outputs, failures = [], []
    def check():
        if cancel.is_set():
            raise Cancelled()
    def unique(name):
        p = out / name; n = 2
        while p.exists():
            p = out / f'{Path(name).stem}_{n}{Path(name).suffix}'; n += 1
        return p
    def report(i, text):
        check(); progress(i, max(1, len(files)), text)
    def commit(doc, name):
        p = unique(name); save_pdf(doc, p); outputs.append(p)

    if op in ('pdf_merge', 'images_pdf', 'stitch'):
        if op == 'stitch':
            canvas, _ = render_collage(files, opts, check=check)
            try:
                p = unique('拼接.' + opts.get('format', 'JPG').lower())
                save_image(canvas, p, opts); outputs.append(p)
            finally:
                canvas.close()
        else:
            with fitz.open() as doc:
                for i, f in enumerate(files):
                    report(i, f.name)
                    if op == 'pdf_merge':
                        with fitz.open(f) as src:
                            if src.needs_pass: raise ValueError(f'{f.name} 已加密，请先解密')
                            doc.insert_pdf(src)
                    else:
                        with read_image(f) as im:
                            page = doc.new_page(width=595, height=842)
                            page.insert_image(fitz.Rect(24, 24, 571, 818), stream=jpeg_bytes(im, opts['quality']), keep_proportion=True)
                check(); commit(doc, '合并.pdf' if op == 'pdf_merge' else '图片打印.pdf')
        progress(len(files), len(files), '完成')
        return outputs, failures

    for i, f in enumerate(files):
        report(i, f.name)
        try:
            if op.startswith('pdf_'):
                with fitz.open(f) as doc:
                    if doc.needs_pass: raise ValueError('加密 PDF 暂不支持，请先解密')
                    selected = pages(opts['pages'], len(doc))
                    if op == 'pdf_images':
                        for j in selected:
                            check(); p = unique(f'{f.stem}_{j+1:03}.png')
                            doc[j].get_pixmap(dpi=opts['dpi'], alpha=False).save(p); outputs.append(p)
                    elif op == 'pdf_split':
                        for j in selected:
                            check()
                            with fitz.open() as part:
                                part.insert_pdf(doc, from_page=j, to_page=j); commit(part, f'{f.stem}_{j+1:03}.pdf')
                    elif op == 'pdf_compress' and opts['pdf_mode'] == '扫描件压缩（页面转图片）':
                        with fitz.open() as result:
                            for page in doc:
                                check(); pix = page.get_pixmap(dpi=opts['dpi'], alpha=False)
                                dest = result.new_page(width=page.rect.width, height=page.rect.height)
                                dest.insert_image(dest.rect, stream=pix.tobytes('jpeg', jpg_quality=opts['quality']))
                            commit(result, f'{f.stem}_扫描压缩.pdf')
                    else:
                        if op == 'pdf_extract': doc.select(selected)
                        elif op == 'pdf_delete':
                            if not opts['pages'].strip(): raise ValueError('请填写要删除的页码')
                            keep = [j for j in range(len(doc)) if j not in selected]
                            if not keep: raise ValueError('不能删除全部页面')
                            doc.select(keep)
                        elif op == 'pdf_rotate':
                            for j in selected: doc[j].set_rotation((doc[j].rotation + opts['angle']) % 360)
                        check(); commit(doc, f'{f.stem}_处理.pdf')
            elif op == 'rename':
                import shutil
                prefix = opts['text'] or '图片'
                if any(c in prefix for c in '<>:"/\\|?*') or prefix in ('.', '..'):
                    raise ValueError('名称包含 Windows 不允许的字符')
                p = unique(f'{prefix}_{i+1:03}{f.suffix}'); shutil.copy2(f, p); outputs.append(p)
            else:
                with (nullcontext(None) if op in ('resize', 'crop', 'rotate_image', 'watermark') else read_image(f)) as source:
                    im = source
                    ext = '.' + opts['format'].lower()
                    if op == 'compress':
                        p = unique(f'{f.stem}_压缩.jpg'); p.write_bytes(compress_image(im, int(opts['target_kb'] * 1024), opts['quality']))
                    else:
                        if op in ('resize', 'crop', 'rotate_image', 'watermark'):
                            im, _ = render_single(f, op, opts)
                        p = unique(f'{f.stem}_处理{ext}'); save_image(im, p, opts)
                        if im is not source: im.close()
                    outputs.append(p)
        except Cancelled:
            raise
        except Exception as e:
            failures.append(f'{f.name}: {e}')
        progress(i+1, len(files), f.name)
    return outputs, failures
