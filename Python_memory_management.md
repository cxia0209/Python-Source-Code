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

  }
}
```
