### 1.Python虚拟机中的控制流

#### a.Python虚拟机中的if控制流

> if_control.py

```python
a = 1
if a > 10:
    print "a > 10"
elif a <= -2
    print "a <= -2"
elif a != 1:
    print "a != 1"
elif a == 1:
    print "a == 1"
else:
    print "Unknown a"
```

```c
/*比较操作的定义*/
[object.h]
/* Rich comparison opcodes */
#define Py_LT 0
#define Py_LE 1
#define Py_EQ 2
#define Py_NE 3
#define PY_GT 4
#define Py_GE 5

[opcode.h]
enum cmp_op {
  PyCmp_LT = Py_LT,
  PyCmp_LE = Py_LE,
  .......
}
```

```c
[COMPARE_OP]

w = POP();
v = Top();
// PyIntObject对象的快速通道
if(PyInt_CheckExact(w) && PyInt_CheckExact(v)){
  register long a,b;
  register int res;
  a = PyInt_AS_LONG(v);
  b = PyInt_AS_LONG(w);
  //根据字节码指令的指令参数选择不同的操作
  switch (oparg) {
    case PyCmp_LT: res = a < b; break;
    case PyCmp_LE: res = a <= b; break;
    case PyCmp_EQ: res = a == b; break;
    case PyCmp_NE: res = a != b; break;
    case PyCmp_GT: res = a > b; break;
    case PyCmp_GE: res = a >= b; break;
    case PyCmp_IS: res = v == w; break;
    case PyCmp_IS_NOT: res = v!= w; break;
    default: goto slow_compare;
  }
  x = res ? Py_True : PyFalse;
  Py_INCREF(x);
}
else{
  //一般对象的慢速通道
  slow_compare:
      x = cmp_outcome(oparg,v,w);
}
Py_DECREF(v);
Py_INCREF(w);
//将比较结果压入到运行时栈中
SET_TOP(x);

if(x == NULL) break;
PREDICT(JUMP_IF_FALSE);
PREDICT(JUMP_IF_TRUE);


//慢速通道cmp_outcome
[ceval.c]
static PyObject* cmp_outcome(int op, register PyObject* v, register PyObject* w){
  int res = 0;
  switch (op) {
    case PyCmp_IS:
      res = (v == w);
      break;
    case PyCmp_IS_NOT:
      res = (v != w);
      break;
    case PyCmp_IN:
      res = PySequence_Contains(w,v);
      if(res < 0)
        return NULL;
      break;
    case PyCmp_NOT_IN:
      res = PySequence_Contains(w,v);
      if(res < 0)
        return NULL;
      res = !res;
      break;
    case PyCmp_EXC_MATCH:
      res = PyErr_GivenExceptionMatches(v,w);
      break;
    default:
      return PyObject_RichCompare(v,w,op);
  }
  v = res ? Py_True : PyFalse;
  Py_INCREF(v);
  return v;
}
```

> 比较操作的结果Python中的bool对象

```c
[boolobject.h]
PyIntObject _Py_ZeroStruct,_Py_TrueStruct;

#define PyFalse ((PyObject *) &_Py_ZeroStruct)
#define PyTrue  ((PyObject *) &_Py_TrueStruct)

[boolobject.c]
PyTypeObject PyBool_Type = {
  PyObject_HEAD_INIT(&PyType_Type)
  0,
  "bool",
  sizeof(PyIntObject),
  .....
}

/* The objects representing bool values False and True */
/* Named Zero for link-level compatibility */
PyIntObject _Py_ZeroStruct = {
  PyObject_HEAD_INIT(&PyBool_Type)
  0
};

PyIntObject _Py_TrueStruct = {
  PyObject_HEAD_INIT(&PyBool_Type)
  1
}
```

> 指令跳跃

```c
//PREDICT宏
[ceval.c]
#define PREDICT(op) if(*next_instr == op) goto PRED_##op

#define PREDICTED(op) PRED_##op: next_instr++

#define PREDICTED_WITH_ARG(op) PRED_##op: oparg = PEEKARG(); next_instr += 3

#define PEEKARG() ((next_instr[2]<<8) + next_instr[1])

```

```c
[ceval.c]
//PREDICT(JUMP_IF_FALSE)的情况
PREDICTED_WITH_ARG(JUMP_IF_FALSE);
case JUMP_IF_FALSE:
  //取出之前的比较操作结果
  w = TOP();
  //比较结果为True
  if(w == Py_True){
    PREDICT(POP_TOP);
    goto fast_next_opcode;
  }

  //比较操作结果为false,进行指令跳跃
  if( w == Py_False){
    JUMPBY(oparg);
    got fast_next_opcode;
  }

  err = PyObject_IsTrue(w);
  if ( err > 0)
    err = 0;
  else if (err == 0)
    JUMPBY(oparg);   // #define JUMPBY(x) (next_instr += (x))
  else
    break;
  continue;

//PREDICTED_WITH_ARG宏
PRED_JUMP_IF_FALSE:
  //取指令参数
  oparg = ((next_instr[2]<<8) + next_instr[1]);
  //调整next_instr
  next_instr += 3;
  case JUMP_IF_FALSE:
      ...

//PREDICT(JUMP_IF_FALSE)的情况
PREDICTED(POP_TOP);
case POP_TOP:
  v = POP();
  Py_DECREF(v);
  goto fast_next_opcode;
```

```c
//print操作
[JUMP_FORWARD]
  JUMPYBY(oparg)
  goto fast_next_opcode;
```

#### b.Python虚拟机中的for循环控制流

> 循环控制结构的初始化

```c
[SETUP_LOOP]
PyFrame_BlockSetup(f,opcode,INSTR_OFFSET() + oparg, STACK_LEVEL());
```

> PyTryBlock

```c
[frameobject.c]
void PyFrame_BlockSetup(PyFrameObject* f, int type, int handler, int level){
  PyTryBlock* b;
  b = &f->f_blockstack[f->f_iblock++];
  b->b_type = type;
  b->b_level = level;
  b->b_handler = handler;
}

//首次使用PyFrameObject中的f_blockstack
typedef struct _frame{
  .....
  int f_iblock; //index in f_blockstack, init = 0
  PyTryBlock f_blockstack[CO_MAXBLOCKS]; /* for try and loop blocks, CO_MAXBLOCKS = 20*/
}

//PyTryBlock定义
[frameobject.h]
typedef struct{
  int b_type;  /* what kind of block this is */
  int b_handler; /* where to jump to find handler */
  int b_level; /* value stack level to pop to */
}
```

```c
//调用PyFrame_BlockSetup地方:循环，异常机制
case SETUP_LOOP:
case SETUP_EXCEPT:
case SETUP_FINALLY:
    PyFrame_BlockSetup(f,opcode,INSTR_OFFSET() + oparg, STACK_LEVEL());
```
> list的迭代器

```c
[GET_ITER]
//从运行时栈获得PyListObject对象
v = TOP();
//获得PyListObject对象的iterator
x = PyObject_GetIter(v);
Py_DECREF(v);

if( x != NULL){
  //将PyListObject对象的iterator压入堆栈
  SET_TOP(x);
  PREDICT(FOR_ITER);
  continue;
}
STACKADJ(-1);
```

```c
//获得PyListObject迭代器
[object.h]
typedef PyObject *(*getiterfunc) (PyObject *);

[abstract.h]
PyObject* PyObject_GetIter(PyObject* o){
  PyTypeObject* t = o->ob_type;
  getiterfunc f = NULL;
  if(PyType_HasFeature(t,Py_TPFLAGS_HAVE_ITER))
    //获得对象中的tp_iter操作
    f = t->tp_iter;
  if(f == NUKK){
    ...
  }else{
    //通过tp_iter操作获得iterator
    PyObject* res = (*f)(o);
    ...
    return res;
  }
}

//list迭代器
typedef struct {
  PyObject_HEAD
  long it_index;
  PyListObject× it_seq;
}listiterobject;

//list迭代器对象类型
PyTypeObject PyListIter_Type = {
  PyObject_HEAD_INIT(&PyType_Type)
  0,   /* ob_size */
  "listiterator" /* tp_name */
  sizeof(listiterobject) /* tp_basicsize */
  0, /* tp_itemsize */
  /* methods */
  ...
  PyObject_SelfIter,  /* tp_iter */
  (iternextfunc)listiter_next, /* tp_iternext */
  0, /* tp_methods */
  ....
}

//list_iter
[listobjct.c]
static PyObject* list_iter(PyObject* seq){
  listiterobject* it;
  it = PyObject_GC_New(listiterobject, &PyListIter_Type);
  it->it_index = 0;
  Py_INCREF(seq);
  //这里seq就是之前创建的PyListObject对象
  it->it_seq = (PyListObject *)seq;
  _PyObject_GC_TRACK(it);
  return (PyObject *)it;
}
```

> 迭代控制

```c
[FOR_ITER]
PREDICTED_WITH_ARG(FOR_ITER);
case FOR_ITER:
  //从运行时栈的栈顶获得iterator对象
  v = TOP();
  //通过iterator对象获得集合中的下一个元素对象
  x = (*v->ob_type->tp_iternext)(v);
  if(x != NULL){
    //将获得的元素对象压入运行时栈
    PUSH(x);
    PREDICT(STORE_FAST);
    PREDICT(UNPACK_SEQUENCE);
    continue;
  }

  /* iterator ended normally */
  // x == NULL ,意味着iterator的迭代已经结束
  x = v = POP();
  Py_DECREF(v);
  JUMPBY(oparg);
  continue;

//PyListObject对象的迭代器
[listobjct.c]
static PyObject* listiter_next(listiterobject* it){
  PyListObject* seq;
  PyObject* item;

  //注意这里的seq是一个PyListObject对象
  seq = it->it_seq;
  if(it->it_index < PyList_GET_SIZE(seq)){
    //获得序号为it_index的元素对象
    item = PyList_GET_ITEM(seq,it->it_index);
    //调整it_index,使其指向下一个元素对象
    ++it->it_index;
    Py_INCREF(item);
    return item;
  }

  //迭代结束
  Py_DECREF(seq);
  it->it_seq = NULL;
  return NULL;
}
```

```c
//向后回退指令
[JUMP_ABSOLUTE]
JUMPTO(oparg);

#define JUMPTO(x) (next_instr = first_instr + (x))
```

> 终止迭代

```c
[POP_BLOCK]
{
  //将运行时栈恢复为迭代前的状态
  PyTryBlock* b = PyFrame_BlockPop(f);
  while(STACK_LEVEL() > b->b_level){
    v = POP();
    Py_DECREF(v);
  }
}

[frameobject.c]
PyTryBlock* PyFrame_BlockPop(PyFrameObject* f){
  PyTryBlock* b;
  //向f_blockstack中归还PyTryBlock
  b = &f->f_blockstack[--f->f_iblock]
  return b;
}
```

#### c.Python虚拟机中的while循环控制对象

> 研究对象---while_control.py

> 循环流程改变指令之continue

> 循环流程改变指令之break

```c
[BREAK_LOOP]
why = WHY_BREAK
goto fast_block_end;


[fast_block_end in PyEval_EvalFrameEx]
fast_block_end;
  while (why != WHY_NOT && f->f_iblock > 0) {
    //取得与当前while循环对应的PyTryBlock
    PyTryBlock *b = PyFrame_BlockPop(f);
    ...
    //将运行时栈恢复到while循环前的状态
    while(STACK_LEVEL() > b->b_level){
      v = POP();
      Py_XDECREF(v);
    }
    //处理break语义动作
    if(b->b_type == SETUP_LOOP && why === WHY_BREAK){
      why = WHY_NOT;
      JUMPTO(b->b_handler);
      break;
    }
    ....
  }

#define JUMPTO(x) (next_instr = first_instr + (x))
```

> Python 中的异常机制

>> Python 虚拟机自身抛出异常

```c
1/0

# LOAD_CONST 0
# LOAD_CONST 1
# BINARY_DIVIDE


[BINARY_DIVIDE]
w = POP();
v = TOP();
x = PyNumber_Divide(v,w);
Py_DECREF(v);
Py_DECREF(w);
SET_TOP(x);
if( x != NULL) continue;
break;

//int_classic_div
[intobject.c]
static PyObject* int_classic_div(PyIntObject* x, PyIntObject* y){
  long xi,yi;
  long d,m;
  //将x,y中维护的整数值转存到xi,yi中
  CONVERT_TO_LONG(x,xi);
  CONVERT_TO_LONG(y,yi);
  switch (i_divmod(xi,yi,&d,&m)) {
    case DIVMOD_OK:
      return PyInt_FromLong(d);
    case DIVMODE_OVERFLOW:
      return PyLong_Type.tp_as_number->nb_divide((PyObject *)x. (PyObject *)y);
    default:
      return NULL;
  }
}

[intobject.c]
/* return type of i_divmod */
enum divmod_result{
  DIVMOD_OK,  /* correct result */
  DIVMOD_OVERFLOW, /* Overflow, try again using longs */
  DIVMOD_ERROR /* Exception raised */
}

static enum divmod_result
i_divmod(register long x, register long y, long* p_xdivy, long* p_xmody){
  long xdivy,xmody;
  //抛出异常的瞬间
  if(y == 0){
    PyErr_SetString(PyExc_ZeroDivisionError, "integer division or modulo by zero");
    return DIVMOD_ERROR;
  }
  ...
}
```

```c
//PyExc_ZeroDivisionError
[pyerrors.h]
PyObject * PyExc_ZeroDivisionError;
```

>>  在线程状态对象中记录异常信息

```c
//PyErr_SetString->PyErr_SetObject->PyErr_Restore

[errors.c]
void PyErr_Restore(PyObject* type, PyObject* value, PyObject* traceback){
  PyThreadState* tstate = PyThreadState_GET();
  PyObject* oldtype,*oldvalue,*oldtraceback;
  //保存以前的异常信息
  oldtype = tstate->curexc_type;
  oldvalue = tstate->curexc_value;
  oldtraceback = tstate->curexc_traceback;
  //设置当前的异常信息
  tstate->curexc_type = type;
  tstate->curexc_value = value;
  tstate->curexc_traceback = traceback;
  //抛弃以前的异常信息
  Py_XDECREF(oldtype);
  Py_XDECREF(oldvalue);
  Py_XDECREF(oldtraceback);
}

void PyErr_SetObject(PyObject *exception, PyObject *value){
  Py_XINCREF(exception);
  Py_XINCREF(value);
  PyErr_Restore(exception,value,(PyObject *)NULL);
}

void PyErr_SetString(PyObject* exception, const char* string){
  PyObject* value = PyString_FromString(string);
  PyErr_SetObject(exception,value);
  Py_XDECREF(value);
}

```

```c
[pystate.h]
#define PyThreadState_GET() (_PyThreadState_Current)

[pystate.c]
PyThreadState* _PyThreadState_Current = NULL;
```

>> 展开栈帧

```c
//如何区分跳出switch块是  正常 or 异常
[ceval.c]
PyObject* PyEval_EvalFrameEx(PyFrameObject* f){
  ...
  for(;;){
    //巨大的switch语句
    if(why == WHY_NOT){
      if(err == 0 && x != NULL){
        continue; //没有异常发生，执行下一条字节码指令
      }
      //设置why，通知虚拟机，异常发生了
      why = WHY_EXCEPTION;
      x = Py_None;
      err = 0;
    }
    //尝试捕捉异常
    if( why != WHY_NOT)
      break;
    ....
  }
  ...
}
```

<p>如果函数调用时引发了异常</p>

```python
def h():
  1/0
def g():
  h()
def f():
  g()

f()
```

![fgh](/image/fgh.png)

```c
//异常输出信息呈现链装的结构，涉及 traceback 对象
[ceval.c]
PyObject* PyEval_EvalFrameEx(PyFrameObject* f){
  ....
  for(;;){
    //巨大的switch语句
    if( why == WHY_EXCEPTION){
      //创建traceback对象
      PyTraceBack_Here(f);
      if(tstate->c_tracefunc != NULL)
          call_exc_trace(tstate->c_tracefunc,tstate->c_traceobj,f);
    }
    ....
  }
....
}
```

```c
\\创建traceback对象
int PyTraceBack_Here(PyFrameObject* frame){
  //获得线程状态对象
  PyThreadState* tstate = frame->f_tstate;
  //保存线程状态对象中现在维护的traceback对象
  PyTraceBackObject* oldtb = (PyTraceBackObject *)tstate->curexc_traceback;
  //创建新的traceback对象
  PyTraceBackObject* tb = newtracebackobject(oldtb,frame);
  //将新的traceback对象交给线程状态对象
  tstate->curexc_traceback = (PyObject *)tb;
  Py_XDECREF(oldtb);
  return 0;
}
```

```c
//traceback对象定义
typedef struct _traceback{
  PyObject_HEAD
  struct _traceback* tb_next;
  struct _frame* tb_frame;
  int tb_lasti;
  int tb_lineno;
}PyTraceBackObject;
```

```c
[traceback.c]
PyTraceBackObject* newtracebackobject(PyTraceBackObject* next, PyFrameObject* frame){
  PyTraceBackObject* tb;
  //申请内存，创建对象
  tb = PyObject_GC_New(PyTraceBackObject,&PyTraceBack_Type);
  if(tb != NULL){
    //建立链表
    tb->tb_next = next;
    tb->tb_frame = frame;
    tb->tb_lasti = frame->f_lasti;
    tb->tb_lineno = PyCode_Addr2Line(frame->f_code,frame->f_lasti);
    PyObject_GC_Track(tb);
  }
  return tb;
}
```

```c
//回退
PyObject* PyEval_EvalFrameEx(PyFrameObject* f){
  ...
  for(;;){
    //尝试捕捉异常
    if(why != WHY_NOT)
        break
  }
  ...
  if( why != WHY_RETURN)
      retval = NULL; //利用retval通知前一个栈帧有异常出现

  ...

  //将线程对象中的活动栈帧设置为当前栈帧的上一个栈帧，完成栈帧回退的动作
  tstate->frame = f->f_back;
  return retval;
}
```

<p>栈帧展开</p>

![traceback](/image/traceback.png)


```c
//由于没有设置任何的异常捕捉代码,python虚拟机的执行流程会一直返回到PyRun_SimpleFileExFlags中
[pythonrun.c]
int PyRun_SimpleFileExFlags(FILE* fp, const char *filename,int closeit,... PyCompilerFlags* flags){
  ....
  //PyRun_FileExFlags将最终调用PyEval_EvalFrameEx
  v = PyRun_FileExFlags(fp,filename,Py_file_input,d,d,closeit,flags);
  if(v == NULL){
    PyErr_Print();
    return -1;
  }
  ....
  return 0;
}
```

> Python中的异常控制语义结构

>> 研究对象--exception_control.py

![finally_except](/image/finally_except.png)

```c
[RAISE_VARARGS]
u = v = w = NULL;
switch (oparg) {
  case 3:
    u = POP(); /* traceback */
  case 2:
    v = POP(); /* value */
  case 1:
    w = POP(); /* exc */
  case 0:
    why = do_raise(w,v,u);  //do_raise最终调用PyErr_Restore，返回一个WHY_EXCEPTION
    break;
  default:
    PyErr_SetString(PyExc_SystemError,"bad RAISE_VARARGS oparg");
    why = WHY_EXCEPTION;
    break;
}
break;
```

```c
PyObject* PyEval_EvalFrameEx(PyFrameObject* f){
  ....
  for(;;){
    ...
    while(why != WHY_NOT && f->f_iblock > 0){
      //获得SETIP_EXCEPT指令创建的PyTryBlock
      PyTryBlock* b = PyFrame_BlockPop(f);
      ...
      if(b->b_type == SETUP_FINALLY ||
        (b->b_type == SETUP_EXCEPT && why == WHY_EXCEPTION )){
          if(why == WHY_EXCEPTION){
            PyObject* exc, *val, *tb;
            //获得线程状态对象中的异常信息
            PyErr_Fetch(&exc,&val,&tb);
            PUSH(tb);
            PUSH(val);
            PUSH(exc);
          }else{
            .....
          }
          why = WHY_NOT;
          JUMPTO(b->b_handler);
          break;
        }
    }
  }
}

[errors.c]
void PyErr_Fetch(PyObject **p_type,PyObject **p_value, PyObject **p_traceback){
  PyThreadState* tstate = PyThreadState_GET();

  *p_type = tstate->curexc_type;
  *p_value = tstate->curexc_value;
  *p_traceback = tstate->curexc_traceback;

  tstate->curexc_type = NULL;
  tstate->curexc_value = NULL;
  tstate->curexc_traceback = NULL;
}
```

```c
//POP TOP  END_FINALLY 完成“重返异常状态”
[END_FINALLY]
v = POP();
if(PyExceptionClass_Check(v) || PyString_Check(v)){
  w = POP();
  u = POP();
  PyErr_Restore(v,w,u);
  why = WHY_RERAISE;
  break;
}

[POP_BLOCK]
{
  PyTryBlock* b = PyFrame_BlockPop(f);
  while(STACK_LEVEL() > b->b_level){
    v = POP();
    Py_DECREF(v);
  }
}
```

![except_flow](/image/except_flow.png)
