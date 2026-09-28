"""Shared image composition for exports and bounded-resolution previews."""
import math
import os
from pathlib import Path
from PIL import Image, ImageOps, ImageColor, ImageDraw, ImageFont

LIMIT = 100_000_000

def image_size(path):
    with Image.open(path) as im:
        w, h = im.size
        return (h, w) if im.getexif().get(274) in (5, 6, 7, 8) else (w, h)

def load_image(path, max_size=None):
    with Image.open(path) as src:
        if max_size:
            # JPEG can decode at reduced resolution; all formats are bounded before composition.
            src.draft('RGB', (max_size, max_size))
        im = ImageOps.exif_transpose(src)
        if max_size: im.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        return im.convert('RGBA')

def collage_plan(sizes, opts):
    if not sizes: raise ValueError('请先添加图片')
    n = len(sizes)
    cols = 1 if opts['layout'] == '纵向' else n if opts['layout'] == '横向' else (opts.get('columns', 0) or math.ceil(math.sqrt(n)))
    cols = min(n, max(1, cols)); rows = math.ceil(n / cols)
    cell_w = min(opts['width'] or 1200, max(w for w, h in sizes))
    fitted = []
    for w, h in sizes:
        factor = min(1, cell_w / w, cell_w * 2 / h)
        fitted.append((max(1, round(w * factor)), max(1, round(h * factor))))
    cell_h = max(h for w, h in fitted)
    gap, margin = opts.get('gap', 0), opts.get('margin', 0)
    if gap < 0 or margin < 0: raise ValueError('间距与外边距不能为负数')
    width = 2 * margin + cols * cell_w + (cols - 1) * gap
    height = 2 * margin + rows * cell_h + (rows - 1) * gap
    if width * height > LIMIT: raise ValueError('拼图超过 1 亿像素，请降低单格宽度或减少图片')
    boxes = []
    for i, (w, h) in enumerate(fitted):
        x = margin + (i % cols) * (cell_w + gap) + (cell_w - w) // 2
        y = margin + (i // cols) * (cell_h + gap) + (cell_h - h) // 2
        boxes.append((x, y, w, h))
    return (width, height), boxes

def render_collage(files, opts, preview_limit=None, check=lambda: None):
    sizes = []
    for path in files:
        check(); sizes.append(image_size(path))
    size, boxes = collage_plan(sizes, opts)
    color = ImageColor.getrgb(opts.get('background', '#ffffff'))
    scale = min(1, preview_limit / max(size)) if preview_limit else 1
    canvas = Image.new('RGB', (max(1, round(size[0] * scale)), max(1, round(size[1] * scale))), color)
    for path, (x, y, w, h) in zip(files, boxes):
        check()
        x1, y1 = round(x * scale), round(y * scale)
        x2, y2 = round((x+w) * scale), round((y+h) * scale)
        target = max(1, x2-x1), max(1, y2-y1)
        with load_image(path, max(target) if preview_limit else None) as im:
            tile = im.resize(target, Image.Resampling.LANCZOS)
            canvas.paste(tile, (x1, y1), tile)
            tile.close()
    return canvas, size

def transformed_size(size, op, opts):
    w, h = size
    if op == 'resize':
        tw, th = opts['width'], opts['height']
        if tw or th:
            if opts['keep_ratio']:
                factor = min(tw / w if tw else float('inf'), th / h if th else float('inf'))
                w, h = max(1, round(w * factor)), max(1, round(h * factor))
            else: w, h = tw or w, th or h
    elif op == 'crop':
        box = tuple(int(v.strip()) for v in opts['crop'].replace('，', ',').split(','))
        if len(box) != 4 or not (0 <= box[0] < box[2] <= w and 0 <= box[1] < box[3] <= h):
            raise ValueError('裁剪范围需为图片内部的 左,上,右,下 像素坐标')
        w, h = box[2]-box[0], box[3]-box[1]
    elif op == 'rotate_image' and opts['angle'] % 180: w, h = h, w
    if w * h > LIMIT: raise ValueError('目标尺寸超过 1 亿像素')
    return w, h

def render_single(path, op, opts, preview_limit=None):
    original = image_size(path); size = transformed_size(original, op, opts)
    # Crop the original coordinate rectangle first, so small crops retain detail.
    if op == 'crop':
        with Image.open(path) as src:
            im = ImageOps.exif_transpose(src).crop(tuple(int(v.strip()) for v in opts['crop'].replace('，', ',').split(','))).convert('RGBA')
        if preview_limit: im.thumbnail((preview_limit, preview_limit), Image.Resampling.LANCZOS)
    else:
        im = load_image(path, preview_limit)
    scale = min(1, preview_limit / max(size)) if preview_limit else 1
    if op == 'resize': im = im.resize((max(1, round(size[0]*scale)), max(1, round(size[1]*scale))), Image.Resampling.LANCZOS)
    elif op == 'rotate_image': im = im.rotate(-opts['angle'], expand=True)
    elif op == 'watermark':
        scale = im.width / original[0]
        layer = Image.new('RGBA', im.size)
        if opts['watermark_path']:
            mark = load_image(opts['watermark_path'])
            mw, mh = mark.size
            factor = min(1, max(1, original[0] // 3)/mw, max(1, original[1] // 3)/mh)
            mark = mark.resize((max(1, round(mw*factor*scale)), max(1, round(mh*factor*scale))), Image.Resampling.LANCZOS)
            mark.putalpha(mark.getchannel('A').point(lambda x: round(x * opts['opacity']/100)))
        else:
            if not opts['text']: raise ValueError('填写文字或选择水印图片后即可预览')
            font = ImageFont.truetype(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/msyh.ttc'), max(1, round(opts['font_size']*scale)))
            box = font.getbbox(opts['text']); pad = max(1, round(6*scale))
            mark = Image.new('RGBA', (box[2]-box[0]+pad*2, box[3]-box[1]+pad*2))
            alpha = round(255 * opts['opacity']/100)
            ImageDraw.Draw(mark).text((pad-box[0],pad-box[1]),opts['text'],font=font,fill=(255,255,255,alpha),stroke_width=max(1,round(scale)),stroke_fill=(0,0,0,alpha))
        inset = round(20*scale)
        x = max(0,(im.width-mark.width)//2) if opts['position']=='居中' else max(0,im.width-mark.width-inset)
        y = max(0,(im.height-mark.height)//2) if opts['position']=='居中' else max(0,im.height-mark.height-inset)
        layer.paste(mark,(x,y)); im = Image.alpha_composite(im,layer)
        mark.close();layer.close()
    return im, size
