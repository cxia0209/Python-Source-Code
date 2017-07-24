try:
    raise Exception('i am an exception')
except Exception, e:
    print e
finally:
    print 'the finally code'
