# 新版运营指标开发文档
项目路径：`packages/monitor_web/statistics/v2`

## 一、如何创建文件
运营指标一般有一级分类和二级分类，文件名选择二级分类的英文名作为文件名称，如果一个一级分类包含多个二级分类，则每个二级分类单独就是一个文件。

例如：一级分类【数据接入】，二级分类【告警源(event_plugin)】，则该运营指标的文件名为`event_plugin.py`，

## 二、如何定义指标类
类名一般与文件名相同，即用二级分类的英文名作为类名，并且继承`monitor_web.statistics.v2.base.BaseCollector`类。

例如：该运营指标文件名为`event_plugin.py`，则该指标类名为`EventPluginCollector`
```python
from monitor_web.statistics.v2.base import BaseCollector


class EventPluginCollector(BaseCollector):
    pass
```

## 三、如何定义指标函数
在每个二级分类中，包含了1-n个相关的指标，每个指标就是该类的一个类函数。每个指标名就是该类函数的函数名，并且需要用`register`方法进行装饰（`register`里面需要补充当前指标的每个维度），函数的说明将作为该指标的说明。

例如：一级分类【数据接入】，二级分类【告警源(event_plugin)】，指标名【告警源接收条数 (event_plugin_ingest_count)】，维度【"bk_biz_id", "bk_biz_name", "plugin_type", "is_public"】
则我们需要在`event_plugin.py`的`EventPluginCollector`类下定义一个`event_plugin_ingest_count`方法
```python
from monitor_web.statistics.v2.base import BaseCollector
from core.statistics.metric import register, Metric


class EventPluginCollector(BaseCollector):
    """
    告警源
    """
    
    @register(labelnames=("bk_biz_id", "bk_biz_name", "plugin_type", "is_public"))
    def event_plugin_count(self, metric: Metric):
        """
        告警源插件数
        """
        pass
```

## 四、如何优化函数
### 4.1 合理抽象
一般的一个二级分类可能会存在多个指标，几个之间之间可能会共用到许多的方法或相同的数据，此时就需要将这些共用到的部分进行抽离出来，如果一个数据在多个指标中都用到了，可以使用`cached_property`进行装饰。

例如：仪表盘指标需要通过api去grafana获取当前的所有组织，但仪表盘存在多个指标都需要这个组织信息，此时就可以将其抽象出来，用`cached_property`装饰
```python
class GrafanaCollector(BaseCollector):
    """
    仪表盘
    """

    @cached_property
    def organizations(self):  # 后面所有的指标只需要共用organizations即可
        organizatios = api.grafana.get_all_organization()["data"]
        new_organizatios = []
        for org in organizatios:
            org_name = org["name"]
            if not org_name.isdigit():
                continue
            if int(org_name) not in self.biz_info:
                continue
            new_organizatios.append(org)
        return new_organizatios
```
### 4.2 不要过于造轮子
当前的`BaseCollector`中封装了`biz_info`、`biz_exists`和`get_biz_name`方法，并且也有相关的`TIME_RANGE`可供使用，不需要在类里面重新定义。
```python
# 1. TIME_RANGE的使用
class AlertActionCollector(BaseCollector):
    """
    告警事件
    """

    @cached_property
    def now(self):
        return arrow.now()
    
    @register(labelnames=("bk_biz_id", "bk_biz_name", "status", "method", "le"))
    def action_notice_count(self, metric: Metric):
        """
        告警通知数
        """
        for le_en, seconds in TIME_RANGE:
            start_time = int(self.now.replace(seconds=-seconds).timestamp)
            search_object = (
                ActionInstanceDocument.search(start_time=start_time, end_time=int(self.now.timestamp))
                .filter("range", create_time={"gte": start_time, "lte": int(self.now.timestamp)})
                .filter("term", action_plugin_type=ActionPluginType.NOTICE)
                .exclude("term", is_parent_action=True)
            )
        ...

# 2. biz相关函数的使用
class UserGroupCollector(BaseCollector):
    """
    告警组
    """

    @cached_property
    def user_groups(self):
        return UserGroup.objects.filter(bk_biz_id__in=list(self.biz_info.keys()))

    @register(labelnames=("bk_biz_id", "bk_biz_name", "need_duty"))
    def user_group_count(self, metric: Metric):
        """
        告警组配置数
        """
        for group in self.user_groups:
            metric.labels(
                bk_biz_id=group.bk_biz_id,
                bk_biz_name=self.get_biz_name(group.bk_biz_id),
                need_duty="1" if group.need_duty else "0",
            ).inc()
        ...
```

## 五、如何生成指标数据
每个函数都会传入一个`metric`参数，它属于`Metric`类的实例，我们在对数据进行处理后，只需要调用labels方法就可以添加相关维度，利用`inc`(默认加一)或者`set`就可以设置指标值。
```python
class UserGroupCollector(BaseCollector):
    """
    告警组
    """

    @cached_property
    def user_groups(self):
        return UserGroup.objects.filter(bk_biz_id__in=list(self.biz_info.keys()))

    @register(labelnames=("bk_biz_id", "bk_biz_name", "need_duty"))
    def user_group_count(self, metric: Metric):
        """
        告警组配置数
        """
        for group in self.user_groups:
            # 1。 用inc方法：inc方法是执行加法，如果里面参数为空，则默认加1，如果传入一个整数，则会在原来的基础上加上这个整数。
            metric.labels(
                bk_biz_id=group.bk_biz_id,  # 往指标中注入bk_biz_id维度，它的值是group.bk_biz_id的结果
                bk_biz_name=self.get_biz_name(group.bk_biz_id),  # 往指标中注入bk_biz_name维度，它的值是self.get_biz_name(group.bk_biz_id)的结果
                need_duty="1" if group.need_duty else "0",  # 往指标中注入need_duty维度，它的值是"1" if group.need_duty else "0"的结果
            ).inc()
            # 2。 用set方法：set方法是直接设置当前的指标值为某一个数字。
            metric.labels(
                bk_biz_id=group.bk_biz_id,  # 往指标中注入bk_biz_id维度，它的值是group.bk_biz_id的结果
                bk_biz_name=self.get_biz_name(group.bk_biz_id),  # 往指标中注入bk_biz_name维度，它的值是self.get_biz_name(group.bk_biz_id)的结果
                need_duty="1" if group.need_duty else "0",  # 往指标中注入need_duty维度，它的值是"1" if group.need_duty else "0"的结果
            ).set(num)  # num为数据处理后得出的一个值
            
```

## 六、如何注册当前指标
所有的指标都需要进行注册，我们需要在`packages/monitor_web/statistics/v2/factory.py`方法中导入这个类，并且在`INSTALLED_COLLECTORS`中进行注册。
```python
from monitor_web.statistics.v2.user_group import UserGroupCollector

INSTALLED_COLLECTORS = [
    ...
    UserGroupCollector
]
```

## 七、如何校验函数是否正确
要校验自己写的指标是否正确，可以直接在终端或者控制台进行导入(import)，执行采集方法(collect)，然后打印出相关数据即可(export_text)
```python
from monitor_web.statistics.v2.user_group import UserGroupCollector
user_group_collect = UserGroupCollector()
user_group_collect.collect()  # 如果在5分钟内执行多次，所得到的数据都是第一次采集的数据，如果要刷新需要添加refresh=True参数
print(user_group_collect.export_text())
```
上面的方法执行完之后，如果有报错就根据报错信息修改即可。正常会出现如下数据
```text
# HELP bkmonitor_user_group_count 告警组配置数  （这个说明是根据该指标的__doc__拿取的，所以每个指标必须都添加上对应的说明）
# TYPE bkmonitor_user_group_count gauge
bkmonitor_user_group_count{need_duty="0",bk_biz_id="2",bk_biz_name="[2] 蓝鲸"} 6.0  （如果本地没有相关数据，这里可能没有）
bkmonitor_user_group_count_updated 1.654831371e+09
```

## 八、其他
旧版运营指标地址：`packages/monitor_web/statistics/metrics.py`

新版运营指标定时任务（每一分钟会刷新一次），地址：`monitor_web.tasks.update_statistics_data`

新版运营指标自定义上报功能，地址：`alarm_backends.service.report.tasks.operation_data_custom_report_v2`
