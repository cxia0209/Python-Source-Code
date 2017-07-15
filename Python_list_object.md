### 1.Python中的List对象(变长对象的可变对象)

#### a.PyListObject对象

```c
/* PyListObject定义 */
[listobject.h]
typedef struct{
  PyObject_VAR_HEAD  //其中ob_size为已经占用的申请内存
  //ob_item为指向元素列表的指针，实际上,Python中的list[0]就是ob_item[0]
  PyObject **ob_item;
  int allocated;    //allocated为一次申请的所有内存
}
```

#### b.PyListObject对象的创建与维护

> 创建对象

```c
[listobject.c]
PyObject* PyList_New(int size){
  PyListObject* op;
  size_t nbytes;

  //内存数量计算，溢出检查
  nbytes = size * sizeof(PyObject*);
  if(nbytes / sizeof(PyObject*) != (size_t)size)
      return PyErr_NoMemory();

  //为PyListObject对象申请空间
  if(num_free_lists){
    //缓冲池可用
    num_free_lists--;
    op = free_lists[num_free_lists];
    _Py_NewReference((PyObject *)op);
  }else{
    //缓冲池不可用
    op = PyObject_GC_New(PyListObject, &PyList_Type);
  }

    //为PyListObject对象中维护的元素列表申请空间
    if(size <= 0)
      op->ob_item = NULL;
    else{
      op->ob_item = (PyObject **) PyMem_MALLOC(nbytes);
      memset(op->ob_item,0,nbytes);
    }

  op->ob_size = size;
  op->allocated = size;
  return (PyObject *)op;
}
```

```c
/* free_lists最多会维护80个PyListObject对象 */
[listobject.c]
#define MAXFREELISTS 80
static PyListObject* free_lists[MAXFREELISTS];
static int num_free_lists = 0;
```

> 设置元素

![new_pylistobj](/image/new_pylistobj.png)

```c
/* 设置元素 */
[listobject.c]
int PyList_SetItem(register PyObject* op, register int i, register PyObject* newitem){
  register PyObject* olditem;
  register PyObject** p;

  //索引检察
  if( i < 0 || i >= ((PyListObject *)op) -> ob_size){
    PyErr_SetString(PyExc_IndexError, "list assignment index out of range");
    return -1;
  }

  //设置元素
  p = ((PyListObject *)op)->ob_item + i;
  olditem = *p;
  *p = newitem;
  Py_XDECREF(olditem);
  return 0;
}
```

```c
/* 插入元素 */
[listobject.c]
int PyList_Insert(PyObject* op, Py_ssize_t where, PyObject* newitem){
  ......//类型检查
  return ins1((PyListObject *)op,where,newitem);
}

static int ins1(PyListObject* self, Py_ssize_t where, PyObject* v){
  Py_ssize_t i,n = self->ob_size;
  PyObject** items;
  .....
  //调整列表容量
  if(list_resize(self,n+1) == -1)
      return -1;
  //确定插入点
  if(where < 0){
    where += n;
    if(where < 0)
      where = 0;
  }

  if( where > n){
    where = n;
  }

  //插入元素
  items = self->ob_item;
  for(i = n; --i >= where; )
      items[i+1] = items[i];
  Py_INCREF(v);
  items[where] = v;
  return 0;
}

static int list_resize(PyListObject* self, int newsize){
  PyObject** items;
  size_t new_allocated;
  int allocated = self->allocated;

  //不需要重新申请内存
  if(allocated >= newsize && newsize >= (allocated >> 1)){
    self->ob_size = newsize;
    return 0;
  }

  //计算重新申请的内存大小
  new_allocated = (newsize >> 3) + (newsize < 9 ? 3 : 6 ) + newsize;
  if(newsize == 0)
      new_allocated = 0;

  items = self->ob_item;
  PyMem_RESIZE(items,PyObject*,new_allocated); //最终调用C中的realloc
  self->ob_item = items;
  self->ob_size = newsize;
  self->allocated = new_allocated;
  return 0;
}
```

```c
/* append方法 */
[listobject.c]
//Python提供的C API
int PyList_Append(PyObject* op, PyObject* newitem){
  if(PyList_Check(op) && (newitem != NULL))
      return app1((PyListObject *)op,newitem);
  return -1;
}

//与append对应的c函数
static PyObject* listappend(PyListObject* self, PyObject* v){
  if(app1(self,v) == 0)
      Py_RETURN_NONE;
  return NULL;
}

static int app1(PyListObject* self,PyObject* v){
  int n = PyList_GET_SIZE(self);
  ......
  if(list_resize(self,n+1) == -1)
      return -1;
  Py_INCREF(v);
  PyList_Set_ITEM(self,n,v);
  return 0;
}
```

> 删除元素

```c
[listobject.c]
static PyObject* listremove(PyListObject* self, PyObject* v){
  int i;
  for(i = 0; i < self.ob_size; i++){
    //比较list中的元素与删除元素
    int cmp = PyOBject_RichCompareBool(self->ob_item[i],v,Py_EQ);
    if(cmp > 0){
      if(list_ass_slice(self,i,i+1,(PyObject* )NULL) == 0)
          Py_RETURN_NONE;
      return NULL;
    }
    else if(cmp < 0)
        return NULL;
  }
  PyErr_SetString(PyExc_ValueError, "list.remove(x) : x not in list");
  return NULL;
}
```

```c
int list_ass_slice(PyListObject* a, Py_ssize_t ilow, Py_ssize_t ihigh, PyObject* v)
/* 两种语义 */
1.a[ilow:ihigh] = v if v != NULL
2.del a[ilow:ihigh] if v == NULL
```

#### PyListObject对象缓冲池

```c
[listobject.c]
static void list_dealloc(PyListObject* op){
  int i;

  //销毁PyListObject对象维护的元素列表
  if(op->ob_item != NULL){
    i = op->ob_size;
    while(--i >= 0){
      Py_XDECREF(op->ob_item[i]);
    }
    PyMem_FREE(op->ob_item);
  }

  //释放PyListObject自身
  if(num_free_lists < MAXFREELISTS && PyList_CheckExact(op))
      free_lists[num_free_lists++] = op;
  else
      op->ob_type->tp_free((PyObject *)op);
}
```
