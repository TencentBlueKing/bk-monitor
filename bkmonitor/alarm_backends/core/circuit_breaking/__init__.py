"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
### 熔断模块埋点
1. access.data(done)

	- 数据分发熔断: 基于策略属性(业务, 数据来源)进行熔断。
	- 命中熔断后, 不会再分发任务到 service-worker 队列, 记录日志

	- 基于 策略 id/ 策略标签 的熔断
	- 在AccessDataProcess任务执行过程中进行
	
	-  熔断后续对应 nodata 检测需要同样阻断

2. alert.builder(doing)
    - run_alert_builder 执行过程中, 正常创建告警, 在创建告警后进行熔断判定, 命中后告警状态设置为被流控, 并不再后续处理。
    - 熔断解决： celery_composite,  celery_composite 队列堵塞,  action 模块
    - 优点: 所有熔断日志均能记录到 es 中, 支持回溯
    - 缺点: alert.builder正常处理流程, 可能引起celery_alert_builder队列堵塞
    - 实现细节:
        - 熔断规则生效情况:
            1. 已存在的告警, 命中熔断后, 告警状态设置为被流控, 并set_end_status关闭告警
            2. 新创建的告警, 命中熔断后, 告警状态设置为被流控，保持告警未恢复状态，后续 关联 event 将 update 进来(由于is_blocked为True, 后续告警处理流程不会执行) 
        - 熔断规则解除:
            1. 熔断解除后, 已存在的告警, 如果is_blocked为True, 继续按原逻辑判定 qos 状态: 
                - 命中qos,则仅update(event)
                - 未命中qos,则set_end_status关闭告警并创建新告警
            2. 已存在的告警, is_blocked为False, 正常流程继续
            3. 新创建的告警, 正常流程继续
    
    - alert.manager 模块同步应用熔断规则, 规则模块尝试从alert.manager获取, 如果未配置, 则复用alert.builder中的熔断规则

3. action(todo)
	create_actions: action创建时熔断
	1. 根据 action 配置中对应的告警策略(业务, 数据来源,  策略 id), 进行熔断, 并记录告警日志流水
	2. 根据 action 配置的 plugin_type 进行熔断(notice 不再此处)
	3. 创建通知 action 时, 基于通知方式, 进行熔断, 并记录告警日志流水

4. action.execute 支持熔断+回放(todo)


### 基于熔断主体生成熔断维度
access.data:
	{
	"strategy_id": 11,
	"bk_biz_id": 11,
	# 支持单独配置源或类型的屏蔽
    "data_source_label": "bk_log_search",
    "data_type_label": "log",
	# 数据源拼接字符串 {source_label}:{type_label}
	"strategy_source": "bk_log_search:log"
	}

### 按模块配置对应的熔断配置(缓存模块管理)
- 配置写入: 缓存模块支持函数设置(封装命令)(core.cache.circuit_breaking)

- circuit_breaking:access.data
```
	# 配置之间为 or 的关系
	# 规则复用
	[{
		"key": "strategy_id",
		"method": "eq",
		"value": ["1", "2"],
	},
	{
		"key": "bk_biz_id",
		"method": "eq",
		"value": ["1", "2"],
		"condition": "or",
	},
	{
		"key": "strategy_source",
		"method": "eq",
		"value": ["bk_log_search:log"],
		"condition": "or",
	},
	]
```
"""
