### 1.Python虚拟机框架

#### a.Python虚拟机的执行环境

> x86 运行可执行文件的过程

![x86_stack](/image/x86_stack.png)

*PyCodeObject对象没有包含也不可能包含程序运行的动态信息--执行环境*

> Python源码中的PyFrameObject

```c
[frameobject.h]
typedef struct _frame{
  PyObject_VAR_HEAD //说明PyFrameObject是变长对象,因为不同的Code Block在执行时所需的空间的大小是不同的
  struct _frame* f_back;  /* 执行环境链上的前一个frame */
  PyCodeObject* f_code; /* PyCodeObject对象 */
  PyObject* f_builtins; /* builtin名字空间 */
  PyObject* f_globals; /* global名字空间 */
  PyObject* f_locals; /* local名字空间 */
  PyObject** f_valuestack; /* 运行时栈的栈底位置 */
  PyObject** f_stacktop; /* 运行时栈的栈顶位置 */
  ....
  int f_lasti; //上一条字节码指令在f_code中的偏移位置
  int f_lineno; //当前字节码对应的源代码行

  ....

  //动态内存，维护(局部变量 + cell对象集合 + free对象集合 + 运行时栈)所需要的空间
  PyObject* f_localsplus[1];
} PyFrameObject;
```

<p>python运行时栈指运算时所需要的内存空间</p>

![Python_runtime](/image/Python_runtime.png)

> PyFrameObject中的动态内存空间

```c
[frameobject.c]
PyFrameObject* PyFrame_New(PyThreadState* tstate, PyCodeObject* code, PyObject* globals, PyObject* locals){
  PyFrameObject* f;
  Py_ssize_t extras,ncells,nfrees,i;
  ncells = PyTuple_GET_SIZE(code->co_cellvars);
  nfrees = PyTuple_GET_SIZE(code->co_freevars);
  //四部分构成了PyFrameObject维护的动态内存区,其大小由extras确定
  extras = code->co_stacksize + code->co_nlocals + ncells + nfrees;
  f = PyObject_GC_NewVar(PyFrameObject, &PyFrame_Type,extras);
  //计算初始化时运行时栈的栈顶
  extras = code->co_nlocals + ncells + nfrees;
  //f_valuestack维护运行时栈的栈底，f_stacktop维护运行时栈的栈顶
  f->f_valuestack = f->f_localsplus + extras;
  f->f_stacktop = f->f_valuestack;
  return f;
}
```

![pyframeobject](/image/pyframeobject.png)

> Python中访问PyFrameObject对象

```python
sys._getframe();
```

#### b.名字、作用域和名字空间

> Python程序的基础结构--module

<p>module：1.代码复用 2.划分名字空间</p>

<p>module加载方法：1.import动态加载 2.主module加载</p>

> 约束与名字空间

<p>(name,obj)关联关系称为*约束*, *约束*的容身之处就是名字空间</p>

<p>*属性引用*是另一个名字空间中的名字，是一个访问对象属性的动作</p>

> 作用域与名字空间

<p>Python具有静态作用域，因为约束在文本中的位置不是在运行时动态决定的</p>

<p>Python支持嵌套作用域</p>

> LGB规则

<p>名字引用动作沿着local作用域、global作用域、builtin作用域的顺序查找名字对应的约束</p>

![lgb](/image/lgb.png)

> LEGB规则(E : enclosing)

```python
a = 1
def f():
  a = 2
  def g():
    print a
  return g

func = f(
func()
)
```

![enclosing](/image/enclosing.png)

> global 表达式

```python
//错误案例

a = 1

def g():
  print a

def f():
  print a
  a = 2
  print a

g()
f()

>> "local variable 'a' referenced before assignment"
```

> 属性引用与名字引用

#### c.Python虚拟机的运行框架

```c
/*Python虚拟机执行字节码指令的整体架构*/
[ceval.c]
/* Interpreter main loop */
PyObject* PyEval_EvalFrameEx(PyFrameObject* f,int throwflag){
  ...
  why = WHY_NOT;
  ...
  for(;;){
    ....
    fast_next_opcode:
        f->f_lasti = INSTR_OFFSET();
        //获得字节码指令
        opcode = NEXTOP();
        oparg = 0;
        //如果指令需要参数，获得指令参数
        if(HAS_ARG(opcode))
          oparg = NEXTARG();
    dispatch_opcode:
        switch (opcode) {
          case NOP:
            goto fast_next_opcode;
          case LOAD_FAST:
            ...
        }
  }
}

/* status code for main loop (reason) for stack unwind */
enum why_code{
  WHY_NOT = 0x0001, /* No error */
  WHY_EXCEPTION =  0x0002  /* Exception occurred */
  WHY_RERAISE = 0x0004 /* Exception re-raised by 'finally' */
  WHY_RETURN = 0x0008  /* 'return' statement */
  WHY_BREAK = 0x0010 /* 'break' statement */
  WHY_CONTINUE = 0x0020 /* 'continue' statement */
  WHY_YIELD = 0x0040 /* yield operator */
};
```

#### d.Python运行时环境初探

<p>PyThreadState实现线程,PyInterpreterState实现进程</p>

```c
[pystate.h]
typedef struct _is{
  struct _is* next;
  struct _ts* tstate_head; //模拟进程环境中的线程集合

  PyObject* modules;
  PyObject* sysdict;
  PyObject* builtins;
  ...
} PyInterpreterState;

typedef struct _ts{
  struct _ts* next;
  PyInterpreterState* iterp;
  struct _frame* frame; //模拟线程中的函数调用堆栈
  int recursion_depth;
  ...
  PyObject* dict;
  ...
  long thread_id;
} PyThreadState;

```

```c
//当Python虚拟机开始执行时，会将当前线程状态对象中的frame设置为当前的执行环境
[ceval.c]
PyObject* PyEval_EvalFrameEx(PyFrameObject* f, int throwflag){
  ...
  //通过PyThreadState_GET获得当前活动线程对应的线程状态对象
  PyThreadState* tstate = PyThreadState_GET();
  ...
  //设置线程状态对象中的frame
  tstate->frame = f;
  co = f->f_code;
  name = co->co_names;
  consts = co->co_consts;
  ...

  //虚拟机主循环
  for(;;){
    ...
  }
}

//建立新的PyFrameObject对象时，则从当前线程的状态对象中取出旧的frame，建立PyFrameObject链表
PyFrameObject* PyFrame_New(PyThreadState* tstate, PyCodeObject* code, PyObject* globals, PyObject* locals){
  //从PyThreadState中获得当前线程的当前执行环境
  PyFrameObject* back = tstate->frame;
  PyFrameObject* f;
  ....
  //创建新的执行环境
  f = PyObject_GC_Resize(PyFrameObject,f,extras);
  ....
  //链接当前执行环境
  f->f_back = back;
  f->f_tstate = tstate;
  ...
  return f;
}
```

![runtime](/image/runtime.png)
