### 1.Python模块的动态加载机制

#### a.import 前奏曲

```c
[IMPORT_NAME]
w = GETITEM(names,oparg); "sys"
x = PyDict_GetItemString(f->f_builtins,"__import__");  //__import__PyCFunctionObject对象
v = POP(); // Py_None
u = TOP(); // -1

//将python的import动作需要使用的信息打包到tuple中
if(PyInt_AsLong(u) != -1 || PyErr_Occurred()){
  w = PyTuple_Pack(5,w,f->f_globals,f->f_locals == NULL ? Py_None : f->f_locals, v, u);
}else{
  w = PyTuple_Pack(4,w,f->f_globals,f->f_locals == NULL ? Py_None : f->f_locals, v);
}

x = PyEval_CallObject(x,w);
SET_TOP(x);
```

```c
[cevcl.c]
#define PyEval_CallObject(func,arg) PyEval_CallObjectWithKeywords(func, arg,(PyObject *)NULL)

PyObject* PyEval_CallObjectWithKeywords(PyObject* func, PyObject* arg, PyObject* kw){
  PyObject* result;

  if(arg == NULL)
    arg = PyTuple_New(0);
  else if(!PyTuple_Check(arg)){
    PyErr_SetString(PyExc_TypeError,"argument list must be a tuple");
    return NULL;
  }

  if(kw != NULL &&  !PyDict_Check(kw)){
    PrErr_SetString(PyExc_TypeError,"keyword list must be a dictionary");
    return NULL;
  }

  result = PyObject_Call(func,arg,kw);
  return result;
}
```

```c
[methodobject.c]
PyTypeObject PyCFunction_Type = {
  PyObject_HEAD_INIT(&PyType_Type)
  0,
  "builtin_function_or_method",
  ...
  PyCFunction_Call, /* tp_call */
  ...
}

[methodobject.c]
PyObject* PyCFunction_Call(PyObject* func, PyObject* ARG, PyObject* kw){
  PyCFunctionObject* f = (PyCFunctionObject *)func;
  PyCFunction meth = PyCFuntion_GET_FUNCTION(func);
  PyObject* self = PyCFuntion_GET_SELF(func);
  int size;

  switch(PyCFunction_GET_FLAGS(func) & ~(METH_CLASS | METH_STATIC | METH_COEXIST)){
    case METH_VARARGS:
      if(kw == NULL || PyDict_Size(kw) == 0)
        return (*meth)(self,arg);
      break;
    case METH_VARARGS | METH_KEYWORDS:
    case METH_OLDARFS | METH_KEYWORDS:
      //函数调用
      return (*(PyCFunctionWithKeywords)meth)(self,arg,kw);
    ...
  }
  PyErr_Format(PyExc_TypeError, "%.200s() takes no keyword arguments", f->m_ml->ml_name);

  return NULL;
}
```

#### b.Python中import机制的黑盒探测

> 标准import

>> Python 内建module

>> 用户自定义module

>> 嵌套import

>> import package

![path_module](/image/path_module.png)

>> from与import

>> 符号重命名

>> 符号的销毁与重载

<p>如果该module不在pool中，这是python才执行动态加载的动作,如果希望动态改变新的module，则oython通过重新加载reload</p>


#### c.import机制的实现

<p>Python运行时的全局module pool的维护和搜索</p>

<p>解析与搜索module路径的树状结构</p>

<p>对不同文件格式的module的动态加载机制</p>

```c
[bltinmodule.c]
static PyObject* builtin__import__(PyObject* self, PyObject* args, PyObject*kwds){
  static char* kwlist[] = {"name","globals","locals","fromlist","level",0};
  char* name;
  PyObject* globals = NULL;
  PyObject* locals = NULL;
  PyObject* fromlist = NULL;
  int level = -1;

  //从tuple中解析出需要的信息
  if(!PyArg_ParseTupleAndKeywords(args,kwds,"s|oooi:__import__",kwlist,&name,&globals,&locals,&fromlist,&level))
    return NULL;
  return PyImport_ImportModuleLevel(name,globals,locals,fromlist,level);
}

int PyArg_ParseTupleAndKeywords(PyObject* args, PyObject*kw,const char* format,char* keywords[],...) //拆包
```

```c
[import.c]
PyObject* PyImport_ImportModuleLevel(char* name, PyObject* globals, PyObject* locals,PyObject* fromlist, int level){
  PyObject* result;
  lock_import();
  result = import_module_level(name,globals,locals,fromlist,level);
  unlock_import();
  return result;
}

[import.c]
static PyObject* import_module_level(char* name,PyObject* globals, PyObject* locals, PyObject* fromlist, int level){
  char buf[MAXPATHLEN + 1];
  int buflen = 0;
  PyObject* parent,*head,*next,*tail;
  //获得import动作发生的package环境
  parent = get_parent(globals,buf,&buflen,level);
  //解析module的“路径”结构,依次加载每一个package/module
  head = load_next(parent, Py_None, &name, buf, &buflen);
  tail = head;
  while(name){
    next = load_next(tail,tail,&name,buf,&buflen);
    tail = next;
  }

  //处理from ** import ***语句
  if(fromlist != NULL){
    if(fromlist == Py_None || !PyObject_IsTrue(fromlist))
      fromlist = NULL;
  }

  //import 的形式不是from *** import **, 返回head
  if(fromlist == NULL){
    return head;
  }

  //import 的形式是from *** import ** 返回tail
  if(!ensure_fromlist(tail,fromlist.buf,buflen,0)){
    return NULL;
  }

  return tail;
}
```

![fromlist](\image\fromlist.png)

> 解析 module/package树状结构

```c
[import.c]
static PyObject* get_parent(PyObject* globals, char* buf, Py_ssize_t* p_buflen, int level){
  PyObject* namestr = NULL;
  PyObject* pathstr = NULL;
  PyObject* modname,*modpath,*modules,*parent;

  //获得当前module的名字
  namestr = PyString_InternFromString("__name__");
  pathstr = PyString_InternFromString("__path__");
  *buf = '\0';
  *p_buflen = 0;
  modname = PyDict_GetItem(globals,namestr);
  modpath = PyDict_GetItem(globals,pathstr);
  if(modpath != NULL){
    //在package的__init__.py中进行import动作
    Py_ssize_t len = PyString_GET_SIZE(modname);
    strcpy(buf,PyString_AS_STRING(modname));
  }else{
    //在package中的module中进行import动作
    char* start = PyString_AS_STRING(modname);
    char* lastdot = strrchr(start,'.');
    size_t len;
    len = lastdot - start;
    buf[len] = '\0'
  }

  while (--level > 0) {
    char* dot = strrchr(buf,'.');
    *dot = '\0';
  }
  *p_buflen = len;

  //在sys.modules中查找当前package的名字对应的module对象
  modules = PyImport_GetModuleDict();
  parent = PyDict_GetItemString(modules,buf);
  return parent;
}
```

<p>Python中的import动作都是发生在某一个package的环境中</p>

```c
[import.c]
static PyObject* load_next(PyObject* mod, PyObject* altmod, char** p_name, cha* buf, int* p_buflen){
  char* name = *p_name;
  char* dot = strrchr(name,'.');
  size_t len;
  char* p;
  PyObject* result;

  ... // 获得下一个需要加载的package或module的名字

  // 对package或module进行import动作
  result = import_submodule(mod,p,buf);
  if(result == PyNone && altmod != mod){  //altmod == mod or altmod == Py_None
    result = import_submodule(altmod,p,p);
  }
  return result;
}
```

![buf_p](/image/buf_p.png)

> 加载 module/package

```c
static PyObject* import_submodule(PyObject* mod, char* subname, char* fullname){
  //获得sys.modules
  PyObject* modules = PyImport_GetModuleDict();
  PyObject* m = NULL;

  /* 约束:
    if mod == None: subname == fullname
    else: mod.__name__ + "." + subname == fullname
  */

  //在sys.modules中查找module/package是否已经被加载
  if((m = PyDict_GetItemString(modules,fullname)) != NULL){
    Py_INCREF(m);
  }
  else{
    PyObject* path, *loader = NULL;
    char* buf[MAXPATHLEN + 1];
    struct filedescr* fdp;
    FILE* fp = NULL;

    //获得import动作的路径信息
    if(mod == PyNone){
      path = NULL;
    }else{
      path = PyObject_GetAttrString(mod,"__path__");
    }

    buf[0] = '\0';

    //搜索module/package
    fdp = find_module(fullname,subname,path,buf,MAXPATHLEN +1 , &fp, &loader);
    //加载module/package
    m = load_module(fullname,fp,buf,fdp->type,loader);
    //将加载的module放入到sys.modules中
    add_submodule(mod,m,fullname,subname,modules);
  }
}
```

> 搜索module(subname.py/subname.pyc/subname.pyd/subname.pyo/subname.dll)

![find_module](/image/find_module.png)

```c
[importdl.h]
/* Definitions for dynamic loading of extension modules */
enum filetype{
  SEARCH_ERROR,
  PY_SOURCE,
  PY_COMPILED;
  C_EXTENSION,
  PY_RESOURCE, /* Mac only */
  PKG_DIRECTORY,
  C_BUILTIN,
  PY_FROZEN,
  PY_CODERESOURCE, /* Mac only */
  IMP_HOOK
};

struct filedescr{
  char* suffix;
  char* mode;
  enum filetype type;
};

extern struct filedescr* _PyImport_Filetab;
```

> 加载module

```c
[import.c]
static PyObject* load_module(char* name,FILE* fp,char* buf, int type, PyObject* loader){
  PyObject* modules;
  PyObject* m;
  int err;

  switch (type) {
    //py
    case PY_SOURCE:
      m = load_source_module(name,buf,fp);
      break;
    //pyc
    case PY_COMPILED:
      m = load_compiled_module(name,buf,fp);
      break;
    //dll(pyd)
    case C_EXTENSION:
      m = _PyImport_LoadDynamicModule(name,buf,fp);
      break;
    //加载package
      m = load_package(name,buf);
      break;
    case C_BUILTIN:
      if(buf != NUll && buf[0] != '\0')
        name = buf;
      //创建内建module
      init_builtin(name);
      //确认内建module出现在sys.modules中，如果没有则抛出异常
      modules = PyImport_GetModuleDict();
      m = PyDict_GetItemString(modules,name);
      if(m == NULL){
        ...//抛出异常
        return NULL;
      }
      Py_INCREF(m);
      break;
      ...
      return m;
  }
}
```

```c
//load package
[import.c]
static PyObject* load_package(char* name, char* pathname){
  PyObject* m,*d;
  PyObject* file = NULL;
  PyObject* path = NULL;
  int err;
  char buf[MAXPATHLEN + 1];
  FILE* fp = NULL;
  struct filedescr* fdp;

  //创建PyModuleObject对象，并加入sys.modules中
  m = PyImport_AddModule(name);
  d = PyModule_GetDict(m);
  ...

  //在package的目录夏寻找并加载__init__.py文件
  fdp = find_module(name, "__init__", path,buf,sizeof(buf), &fp, NULL);
  m = load_module(name,fp,buf,fdp->type,NULL);
  ...
  return m;
}
```

```c
//内建module
//init_builtin("math")
[import.c]
static int init_builtin(char* name){
  struct _inittab* p;

  //在内建module的备份中查找名为name的module
  if(_PyImport_FindExtension(name,name) != NULL)
    return 1;

  //遍历内建module集合，寻找匹配的module
  for(p = PyImport_Inittab; p->name != NULL; p++){  //PyImport_Inittab是一个全局变量，维护着一个内建module的完整列表
    if(strcmp(name,p->name) == 0){
      //初始化内建module
      (*p->initfunc)();
      //加入到内建module备份中
      _PyImport_FixupExtension(name,name);
      return 1;
    }
  }
  return 0;
}

[import.h]
struct _inittab{
  char* name;
  void (*initfunc)(void);
}

[import.c]
struct _inittab* PyImport_Inittab = _PyImport_Inittab;

[PC/config.c]
struct _inittab _PyImport_Inittab[] = {
  ...
  {"math",initmath},
  {"nt",initnt},
  ...
}
```

```c
//C 扩展module
[importdl.c]
PyObject* _PyImport_LoadDynamicModule(char* name,char* pathname, FILE* fp){
  PyObject* m;
  char* lastdot,*shortname,*packagecontext,*oldcontext;
  dl_funcptr p;
  //在python的module备份中检查是否有名为name的module
  if((m = _PyImport_FindExtension(name,pathname)) != NULL){
    Py_INCREF(m);
    return m;
  }
  ...

  //从dll中获得module的初始化函数的其实地址
  p = _PyImport_GetDynLoadFunc(name,shortname,pathname,fp);

  //调用module的初始化函数
  (*p)();
  //从sys.modules中获得已经被加载的module
  m = PyDict_GetItemString(PyImport_GetModuleDict(),name);
  //设置module的__file__属性
  PyModule_AddStringConstant(m,"__file__",pathname);
  //将module加入到python的module备份中
  _PyImport_FixupExtension(name,pathname);
  return m;
}
```

```c
[dynload_win.c]
dl_funcptr _PyImport_GetDynLoadFunc(char* fqname,char* shortname,char* pathname, FILE* fp){
  dl_funcptr p;
  char funcname[258], *import_python;
  //获得module的初始化函数名
  PyOS_snprintf(funcname,sizeof(funcname),"init%.200s",shortname);
  {
    HINSTANCE hDLL = NULL;
    //使用win32 API加载dll文件
    hDLL = LoadLibraryEx(pathname,NULL,LOAD_WITH_ALTERED_SEARCH_PATH);
    if(hDLL == NULL){
      ...//加载dll文件失败。抛出异常
    }else{
      char buffer[256];
      //获得当前python对应的dll文件名
      #ifdef_DEBUG
        PyOS_snprintf(buffer,sizeof(buffer),"python%d%d_d.dll",
      #else
        PyOS_snprintf(buffer,sizeof(buffer),"python%d%d.dll",
      #endif
        PY_MAJOR_VERSION,PY_MINOR_VERSION);
      //获得module中所引用的Python的dll文件名
      import_python = GetPythonImport(hDLL);
      //确保当前Python对应的dll即是module所引用的dll
      if(import_python && strcasecmp(buffer,import_python)){
        ...//dll文件不匹配,抛出异常
      }
    }
    //调用Win32 API获得module初始化函数的地址
    p = GetProcAddress(hDLL,funcname);
  }
  return p;
}
```

```c
[C extension module : abc.dll]
static PyMethodDef abc_methods[] = {
  {"hello",Hello,METH_VARARGS,"say hello"},
  {NULL,NULL}
};

EXPORT int initabc(void){
  Py_InitModule("abc",abc_methods);
  return 0;
}

[modsuport.h]
#define Py_InitModule(name,methods)
  Py_InitModule4(name,methods,(char *)NULL,(PyObject *)NULL,PYTHON_API_VERSION)
```
