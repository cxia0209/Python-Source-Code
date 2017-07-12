### 1.Python 总体架构
![python architecture](/image/py_arch.png)

#### 运行时环境(Runtime Environment)
> 对象/类型系统(Object/Type structures)：python中存在的各种内建对象，比如整数、list和dict以及自定义类型

> 内存分配器(Memory Allocator): 全权负责Python中创建对象时内存的申请，实际是对Python运行时与C中malloc的一层接口

> 运行时状态信息(Current State of Python): 维护了解释器(interpreter)在执行字节码是不同的状态（比如正常or异常）之间切换的动作，可视为有穷状态机

#### 解释器(Interpreter)
> Scanner: 词法分析

> Parser： 语法分析，建立 抽象语法树(AST)

> Compiler: 根据建立的AST生成指令集合 -- Python字节码

>Code Evaluator ： 虚拟机

### 2.Python2.5 源代码组织
![python architecture](/image/code_org.png)

>  Include: 所有头文件, 可用C/C++编写自定义模块扩展Python

> Lib: 标准库，全部都是用Python编写

> Modules: 所有用C语言编写的模块， 比如random， 对速度要求严格

> Parser : 包含Python解释器中Scanner和Parser部分，还有一些其他工具

> Objects : Python内建对象， 包括整数、list、dict等

> Python : 包含Python解释器中的Compiler和执行引擎部分
