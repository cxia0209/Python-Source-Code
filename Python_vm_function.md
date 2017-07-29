### 1.Python 虚拟机中的函数机制

#### a.PyFunctionObject对象

```c
[funcobject.h]
typedef struct {
  PyObject_HEAD
  PyObject* func_code;  //对应函数编译的PyCodeObject对象
  PyObject* func_globals;  //函数运行时的global名字空间
  PyObject* func_defaults; //默认参数(tuple或NULL)
  PyObject* func_closure; // NULL or a tuple of cell objects，用于实现closure
  PyObject* func_doc; //函数的文档
  PyObject* func_name; //函数名称,函数的__name__属性,(PyStringObject)
  PyObject* func_dict; //函数的__dict__属性(PyDictObject或NULL)
  PyObject* func_weakreflist;
  PyObject* func_module; //函数的__module__,可以是任何对象
} PyFunctionObject;
```

![pyc_funobj](/image/pyc_funobj.png)


#### b.无参函数调用

> 函数对象的创建

```python
//func_0.py
def f():
  print "Function"

f()
```

```c
[MAKE_FUNCTION]
v = POP(); //获得与函数f对应的PyCodeObject对象
x = PyFunction_New(v,f->f_globals);
Py_DECREF(v);
...//处理函数参数的默认值
PUSH(x);
break;
```

```c
[function.c]
PyObject* PyFunction_New(PyObject* code,PyObject* globals){
  //申请PyFunctionObject对象所需的内存空间
  PyFunctionObject* op = PyObject_GC_New(PyFunctionObject,&PyFunction_Type);
  static PyObject* __name__ = 0;
  if(op != NULL){
    //初始化PyFunctionObject对象的各个域
    ...
    //设置PyCodeObject对象
    op->func_code = code;
    //设置global名字空间
    op->func_globals = globals;
    //设置函数名
    op->func_name = ((PyCodeObject *)code)->co_name;
    //函数中的常量对象表
    consts = ((PyCodeObject *)code)->co_consts;
    //函数的文档
    if(PyTuple_Size(consts) >= 1){
      doc = PyTuple_GetItem(consts,0);
      if(!PyString_Check(doc) && !PyUnicode_Check(doc))
          doc = PyNone;
    }
    else
        doc = PyNone;
    .....
  }else{
    return NULL;
  }

  return (PyObject *)op;

}
```

> 函数调用

```c
[CALL_FUNCTION]
PyObject** sp;
sp = stack_pointer;
x = call_function(&sp,oparg);
stack_pointer = sp;
PUSH(x);
if(x != NULL)
    continue;
break;

//call_function
[ceval.c]
static PyObject* call_function(PyObject** pp_stack,int oparg){
  //处理函数参数信息
  int na = oparg & 0xff;
  int nk = (oparg>>8) & 0xff;
  int n = na + 2*nk;   //由于位置参数会导致一条LOAD_CONST指令，而键参数会导致两条LOAD_CONST指令,所以n=na+2*nk
  //获得PyFunctionObject对象
  PyObject** pfunc = (*pp_stack) - n - 1;
  PyObject* func = *pfunc;
  PyObject *x, *w;

  if(PyCFunction_Check(func) && nk == 0){
    ...
  }else{
    if(PyMethod_Check(func) && PyMethod_GET_SELF(func) != NULL){
      ...
    }
    //对PyFunctionObject对象进行调用
    if(PyFunction_Check(func))
      x = fast_function(func,pp_stack,n,na,nk);
    else
      x = do_call(func,pp_stack,na,nk);
    ....
  }
  ....
  return x;
}
```

```c
//fast_function
[ceval.c]
static PyObject* fast_function(PyObject* func, PyObject*** pp_stack, int n, int na, int nk){
  PyCodeObject* co = (PyCodeObject *)PyFunction_GET_CODE(func);
  PyObject* globals = PyFunction_GET_GLOBALS(func);
  PyObject* argdefs = PyFunction_GET_DEFAULTS(func);
  PyObject** d = NULL;
  int nd = 0;

  //一般函数的快速通道
  if(argdefs == NULL && co->co_argcount == n && nk =0 && co->co_flags == (CO_OPTIMIZED | CO_NEWLOCALS | CO_NOFREE)){
    PyFrameObject* f;
    PyObject* retval = NULL;
    PyThreadState* tstate = PyThreadState_GET();
    PyObject **fastlocals, **stack;
    int i ;
    f = PyFrame_New(tstate,co,globals,NULL);
    ...
    retval = PyEval_EvalFrameEx(f,0);  //PyFunctionObject主要对字节码指令和global名字空间进行打包和运输
    ...
    return retval;
  }

  if(argdefs != NULL){
    d = &PyTuple_GET_ITEM(argdefs,0);
    nd = ((PyTupleObject *)argdefs)->ob_size;
  }

  return PyEval_EvalCodeEx(co,globals,(PyObject *)NULL,(**pp_stack) - n, na, (*pp_stack) - 2*nk, nk ,d , nd, PyFunction_GET_CLOSURE(func));
}
```

#### c.函数执行时的名字空间

![func_global](/image/func_global.png)

![local_global](/image/local_global.png)

#### d.函数参数的实现

> 参数类别

>> 位置参数(positional argument): f(a,b)、a和b被称为位置参数

>> 键参数(key argument) : f(a,b,name='Python')，其中的name='Python'被称为键参数

>> 扩展位置参数(excess positional argument) ： def f(a,b,*list)，其中的*list被称为扩展位置参数

>> 扩展键参数(excess key argument) : def (a,b,**keys)，其中的**key被称为扩展键参数

<p>CALL_FUNCTION指令参数的长度为*两个字节*,在*低字节*,记录*位置参数*的个数,在*高字节*,记录*键参数*的个数,所以理论上可以有256个位置参数和256个键参数</p>

> 位置参数的传递

```python
//func_1
def f(name,age):
  age += 5
  print "[", name, ", ", age, "]"

age = 5
print age

f("Robert",age)

print age
```

```c
static PyObject* fast_function(PyObject* func, PyObject*** pp_stack, int n, int na, int nk){
  PyCodeObject* co = (PyCodeObject *)PyFunction_GET_CODE(func);
  PyObject* globals = PyFunction_GET_GLOBALS(func);

  if(argdefs == NULL && co->co_argcount == n && nk = 0 &&
    co->co_flags == (CO_OPTIMIZED | CO_NEWLOCALS | CO_NOFREE)){
      PyFrameObject* f;
      PyThreadState* tstate = PyThreadState_GET();
      PyObject** fastlocals, **stack;
      int i;
      //创建与函数对应的PyFrameObject对象
      f = PyFrame_New(tstate,co,globals,NULL);
      //拷贝函数参数: 从运行时栈到PyFrameObject.f_localplus
      fastlocals = f->f_localsplus;
      stack = (*pp_stack) - n;
      for(i = 0; i < n; ++i){
        fastlocals[i] = *stack++;
      }
      retval = PyEval_EvalFrameEx(f,0);
      ....
    }
    ....
}
```

```c
//参数所占用的内存空间 和 运行时栈所占用的内存空间 的关系
[frameobject.c]
PyFrameObject* PyFrame_New(PyThreadState* tstate, PyCodeObject* code, PyObject* globals, PyObject* locals){
  PyFrameObject* f;
  int extras,ncells,nfrees,i;

  ncells = PyTuple_GET_SIZE(code->co_cellvars);
  nfrees = PyTuple_GET_SIZE(code->co_freevars);
  extras = code->co_stacksize + code->co_nlocals + ncells + nfrees;
  ....
  //为f_localplus申请extras的内存空间
  f = PyObject_GC_NewVar(PyFrameObject,*PyFrame_Type,extras);
  ...
  //获得f_localplus中除去运行时栈外，剩余的内存数
  extras = f->f_nlocals + ncells + nfrees;
  for( i = 0; i < extras; i++){
    f->f_localsplus[i] = NULL;
  }
  f->f_valuestack = f->f_localsplus + extras;
  f->f_stacktop = f->f_valuestack;
  return f;
}
````

<p>结论：函数的参数存放在运行时栈之前的那片内存中</p>

![f_localplus](/image/f_localplus.png)

> 位置参数的访问

```c
[ceval.c]
PyObject* PyEval_EvalFrameEx(PyFrameObject* f, int throwflag){
  register PyObject** fastlocals;
  ....
  fastlocals = f->f_localsplus;
  ....
}

#define GETLOCAL(i) (fastlocals[i])

[LOAD_FAST]
x = GETLOCAL(oparg);
if(x != NULL){
  Py_INCREF(x);
  PUSH(x);
  goto fast_next_opcode;
}

#define SETLOCAL(i,value) do {
  PyObject* tmp = GETLOCAL(i);
  GETLOCAL(i) = value;
  Py_XDECREF(tmp);
}while(0)

[STORE_FAST]
v = POP();
SETLOCAL(oparg,v);
goto fast_next_opcode;
```

![change_seq](/image/change_seq.png)

> 位置参数的默认值

```python
def f(a=1,b=2):
  print a + b

f()
f(b=3)
```

```c
[MAKE_FUNCTION]
//获得PyCodeObject对象，并创建PyFunctionObject
v = POP();
x = PyFunction_New(v,f->f_globals);
Py_DECREF(v);
//处理带默认值的函数参数
if(x != NULL && oparg > 0){
  v = PyTuple_New(oparg);
  while(--oparg >= 0){
    w = POP();
    PyTuple_SET_ITEM(v,oparg,w);
  }
  err = PyFunction_SetDefaults(x,v);
  Py_DECREF(v);
}
PUSH(x);

[funcobject.c]
int PyFunction_SetDefaults(PyObject* op, PyObject* defaults){
  ((PyFunctionObject *)op)->func_defaults = defaults;
  return 0;
}
```

>> 函数f的第一次调用

```c
//fast_function
[ceval.c]
static PyObject* fast_function(PyObject* func, PyObject*** pp_stack, int n, int na, int nk){
  PyCodeObject* co = (PyCodeObject *)PyFunction_GET_CODE(func);
  PyObject* globals = PyFunction_GET_GLOBALS(func);
  //获得函数对应的PyFunctionObject中的func_defaults
  PyObject* argdefs = PyFunction_GET_DEFAULTS(func);
  PyObject** d = NULL;
  int nd = 0;

  //判断是否进入快速通道，argdefs!= NULL导致判断失败
  if(argdefs == NULL && co->co_argcount == n && nk =0 && co->co_flags == (CO_OPTIMIZED | CO_NEWLOCALS | CO_NOFREE)){
    PyFrameObject* f;
    PyObject* retval = NULL;
    PyThreadState* tstate = PyThreadState_GET();
    PyObject **fastlocals, **stack;
    int i ;
    f = PyFrame_New(tstate,co,globals,NULL);
    ...
    retval = PyEval_EvalFrameEx(f,0);  //PyFunctionObject主要对字节码指令和global名字空间进行打包和运输
    ...
    return retval;
  }

  //这里获得函数参数默认值的信息(1.第一个默认值的地址 2.默认值的个数)
  if(argdefs != NULL){
    d = &PyTuple_GET_ITEM(argdefs,0);
    nd = ((PyTupleObject *)argdefs)->ob_size;
  }

  return PyEval_EvalCodeEx(co,globals,(PyObject *)NULL,
                          (**pp_stack) - n, na,  //位置参数的信息
                          (*pp_stack) - 2*nk, nk,  //键参数的信息
                          d, nd, //函数默认参数的信息
                          PyFunction_GET_CLOSURE(func));
}
```

```c
PyObject* PyEval_EvalCodeEx(PyCodeObject* co, PyObject* globals, PyObject* locals,
                            PyObject** args,int argcount, //位置参数的信息
                            PyObject** kws,int kwcount,  //键参数的信息
                            PyObject** defs, int defcount,  //函数默认参数的信息
                            PyObject* closure)
{
  register PyFrameObject* f;
  register PyObject* retval = NULL;
  register PyObject** fastlocals, **freevars;
  PyThreadState* tstate = PyThreadState_GET();
  PyObject* x, *u;
  //创建PyFrameObject对象
  f = PyFrame_New(tstate,co,globals,locals);
  fastlocals = f->f_localsplus;
  freevars = f->f_localsplus + f->f_nlocals;

  if(co->co_argcount > 0 || co->co_flags & (CO_VARARGS | CO_VARKEYWORDS)){
    int i;
    //n为CALL_FUNCTION的参数指示的传入的位置参数个数,即na,这里为0
    int n = argcount;
    ....
    //判断是否使用参数的默认值
    if(argcount < co->co_argcount){
      //m = 位置参数总数 - 被设置了默认值的位置参数个数
      int m = co->co_argcount - defcount;
      //函数调用这必须传递一般位置参数的参数值
      for(i = argcount; i < m; i++){
        if(GETLOCAL(i) == NULL){
          goto fail;
        }
      }

      //n > m 意味着调用者希望替换一些默认位置参数的默认值
      if(n > m)
        i = n - m
      else
        i = 0;

      //设置默认位置参数的默认值
      for(;i < defcount; i++){
        if(GETLOCAL(m + i) == NULL){
          PyObject* def = defs[i];
          Py_INCREF(def);
          SETLOCAL(m+i,def);
        }
      }
    }
  }

  retval = PyEval_EvalFrameEx(f,0);
  return retval;
}

```

> 函数f的第二次调用

```c
PyObject* PyEval_EvalCodeEx(PyCodeObject* co, PyObject* globals, PyObject* locals,
                            PyObject** args,int argcount, //位置参数的信息
                            PyObject** kws,int kwcount,  //键参数的信息
                            PyObject** defs, int defcount,  //函数默认参数的信息
                            PyObject* closure)
{
  ....
  if(co->co_argcount > 0 || co->co_flags & (CO_VARARGS | CO_VARKEYWORDS)){
    int i;
    int n = argcount;
    ...
    //遍历键参数，确定函数的def语句中是否出现了键参数的名字
    for(i = 0; i < kwcount; i++){
      PyObject* keyword = kws[2*i];
      PyObject* value = kws[2*i + 1];
      int j;
      //在函数的变量名表中寻找keyword
      for(j = 0; j < co->co_argcount; j++){
        PyObject* nm = PyTuple_GET_ITEM(co->co_varnames,j);
        int cmp = PyObject_RichCompareBool(keyword,nm,Py_EQ);
        if(cmp > 0) // 在co_varnames中找到keyword
          break;
        else if(cmp < 0)
          goto fail;
      }

      //keyword没有在变量名表中出现
      if( j >= co->co_argcount){
        ...
      }
      // keyword在变量名中出现
      else{
        if(GETLOCAL(j) != NULL){
          goto fail;
        }
        Py_INCREF(value);
        SETLOCAL(j,value);
      }
    }
.....

    //设置默认位置参数的默认值
    for(; i < defcount; i++){
      if(GETLOCAL(m+i) == NULL){
        PyObject* def = defs[i];
        Py_INCREF(def);
        SETLOCAL(m+i,def);
      }
    }
  }
}

```

> 扩展位置参数和扩展键参数

<p>*list是由PyTupleObject实现,**key是由PyDictObject实现</p>

```c
//扩展位置参数
PyObject* PyEval_EvalCodeEx(PyCodeObject* co, PyObject* globals, PyObject* locals,
                            PyObject** args,int argcount, //位置参数的信息
                            PyObject** kws,int kwcount,  //键参数的信息
                            PyObject** defs, int defcount,  //函数默认参数的信息
                            PyObject* closure)
{
  register PyFrameObject* f;
  register PyObject** fastlocals, **freevars;
  PyThreadState* tstate = PyThreadState_GET();
  PyObject* x,*u;
  //创建PyFrameObject对象
  f = PyFrame_New(tstate,co,globals,locals);
  fastlocals = f->f_localsplus;
  freevars = f->f_localsplus + f->f_nlocals;
  //判断是否需要处理扩展位置参数或扩展键参数
  if(co->co_argcount > 0 | co->co_flags & (CO_VARARGS | CO_VARKEYWORDS)){
    int i;
    int n = argcount;
    //这里: argcount=na=3,co_argcount = 1
    if(argcount > co->co_argcount){
      n = co->co_argcount;
    }
    //设置位置参数的参数值
    for(i = 0; i < n; i++){
      x = args[i];
      SETLOCAL(i,x);
    }
    //处理扩展位置参数
    if(co->co_flags & CO_VARARGS){
      //将PyTupleObject对象放入到f_localsplus中
      u = PyTuple_New(argcount - n);
      SETLOCAL(co->co_argcount,u);
      //将扩展位置参数放入到PyTupleObject中
      for( i = n; i < argcount; i++){
        x = args[i];
        PyTuple_SET_ITEM(u,i-n,x);
      }
    }
  }
}
```


```c
//扩展键参数
PyObject* PyEval_EvalCodeEx(PyCodeObject* co, PyObject* globals, PyObject* locals,
                            PyObject** args,int argcount, //位置参数的信息
                            PyObject** kws,int kwcount,  //键参数的信息
                            PyObject** defs, int defcount,  //函数默认参数的信息
                            PyObject* closure)
{
  ....
  if(co->co_argcount > 0 || co->co_flags * (CO_VARARGS | CO_VARKEYWORDS)){
    int i;
    int n = argcount;
    PyObject* kwdict = NULL;
    ...
    //创建PyDictObject对象，并将其放到f_localsplus中
    if(co->co_flags && CO_VARKEYWORDS){
      kwdict = PyDict_New();
      i = co->co_argcount;
      //PyDictObject对象必须在PyTupleObject之后
      if(co->co_flags && CO_VARARGS)
          i++;
      SETLOCAL(i,kwdict);
    }

    //遍历键参数，确定函数的def语句中是否出现了键参数的名字
    for(i = 0l i < kwcount; i++){
      PyObject* keyword = kws[2*i];
      PyObject* value = kws[2*i + 1];
      int j;
      //在函数的变量名对象表中寻找keyword
      for(j = 0; j < co->co_argcount; j++){
        PyObject* nm = PyTuple_GET_ITEM(co->co_varnames,j);
        int cmp = PyObject_RichCompareBool(keyword,nm,Py_EQ);
        if(cmp > 0) // 在co_varnames 中找到keyword
          break
        else if (cmp < 0)
          goto fail;
      }

      //keyword没有在变量名对象表中出现
      if(j >= co->co_argcount){
        PyDict_SetItem(kwdict,keyword,value);
      }

      //keyword在变量名对象表中出现
      else{
        SETLOCAL(j,value);
      }

    }
  }
}
```

![extend_arg_kwarg](/image/extend_arg_kwarg.png)

#### e.函数中局部变量的访问

```c
//在调用函数时，Python虚拟机通过PyFrame_New创建新的PyFrameObject对象时，local名字空间没有被创建
[frameobject.c]
PyFrameObject* PyFrame_New(PyThreadState* tstate, PyCodeObject* code, PyObject* globals, PyObject* locals){
  ....
  /* Most functions have CO_NEWLOCALS and CO_OPTIMIZED set. */
  if((code->co_flags & (CO_NEWLOCALS | CO_OPTIMIZED)) == (CO_NEWLOCALS | CO_OPTIMIZED))
      locals = NULL; /* PyFrame_FastToLocals() will set. */
  ...

  f->f_locals = locals;
  ...
}
```

<p>局部变量也在f_localsplus运行时栈前面的那段内存,不使用local名字空间是因为用静态方法来实现</p>

#### f.嵌套函数、闭包与decorator

```python
[compare.py]
def compare(base,value):
  return value > base

compare(10,5)
compare(10,20)
```

```python
[compare2.py]
base = 1
def get_compare(base):
  def real_compare(value):
    return value > base
  return real_compare

compare_with_10 = get_compare(10)
print compare_with_10(5)
print compare_with_10(20)
```

```python
[compare3.py]
base = 1
def get_compare(base):
  def real_compare(value,base = base):
    return value > base
  return real_compare

compare_with_10 = get_compare(10)
print compare_with_10(5)
print compare_with_10(20)
print compare_with_10(5,1)
```

> 实现闭包的基石

<p>在PyCodeObject中，与嵌套函数相关的属性是co_cellvars和co_freevars</p>

<p>co_cellvars：通常是一个tuple，保存嵌套的作用域中使用的变量名集合</p>

<p>co_freevars：通常是一个tuple，保存使用了的外层作用域中的变量名集合</p>

```python
[closure.py]
def get_func():
  value = "inner"
  def inner_func():
    print value
  return inner_func

show_value = get_func()
show_value()
```

<p>在PyFrameObject对象中，与闭包相关的属性是f_localsplus</p>

![f_localsplus](/image/f_localsplus.png)


> 闭包的实现

>> 创建closure

```c
[ceval.c]
PyObject* PyEval_EvalCodeEx(...){
  ...
  if(PyTuple_GET_SIZE(co->co_cellvars)){
    int i,j,nargs,found;
    char* cellname, *argname;
    PyObject* c;
    ....
    for( i = 0; i < PyTuple_GET_SIZE(co->co_cellvars); ++i){
      //获得被嵌套函数共享的符号名
      cellname = PyString_AS_STRING(PyTuple_GET_ITEM(co->co_cellvars,i)); //cellname是在处理内层嵌套函数引用外层函数的默认参数时产生的
      found = 0;
      ...//处理被嵌套函数共享外层函数的默认参数
      if(found == 0){
        c = PyCell_New(NULL);
        if(c == NULL){
          goto fail;
        }

        SETLOCAL(co->co_nlocals + i, c);
      }
    }
  }
}

[cellobject.h]
typedef struct {
  PyObject_HEAD
  PyObject* ob_ref; /* Content of the cell or NULL when empty */
} PyCellObject;

[cellobject.c]
PyObject* PyCell_New(PyObject* obj){
  PyCellObject* op;
  op = (PyCellObject *)PyObject_GC_New(PyCellObject,&PyCell_Type);
  op->ob_ref = obj;
  Py_XINCREF(obj);
  _PyObject_GC_TRACK(op);
  return (PyObject *)op;
}
```

```c
//STORE_DEREF
[PyEval_EvalFrameEx]
freevars = f->f_localsplus + co->co_nlocals

[STORE_DEREF]
w = POP()
x = freevars[oparg];
PyCell_Set(x,w);
Py_DECREF(w);


//设置PyCellObject对象中的ob_ref
[cellobject.h]
#define PyCell_SET(op,v) (((PyCellObject *)(op))->ob_ref = v)
[cellobject.c]
int PyCell_SET(PyObject* op, PyObject* obj){
  Py_XDECREF(((PyCellObject *)op)->ob_ref);
  Py_XINCREF(obj);
  PyCell_SET(op,obj);
  return 0;
}
```

![cell_after](/image/cell_after.png)

```c
//将(value,"inner")约束塞入PyFunctionObject
[LOAD_CLOSURE]
x = freevars[oparg];
Py_INCREF(x);
PUSH(x);
```

```c
//MAKE_CLOSURE 指令完成约束与PyCodeObject的绑定
[MAKE_CLOSURE]
{
  v = POP(); //获得PyCodeObject对象
  x = PyFunction_New(v,f->f_globals); //绑定global名字空间
  v = POP(); //获得tuple,其中包含PyCellObject对象的集合
  err = PyFuntion_SetClosure(x,v); 绑定约束集合
  .../处理拥有默认值的参数
  PUSH(x);
}
```

![get_func_after_func](/image/get_func_after_func.png)

>> 使用closure

<p>closure实在get_func中被创建的,在inner_func中被使用的</p>

```c
\\CALL_FUNCTION中,inner_func对应的PyCodeObject中的co_flags里包含了CO_NESTED，不能通过快速通道
[ceval.c]
PyObject* PyEval_EvalCodeEx(...){
  ...
  if(PyTuple_GET_SIZE(co->co_freevars)){
    int i;
    for(i = 0; i < PyTuple_GET_SIZE(co->co_freevars); ++i){
      PyObject* o = PyTuple_GET_ITEM(closure,i);
      freevars[PyTuple_GET_SIZE(co->co_cellvars) + i] = o;
    }
  }
}

[funcobject.h]
#define PyFunction_GET_CLOSURE(func) (((PyFunctionObject *)func)->func_closure)

[ceval.c]
PyObject* fast_function(...){
  ...
  return PyEval_EvalCodeEx(...,PyFunction_GET_CLOSURE(func));
}
```

![inner_func_frame](/image/inner_func_frame.png)

```c
[LOAD_DEREF]
x = freevars[oparg]; //获得PyCellObject对象
w = PyCell_Get(x); //获得PyCellObject, ob_obj指向的对象
if( w != NULL){
  PUSH(w);
  continue;
}
....
```

> decorator

<p>基于closure技术上,实现了decorator</p>

```python
[decorator.py]
def should_say(fn):
  def say(*args):
    print 'say something...'
    fn(*args)
  return say

@should_say
def func():
  print 'in func'

//输出结果为
//say something
// in func
func()  // 相当于 func = should_say(func)
```
