import sys
def get_current_frame():
    try:
        1/0
    except Exception,e:
        type,value,traceback = sys.exc_info()
        return traceback.tb_frame.f_back
print(get_current_frame())
