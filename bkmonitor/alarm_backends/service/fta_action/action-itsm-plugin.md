# ITSM 流程套餐执行逻辑详细分析

## 概述

ITSM（IT Service Management）流程套餐是蓝鲸监控平台中用于创建和管理 ITSM 工单的处理套餐。当告警触发时，系统会根据配置自动创建 ITSM 工单，并通过轮询机制跟踪工单状态，直到工单完成。

## 核心组件

### 1. 处理器架构

ITSM 流程套餐使用通用的 `ActionProcessor` 处理器（位于 `alarm_backends/service/fta_action/common/processor.py`），而不是专门的 ITSM 处理器。这意味着 ITSM 套餐的执行逻辑是通过配置驱动的通用框架实现的。

### 2. 关键文件

- **`alarm_backends/service/fta_action/common/processor.py`**: 通用处理器，执行 ITSM 套餐的核心逻辑
- **`alarm_backends/service/fta_action/tasks/create_action.py`**: 创建动作实例，处理告警分派中的 ITSM 动作
- **`alarm_backends/service/fta_action/tasks/alert_assign.py`**: 告警分派管理，处理 ITSM 动作的分配
- **`alarm_backends/service/fta_action/__init__.py`**: 基础处理器，包含审批相关功能
- **`api/itsm/default.py`**: ITSM API 资源定义

## 执行流程

### 阶段一：动作创建（create_action.py）

#### 1.1 告警分派处理

在 `CreateActionProcessor.alert_assign_handle()` 方法中：

```480:526:alarm_backends/service/fta_action/tasks/create_action.py
    def alert_assign_handle(self, alert, action_configs, origin_actions, itsm_actions):
        """
        分派操作
        :param alert:
        :param action_configs:
        :param origin_actions:
        :param itsm_actions:
        :return:
        """
        # 注： 指定了处理动作的情况下， 不需要进行分派，主要是webhook回调
        assign_mode = self.notice["options"].get("assign_mode")
        assign_labels = {
            "bk_biz_id": alert.event.bk_biz_id,
            "assign_type": "action",
            "notice_type": self.notice_type,
            "alert_source": getattr(alert.event, "plugin_id", ""),
        }
        with metrics.ALERT_ASSIGN_PROCESS_TIME.labels(**assign_labels).time():
            exc = None
            assignee_manager = None
            try:
                assignee_manager = AlertAssigneeManager(
                    alert,
                    self.notice["user_groups"],
                    assign_mode,
                    self.notice["options"].get("upgrade_config", {}),
                    notice_type=self.notice_type,
                )
                assign_labels.update({"rule_group_id": assignee_manager.matched_group})
            except BaseException as error:
                assign_labels.update({"rule_group_id": None})
                exc = error
                logger.exception("[alert assign error] alert(%s) assign failed, error info %s", alert.id, str(error))
            assign_labels["status"] = metrics.StatusEnum.from_exc(exc)

        metrics.ALERT_ASSIGN_PROCESS_COUNT.labels(**assign_labels).inc()
        if self.execute_times == 0 and self.notice_type != ActionNoticeType.UPGRADE and exc is None:
            # 创建流程单据，仅第一次分派的时候进行操作
            for itsm_action_id in assignee_manager.itsm_actions.keys():
                if str(itsm_action_id) not in action_configs:
                    action_configs[str(itsm_action_id)] = ActionConfigCacheManager.get_action_config_by_id(
                        itsm_action_id
                    )
                if str(itsm_action_id) not in origin_actions:
                    # 不在告警处理中，直接添加
                    itsm_actions.append({"config_id": itsm_action_id, "id": 0, "options": {}})
        return assignee_manager
```

**关键逻辑：**
- 当告警分派规则匹配成功时，如果规则中配置了 `itsm_actions`，系统会将这些 ITSM 动作添加到待创建的动作列表中
- 仅在第一次执行（`execute_times == 0`）且非升级通知时创建 ITSM 工单
- 通过 `AlertAssigneeManager.itsm_actions` 属性获取 ITSM 动作配置

#### 1.2 ITSM 动作获取

在 `AlertAssigneeManager` 中：

```314:318:alarm_backends/service/fta_action/tasks/alert_assign.py
    @property
    def itsm_actions(self):
        if self.match_manager:
            return self.match_manager.matched_rule_info["itsm_actions"]
        return {}
```

**说明：** ITSM 动作信息来自告警分派匹配管理器（`match_manager`）的匹配规则信息。

#### 1.3 动作实例创建

在 `do_create_actions()` 方法中，ITSM 动作会与普通动作一起处理：

```698:742:alarm_backends/service/fta_action/tasks/create_action.py
            for action in actions + itsm_actions:
                action_config = action_configs.get(str(action["config_id"]))
                if not self.is_action_config_valid(alert, action_config):
                    continue
                action_plugin = action_plugins.get(str(action_config["plugin_id"]))
                skip_delay = int(action["options"].get("skip_delay", 0))
                current_time = int(time.time())
                if ActionSignal.ABNORMAL in action["signal"] and current_time - alert["begin_time"] > skip_delay > 0:
                    # 如果当前时间距离告警开始时间，大于skip_delay，则不处理改套餐
                    description = {
                        "config_id": action["config_id"],
                        "action_name": action_config["name"],
                        "action_signal": action["signal"],
                        "skip_delay": skip_delay,
                        "content": f"告警开始时间距离当前时间大于{skip_delay}秒,不处理该套餐",
                    }

                    # 由于并没有实际创建ActionInstance,所以这里的action_instance_id为0
                    action_log = dict(
                        op_type=AlertLog.OpType.ACTION,
                        alert_id=alert.id,
                        description=json.dumps(description, ensure_ascii=False),
                        time=current_time,
                        create_time=current_time,
                        event_id=f"{int(time.time() * 1000)}0",
                    )
                    AlertLog.bulk_create([AlertLog(**action_log)])
                    logger.warning(
                        "[fta_action] AlertID: %s, ActionName: %s, Reason: %s",
                        alert.id,
                        action_config["name"],
                        f"告警开始时间距离当前时间大于{skip_delay}秒,不处理该套餐",
                    )

                    continue
                action_instances.append(
                    self.do_create_action(
                        action_config,
                        action_plugin,
                        alert,
                        action_relation=action,
                        assignee_manager=assignee_manager,
                        shield_ids=shield_ids,
                    )
                )
```

### 阶段二：动作执行（common/processor.py）

#### 2.1 执行入口

```76:96:alarm_backends/service/fta_action/common/processor.py
    def execute(self, failed_times=0):
        """
        执行
        :return:
        """
        # 只有在可执行状态下的任务才能执行
        if self.action.status not in ActionStatus.CAN_EXECUTE_STATUS:
            raise ActionAlreadyFinishedError(_("当前任务状态不可执行"))

        # 执行入口，需要发送自愈通知
        self.set_start_to_execute()

        if not self.backend_config:
            self.set_finished(ActionStatus.FAILURE, message="unknown execute function")

        # 执行函数为配置参数的第一个
        execute_func = getattr(self, self.backend_config[0]["function"])
        if not execute_func:
            self.set_finished(ActionStatus.FAILURE, message="unknown execute function")

        return execute_func()
```

**说明：**
- 执行入口会先调用 `set_start_to_execute()` 更新动作状态为 `RUNNING`
- 根据 `backend_config` 配置的第一个函数（通常是 `create_task`）来执行

#### 2.2 创建工单（create_task）

```119:124:alarm_backends/service/fta_action/common/processor.py
    def create_task(self, **kwargs):
        """
        创建任务阶段
        """
        task_config = self.function_config.get("create_task")
        return self.run_node_task(task_config, **kwargs)
```

**ITSM 套餐的 create_task 配置：**

根据 `support-files/fta/action_plugin_initial.json` 中的配置：

```json
{
  "function": "create_task",
  "name": "创建单据",
  "resource_class": "CommonBaseResource",
  "resource_module": "api.common.default",
  "init_kwargs": {
    "url": "{{bk_paas_inner_host}}/api/c/compapi/v2/itsm/create_ticket/",
    "method": "POST"
  },
  "inputs": [
    {
      "key": "service_id",
      "value": "execute_config.template_id",
      "type": "int",
      "format": "jmespath"
    },
    {
      "key": "fields",
      "value": "execute_config.template_detail[].{key: key, value: value}",
      "type": "list",
      "format": "jmespath"
    },
    {
      "key": "creator",
      "value": "operator",
      "type": "string",
      "format": "jmespath"
    }
  ],
  "outputs": [
    {
      "key": "sn",
      "value": "response.sn",
      "format": "jmespath"
    },
    {
      "key": "id",
      "value": "response.id",
      "format": "jmespath"
    },
    {
      "key": "url",
      "value": "{{itsm_site_url}}#/ticket/detail?id={{id}}",
      "format": "jinja2"
    }
  ],
  "need_insert_log": true,
  "log_template": "根据套餐【{{action_name}}】的配置已成功创建故障工单[{{sn}}]，点击$查看工单详情$"
}
```

#### 2.3 节点任务执行（run_node_task）

```135:214:alarm_backends/service/fta_action/common/processor.py
    def run_node_task(self, config, **kwargs):
        if self.action.status not in ActionStatus.CAN_EXECUTE_STATUS:
            raise ActionAlreadyFinishedError(_("当前任务状态不可执行"))
        node_execute_times_key = "node_execute_times_{}".format(config.get("function", "execute"))
        self.action.outputs[node_execute_times_key] = self.action.outputs.get(node_execute_times_key, 0) + 1
        current_step_name = config.get("name")
        self.insert_action_log(current_step_name, _("执行任务参数： %s") % kwargs)
        try:
            outputs = self.run_request_action(config, **kwargs)
        except (APIPermissionDeniedError, BKAPIError, CustomException) as error:
            self.set_finished(
                to_status=ActionStatus.FAILURE,
                message=_("以当前告警负责人[{}]执行{}时, 接口返回{}").format(
                    ",".join(self.action.assignee), current_step_name, str(error)
                ),
                retry_func=config.get("function", "execute"),
                kwargs=kwargs,
            )
            return
        except EmptyAssigneeError as error:
            self.set_finished(
                to_status=ActionStatus.FAILURE,
                message=_("执行{}出错，{}").format(current_step_name, str(error)),
                retry_func=config.get("function", "execute"),
                kwargs=kwargs,
            )
            return
        except BaseException as exc:
            # 出现异常的时候，当前节点执行三次重新推入队列执行
            logger.exception(str(exc))

            kwargs["node_execute_times"] = self.action.outputs.get(node_execute_times_key, 1)
            self.set_finished(
                ActionStatus.FAILURE,
                failure_type=FailureType.FRAMEWORK_CODE,
                message=_("执行{}: {}").format(current_step_name, str(exc)),
                retry_func=config.get("function", "execute"),
                kwargs=kwargs,
            )
            return

        self.update_action_outputs(outputs)

        if self.is_action_finished(outputs, config.get("finished_rule")):
            # 根据配置任务参数是来判断当前任务是否结束
            if self.is_action_success(outputs, config.get("success_rule")):
                self.set_finished(ActionStatus.SUCCESS)
            else:
                self.set_finished(
                    ActionStatus.FAILURE,
                    message=_("{}阶段出错，第三方任务返回执行失败: {}").format(
                        current_step_name, outputs.get("message")
                    ),
                    retry_func=config.get("function", "execute"),
                    kwargs=kwargs,
                )
            return outputs

        if config.get("need_schedule"):
            # 当前阶段未结束，还需要轮询
            schedule_timedelta = config.get("schedule_timedelta", 5)

            self.wait_callback(
                config.get("function", "schedule"),
                {"pre_node_outputs": outputs},
                delta_seconds=schedule_timedelta,
            )
            return outputs

        if config.get("next_function"):
            # 当前节点已经结束，插入节点日志
            if config.get("need_insert_log"):
                self.action.insert_alert_log(
                    content_template=config.get("log_template", ""), notice_way_display=self.notice_way_display
                )
            self.wait_callback(config.get("next_function"), {"pre_node_outputs": outputs}, delta_seconds=2)
            return outputs

        self.set_finished(ActionStatus.SUCCESS)
        return outputs
```

**关键逻辑：**
1. **执行请求**：调用 `run_request_action()` 执行实际的 API 请求
2. **更新输出**：将 API 返回的结果更新到 `action.outputs` 中
3. **判断完成**：根据 `finished_rule` 判断任务是否完成
4. **判断成功**：根据 `success_rule` 判断任务是否成功
5. **轮询调度**：如果配置了 `need_schedule`，则延迟后调用 `schedule` 函数
6. **下一步函数**：如果配置了 `next_function`，则调用下一个函数

#### 2.4 执行请求动作（run_request_action）

```216:239:alarm_backends/service/fta_action/common/processor.py
    def run_request_action(self, request_schema, **kwargs):
        """执行url请求"""
        try:
            resource_module = import_module(request_schema["resource_module"])
        except ImportError as err:
            logger.exception(err)
            return {}
        source_class = request_schema["resource_class"]
        if not hasattr(resource_module, source_class):
            return {}

        request_class = getattr(resource_module, source_class)
        inputs = self.jmespath_search_data(inputs=request_schema.get("inputs", []), **kwargs)
        inputs.update(
            {
                "assignee": self.action.assignee if self.action.assignee else [],
                "action_plugin_key": self.action.action_plugin["plugin_key"]
                or self.action.action_plugin["plugin_type"],
            }
        )
        inputs.update(request_schema.get("request_data_mapping", {}))
        data = {"response": request_class(**request_schema.get("init_kwargs", {})).request(**inputs)}
        outputs = self.decode_request_outputs(output_templates=request_schema.get("outputs", []), **data)
        return outputs
```

**说明：**
- 动态导入资源模块和类
- 使用 JMESPath 解析输入参数
- 调用资源类的 `request()` 方法执行 API 请求
- 解析输出结果并返回

#### 2.5 轮询工单状态（schedule）

```126:133:alarm_backends/service/fta_action/common/processor.py
    def schedule(self, **kwargs):
        """轮询"""
        # 只有在可执行状态下的任务才能执行
        if self.action.status not in ActionStatus.CAN_EXECUTE_STATUS:
            raise ActionAlreadyFinishedError(_("当前任务状态不可执行"))

        task_config = self.function_config.get("schedule")
        return self.run_node_task(task_config, **kwargs)
```

**ITSM 套餐的 schedule 配置：**

```json
{
  "function": "schedule",
  "name": "轮询状态",
  "resource_class": "CommonBaseResource",
  "resource_module": "api.common.default",
  "init_kwargs": {
    "url": "{{bk_paas_inner_host}}/api/c/compapi/v2/itsm/get_ticket_status/",
    "method": "GET"
  },
  "inputs": [
    {
      "key": "sn",
      "value": "pre_node_outputs.sn",
      "type": "string",
      "format": "jmespath"
    }
  ],
  "outputs": [
    {
      "key": "current_status",
      "value": "response.current_status",
      "type": "string",
      "format": "jmespath"
    },
    {
      "key": "url",
      "value": "response.ticket_url",
      "type": "string",
      "format": "jmespath"
    }
  ],
  "finished_rule": {
    "key": "current_status",
    "method": "equal",
    "value": "FINISHED"
  },
  "need_schedule": true,
  "schedule_timedelta": 2,
  "next_function": "schedule"
}
```

**轮询机制：**
- 每 2 秒（`schedule_timedelta`）轮询一次工单状态
- 使用 `pre_node_outputs.sn`（上一次节点输出的工单号）查询状态
- 当 `current_status == "FINISHED"` 时，任务完成
- 如果未完成，继续调用 `schedule` 函数（`next_function: "schedule"`）

## 数据流转

### 输入数据准备

```47:74:alarm_backends/service/fta_action/common/processor.py
    @cached_property
    def inputs(self):
        """
        输入数据
        """
        template_detail = self.execute_config["template_detail"]
        try:
            template_detail = self.jinja_render(template_detail)
        except BaseException as error:
            logger.error("Format execute params error %s", str(error))
            self.set_finished(ActionStatus.FAILURE, message=_("获取任务参数异常，错误信息：{}").format(str(error)))
            # 直接设置为结束，抛出异常，终止整个执行
            raise

        template_detail_list = [{"key": key, "value": value} for key, value in template_detail.items()]
        execute_config = deepcopy(self.execute_config)
        execute_config["template_detail"] = template_detail_list
        execute_config["template_detail_dict"] = template_detail
        params = {
            "operator": self.notice_receivers[0] if self.notice_receivers else self.action.assignee,
            "execute_config": execute_config,
            "bk_biz_id": self.action.bk_biz_id,
            "action_name": _("[故障自愈]-{}").format(self.action_config.get("name")),
            "bk_paas_inner_host": settings.BK_COMPONENT_API_URL.rstrip("/"),
            "bk_paas_host": settings.BK_PAAS_HOST.rstrip("/"),
        }
        params.update(ActionPlugin.PUBLIC_PARAMS)
        return params
```

**关键步骤：**
1. 从 `execute_config.template_detail` 获取模板详情
2. 使用 Jinja2 渲染模板（支持告警上下文变量）
3. 转换为列表格式和字典格式
4. 添加操作人、业务ID等公共参数

### 参数解析

```260:268:alarm_backends/service/fta_action/common/processor.py
    def jmespath_search_data(self, inputs, **kwargs):
        """
        jmespath解析请求输入数据
        """
        kwargs.update(self.inputs)
        return {
            item["key"]: jmespath.search(item["value"], kwargs) if item.get("format") == "jmespath" else item["value"]
            for item in inputs
        }
```

**说明：** 使用 JMESPath 从上下文中提取配置中指定的参数值。

### 输出解析

```241:258:alarm_backends/service/fta_action/common/processor.py
    def decode_request_outputs(self, output_templates, **kwargs):
        """
        解析请求的输出
        :param output_templates: 输出参数模板
        :param kwargs:
        :return:
        """
        kwargs.update(self.inputs)
        outputs = {}
        for output_template in output_templates:
            kwargs.update(outputs)
            format_type = output_template.get("format", "jmespath")
            key = output_template["key"]
            value = output_template["value"]
            outputs[key] = (
                Jinja2Renderer.render(value, kwargs) if format_type == "jinja2" else jmespath.search(value, kwargs)
            )
        return outputs
```

**说明：** 支持 JMESPath 和 Jinja2 两种格式解析 API 响应数据。

## 完成条件判断

### finished_rule（完成规则）

```396:403:alarm_backends/service/fta_action/__init__.py
    def is_action_finished(self, outputs: list, finished_rule):
        """
        根据配置的条件来判断任务是否结束
        """
        if not finished_rule:
            return False

        return self.business_rule_validate(outputs, finished_rule)
```

### success_rule（成功规则）

```414:421:alarm_backends/service/fta_action/__init__.py
    def is_action_success(self, outputs: list, success_rule):
        """
        根据配置的条件来判断任务是否成功
        """
        if not success_rule:
            return True

        return self.business_rule_validate(outputs, success_rule)
```

### 业务规则验证

```423:440:alarm_backends/service/fta_action/__init__.py
    @staticmethod
    def business_rule_validate(params, rule):
        """ "
        条件判断
        """

        logger.info("business rule validate params %s, rule %s", params, rule)

        if rule["method"] == "equal":
            return jmespath.search(rule["key"], params) == rule["value"]

        if rule["method"] == "in":
            return jmespath.search(rule["key"], params) in rule["value"]

        if rule["method"] == "not in":
            return jmespath.search(rule["key"], params) not in rule["value"]

        return False
```

**ITSM 套餐的完成规则：**
- `finished_rule`: `current_status == "FINISHED"`
- 当工单状态为 `FINISHED` 时，任务完成

## 回调机制

### wait_callback

```177:193:alarm_backends/service/fta_action/__init__.py
    def wait_callback(self, callback_func, kwargs=None, delta_seconds=0):
        """
        等待回调或者轮询
        """
        kwargs = kwargs or {}
        callback_module = getattr(self, "CALLBACK_MODULE", "")
        if not callback_module:
            try:
                callback_module = inspect.getmodule(inspect.stack()[1][0]).__name__
            except BaseException as error:
                logger.exception("inspect module error %s", str(error))

        logger.info("$%s delay to run %s.%s wait(%s)", self.action.id, callback_module, callback_func, delta_seconds)

        PushActionProcessor.push_action_to_execute_queue(
            self.action, countdown=delta_seconds, callback_func=callback_func, kwargs=kwargs
        )
```

**说明：** 将动作推送到执行队列，延迟 `delta_seconds` 秒后执行指定的回调函数。

## 异常处理

### 错误类型

1. **API 权限错误** (`APIPermissionDeniedError`): 告警负责人无权限执行
2. **API 错误** (`BKAPIError`, `CustomException`): ITSM API 返回错误
3. **空负责人错误** (`EmptyAssigneeError`): 没有告警负责人
4. **其他异常**: 框架代码错误，会重试最多 3 次

### 重试机制

```442:492:alarm_backends/service/fta_action/__init__.py
    def set_finished(
        self, to_status, failure_type="", message=_("执行任务成功"), retry_func="execute", kwargs=None, end_time=None
    ):
        """
        设置任务结束
        :param need_poll:
        :param to_status: 结束状态
        :param failure_type: 错误类型
        :param message: 结束日志信息
        :param retry_func: 重试函数
        :param kwargs: 需要重试调用参数
        :return:
        """
        if to_status not in ActionStatus.END_STATUS:
            logger.info("destination status %s is not in end status list", to_status)
            return
        if (
            to_status == ActionStatus.FAILURE
            and failure_type != FailureType.TIMEOUT
            and self.retry_times < self.max_retry_times
        ):
            # 当执行失败的时候，需要进行重试
            # 此处存在的问题： 重试从哪里开始，譬如标准运维的重试，很有可能需要调用重试的接口，
            # 目前延用自愈以前的方式通过通完全重试的方法来进行重试
            if self.retry_times == 0 and self.timeout_setting:
                self.wait_callback(callback_func="timeout_callback", delta_seconds=self.timeout_setting)

            self.is_finished = False
            self.wait_callback(retry_func, delta_seconds=self.retry_interval, kwargs=kwargs)
            return

        if (
            failure_type == FailureType.FRAMEWORK_CODE
            and kwargs.get("node_execute_times", 0) < 3
            and kwargs.get("ignore_error", False) is False
        ):
            # 如果是自愈系统异常并且当前说节点执行次数少于3次，继续重试
            self.is_finished = False
            self.wait_callback(retry_func, delta_seconds=5, kwargs=kwargs)
            self.action.save(update_fields=["outputs"])
            return

        self.is_finished = True
        # 任务结束的时候，需要发送通知
        self.update_action_status(
            to_status=to_status,
            failure_type=failure_type,
            end_time=end_time or datetime.now(tz=timezone.utc),
            need_poll=need_poll(self.action),
            ex_data={"message": message},
        )
        # 更新任务数据(插入日志)
        level = ActionLogLevel.ERROR if to_status == ActionStatus.FAILURE else ActionLogLevel.INFO
        self.insert_action_log(
            step_name=_("第{}次任务执行结束".format(self.retry_times)),
            action_log=_("执行{}: {}").format(ACTION_STATUS_DICT.get(to_status), message),
            level=level,
        )

        self.action.insert_alert_log(notice_way_display=getattr(self, "notice_way_display", ""))

        if self.action.action_plugin.get("plugin_type") != ActionPluginType.NOTICE:
            notify_result = self.notify(STATUS_NOTIFY_DICT.get(to_status), need_update_context=True)
            if notify_result:
                execute_notify_result = self.action.outputs.get("execute_notify_result") or {}
                execute_notify_result.update(notify_result)
                self.update_action_outputs(outputs={"execute_notify_result": execute_notify_result})
```

**重试策略：**
1. **配置重试**：如果配置了 `max_retry_times` 和 `retry_interval`，失败时会自动重试
2. **节点重试**：节点执行失败时，最多重试 3 次
3. **超时处理**：如果配置了超时时间，会设置超时回调

## 审批功能（可选）

ITSM 流程套餐还支持异常防御审批功能，通过 ITSM 快速审批单据实现：

### 创建审批工单

```195:230:alarm_backends/service/fta_action/__init__.py
    def create_approve_ticket(self, **kwargs):
        """
        创建ITSM工单
        """

        content_template = AlarmNoticeTemplate.get_template("notice/fta_action/itsm_ticket_content.jinja")
        approve_content = Jinja2Renderer.render(content_template, self.context)
        ticket_data = {
            "creator": "fta-system",
            "fields": [
                {
                    "key": "title",
                    "value": _("[告警异常防御审批]:是否继续执行套餐【{}】").format(self.action_config["name"]),
                },
                {"key": "APPROVER", "value": ",".join(self.action.assignee)},
                {"key": "APPROVAL_CONTENT", "value": approve_content},
            ],
            "meta": {"callback_url": os.path.join(settings.BK_PAAS_INNER_HOST, "fta/action/instances/callback/")},
        }
        try:
            approve_info = CreateFastApprovalTicketResource().request(**ticket_data)
        except BaseException as error:
            self.set_finished(
                ActionStatus.FAILURE, message=_("创建异常防御审批单据失败,错误信息：{}").format(str(error))
            )
            return
        # 创建快速审批单据并且记录审批信息
        self.update_action_outputs({"approve_info": approve_info})

        # 创建快速审批单据后设置一个30分钟超时任务
        self.wait_callback("approve_timeout_callback", approve_info, delta_seconds=60 * 30)

        # 每隔1分钟之后获取记录
        self.wait_callback("get_approve_result", approve_info, delta_seconds=60)

        self.action.insert_alert_log(notice_way_display=self.notice_way_display)
```

### 获取审批结果

```232:249:alarm_backends/service/fta_action/__init__.py
    def get_approve_result(self, **kwargs):
        """
        获取审批结果 同意：推入队列，直接执行 拒绝
        """
        if self.action.status != ActionStatus.WAITING:
            logger.info("current status %s is forbidden to run", self.action.status)
            return

        sn = kwargs.get("sn") or self.action.outputs.get("approve_info", {}).get("sn")
        try:
            approve_result = TicketApproveResultResource().request(**{"sn": [sn]})[0]
        except BaseException as error:
            logger.exception("get approve result error : %s, request sn: %s", error, sn)
            self.set_finished(
                ActionStatus.FAILURE, message=_("获取异常防御审批结果出错，错误信息：{}").format(str(error))
            )
        else:
            self.approve_callback(**approve_result)
```

### 审批回调处理

```251:275:alarm_backends/service/fta_action/__init__.py
    def approve_callback(self, **kwargs):
        if self.action.status != ActionStatus.WAITING:
            logger.info("current status %s is forbidden to run", self.action.status)
            return

        approve_result = kwargs
        if approve_result["current_status"] == "RUNNING":
            # 还在执行中, 等待五分钟之后再次获取结果
            self.wait_callback("get_approve_result", {"sn": approve_result["sn"]}, delta_seconds=60)
            return
        if approve_result["current_status"] == "FINISHED" and approve_result["approve_result"] is True:
            # 结束并且通过的，直接入到执行队列
            self.update_action_status(ActionStatus.RUNNING)
            self.wait_callback("execute")
            self.insert_action_log(
                step_name=_("异常防御审批通过"),
                action_log=_("{}审批通过，继续执行处理动作，工单详情<a target = 'blank' href='{}'>{}<a/>").format(
                    approve_result["updated_by"], approve_result["sn"], approve_result["ticket_url"]
                ),
                level=ActionLogLevel.INFO,
            )
            return
        self.set_finished(
            ActionStatus.SKIPPED, message=_("审批不通过，忽略执行，审批人{}").format(approve_result["updated_by"])
        )
```

## 总结

### 执行流程图

```
告警触发
  ↓
告警分派匹配
  ↓
发现 ITSM 动作配置
  ↓
创建 ActionInstance
  ↓
推送到执行队列
  ↓
execute() 入口
  ↓
create_task() - 创建 ITSM 工单
  ↓
调用 ITSM API: create_ticket
  ↓
获取工单号 (sn)
  ↓
schedule() - 轮询工单状态
  ↓
调用 ITSM API: get_ticket_status
  ↓
判断状态是否为 FINISHED
  ↓
是 → 任务完成 (SUCCESS)
  ↓
否 → 等待 2 秒后继续轮询
```

### 关键特性

1. **配置驱动**：通过 `backend_config` 配置定义执行流程，无需编写专门代码
2. **模板渲染**：支持 Jinja2 模板，可以使用告警上下文变量
3. **轮询机制**：自动轮询工单状态，直到完成
4. **异常处理**：完善的错误处理和重试机制
5. **审批支持**：可选的异常防御审批功能
6. **状态跟踪**：完整的动作状态和日志记录

### 扩展性

ITSM 流程套餐的实现方式展示了系统的扩展性：
- 通过配置 `backend_config` 可以支持不同的执行流程
- 通过 `resource_class` 和 `resource_module` 可以调用不同的 API
- 通过 `inputs` 和 `outputs` 配置可以灵活映射参数
- 通过 `finished_rule` 和 `success_rule` 可以自定义完成条件

这种设计使得系统可以轻松支持其他类型的处理套餐（如标准运维、作业平台等），而无需修改核心代码。

