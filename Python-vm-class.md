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

```python
[PyCodeObject for class_0.py]
class A(object):
0 LOAD_CONST 0 (A)
3 LOAD_NAME  0 (object)
6 BUILD_TUPLE  1
9 LOAD_CONST  1 (code object for A)
12 MAKE_FUNCTION  0
15 CALL_FUNCTION  0


18 BUILD_CLASS
19 STORE_NAME  1 (A)
```

![make_function](/image/make_function.png)

```python
[PyCodeObject for class A]
0 LOAD_NAME 0 (__name__)
3 STORE_NAME 1 (__module__)
name = 'Python'
6 LOAD_CONST 0 ('Python')
9 STORE_NAME 2 (name)
def __init__(self):
12 LOAD_CONST 1 (code object for function __init__)
15 MAKE_FUNCTION 0
18 STORE_NAME 3 (__init__)
def f(self):
21 LOAD_CONST 2 (code object for function f)
24 MAKE_FUNCTION 0
27 STORE_NAME 4 (f)
def g(self,aValue):
30 LOAD_CONST 3 (code object for function g)
33 MAKE_FUNCTION 0
36 STORE_NAME 5 (g)

39 LOAD_LOCALS
40 RETURN_VALUE
```

```c
[LOAD_LOCALS]
if((x = f->f_locals) != NULL){
  PUSH(x);
  continue;
}
```

```c
[CALL_FUNCTION]
PyObject **sp;
sp = stack_pointer;
x = call_function(&sp,oparg);
stack_pointer = sp;
PUSH(x);
```

![call_function_stack](/image/call_function_stack.png)

>> metaclass

```c
[BUILD_CLASS]
u = TOP(); //class的动态元信息f_locals
v = SECOND(); // class 的基类列表
w = THIRD(); //class的名'A'
STACKADJ(-2);
x = build_class(u,v,w);
SET_TOP(x);
Py_DECREF(u);
Py_DECREF(v);
Py_DECREF(w);
```

![class_A_build_class](/image/class_A_build_class.png)

>> 获得metaclass

```c
[ceval.c]
PyObject* build_class(PyObject* methods, PyObject* bases, PyObject* name){
  PyObject* metaclass = NULL,*result, *base;

  //检查属性表中是否有指定的_metaclass_
  if(PyDict_Check(methods))
    metaclass = PyDict_GetItemString(methods,"__metaclass__"); //metaclass为静态元信息，methods为动态元信息
  if(metaclass != NULL)
    Py_INCREF(metaclass);
  else if(PyTuple_Check(bases) && PyTuple_GET_SIZE(bases) > 0){
    // 获得A的第一基类,object
    base = PyTuple_GET_ITEM(bases,0)
    //获得object.__class__
    metaclass = PyObject_GetAttrString(base,"__class__");
  }
  else{
    ....
  }
  result = PyObject_CallFunctionObjArgs(metaclass,name,bases,methods,NULL);
  ...
  return result;
}
```

![explain_meta_dynamic](/image/explain_meta_dynamic.png)

![meta_dynamic](/image/meta_dynamic.png)

>> 调用metaclass

```c
[object.h]
typedef PyObject* (*ternaryfunc)(PyObject *, PyObject *, PyObject *);

[abstract.c]
PyObject* PyObject_Call(PyObject* func,PyObject* arg,PyObject* kw){
  //arg即是PyObject_CallFunctionObjArgs中打包得到的tuple对象
  ternaryfunc call = func->ob_type->tp_call;
  PyObject* result = (*call)(func,arg,kw);
  return result;
}

[typeobject.c]
type_call(PyTypeObject* type, PyObject* args, PyObject* kwds){
  PyObject* obj;

  obj = type->tp_new(type,args,kwds);

  ...//如果创建的是实例对象，则调用"__init__" 进行初始化
  return obj;
}

[typeobject.c]
static PyObject* type_new(PyTypeObject* metatype, PyObject* args, PyObject* kwds){
  //metatype是PyType_Type<type 'type'>,args中包含了(类名，基类列表，属性表)
  PyObject* name,*bases, *dict;
  static char* kwlist[] = {"name","bases","dict",0};
  PyTypeObject* type,*base,*tmptype,*winner;
  PyHeapTypeObject* et;
  Py_ssize_t slotoffset;

  //将args中的（类名，基类列表，属性表）分别解析到name,bases,dict三个变量中
  PyArg_ParseTupleAndKeywords(args,kwds,"SO!O!:type",kwlist,
                              &name,
                              &PyTuple_Type,&bases.
                              &PyDict_Type,&dict);
  .....//确定最佳metaclass,存储在PyObject* metatype中
  ....//确定最佳base,存储在PyObject* base中

  //为class对象申请内存
  //尽管PyType_Type为0,但PyBaseObject_Type的为PyType_GenericAlloc,
  //在PyType_Ready中被继承了
  //创建的内存大小为tp_basicsize _ tp_itemsize
  type = (PyTypeObject *)metatype->tp_alloc(metatype,nslots);
  et = (PyHeapTypeObject *)type;
  et->ht_name = name;

  //设置PyTypeObject中的各个域
  type->tp_as_number = &et->as_number;
  type->tp_as_sequence = &et->as_sequence;
  type->tp_as_mapping = &et->as_mapping;
  type->tp_as_buffer = &et->as_buffer;
  type->tp_name = PyString_AS_STRING(name);

  //设置基类和基类列表
  type->tp_bases = bases;
  type->tp_base = base;

  //设置属性表
  type->tp_dict = dict = PyDict_Copy(dict);

  //如果自定义class中重写了__new__，将__new__对应的函数改造为static函数
  tmp = PyDict_GetItemString(dict,"__new__");
  tmp = PyStaticMethod_New(tmp);
  PyDict_SetItemString(dict,"__new__",tmp);

  //为class对象对应的instance对象设置内存大小信息
  slotoffset = base->basicsize;
  type->tp_dictoffset = slotoffset;
  slotoffset += sizeof(PyObject *);
  type->tp_weaklistoffset = slotoffset;
  slotoffset += sizeof(PyObject *);
  type->tp_basicsize = slotoffset;
  type->tp_itemsize = base->tp_itemsize;
  ......

  //调用PyType_Ready(type)对class对象进行初始化
  PyType_Ready(type);
  return (PyObject *)type;
}
```

![compare_user_bulitin](/image/compare_user_bulitin.png)

#### d.从class对象到instance对象

```python
[PyCodeObject for class_0.py]
a = A()
22 LOAD_NAME 1 (A)
25 CALL_FUNCTION 0
28 STORE_NAME 2 (a)
```

![instance_local](/image/instance_local.png)

<p>创建class对象，Python虚拟机使用的是type_new；而对于instance对象，Python虚拟机则使用object_new</p>

```c
[typeobject.c]
type_call(PyTypeObject* type, PyObject* args, PyObject* kwds){
  PyObject* obj;

  obj = type->tp_new(type,args,kwds);

  type = obj->ob_type;  //如果创建的是实例对象，则调用"__init__" 进行初始化
  type->tp_init(obj,args,kwds);
  return obj;
}
```

```c
//由于A重写了__init__，所以在fixup_slot_dispatchers中,tp_init会指向slotdefs中指定的与"__init__"对应的slot_tp_init
[typeobject.c]
static int slot_tp_init(PyObject* self, PyObject* args, PyObject* kwds){
  static PyObject* init_str;
  PyObject* meth = lookup_method(self,"__init__",&init_str);
  PyObject_Call(meth,args,kwds);
  return 0;
}
```

![class_to_instance](/image/class_to_instance.png)

#### e.访问instance对象中的属性

```python
[PyCodeObject for class_0.py]
a.f()
31 LOAD_NAME 2 (a)
34 LOAD_ATTR 3 (f)
37 CALL_FUNCTION 0
40 POP_TOP
```

```c
[LOAD_ATTR]
w = GETITEM(names,oparg);  //PyStringObject对象"f"
v = TOP(); //instance对象
x = PyObject_GetAttr(v,w);
Py_DECREF(v);
SET_TOP(x);
```

```c
[object.c]
PyObject* PyObject_GetAttr(PyObject* v, PyObject* name){
  PyTypeObject* tp = v->ob_type;
  //通过tp_getattro获得属性对应对象
  if(tp->tp_getattro != NULL)  //优先调用
    return (*tp->tp_getattro)(v,name);

  //通过tp_getattr获得属性对应对象
  if(tp->tp_getattr != NULL)
    return (*tp->tp_getattr)(v,PyString_AS_STRING(name));

  //属性不存在，排除异常
  PyErr_Format(PyExc_AttributeError, "'%.50s' object has no attribute '%.400s'",tp->tp_name,PyString_AS_STRING(name));
  return NULL;
}

```


```python
#属性访问算法
#首先寻找'f'对应的descriptor
#注意：hasattr会在<class A>的mro列表中寻找符号'f'
if hasattr(A,'f'):
  descriptor = A.f

type = descriptor.__class__
if hasattr(type,'__get__') and (hasattr(type,'__set__') or 'f' not in a.__dict__):
  return type.__get__(descriptor,a,A)

# 通过descriptor访问失败,在instance对象自身__dict__中寻找属性
if 'f' in a.__dict__:
  return a.__dict__['f']

#instance对象的__dict__中找不到属性,返回a的基类列表中某个基类里定义的函数
# 注意：这里的descriptor实际指向了一个普通函数
if descriptor:
  return descriptor.__get__(descriptor,a,A)

```

> instance对象中的__dict__

![a__dict__](/image/a__dict__.png)

```c
//PyObject_GenericGetAttr
[object.c]
PyObject* PyObject_GenericGetAttr(PyObject* obj, PyObject* name){
  PyTypeObject* tp = obj->ob_type;
  PyObject* res = NULL;
  Py_ssize_t dictoffset;
  PyObject** dictptr;

  //inline _PyObject_GetDictPtr函数的代码
  dictoffset = tp->tp_dictoffset;
  if(dictoffset != 0){
    PyObject* dict;
    if(dictoffset < 0){
      ...//处理变长对象
    }
    dictptr = (PyObject **)((char *)obj + dictoffset);
    dict = *dictptr;
    res = PyDict_GetItem(dict,name);
  }
  ....
}
```

```c
//PyObject_GenericSetAttr
[object.c]
int PyObject_GenericSetAttr(PyObject* obj, PyObject* name, PyObject* value){
  PyTypeObject* tp = obj->ob_type;
  PyObject** dictptr;
  ....
  dictptr = _PyObject_GetDictPtr(obj);
  if(dictptr != NULL){
    PyObject* dict = *dictptr;
    if(dict == NULL && value != NULL){
      //这里创建了instance对象中的__dict__
      dict = PyDict_New();
      *dictptr = dict;
    }
    ....
  }
  ....
}
```

> 再论descriptor

<p>一般而言,对于一个Python中的对象obj,如果obj.__class__ 对应的class对象中存在__get__、__set__、__delete__三种操作，那么obj为Python的一个descriptor</p>

```c
[slotdefs in typeobject.c]
.....
TPSLOT("__get__",tp_descr_get,...),
TPSLOT("__set__",tp_descr_set,....),
TPSLOT("__delete__",tp_descr_set,....)
```

<p>如果细分，那么descriptor还可以分为如下两种:</p>

>> data descriptor: type中定义了__get__和__set__的descriptor

>> non data descriptor: type中只定义了__get__的descriptor

![get_attr](/image/get_attr.png)

<p>如果待访问的属性是一个descriptor，若它存在于class对象的tp_dict中，会调用其__get__方法；若它存在于instance对象的tp_dict中，则不会调用其__get__方法</p>

![descriptor](/image/descriptor.png)

> 函数变身

```c
//PyFunction_Type中，"__get__"对应的tp_descr_get被设置成了&func_descr_get，意味着A.f实际上是一个descriptor
//又由于PyFunction_Type并没有设置tp_descr_set，所以A.f是一个non data descriptor
//并且a.__dict__中没有符号'f'的存在,所以a.f的返回值将被descriptor改变，结果将是A.f.__get__,也就是func_descr_get(A.f,a,A)
[funcobject.c]
/* Bind a function to an object */
static PyObject* func_descr_get(PyObject* func,PyObject* obj, PyObject* type){
  if(obj == Py_None)
    obj = NULL;
  return PyMethod_New(func,obj,type);
}

[classobject.c]
PyObject* PyMethod_New(PyObject* func, PyObject* self, PyObject* class){
  register PyMethodObject* im;
  im = free_list;
  if(im != NULL){
    //使用缓冲池
    free_list = (PyMethodObject *)(im->im_self);
    PyObject_INIT(im,&PyMethod_Type);
  }
  else{
    //不使用缓冲池，直接创建PyMethodObject
    im = PyObject_GC_New(PyMethodObject,&PyMethod_Type);
  }

  im->im_weakreflist = NULL;
  im->im_func = func;
  //这里就是"self" ~~~!!!
  im->im_self = self;
  im->im_class = class;
  _PyObject_GC_TRACK(im);
  return (PyObject *)im;
}
```

```c
//PyMethodObject
[classobject.h]
typedef struct {
  PyObject_HEAD
  PyObject* im_func;   //可调用的PyFunctionObject对象,'f'
  PyObject* im_self;   //用于成员函数调用的self参数，instance对象(a)
  PyObject* im_class;   //class对象(A)
  PyObject* im_weakreflist;
} PyMethodObject;
```

> 无参函数的调用

```c
[ceval.c]
static PyObject* call_function(PyObject** pp_stack, int oparg){
  int na = oparg & 0xff;
  int nk = (oparg>>8) & 0xff;
  int n = na + 2*nk;
  PyObject** pfunc = (*pp_stack) - n - 1;
  PyObject* func = *pfunc;
  PyObject* x, *w;

  if(PyCFunction_Check(func) && nk == 0){
    ....
  }else{
    //从PyMethodObject对象中抽取PyFunctionObject对象和self参数
    if(PyMethod_Check(func) && PyMethod_GET_SELF(func) != NULL){
      PyObject* self = PyMethod_GET_SELF(func);
      func = PyMethod_GET_FUNCTION(func);
      //self参数入栈，调整参数信息变量
      *pfunc = self;
      na++;
      n++;
    }
    if(PyFunction_Check(func))
      x = fast_function(func,pp_stack,n,na,nk);
    else
      x = do_call(func,pp_stack,na,nk);
  }
  ....
  return x;
}
```

![self](/image/self.png)

> 带参函数的调用

> Bound Method(a.f) 和 Unbound Method(A.f)

<p>本质区别在于PyFunctionObject有没有与instance对象绑定在PyMethodObject中, Bound Method 完成了绑定动作，而Unbound Method 没有完成绑定动作</p>

> 千变万化的descriptor

>> 用descriptor实现static method

```python
[class_2.py]
class A(object):
  def g(value):
    print value
  g = staticmethod(g)  #staticmethod存在于Python启动并进行初始化设置的builtin名字空间中
```

```c
[funcobject.c]
typedef struct {
  PyObject_HEAD
  PyObject* sm_callable;
} staticmethod;

[funcobject.c]
static int sm_init(PyObject* self,PyObject* args, PyObject* kwds){
  staticmethod* sm = (staticmethod *)self;
  PyObject* callable;

  PyArg_UnpackTuple(args,"staticmethod",1,1,&callable);
  sm->sm_callable = callable;
  return 0;
}
```

<p>PyStaticMethod_Type，创建的staticmethod实际上也是一个descriptor，在PyStaticMethod_Type中，tp_descr_get指向了sm_descr_get</p>

```c
[funcobject.c]
static PyObject* sm_descr_get(PyObject* self, PyObject* obj, PyObject* type){
  staticmethod* sm = (staticmethod *)self;
  return sm->sm_callable;
}
```
