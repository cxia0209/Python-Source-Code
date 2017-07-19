### 1.Python虚拟机中的一般表达式

#### a.简单内建对象的创建

```python
i = 1
s = "python"
d = {}
l = []
```

```c
[PyEval_EvalFrameEx in ceval.c]
//访问tuple中的元素
#define GETITEM(v,i) PyTuple_GET_ITEM((PyTupleObject *)(v),(i))
//调整栈顶指针
#define BASIC_STACKADJ(n) (stack_pointer += n)
#define STACKADJ(n) BASIC_STACKADJ(n);
//入栈操作
#define BASIC_PUSH(v) (*stack_pointer++ = (v))
#define PUSH(v) BASIC_PUSH(v)
//出栈操作
#define BASIC_POP() (*--stack_pointer)
#define POP() BASIC_POP()
```

```c
//LOAD_CONST
[LOAD_CONST]
x = GETITEM(consts,oparg);
Py_INCREF(x);
PUSH(x);

//STORE_NAME
//从符号表中获得符号，其中oparg=0
w = GETITEM(names,oparg);
//从运行时栈中获得值
v = POP();
if((x = f->f_locals) != NULL){
  //将（符号，值）的映射关系存储到local名字空间中
  if(PyDict_CheckExact(x)){
    PyDict_SetItem(x,w,v);
  }else{
    PyObject_SetItem(x,w,v);
  }
  Py_DECREF(v);
}
```

![load_const](/image/load_const.png)

![store_name](/image/store_name.png)

```c
//BUILD_MAP
[BUILD_MAP]
x = PyDict_New();
PUSH(x)

//BUILD_LIST
x = PyList_New(oparg)
if(x != NULL){
  for(; --oparg >=0; ){
    w = POP();
    PyList_SET_ITEM(x,oparg,w);
  }
  PUSH(x);
}

//RETURN_VALUE
[RETURN_VALUE]
retval = POP();
why = WHY_RETURN;
```

#### b.复杂内建对象的创建

```python
i = 1
s = "python"
d = {"1":1,"2":2}
l = [1,2]
```

```c
//DUP_TOP
[DUP_TOP]
v = TOP();
Py_INCREF(v);
PUSH(v);

//ROT_TWO
v = TOP();
W = SECOND();
SET_TOP(w);
SET_SECOND(v);

[ceval.c]
#define TOP() (stack_pointer[-1])
#define SECOND() (stack_pointer[-2])
#define SET_TOP(v) (stack_pointer[-1] = (v))
#define SET_SECOND(v) (stack_pointer[-2] = (v))

//STORE_SUBSCR
[STORE_SUBSCR]
w = TOP();
v = SECOND();
u = THIRD();
STACKADJ(-3);
//v[w] = u, 即dict["1"] = 1
PyObject_SetItem(v,w,u);
Py_DECREF(u);
Py_DECREF(v);
Py_DECREF(w);
```

#### c.其他一般表达式

> 符号搜索

```c
[LOAD_NAME]
//获得变量名
w = GETITEM(names,oparg);
//在local名字空间中查找变量名对应的变量值
v = f->f_locals;
x = PyDict_GetItem(v,w);
Py_XINCREF(x);
if(x == NULL){
  //在global名字空间中查找变量名对应的变量值
  x = PyDict_GetItem(f->f_globals,w);
  if( x == NULL){
    x = PyDict_GetItem(f->f_bulitins,w);
    if( x == NULL){
      //查找变量名失败，抛出异常
      format_exc_check_arg(PyExc_NameError,NAME_ERROR_MSG,w);
      break;
    }
  }
  Py_INCREF(x);
}
PUSH(x)
```

> 数值运算

```c
[BINARY_ADD]
w = POP();
v = TOP();
if(PyInt_CheckExact(v) && PyInt_CheckExact(w)){
  // PyIntObject对象相加的快速通道
  register long a,b,i;
  a = PyInt_AS_LONG(v);
  b = PyInt_AS_LONG(w);
  i = a + b;
  //如果加法运算溢出,转向慢速通道
  if( (i^a) < 0 && (i^b) < 0)
    goto slow_add;
  x =  PyInt_FromLong(i);
}
//PyStringObject 对象相加的快速通道
else if(PyString_CheckExact(v) && PyString_CheckExact(w)){
  x = string_concatenate(v,w,f,next_instr);
  goto skip_decref_vx;
}
else{
  // 一般对象相加的慢速通道
  slow_add:
    x = PyNumber_Add(v,w);
}
Py_DECREF(v);
skip_decref_vx:
  Py_DECREF(w);
  SET_TOP(x);
  break;
```

> 信息输出

```c
[PRINT_ITEM]
v = POP(); //获得待输出对象
if(stream == NULL || stream == Py_None){
  w = PySys_GetObject("stdout")
}
Py_XINCREF(w);
if(w != NULL && PyFile_SoftSpace(w,0))
  err = PyFile_WriteString(" ",w);
if(err == 0)
  err = PyFile_WriteObject(v,w,Py_PRINT_RAW);
...
stream = NULL;
```
