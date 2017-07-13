### 1. Python 中的整数对象

#### a.PyIntObject

> 二分类对象

>> 定长对象 or 变长对象

>> 可变对象(mutable) or 不可变对象(immutable)

> 1.PyIntObject是不可变对象</p>

> 2.Python中整数访问频繁，通过整数 *对象池* ，做成一个对象的缓冲池机制，使得整数对象的使用不会成为Python的瓶颈</p>

```c
/*PyIntObject定义*/

[intobject.h]
typedef struct{
  PyObject_HEAD
  long ob_ival;
} PyIntObject;
```

```c
/*PyInt_Type定义*/
PyTypeObject PyInt_Type = {
	PyObject_HEAD_INIT(&PyType_Type)
	0,
	"int",
	sizeof(PyIntObject),
	0,
	(destructor)int_dealloc,		/* tp_dealloc */
	(printfunc)int_print,			/* tp_print */
	0,					/* tp_getattr */
	0,					/* tp_setattr */
	(cmpfunc)int_compare,			/* tp_compare */
	(reprfunc)int_repr,			/* tp_repr */
	&int_as_number,				/* tp_as_number */
	0,					/* tp_as_sequence */
	0,					/* tp_as_mapping */
	(hashfunc)int_hash,			/* tp_hash */
        0,					/* tp_call */
        (reprfunc)int_repr,			/* tp_str */
	PyObject_GenericGetAttr,		/* tp_getattro */
	0,					/* tp_setattro */
	0,					/* tp_as_buffer */
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_CHECKTYPES |
		Py_TPFLAGS_BASETYPE,		/* tp_flags */
	int_doc,				/* tp_doc */
	0,					/* tp_traverse */
	0,					/* tp_clear */
	0,					/* tp_richcompare */
	0,					/* tp_weaklistoffset */
	0,					/* tp_iter */
	0,					/* tp_iternext */
	int_methods,				/* tp_methods */
	0,					/* tp_members */
	0,					/* tp_getset */
	0,					/* tp_base */
	0,					/* tp_dict */
	0,					/* tp_descr_get */
	0,					/* tp_descr_set */
	0,					/* tp_dictoffset */
	0,					/* tp_init */
	0,					/* tp_alloc */
	int_new,				/* tp_new */
	(freefunc)int_free,           		/* tp_free */
};
```

```c
/* int_compare定义 */
[intobject.c]
static int int_compare(PyObject *v, PyObject *w){
  register long i = v->ob_ival;
  register long j = w->ob->ival;
  return (i < j) ? -1 : (i > j) ? 1 : 0;
}
```

```c
/* int_as_number定义 */
[intobject.c]
static PyNumberMethods int_as_number = {  /* PyNumberMethods定义了39中数值操作 */
  (binaryfunc)int_add, /* nb_add */
  (binaryfunc)int_sub, /* nb_subtract */
  ....
  (binaryfunc)int_div, /* nb_floor_divide */
  int_true_divide, /* nb_true_divide */
  0, /* nb_inplace_floor_divide */
  0, /* nb_inplace_true_divide */
}
```

```c
/* PyIntObject的加法实现 */
[intobject.h]
//宏，牺牲类型安全，换取执行效率
//该宏也可以用函数PyInt_AsLong来代替，但会牺牲运行效率，因为该函数做了很多类型检查
#define PyInt_AS_LONG(op) (((PyIntObject *)(op))->ob_ival)

[intobject.c]
#define CONVERT_TO_LONG(obj, lng)
    if (PyInt_Check(obj)){
      lng = PyInt_AS_LONG(obj);
    }else{
      Py_INCREF(Py_NotImplemented);
      return Py_NotImplemented;
    }

static PyObject* int_add(PyIntObject *v, PyIntObject *w){
  register long a,b,x;
  CONVERT_TO_LONG(v,a);
  CONVERT_TO_LONG(w,b);
  x = a + b;
  // 检查加法结果是否溢出(位操作比较方法)
  if((x^a) >= 0 || (x^b) >= 0)
    return PyInt_FromLong(x);
  return PyLong_Type.tp_as_number->nb_add((PyObject *)v, (PyObject *) w);
}
```

```python
/* 测试加法函数 */
>>> a = 0x7fffffff
>>> type(a)
<type 'int'>
>>> type(a+a)
<type 'long'>
```

> 3.PyIntObject对象的文档信息，元信息维护在int_doc域中

```python
>>> a = 1
>>> print a.__doc__
```

```c
[python.h]
#define PyDoc_VAR(name) static char name[]
#define PyDoc_STRVAR(name,str) PyDoc_VAR(name) = PyDoc_STR(str)
#ifdef WITH_DOC_STRINGS
#define PyDoc_STR(str) str
#else
#define PyDoc_STR(str) ""
#endif

[intobject.c]
PyDoc_STRVAR(int_doc,"int(x[,base])->integer........")
```

#### b.PyIntObject对象的创建和维护

> 对象创建的3种途径

```c
PyObject *PyInt_FromLong(long ival)
/*PyInt_FromString和PyInt_FromUnicode都是先将字符串或Py_UNICODE转换乘浮点数，再调用PyInt_FromFloat(采用了Adaptor Pattern设计模式)*/
PyObject *PyInt_FromString(char *s,char **pend,int base)
#ifdef Py_USING_UNICODE
    PyObject *PyInt_FromUnicode(Py_UNICODE *s, int length, int base)
#endif
```

```c
[intobject.c]
PyObjec* PyInt_FromString(char*s, char** pend, int base){
  char* end;
  long x;
  .......
  //将字符串转换为long值
  if( base == 0 && s[0] == '0'){
    x = (long) PyOS_strtoul(S,&end,base);
  }else{
    x = PyOS_strtol(s,&end,base);
  }
  .......
  return PyInt_FromLong(x);
}
```

> 小整数对象

```c
[intobject.c]
#ifndef NSMALLPOSINTS
    #define NSMALLPOSINTS 257
#endif
#ifndef NSMALLNEGINTS
    #define NSMALLNEGINTS 5
#endif
#if NSMALLNEGINTS + NSMALLPOSINTS > 0
    static PyIntObject* small_ints[NSMALLNEGINTS + NSMALLPOSINTS];
#endif
```

> 大整数对象

<p>PyIntBlock结构+单项列表</p>

```c
[intobject.c]
#define BLOCK_SIZE 1000 /* 1K less typical malloc overhead */
#define BHEAD_SIZE 8 /* Enough for a 64-bit pointer */
#define N_INTOBJECTS ((BLOCK_SIZE - BHEAD_SIZE)/sizeof(PyIntObject))

struct _intblock{
  struct _intblock *next;
  PyIntObject objects[N_INTOBJECTS];
};
typedef struct _intblock PyIntBlock;

static PyIntBlock* block_list = NULL;
static PyIntObject* free_list = NULL;
```

> 添加和删除

<p>以PyInt_FromLong为例子</p>

```c
[intobject.c]
PyObject* PyInt_FromLong(long ival){
  register PyIntObject* v;
  #if NSMALLNEGINTS + NSMALLPOSINTS > 0
  //尝试使用小整数对象池
  if(-NSMALLNEGINTS <= ival && ival < NSMALLPOSINTS){
    v = small_ints[ival + NSMALLNEGINTS];
    Py_INCREF(v);
    return (PyObject*) v;
  }
  #endif

  //为通用整数对象池申请新的内存空间
  if(free_list == NULL){
    if((free_list == fill_free_list()) == NULL)
        return NULL;
  }

  //(inline)内联PyObject_New的行为
  v = free_list;
  free_list = (PyIntObject*)v->ob_type;
  PyObject_INIT(v,&PyInt_Type);
  v->ob_ival = ival'
  return (PyObject* v);
}
```

```c
/* fill_free_list */
/* 当block满了以后free_list会再次为空，所以会再次调用fill_free_list */
/* block_list始终是指向罪最新的PyIntBlock对象 */
[intobject.c]
static PyIntObject* fill_free_list(void){
  PyIntObject *p, *q;
  // 申请大小为sizeof(PyIntBlock)的内存空间，并链接到已有的block list中
  p = (PyIntObject *)PyMem_MALLOC(sizeof(PyIntBlock));
  ((PyIntBlock *)p)->next = block_list;
  block_list = (PyIntBlock *)p;
  // 将PyIntBlock中的PyIntObject数组--objects--转变成单项链表
  p = &((PyIntBlock *)p)->objects[0];
  q = p + N_INTOBJECTS;
  while(--q > p)
    q->ob_type = (struct _typeobject*)(q-1);
  q->ob_type = NULL;
  return p + N_INTOBJECTS - 1;
}
```
![PyIntBlock](/image/py_intblock.png)

> 不同的PyIntBlock中的objects中的空闲块是在一个PyIntObject对象被销毁的时候被链接在一起的

```c
/* PyIntObject对象的tp_dealloc操作 */
[intobject.c]
static void int_dealloc(PyIntObject* v){
  if(PyInt_CheckExact(v)){
    v->ob_type = (struct _typeobject *)free_list;
    free_list = v
  }else{
    v->ob_type->tp_free((PyIntObject*)v);
  }
}
```

![add_delete_example](/image/add_delete_example.png)

> 小整数对象池的初始化
