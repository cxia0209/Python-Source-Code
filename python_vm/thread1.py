import thread
import time

def threadProc():
    print 'sub thread id : ', thread.get_ident()
    while True:
        print 'Hello from sub thread ', thread.get_ident()
        time.sleep(1)

print 'main thread id : ', thread.get_ident()
thread.start_new_thread(threadProc,())

while True:
    print "Hello from main thread ",thread.get_ident()
    time.sleep(1)
