### Python 运行环境初始化

#### a.线程环境初始化

> 线程模型回顾

<p>Py_Initialize  ->  Py_InitializeEx</p>

```c
[pystate.h]
typedef struct _is{
  struct _is* next;
  struct _ts* tstate_head; //模拟进程环境中的线程集合

  PyObject* modules;
  PyObject* sysdict;
  PyObject* builtins;
  ....
} PyInterpreterState; //进程模拟

typedef struct _ts {
  struct _ts *next;
  PyInterpreterState* interp;
  struct _frame* frame; //模拟线程中的函数调用堆栈
  int recursion_depth;
  ...
  PyObject* dict;
  ...
  long thread_id;
} PyThreadState; //线程模拟
```

![pystate](/image/pystate.png)

> 初始化线程环境

```c
//创建进程状态
[pystate.c]
static PyInterpreterState* interp_head = NULL;

PyInterpreterState* PyInterpreterState_New(void){
  PyInterpreterState* interp = malloc(sizeof(PyInterpreterState));
  IF(interp != NULL){
    HEAD_INIT();
    interp->modules = NULL;
    interp->sysdict = NULL;
    interp->builtins = NULL;
    interp->tstate_head = NULL;
    interp->codec_search_path = NULL;
    interp->codec_search_cache = NULL;
    interp->codec_error_registry = NULL;
    HEAD_LOCK();
    interp->next = interp_head;
    interp_head = interp;
    HEAD_UNLOCK();
  }
  return interp;
}

```

```c
//创建线程状态
[pystate.c]
PyThreadState* PyThreadState_New(PyInterpreterState* interp){
  PyThreadState* tstate = (PyThreadState *)malloc(sizeof(PyThreadState));
  //设置获得线程中函数调用栈得操作
  if(_PyThreadState_GetFrame == NULL)
    _PyThreadState_GetFrame = threadstate_getframe;

  if(tstate != NULL){
    //在PyThreadState对象中关联 PyInterpreterState 对象
    tstate->interp = interp;
    tstate->frame = NULL;
    tstate->thread_id = PyThread_get_thread_ident();
    ....
    HEAD_LOCK();
    tstate->next = interp->tstate_head;
    //在PyInterpreterState对象中关联PyThreadState对象
    interp->tstate_head = tstate;
    HEAD_UNLOCK();
  }
  return tstate;
}
```
<p>_PyThreadState_Current全局变量，维护这当前活动的线程</p>

```c
[pystate.c]
PyThreadState* PyThreadState_Swap(PyThreadState* new){
  PyThreadState* old = _PyThreadState_Current;
  _PyThreadState_Current = new;
  return old;
}
```

<p>之后，开始转向类型系统的初始化</p>

```c
//接下来调用_PyFrame_Init来设置全局变量builtin_object
[frameobject.c]
static PyObject* builtin_object;

int _PyFrame_Init(){
  builtin_object = PyString_InternFromString("__builtins");
  return (builtin_object != NULL);
}
```

#### b.系统module初始化

> 创建__builtin__ modules

```c
[pythonrun.c]
void Py_InitializeEx(int install_sigs){
  ...
  interp->modules = PyDict_New();
  bimod = _PyBuiltin_Init();
}


[bltinmodule.c]
PyObject* _PyBuiltin_Init(void){
  PyObject* mod,* dict, *debug;
  //创建并设置__builtin__ module , PyModuleObject
  mod = Py_InitModule4("__builtin__",builtin_methods,builtin_doc,(PyObject *)NULL,PYTHON_API_VERSION);
  //将所有Python内建类型加入到__builtin__ module中
  dict = PyModule_GetDict(mod);

  #define SETBUILTIN(NAME,OBJECT)
    if (PyDict_SetItemString(dict,NAME,(PyObject *)OBJECT) < 0)
      return NULL;

    SETBUILTIN("None", Py_None);
    ...
    SETBUILTIN("dict", &PyDict_Type);
    ...
    SETBUILTIN("int", &PyInt_Type);
    SETBUILTIN("list", &PyList_Type);
    ...
    return mod;
  #undef SETBUILTIN
}

[modsupoort.c]
PyObject* Py_InitModule4(const char* name, PyMethodDef* methods,char* doc, PyObject* passthrough, int module_api_version){
  PyObject* m,*d,*v,*n;
  PyMethodDef* ml;
  ...
  //创建module对象
  if((m = PyImport_AddModule(name)) == NULL){
    return NULL;
  }

  //设置module中的（符号，值）对应关系

  d = PyModule_GetDict(m);
  if(methods != NULL){
    n = PyString_FromString(name);
    //遍历methods指定的module对象中应包含的操作集合
    for(ml = methods; ml->ml_name != NULL; ml++){
      if((ml->ml_flags & METH_CLASS) || (ml->ml_flags & METH_STATIC)){
        PyErr_SetString(PyExc_ValueError,"module functions cannot be set", "METH_CLASS or METH_STATIC");
        return NULL;
      }
      v = PyCFunction_NewEx(ml,passthrough,n);
      PyDict_SetItemString(d,ml->ml_name,v);
    }
  }

  if(doc != NULL){
    v = PyString_FromString(doc);
    PyDict_SetItemString(d,"__doc__",v);
  }

  return m;
}
```

> 创建module对象

```c
[import.c]
PyObject* PyImport_AddModule(char* name){
  //获得Python维护的module集合
  PyObject* modules = PyImport_GetModuleDict();
  PyObject* m;

  //若module集合中没有名为name的module对象，则创建之;否则,直接返回module对象
  if((m = PyDict_GetItemString(modules,name)) != NULL && PyModule_Check(m))
    return m;

  m = PyModule_New(name);

  //将新创建的module对象放入Python全局module集合中
  PyDict_SetItemString(modules,name,m);
  return m;
}
```

```c
[pystate.h]
#define PyThreadState_GET() (_PyThreadState_Current)

[import.c]
PyObject* PyImport_GetModuleDict(void){
  // 通过PyThreadState_GET()获得当前线程状态对象
  // 基于当前线程状态对象获得PyInterpreterState对象
  // 基于PyInterpreterState对象获得其维护的全局module集合
  PyInterpreterState* interp = PyThreadState_GET()->interp;
  return interp->modules;
}
```

```c
[moduleobject.c]
typedef struct {
  PyObject_HEAD
  PyObject* md_dict;
} PyModuleObject;

PyObject* PyModule_New(char* name){
  PyModuleObject* m;
  PyObject* nameobj;
  m = PyObject_GC_New(PyModuleObject, &PyModule_Type);
  nameobj = PyString_FromString(name);
  m->md_dict = PyDict_New();
  PyDict_SetItemString(m->md_dict, "__name__", nameobj);
  PyDict_SetItemString(m->md_dict, "__doc__", Py_None);
  return (PyObject *)m;
}
```

>> 设置module对象

```c
//builtin_methods
[methodobject.h]
typedef PyObject* (*PyCFuntion)(PyObject* , PyObject*);

struct PyMethodDef{
  char* ml_name; /* The name of the built-in function/method */
  PyCFuntion ml_meth; /* The C function that impletments it */
  int ml_flags;
  char* ml_docl /* The __doc__ attribute, or NULL */
};

typedef struct PyMethodDef PyMethodDef;

[bltinmodule.c]
static PyMethodDef builtin_methods[] = {
  ...
  {"dir", builtin_dir, METH_VARARGS, dir_doc},
  ...
  {"getattr", builtin_getattr, METH_VARARGS, getattr_doc},
  ...
  {"len", builtin_len, METH_Om len_doc},
  ...
  {NULL,NULL},
}
```

![PyMethodDoc](/image/PyMethodDoc.png)

```c
//PyCFuntionObject对象
[methodobject.h]
typedef struct {
  PyObject_HEAD
  PyMethodDef* m_ml; /* Description of the C function to call */
  PyObject* m_self; /* Passed as 'self' arg to the C func, can be NULL */
  PyObject* m_module; /* The __module__ attribute, can be anything */
} PyCFuntionObject;

[methodobject.c]
PyObject* PyCFunction_NewEx(PyMethodDef* ml, PyObject* self, PyObject* module){
  PyCFunctionObject* op;
  op = free_list;
  if(op != NULL){
    free_list = (PyCFunctionObject *)(op->m_self);
    PyObject_INIT(op,&PyCFunction_Type);
  }
  else{
    op = PyObject_GC_New(PyCFunctionObject, &PyCFunction_Type);
  }

  op->m_ml = ml;
  op->m_self = self;
  op->m_module = module;
  return (PyObject *)op;
}
```

![builtin_module](/image/builtin_module.png)

```c
[moduleobject.c]
PyObject* PyModule_GetDict(PyObject* m){
  PyObject* d;
  d = ((PyModuleObject *))->md_dict;
  return d;
}

[pythonrun.c]
void Py_InitializeEx(int install_sigs){
  ...
  bimod = _PyBuiltin_Init();
  interp->builtins = PyModule_GetDict(bimod);
  ...
}
```

> 创建sys module

>> sys module 备份

```c
[pythonrun.c]
void Py_InitializeEx(int install_sigs){
  ...
  //创建sys module
  sysmod = _PySys_Init();
  interp->sysdict = PyModule_GetDict(sysmod);

  //备份sys module
  _PyImport_FixupExtension("sys","sys");
  ....
}
```

![sys_module_after](/image/sys_module_after.png)

```c
//对扩展module备份维护
[import.c]
static PyObject* extension = NULL;

PyObject* _PyImport_FixupExtension(char* name, char* filename){
  PyObject* modules,*mod,*dict,*copy;
  //如果extensions为空,则创建PyDictObject对象
  if(extensions == NULL){
    extensions = PyDict_New();
  }

  //获得interp->modules
  modules = PyImport_GetModuleDict();
  // 在interp->modules中查询以name为名的module
  mod = PyDict_GetItemString(modules,name);
  //抽取module中的dict
  dict = PyModule_GetDict(mod);
  //对dict进行拷贝
  copy = PyDict_Copy(dict);
  //将拷贝得到的新的dict存储在extensions中
  PyDict_SetItemString(extensions,filename,copy);
  return copy;
}
```

> 设置module搜索路径

```c
[pythonrun.c]
void Py_InitializeEx(int install_sigs){
  ...
  PySys_SetPath(Py_GetPath());
  ...
}

[sysmodule.c]
void PySys_SetPathO(char* path){
  PyObject* v;
  v = makepathobject(path,DELIM);
  PySys_SetObject("path",v);
}

int PySys_SetObject(char* name, PyObject* v){
  PyThreadState* tstate = PyThreadState_GET();
  PyObject* sd = tstate->interp->sysdict;
  if(v == NULL){
    if(PyDict_GetItemString(sd,name) == NULL)
      return 0;
    else
      return PyDict_DelItemString(sd,name);
  }
  else
    return PyDict_SetItemString(sd,name,v);
}
```

```c
[pythonrun.c]
void Py_InitializeEx(int install_sigs){
  //这里设置了sys.modules,可以看到,他就是interp->modules
  PyDict_SetItemString(interp->sysdict,"modules", interp->modules);
  //初始化import机制的环境
  _PyImport_Init();
  //初始化python内建exceptions
  _PyExc_Init();
  //备份exceptions module和__builtin__ module
  _PyImport_FixupExtension("exceptions","exceptions");
  _PyImport_FixupExtension("__builtin__","__builtin__");

  //在sys module中添加一些对象，用于import机制
  _PyImportHooks_Init();
  ...
}
```

> 创建__main__ module

```c
[pythonrun.c]
static void initmain(void){
  PyObject* m,*d;
  //创建__main__ module, 并将其插入interp->modules中
  m = PyImport_AddModule("__main__");
  //获得__main__ module 中的dict
  d = PyModule_GetDict(m);
  if(PyDict_GetItemString(d,"__builtin__") == NULL){
    //获得interp->modules中的__builtin__ module
    PyObject* bimod = PyImport_ImportModule("__builtin__");
    //将("__builtin__"，__builtin__ module)插入到__main__ module的dict中
    PyDict_SetItemString(d,"__builtin__",bimod);
  }
}
```

>> 设置site-specfic的module的搜索路径

```c
[pythonrun.c]
void Py_InitializeEx(int install_sigs){
  ...
  _PyImportHooks_Init();

  initmain(); /* Module __main__ */
  initsite(); /* Module site */
  ...
}
```

```c
[pythonrun.c]
static void initsite(void){
  PyObject* m;
  m = PyImport_ImportModule("site");
}
```

![site](/image/site.png)

#### c.激活python虚拟机

```c
[main.c]
int Py_Main(int argc, char** argv){
  Py_Initialize();
  ...
  PyRun_AnyFileExFlags(
    fp,
    filename == NULL ? "<stdin>" : filename,
    filename != NULL, &cf);
  ...
}
```

```c
[pythonrun.c]
int PyRun_AnyFileExFlags(FILE* fp, const char* filename, int closeit, PyCompilerFlags* flags){
  //根据fp是否代表交互环境，对程序流程进行分流
  if(Py_FdIsInterative(fp,filename)){
    int err = PyRun_InterativeLoopFlags(fp,filename,flags);
    if(closeit)
      fclose(fp);
    return err;
  }
  else
    return PyRun_SimpleFileExFlags(fp,filename,closeit,flags);
}
```

> 交互式运行方式

```c
[pythonrun.c]
int PyRun_InterativeLoopFlags(FILE* fp, const char* filename, PyCompilerFlags* flags){
  PyObject* v;
  int ret;

  //创建交互式环境提示符 ">>>"
  v = PySys_GetObject("ps1");
  if(v == NULL){
    PySys_SetObject("ps1",v = PyString_FromString(">>> "));
  }

  //创建交互式环境提示符"..."
  v = PySys_GetObject("ps2");
  if(v == NULL){
    PySys_SetObject("ps2", v = PyString_FromString("... "))
  }

  //进入交互式环境
  for(;;){
    ret = PyRun_InterativeOneFlags(fp,filename,flags);
    if(ret == E_EOF)
      return 0;
  }

}

int PyRun_InterativeOneFlags(FILE* fp, char* filename, PyCompilerFlags* flags){
  PyObject* m,*d,*v,*w;
  mod_ty mod;
  PyArena* arena;
  char* ps1 = "", *ps2 = "";

  v = PySys_GetObject("ps1");
  if(v != NULL){
    ps1 = PyString_AsString(v);
  }

  w = PySys_GetObject("ps2");
  if(w != NULL){
    ps2 = PyString_AsString(w);
  }

  //编译用户在交互式环境下输入的python语句
  arena = PyArena_New();
  mod = PyParser_ASTFromFile(fp,filename,Py_single_input,ps1,ps2,flags,&errcode,arena);

  //获得<module __main__>中维护的dict
  m = PyImport_AddModule("__main__");
  d = PyModule_GetDict(m);

  //执行用户输入的Python语句
  v = run_mod(mod,filename,d,d,flags,arena);
  PyArena_Free(arena);
  return 0;
}
```

> 脚本文件运行方式

```c
[python.h]
#define Py_file_input 257

[pythonrun.c]
int PyRun_SimpleFileExFlags(FILE* fp,const char* filename, int closeit, PyCompilerFlag* flags){
  PyObject* m,*d,*v;
  const char* ext;
  //在__main__ module中设置"__file__"属性
  m = PyImport_AddModule("__module__");
  d = PyModule_GetDict(m);
  if(PyDict_GetItemString(d,"__file__") == NULL){
    PyObject* f = PyString_FromString(filename);
    PyDict_SetItemString(d,"__file__",f);
  }

  //执行脚本文件
  v = PyRun_FileExFlags(fp,filename,Py_file_input,d,d,closeit,flags);
  ...
}

PyObject* PyRun_FileExFlags(FILE* fp, const char* filename, int start, PyObject* globals, PyObject* locals, int closeit, PyCompilerFlags* flags){
  PyObject* ret;
  mod_ty mod;
  PyArena* arena = PyArena_New();
  //编译
  mod = PyParser_ASTFromFile(fp,filename,start,0,0,flags,NULL,arena);
  if(closeit)
    fclose(fp);
  //执行
  ret = run_mod(mod,filename,globals,locals,flags,arena);
  PyArena_Free(arena);
  return ret;
}
```

> 启动虚拟机

```c
//启动字节码虚拟机
[pythonrun.c]
static PyObject* run_mod(mod_ty mod, const char* filename, PyObject* globals, PyObject* locals, PyCompilerFlags* flags, PyArena* arena){
  PyCodeObject* co;
  PyObject* v;
  //基于AST编译字节码指令序列，创建PyCodeObject对象
  co = PyAST_Compile(mod,filename,flags,arena);
  //创建PyFrameObject对象,执行PyCodeObject对象中的字节码指令序列
  v = PyEval_EvalCode(co,globals,locals);
  Py_DECREF(co);
  return v;
}
```

```c
[ceval.c]
PyObject* PyEval_EvalCode(PyCodeObject* co, PyObject* globals, PyObject* locals){
  return PyEval_EvalCodeEx(co,
          globals,locals,
          (PyObject **)NULL, 0,
          (PyObject **)NULL, 0,
          (PyObject **)NULL, 0,
          NULL);
}

PyObject* PyEval_EvalCodeEx(PyCodeObject* co, PyObject* globals, PyObject* locals,
            PyObject **args,int argcount,PyObject **kws, int kwcount,
            PyObject **defs,int defcount, PyObject* closure)
{
  register PyFrameObject* f;
  register PyObject* retval = NULL;
  register PyObject** fastlocals, **freevars;
  PyThreadState* tstate = PyThreadState_GET();
  PyObject* x,*u;
  ...
  f = PyFrame_New(tstate,co,globals,locals);
  ...
  fastlocals = f->f_localsplus;
  ...
  retval = PyEval_EvalFrameEx(f,0);
  retur retval;
}
```

> 名字空间

```c
[frameobject.c]
PyFrameObject* PyFrame_New(PyThreadState* tstate, PyCodeObject* code, PyObject* globals, PyObject* locals){
  PyFrameObject* back = tstate->frame;
  PyFrameObject* f;
  PyObject* builtins;
  int extras, ncells, nfrees,i;

  //设置builtin名字空间
  if(back == NULL || back->f_globals != globals){
    builtins = PyDict_GetItem(globals,builtin_object);
  }else{
    builtins = back->f_builtins;
  }
  f->f_builtins = builtins;
  f->f_back = back;

  //设置global名字空间
  f->f_globals = globals;

  //设置local名字空间
  if((code->co_flags & (CO_NEWLOCALS | CO_OPTIMIZED)) == (CO_NEWLOCALS | CO_OPTIMIZED))
    locals = NULL; //调用函数，不需创建local名字空间
  else if(code->co_flags & CO_NEWLOCALS){
    locals = PyDict_New()
  }else{
    if(locals == NULL)
      locals = globals //一般情况下，locals和globals指向相同的dict
  }

  f->f_locals = locals;
  ...
  return f;
}
```

```c
[frameobject.c]
static PyObject* builtin_object;
int _PyFrame_Init(){
  builtin_object = PyString_InternFromString("__builtins__");
  return (builtin_object != NULL);
}
```

<p>Python所有的线程都共享同样的builtin名字空间</p>
