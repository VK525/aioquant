
## 进程锁 & 线程锁

当业务复杂到使用多进程或多线程的时候，并发提高的同时，对内存共享也需要使用锁来解决资源争夺问题。


##### 1. 线程（协程）锁

> 使用  

```python
    from aioquant.utils.decorator import async_method_locker
    
    @async_method_locker("unique_locker_name")
    async def func_foo():
        pass
```

- 函数定义
```python
def async_method_locker(name, wait=True):
    """ 异步方法加锁，用于多个协程执行同一个单列的函数时候，避免共享内存相互修改
    @param name 锁名称
    @param wait 如果被锁是否等待，True等待执行完成再返回，False不等待直接返回
    * NOTE: 此装饰器需要加到async异步方法上
    """
```

> 说明  
- `async_method_locker` 为装饰器，需要装饰到 `async` 异步函数上；
- 装饰器需要传入一个参数 `name`，作为此函数的锁名；
- 参数 `wait` 可选，如果被锁是否等待，True等待执行完成再返回（等待执行,不漏数据），False不等待直接返回（跳过执行，放弃更新的数据）

"""
from aioquant.tasks import LoopRunTask, SingleTask
from aioquant.utils.decorator import async_method_locker


@async_method_locker("test1", True)
async def d(x):
    print("test1 True",x）
    
@async_method_locker("test2", False)
async def k(x):
    print("test2 False",x)
    
for i in range(10):    
    SingleTask.run(d,i)
    SingleTask.run(k,i) 

test1 True 0
test2 False 0
test1 True 1
test1 True 2
test1 True 3
test1 True 4
test1 True 5
test1 True 6
test1 True 7
test1 True 8
test1 True 9
"""
