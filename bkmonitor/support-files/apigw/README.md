# 监控平台网关管理规范

## 网关名称: 
bk_monitor

## 概念说明

### 内部接口与外部接口

#### 内部接口
监控的模块间存在使用网关互相调用的情况，内部的蓝鲸应用比如说日志平台/容器管理平台等也存在需要使用网关调用监控平台的情况，我们称这些接口为`内部接口`。这些接口一般只给内部使用，不允许进行权限申请，只能由网关管理员主动授权，或是配置文件中进行授权。

#### 外部接口
监控平台对外提供的接口，一般通过网关暴露给外部使用，我们称这些接口为`外部接口`。这些接口允许主动进行权限申请，由网关管理员进行审批。


#### 注意事项
1. 为了尽可能减少未来的兼容性压力和管理成本，我们只开放必要的接口给外部使用。
2. 内部接口的 isPublic 属性为 false，外部接口的 isPublic 属性为 true。
3. 内部接口的 allowApplyPermission 属性为 false，外部接口的 allowApplyPermission 属性为 true。
4. 内部接口的定义在 `/resources/internal` 目录下，外部接口的定义在 `/resources/external` 目录下。

### 应用态与用户态

#### 应用态
应用态接口是指可以不进行用户认证的接口，我们称这些接口为应用态接口。

#### 用户态
用户态接口是指需要进行用户认证的接口，我们称这些接口为用户态接口。

#### 注意事项
1. 应用态接口的 userVerifiedRequired 属性为 false，用户态接口的 userVerifiedRequired 属性为 true。
2. 应用态接口的定义在 `/resources/{public_dir}/app` 目录下，用户态接口的定义在 `/resources/{public_dir}/user` 目录下。
3. 为了区分应用态和用户态，一般情况下，应用态接口路径以 `/app/` 开头，用户态接口路径以 `/user/` 开头。

## 接口定义

### 接口定义

1. 在 `/resources` 目录下，根据接口的是内部还是外部接口，是应用态还是用户态，将接口定义在对应的目录下。
2. 每一个 yaml 文件都包含多个接口定义，yaml 的文件名将会作为接口的分类，比如说 apm 的接口，文件名就为 apm.yaml。
3. old 目录下为从 esb 自动转换过来的旧接口，仅作参考。

### 接口路径

为了让接口路径格式更加清晰规范，我们希望接口的路径遵守以下格式：

```
格式:
/{app|user}/{module}/{action}/
/{app|user}/{module}/{action}/{version}/

示例:
/app/as_code/import_config/
/app/as_code/import_config/v1/
```

1. app 为应用态，user 为用户态。
2. module 为模块名/接口分类，action 为接口名。
3. 接口名使用小写字母，多个单词之间使用下划线分隔。
4. 如果接口希望区分版本，可以添加版本号，版本号格式为 `vX`。

### 接口名称

1. 接口名称使用小写字母，多个单词之间使用下划线分隔。
2. 接口的名称可以以动词开头，具有一定的可读性，能够体现出接口的功能，比如 import_as_code_config。
3. 名称中需要体现接口所属模块，避免产生歧义，比如说叫 import_config 就不合适，因为不知道是导入什么配置，而且容易和其他模块冲突。

### 目录结构

```
resources/
├── internal/
│   ├── app/
│   └── user/
├── external/
│   ├── app/
│   └── user/
```

### 接口合并

在注册网关接口前，脚本 `scripts/merge_resources.py` 会自动合并 `/resources` 目录下的所有 yaml 文件，生成一个 `resources.yaml` 文件，用于注册网关接口。
在合并过程中，会自动设置以下字段

1. 根据接口是内部还是外部，设置 `isPublic` 和 `allowApplyPermission` 字段
2. 根据接口是应用态还是用户态，设置 `userVerifiedRequired` 和 `appVerifiedRequired` 字段
3. 如果 yaml 文件中没有 `tags` 字段，则将 yaml 文件名补充到 `tags` 字段。

## 文档管理

1. 网关的文档在 `/docs` 目录下，en 为英文文档，zh 为中文文档。
2. 文档的文件名与资源名(operationId)一致，例如 `as_code_import_config.md`。


## 网关同步

### 同步命令

使用 django manage.py 命令进行网关同步，可以加到 migrate 流程中。

```bash
python manage.py sync_apigw
```

### 注意事项

1. 网关进行全量同步，会删除不存在于 `resources.yaml` 的接口。尽量不要在网关页面上手动添加接口，否则会被删除。
2. grant_permissions进行授权是增量的，如果不是需要在蓝鲸部署时就进行授权，不需要加到这里，直接在网页上授权即可。
