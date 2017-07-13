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

  //处理字符
  if(size == 1 && str != NULL && (op = characters[*str & UNCHAR_MAX]) != NULL){
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
