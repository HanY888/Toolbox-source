import sys
import time
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from app import App
from toolbox.desktop import InstanceBroker

def wait(app,predicate,timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        app.update()
        if predicate():return
        time.sleep(.03)
    raise AssertionError('Lifecycle timeout')

with tempfile.TemporaryDirectory() as temp:
    folder=Path(temp);paths=[]
    for i in range(3):
        p=folder/f'{i}.png';Image.new('RGB',(100,100),'blue').save(p);paths.append(p)
    primary=InstanceBroker(folder/'inbox');app=App(broker=primary,tray=True)
    try:
        wait(app,lambda:app.tray_ready)
        assert app.tray_icon.visible
        app.close();app.update();assert app.state()=='withdrawn'
        secondary=InstanceBroker(folder/'inbox')
        try:assert not secondary.primary;secondary.send(paths[:2])
        finally:secondary.close()
        wait(app,lambda:len(app.files)==2 and app.state()!='withdrawn')
        app.busy=True;app.add(paths[2:]);assert len(app.files)==2;assert app.pending_paths
        app.busy=False;wait(app,lambda:len(app.files)==3)
        app.events.put(('tray_show',));wait(app,lambda:app.state()!='withdrawn')
        app.request_exit();assert app.exiting;assert app.tray_icon is None
        print('Tray visible, close-to-tray, single-instance wake, multi-file delivery, deferred imports, exit: PASS')
    finally:
        if not app.exiting:app.destroy()
