import tempfile
import unittest
from pathlib import Path
from toolbox.desktop import InstanceBroker

class InstanceTests(unittest.TestCase):
    def test_delivery_election_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            one=InstanceBroker(folder);two=InstanceBroker(folder)
            try:
                self.assertTrue(one.primary);self.assertFalse(two.primary)
                two.send(['测试 image.png','two.pdf'])
                two.send(action='show')
                messages=one.drain();self.assertEqual(len(messages),2)
                self.assertEqual(sum(len(m['paths']) for m in messages),2)
                self.assertEqual(one.drain(),[])
                self.assertFalse(list(Path(folder).glob('*.json')))
            finally:two.close();one.close()
            restarted=InstanceBroker(folder)
            try:self.assertTrue(restarted.primary)
            finally:restarted.close()
    def test_invalid_messages_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            one=InstanceBroker(folder)
            try:
                (Path(folder)/('a'*32+'.json')).write_text('bad json')
                (Path(folder)/'unrelated.json').write_text('do not remove')
                self.assertEqual(one.drain(),[])
                self.assertTrue((Path(folder)/'unrelated.json').exists())
            finally:one.close()
