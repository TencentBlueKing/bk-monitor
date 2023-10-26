# 日历服务（Calendar）


现在的蓝鲸监控的告警策略是在三个阶段（告警触发时、告警恢复时、告警关闭时）实施告警的，我们自身也有对应的告警屏蔽方案（只能按照时间范围选择）。但因为不同的业务需要，需要实现根据国家法定节假日、A股等特殊日期的特殊时间进行告警处理（即在设定不可用的时间段内产生的告警不会发送，而该时间段外的告警都属于正常告警，会正常发送）。

## 一、日历服务整个的需要注意点

- 该日历是全局的一个日历，他只承担日历的角色，不需要进行额外的操作（即策略引入对应的日历之后，可以根据日历中包含的事项内容去进行合理的告警）
- 日历具备快速制作能力，即有周末、法定节假日等已经完善的日历作为默认选项
- 需要对时区进行处理（默认取浏览器的时区）
- saas可以通过暴露的api查看该事项是否生效
- 支持按照日、周、月、年的情况给予查询

## 二、目前已知需要开放的接口

- 根据当前时间点或者未来的某个时间点判断该事项是否生效
- 根据日、周、月、年的查询方式给予对应的事项
- 对日历的增删改查接口
- 对事项的增删改查接口

## 三、事项所需注意的点

### 3.1 包含字段

| 字段名       | 类型   | 说明                                                     |
| ------------ | ------ | -------------------------------------------------------- |
| name         | String | 事项名（最大15个汉字）                                   |
| update_user  | String | 更新者                                                   |
| update_time  | Int | 更新时间                                                 |
| create_user  | String | 创建者                                                   |
| create_time  | Int | 创建时间                                                 |
| calendar_id  | Int    | 所属日历ID                                               |
| start_time   | Int | 事项开始时间                                             |
| end_time     | Int | 事项结束时间                                             |
| repeat | Dict   | 重复事项配置信息                                  |
| parent_id    | Int    | 父表ID（在编辑单个事项的时候，该字段将被用到，默认null） |
| time_zone | String | 时区信息（默认`Asia/Shanghai`） |

#### 重复事项配置信息（repeat）

| 字段名       | 类型        | 说明                                                                                                                                             |
| ------------ | ----------- |------------------------------------------------------------------------------------------------------------------------------------------------|
| freq   | String      | 重复频率（天："day"，周："week"，月："month"，年："year"）                                                                                                      |
| interval     | Int         | 重复间隔                                                                                                                                           |
| until | Int      | 重复结束时间                                                                                                                                         |
| every | List（int） | 重复区间，当`label`为`week`时这里是`0-6`(0为周天)的数字，当`label`为`month`的时候，这里是`1-31`的数字，当`label`为`year`的时候这里的数字是`1-12`（注：如果传入的start_time对应的标志不在重复区间内，则会自动将其加入） |
| exclude_date | List(int) | 排除事项日期(这里记录排除在重复范围内的日期)                                                                                                                        |

- 不重复（默认）=>`repeat={}`

- 每天

    ```python
    {
        "freq": "day",
        "interval": 1,  # 间隔
        "until": 1648569600,  # 结束日期
        "every": [],  # 区间
        "exclude_date": []  # 排除事项日期
    }
    ```

- 每个工作日

    ```python
    {
        "freq": "week",
        "interval": 1,
        "until": null,  # 永不结束
        "every": [1,2,3,4,5],
        "exclude_date": []  # 排除事项日期
    }
    ```

- 每周

    ```python
    {
        "freq": "week",
        "interval": 1,
        "until": null,
        "every": [],
        "exclude_date": []  # 排除事项日期
    }
    ```

- 每月

    ```python
    {
        "freq": "month",
        "interval": 1, 
        "until": null,
        "every": [],
        "exclude_date": []  # 排除事项日期
    }
    ```

- 每年

    ```python
    {
        "freq": "year",
        "interval": 1, 
        "until": null,
        "every": [],
        "exclude_date": []  # 排除事项日期
    }
    ```

- 自定义

    自定义这里，根据用户选择的重复结束日期和重复间隔在对应的位置进行处理

    ```python
    # 每三天并且永不结束
    {
        "freq": "day",
        "interval": 3,  # 间隔
        "until": null,  # 结束日期
        "every": [],  # 区间
        "exclude_date": []  # 排除事项日期
    }
    # 每四周并且10.1日结束
    {
        "freq": "week",
        "interval": 4,  # 间隔
        "until": 1664553600,  # 结束日期
        "every": [],  # 区间
        "exclude_date": []  # 排除事项日期
    }
    # 每周四和六并且两周一次，永不结束
    {
        "freq": "week",
        "interval": 2,  # 间隔
        "until": null,  # 结束日期
        "every": [4,6],  # 区间
        "exclude_date": []  # 排除事项日期
    }
    # 每月1号和15号重复，并且间隔3个月，永不重复
    {
        "freq": "month",
        "interval": 3,  # 间隔
        "until": null,  # 结束日期
        "every": [1, 15],  # 区间
        "exclude_date": []  # 排除事项日期
    }
    ```

#### 排除日期（repeat.exclude_date）

当用户对一个重复的事项进行单个编辑或者删除的时候，对应的日期就会存入`exclude_date`

例如：当有一从`2022-03-10至2022-03-20`的每天重复的事项，如果将15号的事项删除，则可以将3.15存入`exclude_date`，使之变成`[1647273600]`

####  demo

下面的例子就是一个名为“新建事项”的事项。他归属于`id`为1的日历，是一个每3天为一个周期，并且设置时间在早上8点到12点的永不停止的事项，但是在2022年1月8日和1月11日跳过的事项。

```python
{
    "name": "新建事项",
    "update_user": "xxx",
    "update_time": 1646883864,
    "create_user": "xxx",
    "create_time": 1646883864,
    "calendar_id": 1,
    "start_time": 1641340800,
    "end_time": 1641355200,
    "time_zone": "Asia/Shanghai",
    "repeat": {
        "freq": "day",
        "interval": 3,  # 间隔
        "until": null,  # 结束日期
        "every": [],  # 区间
        "exclude_date": [1641571200, 1641830400],
    },
    "parent_id": null
}
```

### 3.2 整年事项计算流程

所需参数：calendar_ids(日历列表), year（某年）

1. 根据给定的日历id去循环这些日历的所有事项
2. 利用datatime从该事项的开始时间(拿start_time的year和传入的year进行比较，取大值)开始到结束时间（如果`repeat`中的`until`不存在则为传入year的12.31日，如果存在，则和传入的year进行比较，取小值）进行轮训，每次加`interval` day
3. 利用`repeat`的不同`freq`进行不同的计算（包括间隔、区间）
4. 将计算出来的事项实例存入列表（该列表按照1-12月进行第一层索引，而第二层是按照该月的每天进行索引，第三层则是存放当天的所有事项实例）中

### 3.3 修改事项细化

####  1⃣️ 修改全部事项

对于修改全部事项，可以直接在旧事项中进行修改，但对于子表（第二点创建出来的新事项）不会产生任何效果

#### 2⃣️ 修改循环事项中的单个事项

对于修改单个事项，(1)可以单独创建一个新的事项，(2)但是改事项要挂载到旧事项上（即新事项的`parent`参数为旧事项的id），然后在旧事项中，(3)将新事项的日期存入`exclude_date`中

注：这个单独的新事项在未来的处理事项中，只有在满足特定的情况下（后面会说明）能集联的删除，其余并没有任何关系

#### 3⃣️ 修改循环事项中的事项，并且是当前及未来事项均生效

如果是修改当前事项，并且未来事项均生效的情况，(1)同样会创建一个新事项，但不会挂载到旧事项上，而是一个独立于旧事项的新事项。（2）对该事项的开始时间和旧事项的`until`中间的子表删除关联（这种情况下，旧事项的删除也无法影响之前因修改而创建出的子表）（3）然后将旧事项的`until`修改为该新事项的开始时间。

### 3.4 删除事项细化

#### 1⃣️ 删除全部事项

对于删除全部事项，（1）会删除该事项，（2）并且将子表中`parent_id`为该事项id的事项也全部删除

#### 2⃣️ 删除循环事项中的单个事项

对于删除单个事项，只需要将需要删除的事项日期记录进`exclude_date`即可

#### 3⃣️ 删除循环事项中的事项，并且是当前及未来事项均删除

（1）将当前事项时间及`until`中间产生的并且还挂载（修改第三点可能会删除该挂载关系）的子表进行删除。（2）将`exclude_date`中当前事项时间以后的时间全部删除（3）将`until`往前移动到前一个事项产生日期

## 四、日历所需注意的点

### 4.1 包含字段

| 字段名      | 类型   | 说明                                           |
| ----------- | ------ | ---------------------------------------------- |
| name        | String | 日历名称                                       |
| update_user | String | 更新者                                         |
| update_time | Int | 更新时间                                       |
| create_user | String | 创建者                                         |
| create_time | Int | 创建时间                                       |
| classify    | String | 日历分类（内置："default"，自定义："custom"） |
| deep_color  | String | 日历深色底色                                 |
| light_color | String | 日历浅色底色 |

#### demo

```python
{
    "name": "周末日历",
    "update_user": "xxx",
    "update_time": 1646883864,
    "create_user": "xxx",
    "create_time": 1646883864,
    "classify": "default",
    "deep_color": "#000000",
    "light_color": "#222222"
}
```

### 4.2 具备功能

- 可以根据不同的时区进行展示不同的数据
- 能根据显示时间动态的展示该日历中对应的事项
- 可以根据每周天数（5或7）展示对应的事项
- 可以设定星期开始于周一还是周天
- 支持多个日历合成一个日历进行展示（不同的事项有不同的标志）

## 五、扩充

### 日历导出

根据分析苹果的日历导出格式，发现其有以下规律：

```python
BEGIN:VEVENT  # 事件开始
TRANSP:OPAQUE
DTEND;TZID=Asia/Shanghai:20220327T100000  # 事件结束时间
X-APPLE-TRAVEL-ADVISORY-BEHAVIOR:AUTOMATIC
UID:548499BA-4386-439F-B132-84E19251FC09  # 作为一个事项的唯一标识符
EXDATE;TZID=Asia/Shanghai:20220403T090000  # 排除的日期1
EXDATE;TZID=Asia/Shanghai:20220327T090000  # 排除的日期2
DTSTAMP:20220314T122630Z
SEQUENCE:1
SUMMARY:新建日程  # 该事件名称
LAST-MODIFIED:20220314T122626Z
DTSTART;TZID=Asia/Shanghai:20220327T090000  # 事件开始事件
CREATED:20220314T122608Z
RRULE:FREQ=WEEKLY;INTERVAL=1;UNTIL=20220415T155959Z  # 事件重复规则，FREQ表示重复频率，INTERVAL表示间隔，UNTIL表示结束时间
END:VEVENT
BEGIN:VEVENT
CREATED:20220314T122608Z
UID:548499BA-4386-439F-B132-84E19251FC09  # 如果是编辑重复事项的中的一个单独事项，则会新建一个事项，他的UID指向主事项
DTEND;TZID=Asia/Shanghai:20220410T100000
TRANSP:OPAQUE
X-APPLE-TRAVEL-ADVISORY-BEHAVIOR:AUTOMATIC
SUMMARY:新建日程hhhhh
LAST-MODIFIED:20220314T122807Z
DTSTAMP:20220314T122630Z
DTSTART;TZID=Asia/Shanghai:20220410T090000
SEQUENCE:1
RECURRENCE-ID;TZID=Asia/Shanghai:20220410T090000
END:VEVENT
```

那我们可以根据这个规律，根据现有的数据库也可以仿造出符合苹果日历的导入导出格式

### 日历导入

在知道导出格式之后，同样可以根据上面发现的日历格式很方便的进行分割和提取关键数据。
