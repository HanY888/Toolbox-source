import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import threading
import unittest
from PIL import Image, ImageChops
from toolbox.imaging import render_collage, render_single, collage_plan
from toolbox.engine import run
from toolbox.studio import DEFAULTS

class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.files=[]
        for name,size,color in [('a',(120,80),'red'),('b',(80,120),'blue'),('c',(100,100),(0,255,0,128))]:
            p=self.root/(name+'.png');Image.new('RGBA',size,color).save(p);self.files.append(p)
        self.opts=dict(DEFAULTS)
        for key in ['quality','target_kb','width','height','dpi','font_size','opacity','angle','columns','gap','margin']:self.opts[key]=int(self.opts[key])
        self.opts.update(format='PNG',keep_ratio=True,gap=10,margin=20,background='#123456')
    def tearDown(self):self.temp.cleanup()
    def test_collage_preview_matches_lossless_export(self):
        for layout in ['横向','纵向','宫格']:
            with self.subTest(layout=layout):
                self.opts['layout']=layout
                im,size=render_collage(self.files,self.opts,preview_limit=1800)
                outputs,errors=run(self.files,'stitch',self.root/'out',self.opts,lambda *a:None,threading.Event())
                self.assertEqual(errors,[])
                with Image.open(outputs[0]) as exported:
                    self.assertEqual(exported.size,size)
                    self.assertIsNone(ImageChops.difference(im,exported).getbbox())
                    self.assertEqual(exported.getpixel((0,0)),(18,52,86))
    def test_order_spacing_columns(self):
        self.opts.update(layout='宫格',columns=2)
        size,boxes=collage_plan([(120,80),(80,120),(100,100)],self.opts)
        self.assertEqual(size,(290,290))
        self.assertEqual(boxes[0],(20,40,120,80))
        im,_=render_collage(self.files,self.opts)
        swapped,_=render_collage(list(reversed(self.files)),self.opts)
        self.assertNotEqual(im.getpixel((80,80)),swapped.getpixel((80,80)))
        self.assertEqual(im.getpixel((145,80)),(18,52,86))
    def test_thumbnail_geometry_bounded(self):
        self.opts.update(layout='横向',margin=200,gap=70)
        im,size=render_collage(self.files,self.opts,preview_limit=64)
        self.assertLessEqual(max(im.size),64)
        self.assertLess(abs(im.width/im.height-size[0]/size[1]),.05)
    def test_transformed_previews_match_exports(self):
        self.opts.update(width=90,height=0,crop='10,10,70,60',text='预览',font_size=18)
        for op in ['resize','crop','rotate_image','watermark']:
            with self.subTest(op=op):
                im,size=render_single(self.files[0],op,self.opts,preview_limit=1800)
                outputs,errors=run([self.files[0]],op,self.root/'out',self.opts,lambda *a:None,threading.Event())
                self.assertEqual(errors,[])
                with Image.open(outputs[0]) as exported:
                    self.assertEqual(exported.size,size)
                    self.assertIsNone(ImageChops.difference(im.convert('RGB'),exported.convert('RGB')).getbbox())
    def test_bad_crop_and_large_collage(self):
        self.opts['crop']='0,0,999,999'
        with self.assertRaises(ValueError):render_single(self.files[0],'crop',self.opts,1800)
        self.opts.update(width=30000,layout='横向')
        with self.assertRaises(ValueError):collage_plan([(30000,30000)]*2,self.opts)

if __name__=='__main__':unittest.main(verbosity=2)
