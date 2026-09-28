import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import threading
import unittest
import hashlib
from PIL import Image
import fitz
from toolbox.engine import run, pages, Cancelled

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.image=self.root/'透明.png';Image.new('RGBA',(1200,800),(20,130,210,140)).save(self.image)
        self.pdf=self.root/'文档.pdf'
        with fitz.open() as doc:
            for i in range(3):doc.new_page().insert_text((72,72),f'Page {i+1}')
            doc.save(self.pdf)
        self.hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in [self.image,self.pdf]}
        self.opts=dict(quality=85,target_kb=8,format='PNG',width=300,height=0,dpi=96,text='测试',font_size=36,opacity=60,position='居中',watermark_path='',crop='0,0,100,100',angle=90,pages='',layout='宫格',pdf_mode='无损压缩（保留文字）',keep_ratio=True)
    def tearDown(self):
        for p,h in self.hashes.items():self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),h)
        self.temp.cleanup()
    def process(self,op,files=None):
        result,errors=run(files or [self.pdf if op.startswith('pdf_') else self.image],op,self.root/'out',self.opts,lambda *args:None,threading.Event())
        self.assertEqual(errors,[]);self.assertTrue(result)
        return result
    def test_image_operations(self):
        for op in ['compress','convert','resize','watermark','crop','rotate_image','rename','stitch']:
            with self.subTest(op=op):
                p=self.process(op)[0]
                with Image.open(p) as im:
                    im.load()
                    if op=='compress':self.assertLessEqual(p.stat().st_size,8192)
                    if op=='resize':self.assertEqual(im.size,(300,200))
                    if op=='crop':self.assertEqual(im.size,(100,100))
                    if op=='rotate_image':self.assertEqual(im.size,(800,1200))
    def test_pdf_operations(self):
        for op in ['pdf_compress','pdf_merge','pdf_split','pdf_extract','pdf_rotate','pdf_images','images_pdf']:
            with self.subTest(op=op):
                files=[self.pdf,self.pdf] if op=='pdf_merge' else None
                results=self.process(op,files)
                if op=='pdf_images':
                    self.assertEqual(len(results),3)
                else:
                    with fitz.open(results[0]) as doc:
                        if op=='pdf_merge':self.assertEqual(len(doc),6)
                        if op=='pdf_rotate':self.assertEqual(doc[0].rotation,90)
                        if op=='pdf_compress':self.assertIn('Page 1',doc[0].get_text())
        self.opts['pages']='2';p=self.process('pdf_delete')[0]
        with fitz.open(p) as doc:self.assertEqual(len(doc),2);self.assertIn('Page 3',doc[1].get_text())
        self.opts['pages']='3,1';p=self.process('pdf_extract')[0]
        with fitz.open(p) as doc:self.assertIn('Page 3',doc[0].get_text())
        self.opts['pages']='';self.opts['pdf_mode']='扫描件压缩（页面转图片）';p=self.process('pdf_compress')[0]
        with fitz.open(p) as doc:self.assertEqual(len(doc),3);self.assertTrue(doc[0].get_images())
    def test_errors_and_cancel(self):
        with self.assertRaises(ValueError):pages('4',3)
        with self.assertRaises(ValueError):pages('3-1',3)
        self.opts['pages']='1-3'
        outputs,errors=run([self.pdf],'pdf_delete',self.root/'bad',self.opts,lambda *a:None,threading.Event())
        self.assertFalse(outputs);self.assertEqual(len(errors),1)
        cancel=threading.Event();cancel.set()
        with self.assertRaises(Cancelled):run([self.image],'convert',self.root/'cancel',self.opts,lambda *a:None,cancel)
    def test_existing_output_preserved(self):
        p=self.process('convert')[0];before=p.read_bytes();q=self.process('convert')[0]
        self.assertNotEqual(p,q);self.assertEqual(p.read_bytes(),before)

if __name__=='__main__':unittest.main(verbosity=2)
