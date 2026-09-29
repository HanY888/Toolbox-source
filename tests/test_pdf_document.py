import tempfile
import unittest
from pathlib import Path
from PIL import Image
import pymupdf as fitz
from toolbox.pdf_document import PDFDocument,preview_file

class PDFEditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.source=self.root/'original.pdf'
        with fitz.open() as doc:
            for i in range(3):
                page=doc.new_page(width=400,height=600);page.insert_text((40,50),f'Original page {i+1}',fontsize=18)
            doc.save(self.source)
        self.original=self.source.read_bytes();self.model=PDFDocument(self.source)
    def tearDown(self):
        self.model.close();self.assertEqual(self.source.read_bytes(),self.original);self.temp.cleanup()
    def test_reorder_rotate_delete_undo(self):
        self.model.move(0,2);self.assertIn('page 1',self.model.doc[2].get_text())
        self.model.move(2,0);self.assertIn('page 1',self.model.doc[0].get_text())
        self.model.rotate(0);self.assertEqual(self.model.doc[0].rotation,90)
        self.model.undo();self.assertEqual(self.model.doc[0].rotation,0)
        self.model.delete(1);self.assertEqual(len(self.model),2)
        self.model.undo();self.assertEqual(len(self.model),3)
        self.model.delete(2);self.model.delete(1)
        with self.assertRaises(ValueError):self.model.delete(0)
    def test_overlays_save_and_rotation_coordinates(self):
        self.model.rotate(0)
        self.model.overlay(0,(30,80,400,145),'text',text='Toolbox 中文测试',font_size=20)
        self.assertEqual(self.model.doc[0].rect.width,600)
        self.assertIn('Toolbox',self.model.doc[0].get_text())
        self.model.overlay(0,(30,170,90,230),'cover',color=(1,0,0))
        image=self.root/'image.png';Image.new('RGB',(40,40),'blue').save(image)
        self.model.overlay(0,(150,170,210,230),'image',image=image)
        output=self.root/'edited.pdf';self.model.save(output);self.assertFalse(self.model.dirty)
        with fitz.open(output) as doc:
            pix=doc[0].get_pixmap();self.assertEqual(pix.pixel(60,200),(255,0,0));self.assertEqual(pix.pixel(180,200),(0,0,255))
            self.assertIn('Original page 1',doc[0].get_text())
        self.model.undo();self.assertTrue(self.model.dirty)
        with self.assertRaises(ValueError):self.model.save(self.source)
    def test_insert_preview_and_transaction(self):
        image=self.root/'image.png';Image.new('RGB',(80,50),'green').save(image)
        self.model.insert([self.source,image],0);self.assertEqual(len(self.model),7)
        self.model.undo();self.assertEqual(len(self.model),3)
        before=self.model.doc[0].get_text()
        with self.assertRaises(ValueError):self.model.overlay(0,(1,1,4,4),'text',text='Too much text',font_size=100)
        self.assertEqual(self.model.doc[0].get_text(),before)
        im,size,index,total=preview_file(self.source,999,200)
        self.assertEqual((index,total),(2,3));self.assertLessEqual(max(im.size),200)
