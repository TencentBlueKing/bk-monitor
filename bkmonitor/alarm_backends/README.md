# alarm_backends 

```
worker
├── bin        # 启动脚本相关
├── conf       # 配置相关，这个目录目前放在外层
├── common     # 公共服务，组件的使用
│   ├── cache
│   ├── db
│   └── queue
├── service    # 后台进程
│   ├── access
│   ├── detect
│   ├── event
│   ├── notice
│   ├── recovery
│   └── selmon
└── tests      # 单元测试
    ├── __init__.py
    ├── test_access.py
    ├── test_detect.py
    └── test_trigger.py

```


## 功能点
- 主体功能
- 流控
- 单元测试
- 自监控
    - 日志轮转
    - 数据处理链路，各个阶段的指标数据上报
    - 工具，包括简单的分析，做辅助排查
- 升级方案
    - DB结构迁移方案
    - 策略配置数据迁移方案
    - 代码部署的升级方案


## 本地启动方式
统一走django的manage启动方式

- 设置环境变量(修改一下变量参数)

```
export DJANGO_SETTINGS_MODULE=settings
export DJANGO_CONF_MODULE=conf.worker.development.enterprise

export APP_TOKEN=replace-me-to-your-app-token
export BK_PAAS_HOST=https://replace.me
```

- 启动run_access

```
python manage.py run_access -s access --access-type=data --min-interval 30
```

- 启动其他服务run_service

```
python manage.py run_service -s detect
```

- 采用celery异步任务的方式运行（默认在当前进程启动）

```
python manage.py run_service -s detect -H celery
```


## supervisor启动方式

- 通过命令生成好配置文件`supervisord.conf`，目录在`alarm_backends/conf`下

```bash
# 根据settings相关配置，生成supervisor启动配置文件
python manage.py gen_config
```

- 启动supervisor
- 
```bash
supervisord -c alarm_backends/conf/supervisord.conf
``` 

## 如何在本地运行单元测试

首先需要在本地增加环境变量配置

```bash
export APP_CODE=bk_monitorv3
export APP_TOKEN=*********
export BK_PAAS_HOST=https://paas.example.com
export BKAPP_DEPLOY_PLATFORM=enterprise
export DJANGO_CONF_MODULE=conf.worker.development.default_settings
export DJANGO_SETTINGS_MODULE=settings
export USE_DYNAMIC_SETTINGS=0
```

然后需要确保所有的开发&生产的依赖都已经安装了
```bash
pip install -r requirements.txt
pip install -r requirements_test.txt
```

由于 `fakeredis` 使用的版本较老，有一些库路径问题，需要在本地代码启动前增加一段 [work around patch](https://github.com/webrecorder/pywb/issues/616#issuecomment-789713811) （可以放到 `local_settings.py` 中）

```python
import sys
import ctypes


def patch_ctypes_on_macos_11():  # pragma: no cover
    """Work around a problem loading pywb under macOS 11.
    pywb has a dependency on an old version of fakeredis which fails to load
    when using Python <= 3.8 under macOS 11.  This function patches `ctypes.util.find_library`
    to work around the issue.
    """

    if sys.platform != "darwin":
        return

    def _find_library_patched(name):
        path = f"lib{name}.dylib"
        try:
            # In macOS 11, some system libraries don't exist on disk. Instead you test
            # the validity of a library path by trying to load it.
            # See https://bugs.python.org/issue41179.
            ctypes.CDLL(path)
        except OSError:
            # Fall back to the un-patched version.
            path = ctypes.util.find_library(name)
        return path

    ctypes.util.find_library = _find_library_patched


# Apply ctypes patch before pywb is imported.
patch_ctypes_on_macos_11()
```