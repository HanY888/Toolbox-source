"""Exercise the real desktop task queue, then capture this app's window."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import time
from PIL import Image,ImageGrab
from app import App

root=Path(__file__).resolve().parents[1]/'verification';root.mkdir(exist_ok=True)
sample=root/'示例图片.png';Image.new('RGB',(1600,1000),'#219cba').save(sample)
app=App();app.output.set(str(root/'outputs'));app.add([sample]);app.vars['target_kb'].set('20');app.start()
deadline=time.monotonic()+30
while app.busy and time.monotonic()<deadline:
    app.update();time.sleep(.05)
assert not app.busy,'Task did not finish'
assert list(app.last_out.glob('*.jpg')),'No output from UI task'
app.update();app.lift();app.update();time.sleep(.5)
try:
    ImageGrab.grab(bbox=(app.winfo_rootx(),app.winfo_rooty(),app.winfo_rootx()+app.winfo_width(),app.winfo_rooty()+app.winfo_height())).save(root/'app-preview.png')
except OSError:
    print('Screen capture unavailable in this desktop session')
from toolbox.engine import OPS
for operation in OPS:
    app.op.set(operation);app.update_fields();app.update()
    assert app.progress.winfo_y()+app.progress.winfo_height()<app.winfo_height(),'Progress clipped'
app.destroy()
print('Desktop queue integration passed')
