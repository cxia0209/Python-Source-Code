### 1.Python虚拟机中的类机制

#### a.Python中的对象模型

> Python中的三类对象

<p>type对象：表示Python内置的类型</p>

<p>class对象：表示Python程序员定义的类型</p>

<p>instance对象：表示由class对象创建的实例</p>

> 对象间的关系

<p>is-kind-of:基类与子类的关系</p>

<p>is-instance-of：类与实例之间的关系</p>

> <type 'type'>和<type 'object'>

> 从type对象到class对象

<p>*可调用性*,class对象中实现了"__call__"操作（在Python内部的PyTypeObject中tp_call不为空），则可调用</p>

```python
class A(object):
  def __call__(self):
    print 'Hello Python'

a = A()
a()
```

> 处理基类和type信息

```c
[typeobject.c]
int PyType_Ready(PyTypeObject* type){
  PyObject* dict, *bases;
  PyTypeObject* base;
  Py_ssize_t i,n;

  //尝试获得type的tp_base中指定基类(super type)
  base = type->type_base;
  if(base == NULL && type != &PyBaseObject_Type){
    base = type->tp_base = &PyBaseObject_Type;
  }

  //如果基类没有初始化，先初始化基类
  if(base && base->tp_dict == NULL){
    PyType_Ready(base);
  }

  //设置type信息
  if(type->ob_type == NULL && base != NULL){
    type->ob_type = base->ob_type;
  }
  ...
}
```

> 处理基类列表

```c
[typeobject.c]
int PyType_Ready(PyTypeObject* type){
  PyObject* dict, *bases;
  PyTypeObject* base;
  Py_ssize_t i,n;
  ...
  //尝试获得type的tp_base中指定基类(super type)
  base = type->tp_base;
  if(base == NULL && type != &PyBaseObject_Type){
    base = type->tp_base = &PyBaseObject_Type;
  }
  ...
  //处理bases:基类列表
  bases = type->tp_bases;
  if(bases == NULL){
    //如果bases为空，则根据base的情况设定bases
    if(base == NULL)
      bases = PyTuple_New(0);
    else
      bases = PyTuple_Pack(1,base);
    type->tp_bases = bases;
  }
}
```

> 填充tp_dict

```c
[typeobject.c]
int PyType_Ready(PyTypeObject* type){
  PyObject* dict, *bases;
  PyTypeObject* base;
  Py_ssize_t i,n;
  ...
  //设定tp_dict
  dict = type->tp_dict;
  if(dict == NULL){
    dict = PyDict_New();
    type->tp_dict = dict;
  }

  //将与type相关的descriptor加入到tp_dict中
  add_operators(type);
  if(type->tp_methods != NULL){
    add_methods(type,type->tp_methods)
  }
  if(type->tp_members != NULL){
    add_members(type,type->tp_members)
  }
  if(type->tp_getset != NULL){
    add_getset(type,type->tp_getset);
  }
  ....
}
```

> slot与操作排序

<p>slot可以视为表示PyTypeObject中定义的操作</p>

```c
[typeobject.c]
typedef struct wrapperbase slotdef;

[descrobject.h]
struct wrapperbase{
  char* name;  //操作名称，比如"__add__"
  int offset;  //操作的函数地址在PyHeapTypeObject中的偏移量
  void* function;  //slot function的函数
  wrapperfunc wrapper;
  char* doc;
  int flags;
  PyObject* name_strobj;
};

//定义slot
[typeobject.c]
#define TPSLOT(NAME,SLOT,FUNCTION,WRAPPER,DOC)
 {NAME,offsetof(PyTypeObject,SLOT),(void *)(FUNCTION),WRAPPER,PyDoc_STR(DOC)}

 #define ETSLOT(NAME,SLOT,FUNCTION,WRAPPER,DOC)
  {NAME,offsetof(PyHeapTypeObject,SLOT),(void *)(FUNCTION),WRAPPER,PyDoc_STR(DOC)}

[structmember.h]
#define offsetof(type,member) ((int)&((type*)0)->member)

[object.h]
typedef struct _heaptypeobject {
  PyTypeObject ht_type;
  PyNumberMethods as_number;
  PyMappingMethods as_mapping;
  PySequenceMethods as_sequence;
  PyBufferProcs as_buffer;
  PyObject* ht_name,*ht_slots;
} PyHeapTypeObject;  //定于顺序表示优先级

//slot集合:slotdefs
[typeobject.c]
....
#define SQSLOT(NAME,SLOT,FUNCTION,WRAPPER,DOC)
  ETSLOT(NAME,as_sequence.SLOT,FUNCTION,WRAPPER,DOC)
....

static slotdef slotdefs[] = {
  ...
  //[不同操作名对应相同的操作]
  BINSLOT("__add__",nb_add,slot_nb_add,"+"),
  RBINSLOT("__radd__",nb_add,slot_nb_add,"+"),
  //相同操作名对应不同操作
  SQSLOT("__getitem__",sq_item,slot_sq_item,wrap_sq_item,"x.__getitem__(y)<==>x[y]"),
  MPSLOT("__getitem__",mp_subscript,slot_mp_subscript,wrap_binaryfunc,"x.___getitem__(y)<==>x[y]"),
  ...
}
```

```c
//slotdefs的排序在init_slotdefs中完成
[typeobject.c]
static void init_slotdefs(void){
  slotdefs* p;
  static int initialized = 0;
  //init_slotdefs只会进行一次
  if(initialized)
    return
  for(p=slotdefs;p->name;p++){
    //填充slotdef结构体中的name_strobj
    p->name_strobj = PyString_InternFromString(p->name);
  }
  //对slotdefs中的slotdef进行排序
  qsort((void *)slotdefs,(size_t)(p-slotdefs),sizeof(slotdef),slotdef_cmp);
  initialized = 1;
}

//slot排序的比较策略
static int slotdef_cmp(const void* aa,const void* bb){
  const slotdef* a = (const slotdef *)aa, *b = (const slotdef *)bb;
  int c = a->offset - b->offset;
  if(c != 0)
    return c;
  else
    return (a > b) ? 1 : (a < b) ? -1 : 0;
}
```

> 从slot到descriptor

```c
[descrobject.h]
#define PyDescr_COMMON
  PyObject_HEAD
  PyTypeObject* d_type;
  PyObject* d_name

typedef struct{
  PyDescr_COMMON;
  struct wrapperbase* d_base;
  void* d_wrapped; /* This can be any function pointer */
} PyWrapperDescrObject;

[descrobject.c]
static PyDescrObject* descr_new(PyTypeObject* descrtype, PyTypeObject* type, char* name){
  PyDescrObject* descr;
  //申请空间
  descr = (PyDescrObject *)PyType_GenericAlloc(descrtype,0);
  descr->d_type = type;
  descr->d_name = PyString_InternFromString(name);
  return descr;
}

PyObject* PyDescr_NewWrapper(PyTypeObject* type,struct wrapperbase* base, void* wrapped){
  PyWrapperDescrObject* descr;
  descr = descr_new(&PyWrapperDescr_Type,type,base->name);
  descr->d_base = base;
  descr->d_wrapped = wrapped;
  return (PyObject *)descr;
}
```

> 建立练习

<p>排序后的结果放在slotdefs中，Python虚拟机可以从头到尾遍历slotdefs，基于每一个slot建立一个descriptor,然后在tp_dict中建立从操作名到descriptor的关联</p>

```c
[typeobject.c]
static int add_operators(PyTypeObject* type){
  PyObject* dict = type->tp_dict;
  slotdef* p;
  PyObject* descr;
  void **ptr;
  //对slotdefs进行排序
  init_slotdefs();
  for(p = slotdefs; p->name; p++){
    //如果slot中没有指定wrapper，则不处理
    if(p->wrapper == NULL)
      continue;
    //获得slot对应的操作在PyTypeObject中的函数指针
    ptr = slotptr(type,p->offset);
    //如果tp_dict中已经存在操作名，则放弃
    if(PyDict_GetItem(dict,p->name_strobj))
      continue;
    //创建descriptor
    descr = PyDescr_NewWrapper(type,p,*ptr);
    //将(操作名，descriptor)放入tp_dict中
    PyDict_SetItem(dict,p->name_strobj,descr);
  }
  return 0;
}
```

```c
//slotptr完成转换
[typeobject.c]
static void** slotptr(PyTypeObject* type,int offset){
  char *ptr;

  //判断从PyHeapTypeObject中排在后面的PySequenceMethods开始
  if(offset >= offsetof(PyHeapTypeObject,as_sequence)){
    ptr = (void *)type->tp_as_sequence;
    offset -= offsetof(PyHeapTypeObject,as_sequence);
  }
  else if(offset >= offsetof(PyHeapTypeObject,as_mapping)){
    ptr = (void *)type->tp_as_mapping;
    offset -= offsetof(PyHeapTypeObject,as_mapping);
  }
  else if(offset >= offsetof(PyHeapTypeObject,as_number)){
    ptr = (void *)type->tp_as_number;
    offset -= offsetof(PyHeapTypeObject, as_number);
  }
  else{
    ptr = (void *)type;
  }

  if( ptr != NULL )
    ptr += offset;

  return (void **)ptr;
}
```

![add_operator_pylist](/image/add_operator_pylist.png)


> __repr__重写

```python
class A(list):
  def __repr__(self):
    return 'Python'

s = '%s' % A()
print s
```

```c
[typeobject.c]
static PyObject* slot_tp_repr(PyObject* self){
  PyObject* func, *res;
  static PyObject* repr_str;
  //查找"__repr__"属性
  func = lookup_method(self,"__repr__",&repr_str);
  //调用"__repr__"对象的对象
  res = PyEval_CallObject(func,NULL);
}
```

![initial_class_A](/image/initial_class_A.png)

> 确定MRO(Method Resolve Order)

```python
[mro.py]
class A(list):
  def show(self):
    print "A::show"


class B(list):
  def show(value):
    print 'B::show'

class C(A):
  pass

class D(C,B):
  pass

d = D()
d.show()
```

![mro_list](/image/mro_list.png)

> 继承基类操作

```c
[typeobject.c]
int PyType_Ready(PyTypeObject* type){
  ...
  bases = type->tp_mro;
  n = PyTuple_GET_SIZE(bases);
  for( i = 1; i < n; i++){
    PyObject* b = PyTuple_GET_ITEM(bases,i);
    inherit_slots(type,(PyTypeObject *)b);
  }
  ...
}

[typeobject.c]
static void inherit_slots(PyTypeObject* type,PyTypeObject* base){
  PyTypeObject* basebase;

#define SLOTDEFINED(SLOT)
    (base->SLOT != 0 && (basebase ==NULL || base->SLOT != basebase->SLOT))

#define COPYSLOT(SLOT)
    if(!type->SLOT && SLOTDEFINED(SLOT)) type->SLOT = base->SLOT

#define COPYNUM(SLOT) COPYSLOT(tp_as_number->SLOT)
    if(type->tp_as_number != NULL && base->tp_as_number != NULL){
      basebase = base->tp_base;
      if(basebase->tp_as_number == NULL)
        basebase = NULL;
      COPYNUM(nb_add);
      ...
    }
    ....
}
```

> 填充基类中的子类列表

```c
[typeobject.c]
int PyType_Ready(PyTypeObject* type){
  PyObject* dict, *bases;
  PyTypeObject* base;
  Py_ssize_t i,n;
  ...

  //填充基类的子类列表
  bases = type->tp_bases;
  n = PyTuple_GET_SIZE(bases);
  for( i = 0; i < n; i++){
    PyObject* b = PyTuple_GET_ITEM(bases,i);
    add_subclass((PyTypeObject *)b,type);
  }
  ...
}

```

#### c.用户自定义class

```python
[class_0.py]
class A(object):
  name = 'python'
  def __init__(self):
    print 'A::__init__'

  def f(self):
    print 'A::f'

  def g(self,aValue):
    self.value = aValue
    print self.value

a = A()
a.f()
a.g(10)
```

> 创建class对象

>> class的动态元信息
