import threading
import time

class MyThread(threading.Thread):
    def run(self):
        while True:
            print 'sub thread : ',threading._get_ident()
            time.sleep(1)

mythread = MyThread()
mythread.start()

while True:
    print 'main thread : ', threading._get_ident()
    time.sleep(1)
