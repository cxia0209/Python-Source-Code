### 1.Python的编译结果--Code对象与pyc文件

#### a.Python程序的执行过程

<p>Python虚拟机是一种抽象层次更高的虚拟机</p>

#### b.Python编译器的编译结果--PyCodeObject对象

> PyCodeObject对象pyc文件

<p>对于Python编译器来说，PyCodeObject对象是真正的编译结果，pyc文件只是这个对象在硬盘上的表现形式</p>

> Python源码中的PyCodeObject

```c
[code.h]
typedef struct {
  PyObject_HEAD
  int co_argcount; /* #arguments, except *args */
  int co_nlocals; /* #local variables */
  int co_stacksize; /* #entries needed for evaluation stack */
  int co_flags;
  PyObject* co_code; /* instruction opcodes */
  PyObject* co_consts; /* list (constants used) */
  PyObject* co_names; /* list of strings (names used) */
  PyObject* co_varnames; /* tuple of strings (local variable names) */
  PyObject* co_freevars; /* tuple of strings (free variable names) */
  PyObject* co_cellvars; /* tuple of strings (cell variable names) */
  /* The rest doesn't count for hash/cmp */
  PyObject* co_filename; /* string (where it was loaded from) */
  PyObject* co_name; /* string (name, for reference) */
  int co_firstlineno; /* first source line number */
  PyObject* co_lnotab; /* string (encoding add<->lineno mapping) */
  void* co_zombieframe; /* for optimization only */
} PyCodeObject;
```

<p>当进入一个新的名字空间或者作用域时，就进入一个新的Code Block</p>

<p>名字空间链</p>

> pyc文件

```python
import imp
import sys

def generate_pyc(name):
    fp,pathname,description = imp.find_module(name)
    try:
        imp.load_module(name,fp,pathname,description)
    finally:
        if fp:
            fp.close()

if __name__ == '__main__':
    generate_pyc(sys.argv[1])
```

> 在Python中访问PyCodeObject对象

```python
source = open('demo.py').read()
co = compile(source,'demo.py','exec')
type(co)
```

#### c.Pyc文件的生成

> 创建pyc文件的具体过程

```c
[import.c]
static void write_compiled_module(PyCodeObject* co, char* cpathname, long mtime){
  FILE* fp;
  //排他性打开文件
  fp = open_exclusive(cpathname);
  //写入python的magic number，用来解决因为python字节码不兼容的问题
  PyMarshal_WriteLongToFile(pyc_magic,fp,Py_MARSHAL_VERSION);
  //写入时间
  PyMarshal_WriteLongToFile(mtime,fp,Py_MARSHAL_VERSION);
  //写入PyCodeObject对象
  PyMarshal_WriteObjectToFile((PyObject *)co,fp,Py_MARSHAL_VERSION);
}
```

```c
/* python2.5 pyc_number 的定义 */
[import.c]
#define MAGIC (62131 | ((long)'\r' << 16) | ((long)'\n' << 24))
static long pyc_magic = MAGIC
```

```c
[marshal.c]
typedef struct {
  FILE *p;
  int depth;
  PyObject* strings; /* dict on marshal, list on unmarshal 写入时指向PyDictObject对象,读出时指向PyListObject对象*/
} WFILE;

#define w_byte(c,p) putc((c),(p)->fp)

static void w_long(long x, WFILE* p){
  w_byte((char)(x & 0xff),p);
  w_byte((char)((x>>8) & 0xff), p);
  w_byte((char)((x>>16) & 0xff), p);
  w_byte((char)((x>>24) & 0xff),p);
}

static void w_string(char* s,int n, WFILE* p){
  fwrite(s,1,n,p->fp);
}

static void w_object(PyObject* v, WFILE* p){
  ...
  /*面对PyCodeObject*/
  else if(PyCode_Check(v)){
    PyCodeObject* co = (PyCodeObject *)v;
    w_byte(TYPE_CODE,p);
    w_long(co->co_argcount,p);
    .....
    w_object(co->co_code,p);
    w_object(co->co_consts,p);
    w_object(co->co_names,p);
    .....
    w_object(co->co_lnotab,p);
  }
  ....
  /*面对PyListObject*/
  else if(PyList_Check(v)){
    w_byte(TYPE_LIST,p);
    n = PyList_GET_SIZE(v);
    w_long((long)n,p);
    for(i = 0;i < n; i++){
      w_object(PyList_GET_ITEM(v,i),p);
    }
  }
  ..../*面对PyIntObkect*/
  else if(PyInt_Check(v)){
    w_byte(TYPE_INT,p);
    w_long(x,p);
  }
}
```

> 向pyc文件写入字符串

```c
[marshal.c]
/*写入用PyDictObject*/
void PyMarshal_WriteObjectToFile(PyObject* x, FILE* fp, int version){
  WFILE wf;
  wf.fp = fp;
  wf.strings = (version > 0) ? PyDict_New() : NULL;
  w_object(x,&wf);
}
```

```c
/* 在w_object的字符串处理部分 */
...
else if(PyString_Check(v)){
  if(p->strings && PyString_CHECK_INTERNED(v)){
    //获得PyStringObject对象在strings符号
    PyObject* o = PyDict_GetItem(p->strings,v);
    //intern 字符串的非首次写入
    if(o){
      long w = PyInt_AsLong(o);
      w_byte(TYPE_STRINGREF,p);
      w_long(w,p);
      goto exit;
    }
    //intern字符串男的首次写入
    else{
      o = PyInt_FromLong(PyDict_Size(p->strings));
      PyDict_SetItem(p->strings,v,o);
      Py_DECREF(o);
      w_byte(TYPE_INTERNED,p);
    }
    //写入普通string
    else{
      //写入字符串的类型TYPE_STRING
      w_byte(TYPE_STRING,p);
    }

    //写入字符串的长度
    n = PyString_GET_SIZE(v);
    w_long((long)n,p);
    //写入字符串
    w_string(PyString_AS_STRING(v),n,p);
  }
}
```

![type_refcount](/image/type_refcount.png)

![pyc_intern_string](/image/pyc_intern_string.png)

```c
/*由于PyDictObject没有访问索引的能力，所以读出时使用PyListObject*/
[marshal.c]
PyObject* PyMarshal_ReadObjectFromFile(FILE* fp){
  RFILE rf;
  PyObject* result;
  rf.fp = fp;
  rf.strings = PyList_New(0);
  result = r_object(&rf);
  return result;
}
```

![pyc_read](/image/pyc_read.png)

> 一个PyCodeObject，多个PyCodeObject

![pycode_qiantao](/image/pycode_qiantao.png)

#### d.Python的字节码

<p>一共定义了104条字节码指令</p>

```c
[opcode.h]
#define STOP_CODE 0
#define POP_TOP 1
#define ROT_TWO 2
....
#define CALL_FUNCTION_KW 141
#define CALL_FUNCTION_VAR_KW 142
#define EXTENDED_ARG 143
```

#### e.解析pyc文件
