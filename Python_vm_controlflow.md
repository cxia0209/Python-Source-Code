### 1.Python虚拟机中的控制流

#### a.Python虚拟机中的if控制流

> if_control.py

```python
a = 1
if a > 10:
    print "a > 10"
elif a <= -2
    print "a <= -2"
elif a != 1:
    print "a != 1"
elif a == 1:
    print "a == 1"
else:
    print "Unknown a"
```

```c
/*比较操作的定义*/
[object.h]
/* Rich comparison opcodes */
#define Py_LT 0
#define Py_LE 1
#define Py_EQ 2
#define Py_NE 3
#define PY_GT 4
#define Py_GE 5

[opcode.h]
enum cmp_op {
  PyCmp_LT = Py_LT,
  PyCmp_LE = Py_LE,
  .......
}
```

```c
[COMPARE_OP]

w = POP();
v = Top();
// PyIntObject对象的快速通道
if(PyInt_CheckExact(w) && PyInt_CheckExact(v)){
  register long a,b;
  register int res;
  a = PyInt_AS_LONG(v);
  b = PyInt_AS_LONG(w);
  //根据字节码指令的指令参数选择不同的操作
  switch (oparg) {
    case PyCmp_LT: res = a < b; break;
    case PyCmp_LE: res = a <= b; break;
    case PyCmp_EQ: res = a == b; break;
    case PyCmp_NE: res = a != b; break;
    case PyCmp_GT: res = a > b; break;
    case PyCmp_GE: res = a >= b; break;
    case PyCmp_IS: res = v == w; break;
    case PyCmp_IS_NOT: res = v!= w; break;
    default: goto slow_compare;
  }
  x = res ? Py_True : PyFalse;
  Py_INCREF(x);
}
else{
  //一般对象的慢速通道
  slow_compare:
      x = cmp_outcome(oparg,v,w);
}
Py_DECREF(v);
Py_INCREF(w);
//将比较结果压入到运行时栈中
SET_TOP(x);

if(x == NULL) break;
PREDICT(JUMP_IF_FALSE);
PREDICT(JUMP_IF_TRUE);


//慢速通道cmp_outcome
[ceval.c]
static PyObject* cmp_outcome(int op, register PyObject* v, register PyObject* w){
  int res = 0;
  switch (op) {
    case PyCmp_IS:
      res = (v == w);
      break;
    case PyCmp_IS_NOT:
      res = (v != w);
      break;
    case PyCmp_IN:
      res = PySequence_Contains(w,v);
      if(res < 0)
        return NULL;
      break;
    case PyCmp_NOT_IN:
      res = PySequence_Contains(w,v);
      if(res < 0)
        return NULL;
      res = !res;
      break;
    case PyCmp_EXC_MATCH:
      res = PyErr_GivenExceptionMatches(v,w);
      break;
    default:
      return PyObject_RichCompare(v,w,op);
  }
  v = res ? Py_True : PyFalse;
  Py_INCREF(v);
  return v;
}
```

> 比较操作的结果Python中的bool对象

```c
[boolobject.h]
PyIntObject _Py_ZeroStruct,_Py_TrueStruct;

#define PyFalse ((PyObject *) &_Py_ZeroStruct)
#define PyTrue  ((PyObject *) &_Py_TrueStruct)

[boolobject.c]
PyTypeObject PyBool_Type = {
  PyObject_HEAD_INIT(&PyType_Type)
  0,
  "bool",
  sizeof(PyIntObject),
  .....
}

/* The objects representing bool values False and True */
/* Named Zero for link-level compatibility */
PyIntObject _Py_ZeroStruct = {
  PyObject_HEAD_INIT(&PyBool_Type)
  0
};

PyIntObject _Py_TrueStruct = {
  PyObject_HEAD_INIT(&PyBool_Type)
  1
}
```

> 指令跳跃

```c
//PREDICT宏
[ceval.c]
#define PREDICT(op) if(*next_instr == op) goto PRED_##op

#define PREDICTED(op) PRED_##op: next_instr++

#define PREDICTED_WITH_ARG(op) PRED_##op: oparg = PEEKARG(); next_instr += 3

#define PEEKARG() ((next_instr[2]<<8) + next_instr[1])

```

```c
[ceval.c]
//PREDICT(JUMP_IF_FALSE)的情况
PREDICTED_WITH_ARG(JUMP_IF_FALSE);
case JUMP_IF_FALSE:
  //取出之前的比较操作结果
  w = TOP();
  //比较结果为True
  if(w == Py_True){
    PREDICT(POP_TOP);
    goto fast_next_opcode;
  }

  //比较操作结果为false,进行指令跳跃
  if( w == Py_False){
    JUMPBY(oparg);
    got fast_next_opcode;
  }

  err = PyObject_IsTrue(w);
  if ( err > 0)
    err = 0;
  else if (err == 0)
    JUMPBY(oparg);   // #define JUMPBY(x) (next_instr += (x))
  else
    break;
  continue;

//PREDICTED_WITH_ARG宏
PRED_JUMP_IF_FALSE:
  //取指令参数
  oparg = ((next_instr[2]<<8) + next_instr[1]);
  //调整next_instr
  next_instr += 3;
  case JUMP_IF_FALSE:
      ...

//PREDICT(JUMP_IF_FALSE)的情况
PREDICTED(POP_TOP);
case POP_TOP:
  v = POP();
  Py_DECREF(v);
  goto fast_next_opcode;
```

```c
//print操作
[JUMP_FORWARD]
  JUMPYBY(oparg)
  goto fast_next_opcode;
```

#### Python虚拟机中的for循环控制流

> 循环控制结构的初始化

```c
[SETUP_LOOP]
PyFrame_BlockSetup(f,opcode,INSTR_OFFSET() + oparg, STACK_LEVEL());
```

> PyTryBlock
