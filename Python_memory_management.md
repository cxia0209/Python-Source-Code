### 1.Python的内存管理机制

#### a.内存管理架构

![mem_layer](/image/mem_layer.png)

> 第一层PyMem_API

```c
[pymem.h]
PyAPI_FUNC(void *) PyMem_Malloc(size_t);
PyAPI_FUNC(void *) PyMem_Realloc(void *, size_t);
PyAPI_FUNC(void) PyMem_Free(void *);

[object.h]
void* PyMem_Malloc(size_t nbytes){
  return PyMem_MALLOC(nbytes);
}

void* PyMem_Realloc(void *p, size_t nbytes){
  return PyMem_REALLOC(p,nbytes);
}

void PyMem_Free(void* p){
  PyMem_FREE(p);
}

[pymem.h]
#define PyMem_MALLOC(n) malloc((n) ? (n) : 1)
#define PyMem_REALLOC(n) realloc((p), (n) ? (n) : 1)
#define PyMem_FREE free
```

```c
[pymem.h]
#define PyMem_New(type,n)
  ( (type *)PyMem_Malloc((n) * sizeof(type)) )

#define PyMem_NEW(type,n)
  ( (type *)PyMem_MALLOC((n) * sizeof(type)) )

#define PyMem_Resize(p,type,n)
  ( (p) = (type *)PyMem_Realloc((p), (n) * sizeof(type)) )
#define PyMem_RESIZE(p,type,n)
  ( (p) = (type *)PyMem_REALLOC((p), (n) * sizeof(type)) )

#define PyMem_Del PyMem_Free
#define PyMem_DEL PyMem_FREE
```

<p>第二层构建了PyObject_位前缀的函数族,Pymalloc机制</p>

#### b.小块空间的内存池

<p>PyObject_Malloc、PyObject_Realloc、PyObject_Free</p>

> Block(block 只是一个概念上的东西， 实际不与python某个源码中的东西对应)

```c
[obmalloc.c]
#define ALIGNMENT 8 /* must be 2^N */
#define ALIGNMENT_SHIFT 3
#define ALIGNMENT_MASK (ALIGNMENT - 1)

[obmalloc.c]
#define SMALL_REQUEST_THRESHOLD 256  //block的大小的上限值
#define NB_SMALL_SIZE_CLASSES (SMALL_REQUEST_THRESHOLD / ALIGNMENT)
```

![block](/image/block.png)

```c
[obmalloc.c]
//从size class index 转念换到 size class
#define INDEX2SIZE(I) (((uint)(I)+ 1) << ALIGNMENT_SHIFT)

//从size class 转换到 size class size
size = (uint )(nbytes - 1 ) >> ALIGNMENT_SHIFT;
```

> Pool(通常为一个系统内存页)

```c
[obmalloc.c]
#define SYSTEM_PAGE_SIZE (4 * 1024)
#define SYSTEM_PAGE_SIZE_MASK (SYSTEM_PAGE_SIZE - 1)

#define POOL_SIZE SYSTEM_PAGE_SIZE /* must be 2^N */
#define POOL_SIZE_MASK SYSTEM_PAGE_SIZE_MASK
```

```c
[obmalloc.c]
typedef uchar block;

/* Pool for small blocks */
struct pool_header {
  union{
    block* _padding;
    uint count;
  } ref; /* number of allocated blocks */
  block* freeblock; /* pool's freelist head */
  struct pool_header* nextpool; /* next pool of this size class */
  struct pool_header* prevpool; /* previous pool */
  uint arenaindex; /* index into arenas of base adr */
  uint szidx; /* block size class index */
  uint nextoffset; /* bytes to virgin block */
  uint maxnextoffset; /* largest valid nextoffset */
};
```

```c
[obmalloc.c]-[convert 4k raw memory to pool]
#define ROUNDUP(x)  (((x) + ALIGNMENT_MASK) & ~ALIGNMENT_MASK)
#define POOL_OVERHEAD  ROUNDUP(sizeof(struct pool_header))
#define struct pool_header* poolp
#define uchar block

poolp pool;
block* bp;

...// pool指向了一块4KB的内存
pool->ref.count = 1
//设置pool的size class index
pool->szidx = size;
//将size class index转换为size，比如3转换为32字节
size = INDEX2SIZE(size);
//跳过用于pool_header的内存，并进行对齐
bp = (block *)pool + POOL_OVERHEAD
//实际就是pool->nextoffset = POOL_OVERHEAD + size + size
pool->nextoffset = POOL_OVERHEAD + (size << 1);
pool->maxnextoffset = POOL_SIZE - size;
pool->freeblock = bp + size;
*(block **)(pool->freeblock) = NULL;
return (void *)bp;
```

![pool_after_4kb](/image/pool_after_4kb.png)

```c
//申请内存
[obmalloc.c]-[allocate block]
if(pool != pool->nextpool){
  ++pool->ref.count;
  bp = pool->freeblock;
  ...
  if(pool->nextoffset <= pool->maxnextoffset){
    //有足够的block空间
    pool->freeblock = (block *)pool + pool->nextoffset;
    pool->nextoffset += INDEX2SIZE(size);
    *(block **)(pool->freeblock) = NULL;
    return (void *)bp;
  }
}
```

```c
[obmalloc.c]
//基于地址P获得离P最近的pool的边界地址
#define POOL_ADDR(P) ((poolp)((uptr)(P) & ~(uptr)POOL_SIZE_MASK))

void PyObject_Free(void* p){
  poolp pool;
  block* lastfree;
  poolp next,prev;
  uint size;

  pool = POOL_ADDR(p);
  //判断p指向的block是否属于pool
  if(Py_ADDRESS_IN_RANGE(p,pool)){
    *(block **)p = lastfree = pool->freeblock;
    pool->freeblock = (block *)p;
    ...
  }
}
```

```c
/* 遍历是通过freeblock = *freeblock */
[obmalloc.c]-[allocate block]
if(pool != pool->nextpool){
  ++pool->ref.count;
  bp = pool->freeblock;

  if((pool->freeblock = *(block **)bp) != NULL){
    return (void *bp);
  }

  if(pool->nextoffset <= pool->maxnextoffset){
    ....
  }
  ...
}
```

> arena

<p>多个pool聚合的结果就是一个arena,一个arena256KB</p>

```c
[obmalloc.c]
#define ARENA_SIZE (256 << 10) /* 256KB */

[obmalloc.c]
typedef uchar block;

struct arena_object {
  uptr address;
  block* pool_address;
  uint nfreepools;
  uint ntotalpools;
  struct pool_header* freepools;

  struct arena_object* nextarena;
  struct arena_object* prevarena;
}
```

>> "未使用"的arena和“可用”的arena

![pool_vs_arena](/image/pool_vs_arena.png)

<p>pool_header与arena_object对比：当pool_header被申请时，它所管理的pool集合的内存一定也被申请;但是当arena_object被申请时，它所管理的pool集合的内存则没有被申请</p>

<p>arena的两种状态: 当一个arena的arena_object没有与pool集合建立联系时，这时的arena处于“未使用”状态，一旦建立了联系，这时arena就转换到了“可用”状态。</p>

<p>”未使用“的arena的链表表头是unused_arena_objects,通过nextarena链接，是一个单项链表</p>

<p>”可用“的arena的链表表头是usable_arenas,通过nextarena与prevarena链接，是一样个双向链表</p>

![arenas](/image/arenas.png)

>> 申请arena

```c
[obmalloc.c]
//arenas管理着arena_object的集合
static struct arena_object* arenas = NULL;
//当前arenas中管理的arena_object的个数
static uint maxarena = 0;
//”未使用“arena_object链表
static struct arena_object* unused_arena_objects = NULL;
//”可用“arena_object链表
static struct arena_object* usable_arenas = NULL;
//初始化是需要申请的arena_object的个数
#define INITIAL_ARENA_OBJECTS 16;

static struct arena_object* new_arena(void){
  struct arena_object* arenaobj;
  uint excess; /* number of bytes above pool alignment */

  //判断是否需要扩充”未使用“arena_object列表
  if(unused_arena_objects == NULL){
    uint i;
    uint numarenas;
    size_t nbytes;

    //确定本次需要申请的arena_object的个数，并申请内存
    numarenas = maxarenas ? maxarenas << 1 : INITIAL_ARENA_OBJECTS;

    if(numarenas <= maxarenas)
      return NULL; //溢出

    nbytes = numarenas * sizeof(*arenas);

    if(nbytes/sizeof(*arenas) != numarenas)
      return NULL; //溢出

    arenaobj = (struct arena_object *)realloc(arenas,nbytes);

    if(arenaobj == NULL)
      return NULL;

    arenas = arenaobj;


    //初始化新申请的arena_object,并将其放入unused_arena_objects链表中
    for(i = maxarenas; i < numarenas; ++i){
      arenas[i].address = 0; /* mark as unassocaited */
      arenas[i].nextarena = i < numarenas -1 ? &arenas[i+1] : NULL;
    }

    /* Update globals */
    unused_arena_objects = &arenas[maxarenas];
    maxarenas = numarenas;
  }

  //从unused_arena_objects链表中取出一个”未使用“的arena_object
  arenaobj = unused_arena_objects;
  unused_arena_objects = arenaobj->nextarena;
  assert(arenaobj->address == 0);

  //申请arena_object管理的内存
  arenaobj->address = (uptr)malloc(ARENA_SIZE);
  ++narenas_currently_allocated;

  //设置pool集合的相关信息
  arenaobj->freepools = NULL;
  arenaobj->pool_address = (block *)arenaobj->address;
  arenaobj->nfreepools = ARENA_SIZE/POOL_SIZE;

  //将pool的起始地址调整为系统页的边界
  excess = (uint)(arenaobj->address & POOL_SIZE_MASK);
  if(excess != 0){
    --arenaobj->nfreepools;
    arenaobj->pool_address += POOL_SIZE - excess;
  }

  arenaobj->ntotalpools = arenaobj->nfreepools;

  return arenaobj;
}

```

> 内存池

>> 可用pool缓冲池--usedpools

<p>当Python在WITH_MEMORY_LIMITS编译符号打开的情况下进行编译时，Python的另一个符号会被激活，这个名为SMALL_MEMORY_LIMIT的符号限制了整个内存池的大小,同时也就限制了可以创建的arena的个数</p>

```c
[obmalloc.c]
#ifdef WITH_MEMORY_LIMITS
#ifndef SMALL_MEMORY_LIMIT
#define SMALL_MEMORY_LIMIT (64 * 1024 * 1024)  /* 64MB -- more? */
#endif
#endif


#ifdef WITH_MEMORY_LIMITS
#define MAX_ARENAS (SMALL_MEMORY_LIMIT/ARENA_SIZE)
#endif
```

<p>Python申请内存时，最基本的操作单元并不是arena，而是pool</p>

<p>pool的三种状态：used,full,empty</p>

![pool_status](/image/pool_status.png)

```c
//usedpools结构
[obmalloc.c]
typedef uchar block;

#define PTA(x) ((poolp)((uchar* )&usedpools[2 * (x)]) - 2 * sizeof(block *)))

#define PT(x) PTA(x), PTA(x)

static poolp usedpools[2 * (NB_SMALL_SIZE_CLASSES + 7)/8 * 8] = {
  PT(0),PT(1),PT(2),PT(3),PT(4),PT(5),PT(6),PT(7)
  #if NB_SMALL_SIZE_CLASSES > 8
    , PT(8), PT(9), PT(10), PT(11), PT(12), PT(13), PT(14), PT(15)
    ...
  #endif
}

//NB_SMALL_SIZE_CLASSES
[obmalloc.c]
#define NB_SMALL_SIZE_CLASSES (SMALL_REQUEST_THRESHOLD / ALIGNMENT)
```

![usedpools](/image/usedpools.png)

```c
[obmalloc.c]
void* PyObject_Malloc(size_t nbytes){
  block* bp;
  poolp pool;
  poolp next;
  uint size;

  if((nbytes - 1) < SMALL_REQUEST_THRESHOLD){
    LOCK();
    //获得size class index
    size = (uint )(nbytes - 1) >> ALIGNMENT_SHIFT
    pool = usedpools[size + size];
    //usedpools中有可用的pool
    if(pool != pool->nextpool){
      ....//usedpools中有可用的pool
    }

    ...//usedpools中无可用pool，尝试获取empty状态pool

  }
}
```

>> pool 的初始化

<p>!!!!!!arena没有size class的属性，而pool才有</p>

```c
[obmalloc.c]
void* PyObject_Malloc(size_t nbytes){
  block* bp;
  poolp pool;
  poolp next;
  uint size;

  if((nbytes - 1) < SMALL_REQUEST_THRESHOLD){
    LOCK();
    size = (uint)(nbytes - 1) >> ALIGNMENT_SHIFT;
    pool = usedpools[size + size];
    if(pool != pool->nextpool){
      ...//usedpools中有可用的pool
    }

    //usedpools中无可用pool，尝试获取empty状态pool
    //如果usable_arenas链表为空，则创建链表
    if(usable_arenas == NULL){
      //申请新的arena_object，并放入usable_arenas链表
      usable_arenas = new_arena();
      usable_arenas->nextarena = usable_arenas->prevarena = NULL;
    }

    //从usable_arenas链表中第一个arena的freepools中抽取一个可用的pool
    pool = usable_arenas->freepools;
    if(pool != NULL){
      usable_arenas->freepools = pool->nextpool;
      //调整usable_arenas链表中第一个arena中的可用pool数量
      //如果调整后数量为0,则将该arena从usable_arenas链表中摘除
      --usable_arenas->nfreepools;
      if(usable_arenas->nfreepools == 0){
        usable_arenas = usable_arenas->nextarena;
        if(usable_arenas != NULL){
          usable_arenas->prevarena = NULL;
        }
      }
      init pool:
        ...
    }

  }
}
```

>>> 初始化之一

```c
[obmalloc.c]
#define ROUNDUP(x)  (((x) + ALIGNMENT_MASK) & ~ALIGNMENT_MASK)
#define POOL_OVERHEAD  ROUNDUP(sizeof(struct pool_header));
void *PyObject_Malloc(size_t nbytes){
  ...
  init_pool:
    //将pool放入usedpools中
    next = usedpools[size + size];  /* == prev */
    pool->nextpool = next;
    pool->prevpool = next;
    next->nextpool = pool;
    next->prevpool = pool;
    pool->ref.count = 1;
    // pool在之前就具有正确的size结构,直接返回pool中的一个block

    //只有当一个pool从empty状态重新转为used状态之后，由于这时szidx还是其转为empty状态之前的szidx，所有才有可能执行
    if(pool->szidx == size){
      bp = pool->freeblock;
      pool->freeblock = *(block **)bp;
      UNLOCK();
      return (void *)bp;
    }

    //初始化pool header，将freeblock指向第二个block，返回第一个block
    pool->szidx = size;
    size = INDEX2SIZE(size);
    bp = (block *)pool + POOL_OVERHEAD;
    pool->nextoffset = POOL_OVERHEAD + (size << 1);
    pool->maxnextoffset = POOL_SIZE - size;
    pool->freeblock = bp + size;
    *(block **)(pool->freeblock) = NULL;
    UNLOCK();
    return (void *)bp;
    ...
}
```

<p>empty状态转换到used状态</p>

```c
[obmalloc.c]
...
pool = usable_arenas->freepools;
if(pool != NULL){
  usable_arenas->freepools = pool->nextpool;
  ...//调整usable_arenas->nfreepools和usable_arenas自身
  [init_pool]
}
```

>>> 初始化之二

```c
[obmalloc.c]
#define DUMMY_SIZE_IDX 0xffff /* size class of newly cached pools */
void* PyObject_Malloc(size_t nbytes){
  block* bp;
  poolp pool;
  poolp next;
  uint size;
  ...

  //从arena中取出一个新的pool
  pool = (poolp)usable_arenas->pool_address;
  pool->arenaindex = usable_arenas - arenas;
  pool->szidx = DUMMY_SIZE_IDX;
  usable_arenas->pool_address += POOL_SIZE;
  --usable_arenas->nfreepools;

  if(usable_arenas->nfreepools == 0){
    /* Unlink the arena : it is completely allocated */
    usable_arenas = usable_arenas->nextarena;
    if(usable_arenas != NULL){
      usable_arenas->prevarena = NULL;
    }
  }

  goto init_pool:
  ...

//判断一个block是否在某一个pool中
[obmalloc.c]
//P为指向一个block的指针，pool为指向一个pool的指针
int Py_ADDRESS_IN_RANGE(void* P, poolp pool){
  return pool->arenaindex < maxarenas &&
          (uptr)P - arenas[pool->arenaindex].address < (uptr)ARENA_SIZE && arenas[pool->arenaindex].address != 0;
}

```

```c
//PyObject_Malloc的总体结构
[obmalloc.c]
void* PyObject_Malloc(size_t nbytes){
  block* bp;
  poolp pool;
  poolp next;
  uint size;


  //如果申请的内存小于SMALL_REQUEST_THRESHOLD,使用Python的小块内存的内存池
  //否则转向malloc
  if((nbytes - 1) < SMALL_REQUEST_THRESHOLD){
    //根据申请内存的大小获得对应的size class index
    size = (uint)(nbytes - 1) >> ALIGNMENT_SHIFT;
    pool = usedpools[size + size];
    //如果usedpools中可用的pool，使用这个pool来分配block
    if(pool != pool->next){
      ...//在pool中分配block
      //分配结束后，如果pool中的block被分配了，将pool从usedpools中摘除(其实就是在双链表中去掉节点)
      next = pool->nextpool;
      pool = pool->prevpool;
      next->prevpool = pool;
      pool->nextpool = next;
      return (void *)bp;
    }

    //usedpools中没有可用的pool，从usable_arenas中获取pool
    if(usable_arenas == NULL){
      //usable_arenas中没有“可用”的arena，开始申请arena
      usable_arenas = new_arena();
      usable_arenas->nextarena = usable_arenas->prevarena = NULL;
    }

    //从usable_arenas中的第一个arena中获取一个pool
    pool = usable_arenas->freepools;
    if(pool != NULL){
      init_pool:
      //获取pool成功，进行init pool的动作，将pool放入used_pools中，
      //并返回分配得到的block
      ......
    }

    //获取pool失败，对arena中的pool集合进行初始化
    //然后转入goto到init pool的动作处，初始化一个特定的pool

    ...
      goto init_pool;

  }

redirect:
  //如果申请的内存不小于SMALL_REQUEST_THRESHOLD,使用malloc
  if(nbytes == 0)
    nbytes = 1;

  return (void *)malloc(nbytes);

}
```

>>> block的释放

<p>释放一个block后，pool的状态有两种转变情况: 1.used状态转变为empty状态  2.full状态转变为used状态 3.used仍然处于used状态 </p>

```c
//used->used
[obmalloc.c]
void PyObject_Free(void *p){
  poolp pool;
  block* lastfree;
  poolp next, prev;
  uint size;

  pool = POOL_ADDR(p);
  if(Py_ADDRESS_IN_RANGE(p,pool)){
    //设置离散自由block链表
    *(block **)p = lastfree = pool->freeblock;
    pool->freeblock = (block *)p;
    if(lastfree){ //lastfree有效，表明当前pool不是处于full状态
      if(--pool->ref.count != 0){ // pool不需要转换为empty状态
        return;
      }
      ...
    }
    ...
  }

  //待释放的内存在PyObject_Malloc中是通过malloc获得的
  //所以要归还给系统
  free(p);
}
```

```c
//full->used
[obmalloc.c]
void PyObject_Free(void *p){
  poolp pool;
  block *lastfree;
  poolp next,prev;
  uint size;

  pool = POOL_ADDR(p);
  if(Py_ADDRESS_IN_RANGE(p,pool)){
    ......
    //当前pool处于full状态,在释放一块block后，需将其转换为used状态，并重新链入usedpools的头部
    //链入usedpool头部
    --pool->ref.count;
    size = pool->szidx;
    next = usedpools[size + size];
    prev = next->prevpool;
    pool->nextpool = next;
    pool->prevpool = prev;
    next->prevpool = pool;
    prev->nextpool = pool;
    return;
  }
  ...
}
```

```c
//used->empty
[obmalloc.c]
void PyObject_Free(void *p){
  poolp pool;
  block* lastfree;
  poolp next, prev;
  uint size;

  pool = POOL_ADDR(p);
  if(Py_ADDRESS_IN_RANGE(p,pool)){
    //设置离散自由block链表
    *(block **)p = lastfree = pool->freeblock;
    pool->freeblock = (block *)p;
    if(lastfree){
      struct arena_object* ao;
      uint nf; //ao->nfreepools
      if(--pool->ref.count != 0){
        return;
      }

      //将pool放入freepools维护的链表中
      ao = &arenas[pool->arenaindex];
      pool->nextpool = ao->freepools;
      ao->freepools = pool;
      nf = ++ao->nfreepools;
      ...
    }
    ...
  }
}
```
