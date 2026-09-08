# 统一异常处理
## 简介
本模块提供了统一的异常定义，定义了标准异常(基)类和错误码。
可以在需要使用的应用的drf的error_handler进行拦截处理
## 使用规范
1. 各领域的异常类路径为 bk_monitor_base.domains.领域名.errors（统一后面会扫描自动生成异常码文档）
2. 模块基类和各个异常子类集合位置暂不强制要求
### 目录结构
以 空间管理(space) 为例

```text
bk_monitor_base/
├── domains/
|   ├── space/ # 空间管理模块
|   │   ├── __init__.py
|   │   ├── errors.py   # 异常定义
|   │   ├── ... # 其他文件
├── space.py # 空间管理入口
```

在domains/space/ 目录下
- `errors.py` 定义了空间管理模块的所有异常
- `...` 定义了空间管理其他文件

### 模块入口
为了让使用者可以方便导入，同时避免对外暴露不必要的API，需要在 `infras/exception`的同级目录下定义模块的入口，在其中只暴露必要的函数/类/变量。

### 常见用法

以空间管理(space) 为例

#### 1. 模块/领域导入异常类的方法
```python  
# ❌
from bk_monitor_base.exception import BaseError
# ✅
from bk_monitor_base.domains.space.errors import SPACE_NOT_FOUND

```
#### 2. 定义模块/领域的异常子类
```python
# ✅
class SpaceError(BaseError):
    MODULE_CODE = "01"
    MESSAGE = "" # 不需要定义统一前缀MESSAGE
# ✅
class SpaceError(BaseError):
    MODULE_CODE = "01"  # 模块代码，空间管理模块为01,需要与Base的模块区分开
    MESSAGE = _("空间管理异常")  # 一类异常的提示(会加在message前面)
    DELIMITER: str = ": " # 分隔符，默认是": "，可以根据需要修改
```

#### 3. ErrorCodes定义样例
```python
# src/bk_monitor_base/domains/space/errors.py
# ❌
class ErrorCodes:
    SPACE_NOT_FOUND = SpaceError(error_code='001') # 必须存在默认message
    SPACE_ALREADY_EXISTS = SpaceError(_("空间已存在"))# 错误异常码短码和完整异常码必须存在一个
# ❌ 
class AllErrorCode: #名称必须统一为ErrorCodes
    ... 
# ✅
class ErrorCodes:
    SPACE_NOT_FOUND = SpaceError(_("空间未找到"),error_code='001')
    SPACE_ALREADY_EXISTS = SpaceError(_("空间已存在"),error_code='002') 
    SPACE_SPECIAL_ERROR = SpaceError(_("空间特殊错误"),code_num=8801500) #特殊情况下需要覆盖完整异常码

```

#### 4. 简单使用样例
```python
# main.py
# ❌ 不应该在逻辑里实例化异常，请先定义后使用
def main():
    try:
        # 业务逻辑
        pass
    except Exception as e:
        # 捕获异常并格式化错误信息
        space_id = 123  # 假设空间ID为123
        raise SpaceError(_("空间未找到"),error_code='001').set_data({"space_id": 123}).set_message(f"空间未找到: {space_id}").set_errors(e)

# ✅
def main():
    try:
        # 业务逻辑
        pass
    except Exception as e:
        # 捕获异常并格式化错误信息
        space_id = 123  # 假设空间ID为123
        raise ErrorCodes.SPACE_NOT_FOUND
```

##### 5. 其他应用使用，例如鲸眼的kac
```PYTHON
# 应用的基类定义
# src/kingeye/common/exceptions.py
from bk_monitor_base.infras.exception import StdError
class KingeyeBaseError(StdError):
    """鲸眼系统的基类异常"""
    SYSTEM_CODE = "88"  # 鲸眼的系统编码为88

```
```python
# 模块的基类定义
# src/kingeye/kac/common/exceptions.py
class KacException(KingeyeBaseError):
    MODULE_CODE = ErrorCode.KAC_CODE
    # fixme 由于kac 在 blueapps 定义过特殊逻辑, api error状态码都是200.
    #  在统一 error 后这里理应是500, 但是涉及前端改动量较大. 所以暂时手动设置为200
    STATUS_CODE = 200

    def response_data(self):
        if len(str(self.code)) == 3:
            self.code = f"{self.SYSTEM_CODE}{self.MODULE_CODE}{self.code}"
        message = f"{self.message}（{self.code}）"
        if self.errors:
            message += f"（detail => {self.errors}）"
        return {"result": False, "code": self.code, "data": self.data, "message": message, "errors": self.errors}


class ErrorCodes:
    UploadFileError = KacException(_("文件上传失败"), error_code='180')
    RequestParamsError = KacException(_("请求参数错误"), error_code='181')
    ...

```


### 更多异常方法说明

#### set_data() - 设置附加数据
用于传递与异常相关的上下文数据，通常是导致异常的相关信息，便于调试和日志记录。

```python
# 示例：传递空间ID等上下文信息
raise ErrorCodes.SPACE_NOT_FOUND.set_data({
    "space_id": 123,
    "user_id": "admin", 
    "operation": "query_space"
})

# 数据会在异常处理时被使用，比如在日志中记录或返回给前端
```

#### set_errors() - 设置原始异常
用于保存捕获到的原始异常信息，通常用于异常链追踪，便于定位问题根源。

```python
try:
    # 可能抛出 DatabaseError 的数据库操作
    space = Space.objects.get(id=space_id)
except DatabaseError as e:
    # 将原始数据库异常保存到 errors 中
    raise ErrorCodes.SPACE_NOT_FOUND.set_errors(e)
    
# 原始异常信息会被保存，便于调试时了解真正的错误原因
```

#### set_message() - 动态设置消息
用于覆盖或补充预定义的错误消息，可以添加动态的上下文信息。

```python
# 基础错误码已定义: SPACE_NOT_FOUND = SpaceError(_("空间未找到"), error_code='001')
# 动态添加具体信息
raise ErrorCodes.SPACE_NOT_FOUND.set_message(f"空间未找到，空间ID: {space_id}")
```

#### 链式调用
这些方法支持链式调用，可以同时设置多个属性：

```python
# 完整的异常处理示例
try:
    space = get_space_by_id(space_id)
except DatabaseError as db_err:
    raise (ErrorCodes.SPACE_NOT_FOUND
           .set_data({"space_id": space_id, "user_id": current_user.id})
           .set_message(f"无法获取空间信息，空间ID: {space_id}")
           .set_errors(db_err))
```