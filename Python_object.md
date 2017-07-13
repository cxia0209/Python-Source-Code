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
> 函数指针直接决定这一个对象在运行时所表现出的行为

<p>比如</p>

> 数值特性(PyNumberMethods *tp_as_number)

> 序列特性(PySequenceMethods *tp_as_sequence)

> 关联特性(PyMappingMethods *tp_as_mapping)

```c
[object.h]
typedef PyObject *(*binaryfunc)(PyObject *, PyObject *);

typedef struct{
  binaryfunc nb_add;
  binaryfunc nb_subtract;
  ......
} PyNumberMethods;
```

<p>特性的混合</p>

```python
class MyInt(int):
    def __getitem__(self,key):
        return key + str(self)
>> a = Myint(1)
>> b = Myint(2)
>> print a + b
3
>> a['key']
'key1'
```

#### f.类型的类型
> PyType_Type => <type 'type'> 它是所有class的class，被称为metaclass

```c
[typeobject.c]
PyTypeObject PyType_Type = {
  PyObject_HEAD_INIT(&PyType_Type)
  0, /* ob_size */
  "type" /* tp_name */
  sizeof(PyHeapTypeObject), /* tp_basicsize */
  sizeof(PyMemberDef),  /* tp_itemsize */
  ...
};
```

<p>PyTypeObject和PyType_Type的关系</p>

```python
>> class A(object):
    pass
>>A.__class__
<type 'type'>
>>int.__class__
<type 'type'>
>>type.__class__
<type 'type'>
```
<p>举例</p>

<p>PyInt_Type和PyType_Type之间的关系</p>

```c
[intobject.c]
PyTypeObject PyInt_type = {
  PyObject_HEAD_INIT(&PyType_Type)
  0,
  "int",
  sizeof(PyIntObject),
  ...
}
```
<p>运行时整数对象及其类型之间的关系</p>

![pyint_pytype](/image/pyint_pytype.png)

#### g.Python对象的多态性

<p>通过ob_type域动态进行判断，Python实现了多态机制</p>

```c
void Print(PyObject *object){
  object->ob_type->tp_print(object);
}
```

#### h.引用计数

> ob_refcnt 变量，32位整型，决定着对象的创建与消亡

> 通过Py_INCREF(op) 和 PyDECREF(op) 两个宏来增加和减少一个对象的引用计数

> 通过_Py_NewReference(op)宏来将对象的引用计数初始化为1

> PyDECREF 的“析构动作” 是通过一个函数指针tp_dealloc来进行的(Observer设计模式)

> 在Python的各种对象中， 类型对象永远不会被析构

```c
[object.h]
#define _Py_NewReference(op) ((op)->ob_refcnt = 1)
#define _Py_Dealloc(op) ((*(op)->ob_type->tp_dealloc)((PyObject *)(op)))
#define Py_INCREF ((op)->ob_refcnt++)
#define Py_DECREF(op)
        if(--(op)->ob_refcnt != 0);
        else
            _Py_Dealloc((PyObject *)(op))

/* Macros to use in case the object pointer may be NULL */
#define Py_XINCREF(op) if ((op) == NULL); else Py_INCREF(op)
#define Py_XDECREF(op) if ((op) == NULL); else Py_DECREF(op)
```

#### i.Python对象的分类

![python_object](/image/python_object.png)
