### 1.Python中的Dict对象

#### a.使用散列表(hash table)

<p>开放地址法 + 伪删除</p>

#### b.PyDictOject

>  关联容器的entry

```c
[dictobject.h]
typedef struct{
  Py_ssize_t me_hash;     /* cached hash code of me_key */
  PyObject* me_key;
  PyObject* me_value;
} PyDictEntry;
```

<p>PyDictObject三种状态转换:Unused态，Active态，Dummy态</p>

![station_trans](/image/station_trans.png)

> 关联容器的实现

```c
[dictobject.h]
#define PyDict_MINSIZE 8
typedef struct _dictobject PyDictObject;
struct _dictobject{
  PyObject_HEAD
  Py_ssize_t ma_fill;  //元素个数: Active + Dummy
  Py_ssize_t ma_used; //元素个数: Active
  Py_ssize_t ma_mask;
  PyDictEntry* ma_table;
  PyDictEntry* (*ma_lookup)(PyDictObject* mp, PyObject* key, long hash);  //搜索策略
  PyDictEntry ma_smalltable[PyDict_MINSIZE];
}
```

![dict_8](/image/dict_8.png)

#### c.PyDictObject的创建和维护

> PyDictObject对象创建

```c
[dictobject.c]
typedef PyDictEntry dictentry;
typedef PyDictObject dictobject;

#define INIT_NONZERO_DICT_SLOTS(mp) do{
  (mp)->ma_table = (mp)->ma_smalltable;
  (mp)->ma_mask = PyDict_MINSIZE - 1;
}while(0)

#define EMPTY_TO_MINSIZE(mp) do{
  memset((mp)->ma_smalltable,0,sizeof((mp)->ma_smalltable));
  (mp)->ma_used = (mp)->ma_fill = 0;
  INIT_NONZERO_DICT_SLOTS(mp);
}while (0)

PyObject* PyDIct_New(void){
  register dictobject* mp;
  //自动创建dummy对象
  if(dummy == NULL){
      dummy = PyString_FromString("<dummy key>");
  }


  if(num_free_dicts){
    ...//使用缓冲池
  }
  else{
    //创建PyDictObject对象
    mp = PyObject_GC_New(dictobject,&PyDict_Type);
    EMPTY_TO_MINSIZE(mp);
  }
  mp->ma_lookup = lookdict_string;
  return (PyObject* )mp;
}
```
> PyDictObject中的元素搜索

<p>两种搜索策略,lookdict和lookdict_string(默认搜索策略)</p>

![first_exam](/image/first_exam.png)

```c
[dictobject.c]
static dictentry* lookdict(dictobject *mp, PyObject *key, register long hash){
  register size_t i;
  register size_t perturb;
  register dictentry *freeslot;
  register size_t mask = mp->ma_mask;
  dictentry *ep0 = mp->ma_table;
  register dictentry *ep;

  register int restore_error;
  register int checked_error;
  register int cmp;
  PyObject* err_type, *err_value, *err_tb;
  PyObject* startkey;

  //散列,定位冲突探测链的第一个entry
  i = hash & mask;
  ep = &ep0[i];

  //1.entry处于Unused态
  //2.entry中的key与待搜索的key匹配
  if(ep->me_key == NULL || ep->me_key == key)
    return ep;

  //第一个entry处于Dummy态,设置freeslot
  if(ep->me_key == dummy)
    freeslot = ep;
  else{
    //检查Active态entry
    if(ep->me_hash == hash){
      startkey = ep->me_key;
      cmp = PyObject_RichCompareBool(startkey,key,Py_EQ);  //值相同 or 引用相同
      if(cmp > 0)
          return ep;
    }
    freeslot = NULL;
  }
  ....
}
```

![next_entry](/image/next_entry.png)

```c
/*如果第一个entry不匹配，在探测链上找*/
[dictobject.c]
static dictentry* lookdict(dictobject* mp,PyObject* key, register long hash){
  register int i;
  register unsigned int perturb;
  register dictentry* freeslot;
  register unsigned int mask = mp->ma_mask;
  dictentry *ep0 = mp->ma_table;
  register dictentry* ep;
  register int cmp;
  PyObject* startkey;
  ....
  for(perturb = hash;;perturb >>= PERTURB_SHIFT){

    //寻找探测链上下一个entry
    i = (i<<2) + i + perturb + 1;
    ep = &ep0[i & mask];

    //到达Unused态entry,搜索失败
    if(ep->me_key == NULL)
      return freeslot == NULL ? ep : freeslot;


    //检查"引用相同"是否成立
    if(ep->me_key == key)
      return ep;


    //检查“值相同”是否成立
    if(ep->me_hash == hash && ep->me_key != dummy){
      startkey = ep->me_key;
      cmp = PyObject_RichCompareBool(startkey,key,Py_EQ);
      if(cmp > 0)
        return ep;
    }   //设置freeslot
    else if(ep->me_key == dummy && freeslot == NULL)
      freeslot = ep;
  }

}
```

```c
/* 默认搜索lookdict_string */
/* Python 自身大量使用 */
[dictobject.c]
static dictentry* lookdict_string(dictobject* mp, PyObject* key, register long hash){
  register int i;
  register unsigned int perturb;
  register dictentry* freeslot;
  register unsigned int mask = mp->ma_mask;
  dictentry* ep0 = mp->ma_table;
  register dictentry* ep;

  //选择搜索策略
  if(!PyString_CheckExact(key)){
    mp->ma_lookup = lookdict;
    return lookdict(mp,key,hash);
  }

  //搜索第一阶段：检查冲突链上第一个entry
  //散列，定位冲突探测链的第一个entry
  i = hash & mask;
  ep = &ep0[i];

  //1.entry处于Unused态
  //2.entry中的key与待搜索的key匹配
  if(ep->me_key == NULL || ep->me_key == key)
    return ep;

  //第一个entry处于Dummy态，设置freeslot
  if(ep->me_key == dummy)
    freeslot = ep;
  else{
    //检查Active态entry
    if(ep->me_hash == hash && _PyString_Eq(ep->me_key,key)){ //_PyString_Eq保证能处理非PyStringObject* 对象
      return ep;
    }
    freeslot = NULL;
  }

  //搜索第二阶段：遍历冲突链，检查每一个entry
  for(perturb = hash; ; perturb >> PERTURB_SHIFT){
    i = (i << 2) + i + perturb + 1;
    ep = &ep0[i&mask]
    if(ep->me_key == NULL)
      return freeslot == NULL ? ep : freeslot;
    if(ep->me_key == key
      || (ep->me_hash == hash && ep->me_hash != dummy &&
          _PyString_Eq(ep->me_key, key)))
      return ep;
    if(ep->me_key == dummy && freeslot == NULL)
        freeslot = ep;
  }
}
```

> 插入与删除

<p>插入</p>

```c
[dictobject.c]
static void insertdict(register dictobject* mp, PyObject* key, long hash , PyObject* value){
  PyObject* old_value;
  register dictentry* ep;

  ep = mp->ma_lookup(mp,key,hash);

  //搜索成功
  if(ep->me_value != NULL){
    old_value = ep->me_value;
    ep->me_value = value;
    Py_DECREF(old_value);
    Py_DECREF(key);
  }
  //搜索失败
  else{
    if(ep->me_key == NULL) //Unused
      mp->ma_fill++;
    else                   //Dummy
      Py_DECREF(ep->me_key);
    ep->me_key = key;
    ep->me_hash = hash;
    ep->me_value = value;
    mp->ma_used++;
  }
}
```

```c
/* 在调用insertdict之前先设置hash值 */
[dictobject.c]
int PyDict_SetItem(register PyObject* op, PyObject* key, PyObject* value){
  register dictobject* mp;
  register long hash;
  register Py_ssize_t n_used;

  mp = (dictobject *)op;
  //计算hash值
  if(PyString_CheckExact(key)){
    hash = ((PyStringObject *)key)->ob_shash;
    if(hash == -1)
      hash = PyObject_Hash(key);
  }
  else{
    hash = PyObject_Hash(key);
    if(hash == -1)
      return -1;
  }

  //插入(key,value)元素对
  n_used = mp->ma_used;
  insertdict(mp,key,hash,value);

  //必要时调整dict的内存空间
  if(!(mp->ma_used > n_used && mp->ma_fill*3 >= (mp->ma_mask + 1)*2)) //如果装载率大于等于2/3,改变table大小
    return 0;
  return dictresize(mp,mp->ma_used*(mp->ma_used > 50000 ? 2 : 4));
}
```

```c
/* 如何改变table大小 */
static int dictresize(dictobject* mp, int minused){
  Py_ssize_t newsize;
  dictentry* oldtable, *newtable, *ep;
  Py_ssize_t i;
  int is_oldtable_malloced;
  dictentry small_copy[PyDict_MINSIZE];

  //确定新的table的大小
  for(newsize = PyDict_MINSIZE; newsize <= minused && newsize > 0; newsize <<=1);

  oldtable = mp->ma_table;
  is_oldtable_malloced = (oldtable != mp->ma_smalltable);

  //新的table可以使用mp->ma_smalltable
  if(newsize == PyDict_MINSIZE){
    newtable = mp->ma_smalltable;
    if(newtable == oldtable){
      if(mp->ma_fill == mp->ma_used){
        //没有任何dummy态entry，直接返回
        return 0;
      }
      //将旧table拷贝，进行备份
      memcpy(small_copy,oldtable,sizeof(small_copy));
      oldtable = small_copy;
    }
  }

  //新的table不能使用ma->ma_smalltable，需要在系统堆上申请
  else{
    newtable = PyMem_NEW(dictentry,newsize);
  }

  //设置新的table
  mp->ma_table = newtable;
  mp->ma_mask = newsize - 1;
  memset(newtable,0,sizeof(dictentry)*newsize);
  mp->ma_used = 0;
  i = mp->ma_fill;
  mp->ma_fill = 0;

  //处理旧table中的entry
  //Active态entry，搬移到新table中
  //Dummy态entry，调整key的引用计数，丢弃该entry
  for(ep = oldtable; i> 0; ep++){
    if(ep->me_value != NULL){ /* active entry */
      --i;
      insertdict(mp,ep->me_key,ep->me_hash,ep->me_value);
    }
    else if(ep->me_key != NULL){/* dummy entry */
      --i;
      assert(ep->me_key == dummy);
      Py_DECREF(ep->me_key);
    }
  }

  //必要时释放旧table所维护的内存空间
  if(is_oldtable_malloced)
    PyMem_DEL(oldtable);
  return 0;
}
```

<p>删除</p>

```c
[dictobject.c]
int PyDict_DelItem(PyObject* op, PyObject* key){
  register dictobject* mp;
  register long hash;
  register dictentry* ep;
  PyObject* old_value, *old_key;

  //获得hash值
  if(!PyString_CheckExact(key))
}
```
