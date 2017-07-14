### 1.Python中的字符串对象(变长对象中的不可变对象)

#### a.PyStringObject与PyString_Type

```c
[stringobject.h]
typedef struct {
  PyObject_VAR_HEAD //其中有个ob_size记录可变长度内存的大小
  long ob_shash; //缓存该对象的hash值，初始值为-1
  int ob_state; //标记了该对象是否已经过intern机制的处理
  char ob_sval[1];
} PyStringObject;
```

```c
/* hash值算法 */
[stringobject.h]
static long string_hash(PyStringObject *a){
  register int len;
  register unsigned char *p;
  register long x;

  if(a->ob_shash != -1)
    return a->ob_shash;
  len = a->ob_size;
  p = (unsigned char *) a->ob_sval;
  x = *p << 7;
  while(--len >= 0){
    x = (1000003*x) ^ *p++;
  }
  x ^= a->ob_size;
  if(x == -1)
      x = -2;
  a->ob_shash = x;
  return x;
}
```

```c
[stringobject.c]
PyTypeObject PyString_Type = {
  PyObject_HEAD_INIT(&PyType_Type)
  0,
  "str",
  sizeof(PyStringObject),
  sizeof(char),
  ....
  (reprfunc)string_repr, /* tp_repr */
  &string_as_number,  /* tp_as_number */
  &string_as_sequence, /* tp_as_sequence */
  &string_as_mapping, /* tp_as_mapping */
  (hashfunc)string_hash, /* tp_hash */
  0, /* tp_call */
  ....
  string_new /* tp_new */
  PyObject_Del, /*  tp_free */
}
```

#### b.创建PyStringObject对象

> 从PyString_FromString创建

```c
[stringobject.c]
PyObject* PyString_FromString(const char* str){
  register size_t size;
  register PyStringObject *op;

  //判断字符串长度
  size = strlen(str);
  if(size > PY_SSIZE_T_MAX){
    return NULL;
  }

  //处理 null string
  if(size == 0 && (op = nullstring) != NULL){
    return (PyObject*)op;
  }

  /* 创建新的PyStringObject对象，并初始化 */
  /* Inline PyObject_NewVar */
  op = (PyStringObject *)PyObject_MALLOC(sizeof(PyStringObject) + size);
  PyObject_INIT_VAR(op,&PyString_Type,size);
  op->ob_shash = -1;
  op->ob_sstate = SSTATE_NOT_INTERNED;
  memcpy(op->ob_sval,str,size+1);
  ...
  return (PyObject*)op;
}
```

![PyStringObject_mem](/image/PyStringObject_mem.png)

> 从PyString_FromStringAndSize创建

```c
[stringobject.c]
PyObject* PyString_FromStringAndSize(const char* str, int size){
  register PyString *op;
  //处理null string
  if(size == 0 && (op = nullstring) != NULL){
    return (PyObject*)op;
  }

  //处理字符,检查字符缓冲区是否已经有了该字符对象，如果有则直接返回
  if(size == 1 && str != NULL && (op = characters[*str & UCHAR_MAX]) != NULL){
    return (PyObject *)op;
  }

  //创建新的PyStringObject对象，并初始化
  //Inline PyObject_NewVar
  op = (PyStringObject*)PyObject_MALLOC(sizeof(PyStringObject) + size);
  PyObject_INIT_VAR(op,&PyString_Type,size);
  op->ob_shash = -1;
  op->ob_sstate = SSTATE_NOT_INTERNED;
  if(str != NULL)
      memcpy(op->ob_sval,str,size);
  op->ob_size[size] = '\0';
  ....
  return (PyObject*)op;
}
```

#### c.字符串对象的intern机制

<p>当字符串长度为0或1时，需要进行PyString_InternInPlace，这就是intern机制</p>

```c
[stringobject.c]
PyObject* PyString_FromString(const char* str){
  register size_t size;
  register PyStringObject *op;

  .... //创建PyStringObject对象

  //intern(共享)长度较短的PyStringObject对象
  if(size == 0){
    PyObject* t = (PyObject *)op;
    PyString_InternInPlace(&t);
    op = (PyStringObject *)t;
    nullstring = op;
  }else if(size == 1){
    PyObject* t = (PyObject *)op;
    PyString_InternInPlace(&t);
    op = (PyStringObject *)t;
    characters[*str & UCHAR_MAX] = op;
  }

  return (PyObject *)op;
}
```

<p>被intern之后的字符串，在整个Python的运行期间，系统中都只有唯一一个与字符串对应的PyStringObject对象</p>

```c
/* intern */
[stringobject.c]
void PyString_InternInPlace(PyObject **p){
  register PyStringObject *s = (PyStringObject *)(*p);
  PyObject *t;
  //对PyStringObject进行类型和状态检查
  if(!PyString_CheckExact(s))
    return;
  if(PyString_CHECK_INTERNED(s))
    return;
  //创建记录经intern机制处理后的PyStringObject的dict
  if(interned = NULL){  // 在stringobject.c中被定义为static PyObject* interned
    interned = PyDict_New();
  }
  //检查PyStringObject对象s是否存在对应的intern后的PyStringObject对象
  t = PyDict_GetItem(interned,(PyObject *)s);
  if(t){
    //注意这里对引用计数的调整
    Py_INCREF(t);
    Py_DECREF(*p);
    *p = t;
    return;
  }

  //在interned中记录检查PyStringObject对象s
  PyDict_SetItem(interned,(PyObject *)s, (PyObject *)s);
  //注意这里对引用计数的调整
  s->ob_refcnt -= 2;  //在将PyObject指针作为key和value添加到interned中时，PyDictObject会通过两个指针对引用计数进行两次加1
  // 调整s中的itern状态标志
  PyString_CHECK_INTERNED(s) = SSTATE_INTERNED_MORTAL;
}
```

![intern_bef_aft](/image/intern_bef_aft.png)

```c
[stringobject.c]
static void string_dealloc(PyObject* op){
  switch (PyString_CHECK_INTERNED(op)) {
    case SSTATE_NOT_INTERNED:
        break;
    case SSTATE_INTERNED_MORTAL:
        /* revive dead object temporarily for DelItem */
        op->ob_refcnt = 3;
        if(PyDict_DelItem(interned,op) != 0)
          Py_FatalError("deletion of interned string failed");
        break;
    case SSTATE_INTERNED_IMMORTAL:
        Py_FatalError("Immortal interned string died.");
    default:
        Py_FatalError("Inconsistent interned string state.");
  }
  op->ob_type->tp_free(op);
}
```

```c
/* 创建SSTATE_INTERNED_IMMORTAL对象 */
[stringobject.c]
void PyString_InternImmortal(PyObject **p){
  PyString_InternInPlace(p)
  if(PyString_CHECK_INTERNED(*p) != SSTATE_INTERNED_IMMORTAL){
    PyString_CHECK_INTERNED(*p) = SSTATE_INTERNED_IMMORTAL;
    Py_INCREF(*p);
  }
}
```

#### d.字符缓冲池

> 为PyStringObject中的一个字节的字符对应的PyStringObject对象设计了一个对象池characters

```c
static PyStringObject* characters[UCHAR_MAX + 1]; // UCHAR_MAX是一个平台相关的常量
#define UCHAR_MAX 0xff //win32平台
```

```c
/* 如果字符串只有一个字符 */
[stringobject.c]
PyObject* PyString_FromStringAndSize(const char* str, int size){
  ...
  else if(size == 1 && str != NULL){
    PyObject* t = (PyObject *)op;
    PyString_InternInPlace(&t);
    op = (PyStringObject *)t;
    characters[*str & UCHAR_MAX] = op;
    Py_INCREF(op);
  }
  return (PyObject *)op;
}
```

![1_char_intern](/image/1_char_intern.png)

#### PyStringObject效率相关问题

> 字符串连接

<p>Python中"+"进行字符串连接效率非常低下，因为PyStringObject对象是一个不可变对象，每次连接需要创建新的PyStringObject对象</p>

*通过利用PyStringObject的join操作来对操作，只分配一次内存，效率大大提高*

```c
/* 通过“+”操作符对字符串进行连接 */

static PyObject* string_concat(register PyStringObject* a, register PyObject* bb){
  register unsigned int size;
  register PyStringObject* op;
  #define b ((PyStringObject *)bb)
  ...
  //计算字符串连接后的长度
  size  = a->ob_size + b->ob_size;

  /* Inline PyObject_NewVar */
  //创建新的PyStringObject对象，其维护的用于存储字符的内存长度为size

  op = (PyStringObject *)PyObject_MALLOC(sizeof(PyStringObject) + size);
  PyObject_INIT_VAR(op, &PyString_Type, size);
  op->ob_shash = -1;
  op->ob_sstate = SSTATE_NOT_INTERNED;

  //将a和b中的字符拷贝到新创建的PyStringObject中
  memcpy(op->ob_sval,a->ob_sval,(int)a->ob_size);
  memcpy(ob->ob_sval + a->ob_size, b->ob_sval, (int)b->ob_size);
  op->ob_sval[size] = '\0';
  return (PyObject *)op;

  #undef b
}

```

```c
/* 通过“join”操作符对字符串进行连接 */

```
