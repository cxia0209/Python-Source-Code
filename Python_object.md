### 1. 对象机制的基石 -- PyObject

#### a.PyOject 定义

```c
[object.h]
typedef struct _object{
  int ob_refcnt;  //引用计数
  struct _typeobject *ob_type; //类型信息
} PyObject
```

<p>每一个python对象除了PyObject这部分必要信息，还有其他，比如PyIntObject</p>

```c
[intobject.h]
typedef struct{
  PyObject_HEAD
  long ob_ival; //整数的值
} PyIntObject;
```

#### b.定长对象和变长对象
如何实现字符串？
```c
[object.h]
#define PyObject_VAR_HEAD
  PyObject_HEAD
  int ob_size; /*Number of items in variable part*/

typedef struct{
  PyObject_VAR_HEAD
} PyVarObject;
```

#### c.类型对象

> 类型对象 _typeobject

> 其中主要包含四类信息

>> 类型名 tp_name

>> 创建该类型对象时分配的内存空间大小的信息 tp_basicsize和tp_itemsize

>> 与该类型对象相关联的操作信息

>> 其他类型信息

```c
[object.h]
typedef struct _typeobject {
  PyObject_VAR_HEAD
  char *tp_name; /* For printing, in format "<module>.<name>" */
  int tp_basicsize,tp_itemsize; /* For allocation */

  /* Methods to implement standard operations */
  destructor tp_dealloc;
  printfunc tp_print;

  ......

  /* More standard operations (here for binary compatibility) */
  hashfunc tp_hash;
  ternaryfunc to_call;

  ......
}
```

#### d.对象的创建

> Python内部创建
>> 通过Python C API
>>> 范型的API(AOL, Abstract Object Layer) 比如：PyObject* intObj = PyObject_New(PyObject, &PyInt_Type)

>>> 类型相关的API(COL, Concrete Object Layer) 比如: PyObject *intObj = PyInt_FromLong(10);

>> 通过类型对象PyInt_Type

![pyint_type调用](/image/pyint_type.png)

#### e.对象的行为
