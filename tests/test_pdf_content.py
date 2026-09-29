import tempfile
import unittest
from pathlib import Path
import pymupdf as fitz
from PIL import Image
from toolbox.pdf_document import PDFDocument

class ContentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.path=self.root/'source.pdf'
        self.image=self.root/'blue.png';Image.new('RGB',(50,50),'blue').save(self.image)
        with fitz.open() as doc:
            for i in range(3):
                p=doc.new_page(width=500,height=650)
                p.draw_rect((20,20,480,180),fill=(.9,.95,1),color=None)
                p.insert_text((40,70),'Original heading',fontsize=18)
                p.insert_text((40,110),'Keep this nearby text',fontsize=12)
            doc[0].insert_image((40,220,140,320),filename=str(self.image))
            doc.save(self.path)
        self.model=PDFDocument(self.path);self.before=self.path.read_bytes()
    def tearDown(self):
        self.model.close();self.assertEqual(self.before,self.path.read_bytes());self.temp.cleanup()
    def item(self):return next(o for o in self.model.objects(0) if o.get('text')=='Original heading')
    def test_replace_remove_original_keep_background_and_redo(self):
        self.model.replace_text(0,self.item(),'New heading',font='Arial Bold',size=20,color=(1,0,0))
        text=self.model.doc[0].get_text().replace('\xa0',' ');self.assertNotIn('Original',text);self.assertIn('New heading',text);self.assertIn('nearby',text)
        self.assertEqual(self.model.doc[0].get_pixmap().pixel(25,25),(229,242,255))
        spans=self.model.objects(0);new=next(o for o in spans if o.get('text','').replace('\xa0',' ')=='New heading')
        self.assertEqual(new['color'],0xff0000);self.assertAlmostEqual(new['size'],20)
        self.model.undo();self.assertIn('Original',self.model.doc[0].get_text().replace('\xa0',' '));self.model.redo();self.assertIn('New heading',self.model.doc[0].get_text().replace('\xa0',' '))
        output=self.root/'result.pdf';self.model.save(output)
        with fitz.open(output) as doc:self.assertNotIn('Original',doc[0].get_text().replace('\xa0',' '));self.assertIn('New heading',doc[0].get_text().replace('\xa0',' '))
    def test_chinese_fonts_search_and_rollback(self):
        self.model.replace_text(0,self.item(),'中文标题',size=18)
        self.assertIn('中文标题',self.model.doc[0].get_text().replace('\xa0',' '));self.assertEqual(len(self.model.search('nearby')),3)
        item=next(o for o in self.model.objects(0) if o.get('text')=='中文标题')
        with self.assertRaises(ValueError):self.model.replace_text(0,item,'Too long '*200)
        self.assertIn('中文标题',self.model.doc[0].get_text().replace('\xa0',' '))
        self.model.undo();self.assertIn('Original',self.model.doc[0].get_text().replace('\xa0',' '))
        with self.assertRaises(ValueError):self.model.replace_text(0,self.item(),'Collision',position=(40,110))
        self.assertIn('Original',self.model.doc[0].get_text().replace('\xa0',' '))
    def test_image_move_resize_replace_delete(self):
        item=next(o for o in self.model.objects(0) if o['kind']=='image')
        self.model.edit_image(0,item,(220,220,370,370))
        self.assertEqual(self.model.doc[0].get_pixmap().pixel(280,280),(0,0,255))
        self.assertEqual(self.model.doc[0].get_pixmap().pixel(80,280),(255,255,255))
        self.model.undo();item=next(o for o in self.model.objects(0) if o['kind']=='image')
        replacement=self.root/'red.png';Image.new('RGB',(50,50),'red').save(replacement)
        self.model.edit_image(0,item,replacement=replacement)
        self.assertEqual(self.model.doc[0].get_pixmap().pixel(80,280),(255,0,0))
    def test_annotations_batch_pages_extract(self):
        self.model.annotate(0,(35,50,200,75),'highlight')
        self.model.annotate(0,(220,200,260,250),'note','Review this')
        self.assertEqual(len(list(self.model.doc[0].annots())),2)
        self.model.pages_action([0,1],'rotate');self.assertEqual(self.model.doc[1].rotation,90)
        self.model.pages_action([0,1],'delete');self.assertEqual(len(self.model),1)
        self.model.undo();self.assertEqual(len(self.model),3)
        output=self.root/'extract.pdf';self.model.extract([0,2],output)
        with fitz.open(output) as doc:self.assertEqual(len(doc),2)
        with self.assertRaises(ValueError):self.model.pages_action([0,1,2],'delete')
    def test_font_changes_and_stale_selection_rejected(self):
        old=self.item();self.model.replace_text(0,old,'New heading',font='Arial Bold')
        with self.assertRaises(ValueError):self.model.replace_text(0,old,'Stale')
        item=next(o for o in self.model.objects(0) if 'New' in o.get('text',''))
        self.model.replace_text(0,item,'Italic heading',font='Arial Italic')
        item=next(o for o in self.model.objects(0) if 'Italic' in o.get('text',''))
        self.assertIn('Italic',item['font'])
        self.model.undo();self.model.replace_text(0,next(o for o in self.model.objects(0) if 'New' in o.get('text','')),'Branch')
        self.assertFalse(self.model.future)
    def test_shared_images_and_rotated_text_are_not_silently_changed(self):
        item=next(o for o in self.model.objects(0) if o['kind']=='image')
        self.model.doc[1].insert_image((20,220,120,320),xref=item['xref'])
        with self.assertRaises(ValueError):self.model.edit_image(0,item,delete=True)
        self.assertEqual(self.model.doc[0].get_pixmap().pixel(80,280),(0,0,255))
        self.model.rotate(0)
        with self.assertRaises(ValueError):self.model.replace_text(0,self.item(),'New')
