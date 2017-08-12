import thread
import time

input = None
lock = thread.allocate_lock()

def threadProc():
    while True:
        print 'sub thread id : ',thread.get_ident()
        print 'sub thread %d wait lock...' % thread.get_ident()
        lock.acquire()
        print 'sub thread %d get lock...' % thread.get_ident()
        print 'sub thread %d receive input : %s' % (thread.get_ident(),input)
        print 'sub thread %d release lock...' % thread.get_ident()
        lock.release()
        print 'sub thread released'
        time.sleep(1)

thread.start_new_thread(threadProc,())
print 'main thread id : ', thread.get_ident()
while True:
    print 'main thread %d wait lock...' % thread.get_ident()
    lock.acquire()
    print 'main thread %d get lock...' % thread.get_ident()
    input = raw_input()
    print 'main thread %d release lock...' % thread.get_ident()
    lock.release()
    time.sleep(1)
