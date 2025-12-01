# 监控目标类型扩展开发指南

## 1. 概述

本文档旨在指导新加入项目的开发人员如何扩展监控目标类型。监控目标用于在监控策略中指定需要监控的对象，同时也用于告警屏蔽规则的配置。

### 1.1 当前支持的监控目标类型

- **主机IP** (`ip` / `bk_target_ip`): 通过IP地址和云区域ID标识主机
- **服务实例** (`service_instance_id` / `bk_target_service_instance_id`): 通过服务实例ID标识服务
- **拓扑节点** (`*_topo_node`): 通过CMDB拓扑节点标识（如 `host_topo_node`, `service_topo_node`）
- **动态分组** (`dynamic_group`): 通过动态分组ID标识一组主机

### 1.2 扩展目标

本文档以新增**对象模型监控目标类型**为例，说明扩展流程。该类型包含：
- 配置字段：`cw_object_model_code`（对象类型代码）
- 配置字段：`cw_object_model_inst_id`（对象实例ID）
- 数据上报维度：`cw_object_model_id`（对象模型ID，与 `cw_object_model_code` 一一对应）
- 数据上报维度：`cw_object_model_inst_id`（对象实例ID）

## 2. 架构说明

### 2.1 核心组件

监控目标处理涉及以下核心组件：

1. **TargetCondition** (`bkmonitor/utils/range/target.py`): 负责监控目标的匹配逻辑
2. **策略配置** (`bkmonitor/models/base.py`): Item模型中的target字段存储监控目标配置
3. **告警屏蔽** (`packages/monitor_web/shield/utils.py`): ShieldDetectManager处理屏蔽规则的匹配
4. **前端选择器**: 前端IP选择器组件用于配置监控目标

### 2.2 数据流

```
前端配置 → 策略保存 → TargetCondition匹配 → 告警生成
                ↓
        告警屏蔽规则 → ShieldDetectManager匹配 → 屏蔽判断
```

## 3. 后端扩展步骤

### 3.1 定义目标字段类型常量

**文件位置**: `constants/strategy.py`

在 `TargetFieldType` 类中添加新的字段类型：

```python
class TargetFieldType:
    # ... 现有字段 ...
    cw_object_model = "cw_object_model"  # 新增对象模型类型
```

在 `TargetFieldList` 中添加新类型（如果需要在前端显示）：

```python
TargetFieldList = [
    # ... 现有类型 ...
    TargetFieldType.cw_object_model,  # 新增
]
```

### 3.2 扩展 TargetCondition 类

**文件位置**: `bkmonitor/utils/range/target.py`

#### 3.2.1 修改 `load_target_condition` 方法

在 `load_target_condition` 方法中添加对新字段类型的处理逻辑：

```python
def load_target_condition(self, target: list[list[dict]]):
    """
    加载监控目标条件
    """
    if not target:
        return []

    conditions_list = []
    for target_condition in target:
        conditions = []
        for condition in target_condition:
            field = condition["field"].lower()
            method = condition["method"].lower()
            values = condition["value"]

            target_keys = set()
            
            # ... 现有的IP、服务实例、拓扑节点处理 ...
            
            # 新增：对象模型类型处理
            elif field == "cw_object_model":
                for value in values:
                    cw_object_model_code = value.get("cw_object_model_code")
                    cw_object_model_inst_id = value.get("cw_object_model_inst_id")
                    
                    if not cw_object_model_code or not cw_object_model_inst_id:
                        continue
                    
                    # 使用 "模型代码|实例ID" 作为唯一标识
                    target_keys.add(f"{cw_object_model_code}|{cw_object_model_inst_id}")

            if not target_keys:
                continue

            conditions.append({"field": field, "method": method, "target_keys": target_keys})

        if conditions:
            conditions_list.append(conditions)
    return conditions_list
```

#### 3.2.2 修改 `is_match` 方法

在 `is_match` 方法中添加匹配逻辑：

```python
def is_match(self, data: dict):
    """
    判断数据是否匹配监控目标
    """
    for conditions in self.conditions_list:
        for condition in conditions:
            field = condition["field"]
            method = condition["method"]
            values: set = condition["target_keys"]

            target_keys = set()
            
            # ... 现有的IP、服务实例、拓扑节点匹配逻辑 ...
            
            # 新增：对象模型类型匹配
            elif field == "cw_object_model":
                # 从数据维度中获取对象模型信息
                # 注意：数据上报维度是 cw_object_model_id 和 cw_object_model_inst_id
                cw_object_model_id = data.get("cw_object_model_id")
                cw_object_model_inst_id = data.get("cw_object_model_inst_id")
                
                if not cw_object_model_id or not cw_object_model_inst_id:
                    continue
                
                # 需要将 cw_object_model_id 转换为 cw_object_model_code
                # 这里假设有一个映射关系，实际实现需要根据业务逻辑调整
                # 如果数据中直接包含 cw_object_model_code，可以直接使用
                cw_object_model_code = data.get("cw_object_model_code")
                
                # 如果数据中没有 code，需要通过 model_id 查询映射关系
                # 建议：在数据上报时同时上报 code 和 id，或者建立映射缓存
                if not cw_object_model_code:
                    # 从映射关系获取（需要实现映射逻辑）
                    cw_object_model_code = self._get_model_code_by_id(cw_object_model_id)
                
                if cw_object_model_code:
                    target_keys.add(f"{cw_object_model_code}|{cw_object_model_inst_id}")
                
                if not target_keys:
                    continue
            
            if method == "eq":
                is_match = values & target_keys
            else:
                is_match = not (values & target_keys)

            # 有一个条件不满足，则跳过
            if not is_match:
                break
        else:
            # 所有条件都满足，则返回True
            return True
    return False

def _get_model_code_by_id(self, model_id):
    """
    根据模型ID获取模型代码
    使用对象模型缓存管理器获取
    """
    from alarm_backends.core.cache.cmdb.object_model import ObjectModelManager
    
    # 从缓存中获取对象模型信息
    object_model = ObjectModelManager.get(
        bk_tenant_id=self.bk_tenant_id,
        model_id=model_id
    )
    
    if object_model:
        return object_model.model_code
    
    return None
```

**重要说明**：
- 数据上报维度是 `cw_object_model_id`，但配置使用的是 `cw_object_model_code`
- 需要在数据匹配时建立 `model_id` 到 `model_code` 的映射关系
- 建议在数据上报时同时包含 `cw_object_model_code` 和 `cw_object_model_id`，避免查询开销
- 使用 `ObjectModelManager` 缓存管理器来管理对象模型ID到代码的映射关系

### 3.3 扩展告警屏蔽匹配逻辑

**文件位置**: `packages/monitor_web/shield/utils.py`

#### 3.3.1 修改 `ShieldDetectManager.is_shielded` 方法

在 `is_shielded` 方法中添加对新字段类型的处理：

```python
def is_shielded(self, shield_obj, match_info):
    """
    检测单个屏蔽策略是否生效
    """
    # 遍历屏蔽的维度进行匹配
    for key, value in list(shield_obj.dimension_config.items()):
        # 以'_'开头的key不去进行校验
        if key.startswith("_") or not value:
            continue

        if key == "dimension_conditions" and value:
            break

        # 范围屏蔽——ip的情况
        if key == "bk_target_ip" and isinstance(value, list):
            value = ["{}|{}".format(item.get("bk_target_ip"), item.get("bk_target_cloud_id")) for item in value]

        # 范围屏蔽——节点的情况
        if key == "bk_topo_node":
            value = ["{}|{}".format(item.get("bk_obj_id"), item.get("bk_inst_id")) for item in value]

        if key == "dynamic_group":
            value = [str(item["dynamic_group_id"]) for item in value if "dynamic_group_id" in item]

        # 新增：对象模型类型处理
        if key == "cw_object_model" and isinstance(value, list):
            value = [
                "{}|{}".format(
                    item.get("cw_object_model_code"), 
                    item.get("cw_object_model_inst_id")
                ) 
                for item in value
            ]

        alarm_set = set(self.get_match_info_value(key, match_info))
        shield_set = set(self.get_list(value))

        # 若未匹配到，则使用下一条屏蔽进行匹配
        if not alarm_set & shield_set:
            break
    else:
        return True
    return False
```

#### 3.3.2 修改 `get_match_info_value` 方法

在 `get_match_info_value` 方法中添加对新字段类型的值提取逻辑：

```python
def get_match_info_value(self, key, data):
    # 针对告警事件的IP维度，做一些特殊处理，统一返回的格式
    if key == "bk_target_ip":
        # ... 现有逻辑 ...
        return [f"{ip_value}|{bk_cloud_id}"]

    # 新增：对象模型类型值提取
    if key == "cw_object_model":
        # 从告警维度中获取对象模型信息
        cw_object_model_code = data.get("cw_object_model_code")
        cw_object_model_inst_id = data.get("cw_object_model_inst_id")
        
        # 如果数据中只有 model_id，需要转换为 code
        if not cw_object_model_code:
            cw_object_model_id = data.get("cw_object_model_id")
            if cw_object_model_id:
                # 使用对象模型缓存管理器获取 code
                from alarm_backends.core.cache.cmdb.object_model import ObjectModelManager
                from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
                
                bk_biz_id = data.get("bk_biz_id")
                if bk_biz_id:
                    bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
                    cw_object_model_code = ObjectModelManager.get_model_code_by_id(
                        bk_tenant_id=bk_tenant_id,
                        model_id=str(cw_object_model_id)
                    )
        
        if cw_object_model_code and cw_object_model_inst_id:
            return [f"{cw_object_model_code}|{cw_object_model_inst_id}"]
        
        return []

    return self.get_list(data.get(key, []))
```

### 3.4 扩展告警维度处理

**文件位置**: `alarm_backends/service/converge/shield/shield_obj.py`

在 `AlertShieldObj.get_dimension` 方法中，确保新字段能够正确传递到屏蔽匹配逻辑中：

```python
def get_dimension(self, alert: AlertDocument):
    try:
        dimension = copy.deepcopy(alert.origin_alarm["data"]["dimensions"])
    except BaseException as error:
        dimension = {}
        logger.info("Get origin alarm dimensions  of alert(%s) error, %s", alert.id, str(error))
    
    alert_dimensions = [d.to_dict() for d in alert.dimensions]
    dimension.update({d["key"]: d.get("value", "") for d in alert_dimensions})
    
    # ... 现有逻辑 ...
    
    # 新增：确保对象模型维度正确传递
    # 如果数据上报维度是 cw_object_model_id，需要转换为 cw_object_model_code
    if "cw_object_model_id" in dimension and "cw_object_model_code" not in dimension:
        cw_object_model_id = dimension.get("cw_object_model_id")
        if cw_object_model_id:
            # 使用对象模型缓存管理器获取 code
            from alarm_backends.core.cache.cmdb.object_model import ObjectModelManager
            from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
            
            bk_biz_id = alert.event_document.bk_biz_id
            if bk_biz_id:
                bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
                model_code = ObjectModelManager.get_model_code_by_id(
                    bk_tenant_id=bk_tenant_id,
                    model_id=str(cw_object_model_id)
                )
                if model_code:
                    dimension["cw_object_model_code"] = model_code
    
    return dimension
```

## 4. 前端扩展步骤

### 4.1 扩展目标字段类型映射

**文件位置**: `webpack/src/monitor-pc/pages/strategy-config/strategy-config-set-new/strategy-config-set.tsx`

在目标字段类型映射中添加新类型：

```typescript
// 主机目标字段类型映射
const hostTargetFieldType = {
  TOPO: 'host_topo_node',
  INSTANCE: 'ip',
  SERVICE_TEMPLATE: 'host_service_template',
  SET_TEMPLATE: 'host_set_template',
  DYNAMIC_GROUP: 'dynamic_group',
  // 新增：对象模型类型
  OBJECT_MODEL: 'cw_object_model',
};

// 服务目标字段类型映射（如果需要）
const serviceTargetFieldType = {
  TOPO: 'service_topo_node',
  SERVICE_TEMPLATE: 'service_service_template',
  SET_TEMPLATE: 'service_set_template',
  DYNAMIC_GROUP: 'dynamic_group',
  // 新增：对象模型类型
  OBJECT_MODEL: 'cw_object_model',
};
```

### 4.2 扩展IP选择器组件

**文件位置**: `webpack/src/monitor-pc/pages/strategy-config/strategy-config-target/strategy-config-target.vue`

需要在IP选择器组件中添加对象模型选择面板。IP选择器组件通常位于：
`webpack/src/monitor-pc/components/ip-selector/`

#### 4.2.1 添加对象模型选择面板

创建新的选择面板组件，用于选择对象模型和实例：

```vue
<!-- webpack/src/monitor-pc/components/ip-selector/panels/object-model-panel.vue -->
<template>
  <div class="object-model-panel">
    <!-- 对象模型选择器 -->
    <bk-select
      v-model="selectedModelCode"
      :loading="modelLoading"
      @change="handleModelChange"
    >
      <bk-option
        v-for="model in modelList"
        :key="model.code"
        :value="model.code"
        :label="model.name"
      />
    </bk-select>
    
    <!-- 对象实例选择器 -->
    <bk-select
      v-model="selectedInstances"
      multiple
      :loading="instanceLoading"
      :disabled="!selectedModelCode"
    >
      <bk-option
        v-for="instance in instanceList"
        :key="instance.id"
        :value="instance.id"
        :label="instance.name"
      />
    </bk-select>
  </div>
</template>

<script>
export default {
  name: 'ObjectModelPanel',
  props: {
    value: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      selectedModelCode: '',
      selectedInstances: [],
      modelList: [],
      instanceList: [],
      modelLoading: false,
      instanceLoading: false
    }
  },
  methods: {
    async loadModelList() {
      // TODO: 调用API获取对象模型列表
      // this.modelList = await api.getObjectModelList()
    },
    async handleModelChange(modelCode) {
      // TODO: 根据模型代码加载实例列表
      // this.instanceList = await api.getObjectModelInstances(modelCode)
    }
  }
}
</script>
```

#### 4.2.2 在IP选择器中注册新面板

在IP选择器主组件中注册新面板：

```typescript
// webpack/src/monitor-pc/components/ip-selector/index.tsx
import ObjectModelPanel from './panels/object-model-panel.vue'

// 在组件配置中添加
const panels = {
  // ... 现有面板 ...
  objectModel: ObjectModelPanel
}
```

### 4.3 扩展策略配置序列化

**文件位置**: `packages/monitor_web/strategies/serializers.py`

在策略序列化器中，确保新字段类型能够正确序列化和反序列化：

```python
# 在 handle_target 函数中添加新类型的处理
def handle_target(value):
    """
    处理监控目标配置
    """
    # ... 现有逻辑 ...
    
    # 新增：对象模型类型处理
    for target_condition in value:
        for condition in target_condition:
            field = condition.get("field", "").lower()
            
            if field == "cw_object_model":
                # 验证和规范化对象模型配置
                for item in condition.get("value", []):
                    if not item.get("cw_object_model_code"):
                        raise ValidationError("cw_object_model_code is required")
                    if not item.get("cw_object_model_inst_id"):
                        raise ValidationError("cw_object_model_inst_id is required")
    
    return value
```

## 5. 数据上报维度映射

### 5.1 维度映射关系

**配置字段** → **数据上报维度**：
- `cw_object_model_code` → `cw_object_model_id`（需要建立映射关系）
- `cw_object_model_inst_id` → `cw_object_model_inst_id`（直接对应）

### 5.2 实现映射方案

#### 方案一：数据上报时同时包含 code 和 id

**推荐方案**：在数据上报时，同时包含 `cw_object_model_code` 和 `cw_object_model_id`，避免在匹配时进行查询。

```python
# 数据上报示例
dimensions = {
    "cw_object_model_code": "host",  # 对象模型代码
    "cw_object_model_id": "123",      # 对象模型ID
    "cw_object_model_inst_id": "456", # 对象实例ID
    # ... 其他维度
}
```

#### 方案二：建立映射缓存（推荐）

如果数据上报时只包含 `cw_object_model_id`，需要建立映射缓存。参考 `alarm_backends/core/cache/cmdb` 的实现模式，创建对象模型缓存管理器。

##### 2.1 创建对象模型缓存管理器

**文件位置**: `alarm_backends/core/cache/cmdb/object_model.py`

```python
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from typing import cast

from core.drf_resource import api

from .base import CMDBCacheManager

logger = logging.getLogger("cache")


class ObjectModel:
    """
    对象模型数据类
    """
    def __init__(self, model_id: str, model_code: str, model_name: str = ""):
        self.model_id = model_id
        self.model_code = model_code
        self.model_name = model_name
    
    def to_dict(self):
        return {
            "model_id": self.model_id,
            "model_code": self.model_code,
            "model_name": self.model_name,
        }


class ObjectModelManager(CMDBCacheManager):
    """
    对象模型缓存管理器
    用于缓存对象模型ID到模型代码的映射关系
    """

    cache_type = "object_model"

    @classmethod
    def get(cls, *, bk_tenant_id: str, model_id: str, **kwargs) -> ObjectModel | None:
        """
        获取单个对象模型信息
        :param bk_tenant_id: 租户ID
        :param model_id: 对象模型ID
        :return: 对象模型信息
        """
        cache_key = cls.get_cache_key(bk_tenant_id)
        result = cast(str | None, cls.cache.hget(cache_key, str(model_id)))
        if not result:
            return None
        model_data = json.loads(result)
        return ObjectModel(**model_data)

    @classmethod
    def mget(cls, *, bk_tenant_id: str, model_ids: list[str]) -> dict[str, ObjectModel]:
        """
        批量获取对象模型信息
        :param bk_tenant_id: 租户ID
        :param model_ids: 对象模型ID列表
        :return: 对象模型信息字典，key为model_id
        """
        if not model_ids:
            return {}

        cache_key = cls.get_cache_key(bk_tenant_id)
        model_id_list = [str(model_id) for model_id in model_ids]
        results: list[str | None] = cast(
            list[str | None], cls.cache.hmget(cache_key, model_id_list)
        )
        return {
            model_id: ObjectModel(**json.loads(result))
            for model_id, result in zip(model_ids, results)
            if result
        }

    @classmethod
    def get_model_code_by_id(cls, *, bk_tenant_id: str, model_id: str) -> str | None:
        """
        根据模型ID获取模型代码（便捷方法）
        :param bk_tenant_id: 租户ID
        :param model_id: 对象模型ID
        :return: 模型代码，如果不存在返回None
        """
        object_model = cls.get(bk_tenant_id=bk_tenant_id, model_id=model_id)
        return object_model.model_code if object_model else None

    @classmethod
    def refresh(cls, *, bk_tenant_id: str) -> dict[str, ObjectModel]:
        """
        刷新对象模型缓存
        从CMDB获取所有对象模型信息并缓存
        :param bk_tenant_id: 租户ID
        :return: 对象模型信息字典
        """
        try:
            # 从CMDB获取对象模型列表
            # 注意：这里需要根据实际的CMDB API调整
            # 示例：model_list = api.cmdb.get_object_model_list()
            # 实际实现需要根据CMDB API接口调整
            model_list = api.cmdb.get_object_model_list()  # 需要实现此API
            
            # 构建对象模型字典
            object_models = {}
            for model_info in model_list:
                model_id = model_info.get("id") or model_info.get("model_id")
                model_code = model_info.get("bk_obj_id") or model_info.get("model_code")
                model_name = model_info.get("bk_obj_name") or model_info.get("model_name", "")
                
                if model_id and model_code:
                    object_models[model_id] = ObjectModel(
                        model_id=str(model_id),
                        model_code=model_code,
                        model_name=model_name
                    )
            
            # 刷新缓存
            cache_key = cls.get_cache_key(bk_tenant_id)
            pipeline = cls.cache.pipeline()
            
            # 批量写入缓存，每1000条一批
            for i in range(0, len(object_models), 1000):
                batch = dict(list(object_models.items())[i : i + 1000])
                pipeline.hmset(
                    cache_key,
                    {
                        model_id: json.dumps(model.to_dict(), ensure_ascii=False)
                        for model_id, model in batch.items()
                    },
                )
            pipeline.execute()
            
            # 设置缓存过期时间
            cls.cache.expire(cache_key, cls.CACHE_TIMEOUT)
            
            return object_models
            
        except Exception as e:
            logger.exception(f"Failed to refresh object model cache: {e}")
            return {}
```

##### 2.2 在 CMDB 缓存模块中注册

**文件位置**: `alarm_backends/core/cache/cmdb/__init__.py`

```python
from .object_model import ObjectModelManager

__all__ = [
    # ... 现有导出 ...
    "ObjectModelManager",
]
```

##### 2.3 在 TargetCondition 中使用缓存管理器

修改 `TargetCondition` 类中的 `_get_model_code_by_id` 方法：

```python
def _get_model_code_by_id(self, model_id):
    """
    根据模型ID获取模型代码
    使用对象模型缓存管理器获取
    """
    from alarm_backends.core.cache.cmdb.object_model import ObjectModelManager
    
    # 从缓存中获取对象模型信息
    model_code = ObjectModelManager.get_model_code_by_id(
        bk_tenant_id=self.bk_tenant_id,
        model_id=str(model_id)
    )
    
    return model_code
```

##### 2.4 缓存刷新任务

如果需要定期刷新缓存，可以创建管理命令或定时任务：

**文件位置**: `alarm_backends/management/commands/refresh_object_model_cache.py`

```python
"""
刷新对象模型缓存的管理命令
使用方法: python manage.py refresh_object_model_cache
"""

from django.core.management.base import BaseCommand
from alarm_backends.core.cache.cmdb.object_model import ObjectModelManager
from bkmonitor.utils.tenant import get_all_tenant_ids


class Command(BaseCommand):
    help = "刷新对象模型缓存"

    def handle(self, *args, **options):
        self.stdout.write("开始刷新对象模型缓存...")
        
        # 获取所有租户ID
        tenant_ids = get_all_tenant_ids()
        
        for tenant_id in tenant_ids:
            try:
                ObjectModelManager.refresh(bk_tenant_id=tenant_id)
                self.stdout.write(
                    self.style.SUCCESS(f"成功刷新租户 {tenant_id} 的对象模型缓存")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"刷新租户 {tenant_id} 的缓存失败: {e}")
                )
        
        self.stdout.write(self.style.SUCCESS("对象模型缓存刷新完成"))
```

**注意事项**：
1. 缓存使用 Redis Hash 结构存储，key 为 `{tenant_id}.monitor.cache.cmdb.object_model`，field 为 `model_id`
2. 缓存过期时间为 24 小时（`CACHE_TIMEOUT = 60 * 60 * 24`）
3. 支持多租户模式，不同租户的缓存相互隔离
4. 如果缓存未命中，需要实现从 CMDB API 获取数据的逻辑
5. 建议在系统启动时或定期任务中刷新缓存，避免实时查询影响性能

## 6. 测试验证

### 6.1 单元测试

创建测试文件：`alarm_backends/tests/utils/test_target_condition.py`

```python
from unittest.mock import patch
from bkmonitor.utils.range.target import TargetCondition

class TestObjectModelTarget:
    """测试对象模型监控目标"""
    
    def test_load_object_model_condition(self):
        """测试加载对象模型条件"""
        target = [[{
            "field": "cw_object_model",
            "method": "eq",
            "value": [
                {
                    "cw_object_model_code": "host",
                    "cw_object_model_inst_id": "123"
                }
            ]
        }]]
        
        condition = TargetCondition(bk_biz_id=2, target=target)
        assert len(condition.conditions_list) == 1
        assert condition.conditions_list[0][0]["target_keys"] == {"host|123"}
    
    def test_match_object_model_data(self):
        """测试匹配对象模型数据"""
        target = [[{
            "field": "cw_object_model",
            "method": "eq",
            "value": [
                {
                    "cw_object_model_code": "host",
                    "cw_object_model_inst_id": "123"
                }
            ]
        }]]
        
        condition = TargetCondition(bk_biz_id=2, target=target)
        
        # 测试匹配成功
        data = {
            "cw_object_model_code": "host",
            "cw_object_model_inst_id": "123"
        }
        assert condition.is_match(data) is True
        
        # 测试匹配失败
        data = {
            "cw_object_model_code": "host",
            "cw_object_model_inst_id": "456"
        }
        assert condition.is_match(data) is False
```

### 6.2 集成测试

1. **策略配置测试**：创建包含对象模型监控目标的策略，验证策略能够正确保存和加载
2. **告警生成测试**：验证符合对象模型条件的数据能够正确触发告警
3. **告警屏蔽测试**：验证对象模型屏蔽规则能够正确匹配和屏蔽告警

### 6.3 前端测试

1. **选择器测试**：验证对象模型选择器能够正确显示和选择
2. **配置保存测试**：验证配置能够正确保存到后端
3. **配置回显测试**：验证编辑策略时能够正确回显对象模型配置

## 7. 注意事项

### 7.1 性能考虑

1. **映射查询优化**：如果需要在匹配时查询 `model_id` 到 `model_code` 的映射，建议使用缓存
2. **批量查询**：在 `sync_updated_parent_actions` 等批量操作中，使用批量查询减少数据库访问
3. **索引优化**：如果对象模型相关字段需要频繁查询，考虑在数据库中添加索引

### 7.2 兼容性

1. **向后兼容**：确保新字段类型的添加不影响现有功能
2. **数据迁移**：如果有历史数据需要迁移，需要编写迁移脚本
3. **API兼容**：确保API接口的变更不影响现有调用方

### 7.3 错误处理

1. **字段缺失**：当数据中缺少必要字段时，应该优雅降级，而不是抛出异常
2. **映射失败**：当 `model_id` 到 `model_code` 的映射失败时，应该记录日志并跳过匹配
3. **配置验证**：在前端和后端都应该对配置进行验证，确保必填字段存在

## 8. 完整示例

### 8.1 策略配置示例

```json
{
  "target": [
    [
      {
        "field": "cw_object_model",
        "method": "eq",
        "value": [
          {
            "cw_object_model_code": "host",
            "cw_object_model_inst_id": "123"
          },
          {
            "cw_object_model_code": "host",
            "cw_object_model_inst_id": "456"
          }
        ]
      }
    ]
  ]
}
```

### 8.2 数据上报示例

```json
{
  "dimensions": {
    "cw_object_model_code": "host",
    "cw_object_model_id": "1",
    "cw_object_model_inst_id": "123",
    "metric_name": "cpu_usage"
  },
  "value": 85.5,
  "timestamp": 1234567890
}
```

### 8.3 告警屏蔽配置示例

```json
{
  "dimension_config": {
    "cw_object_model": [
      {
        "cw_object_model_code": "host",
        "cw_object_model_inst_id": "123"
      }
    ]
  }
}
```

## 9. 总结

扩展监控目标类型需要修改以下关键位置：

1. **后端核心逻辑**：
   - `constants/strategy.py`: 定义字段类型常量
   - `bkmonitor/utils/range/target.py`: 实现匹配逻辑
   - `packages/monitor_web/shield/utils.py`: 实现屏蔽匹配逻辑

2. **前端配置界面**：
   - 策略配置组件：添加新类型选择器
   - IP选择器组件：添加新选择面板

3. **数据映射**：
   - 建立配置字段到数据维度的映射关系
   - 实现 `model_id` 到 `model_code` 的转换逻辑

4. **测试验证**：
   - 单元测试：验证核心逻辑
   - 集成测试：验证端到端流程
   - 前端测试：验证用户交互

按照本文档的步骤，可以系统性地扩展新的监控目标类型，确保功能的完整性和稳定性。

