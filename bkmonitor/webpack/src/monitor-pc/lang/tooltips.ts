/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

// tooltips 相关的词条
export default {
  // 规范： 仅首字母大写

  // Tooltip：鼠标悬停在某个元素上时显示的文本提示，例如图标、按钮等。
  'MTTA指平均应答时间 = 所有告警的总持续时间 / 总告警数量':
    'MTTA refers to the average response time = the total duration of all alarms Time/total number of alarms',
  'MTTR指平均解决时间，平均解决时间=所有告警的持续时间/总告警数量':
    'MTTR refers to the average resolution time, and the average resolution time=all Duration of the alarm/total number of alarms',
  '自愈覆盖率指致命告警有告警处理(除工单外) / 总致命告警数，致命告警建议补齐自愈能力':
    'Self-healing coverage means fatal alarms have alarm processing (Except for work orders) / Total number of fatal alarms, fatal alarms are suggested to supplement the self-healing ability',
  AIOps算法只支持单指标: 'AIOps algorithm only supports single indicator',
  往当前用户发送一封测试邮件: 'Send a test email to the current user',
  点击展开收藏: 'Click to Expand favorites',
  点击收起检索: 'Click to Collapse Search',
  切换手动查询: 'Switch to manual query',
  切换自动查询: 'Switch to auto query',
  点击重试: 'Click to Retry',
  点击展开: 'Click to Expand',
  点击查看: 'Click to View',
  点击查询: 'Click to Query',
  '原因: Agent未安装或者状态异常': 'Reason: Agent is not installed or in abnormal state',
  '原因：查看进程本身问题或者检查进程配置是否正常':
    'Reason: Check the problem of the process itself or check whether the process configuration is normal',
  '原因：bkmonitorbeat未安装或者状态异常': 'Reason: bkmonitorbeat is not installed or in an abnormal state',
  '原因：bkmonitorbeat进程采集器未安装或者状态异常':
    'Reason: The bkmonitorbeat process collector is not installed or the status is abnormal ',
  '原因:bkmonitorbeat未安装或者状态异常': 'Reason: bkmonitorbeat is not installed or in an abnormal state',
  '原因:查看进程本身问题或者检查进程配置是否正常':
    'Reason: Check the process itself for issues or check if the process configuration is normal',
  '原因:bkmonitorbeat进程采集器未安装或者状态异常':
    'Reason: The BKmonitorbeat process collector is not installed or in an abnormal state',
  '服务端进程的第一个 Service':
    'This is the entry serivce of entrie trace. The Serivce that generates by a server service.',
  '整个 Trace 的第一个 Span':
    'This is the entry point of the entire trace. The Service that generates this first span also creates the Trace ID.',
  '每个 Service 的第一个 Span': 'This is the first span generated by a service each time it is called.',
  入口服务的第一个接口: 'This is the entry point of the Root Service.',
  包含根span的trace: 'Trace containing root span',
  '复制 TraceID': 'Copy TraceID',
  '动态：只能选择节点，策略目标按节点动态变更。静态：只能选择主机IP，采集目标不会变更。':
    'Dynamic: Only nodes can be selected, and the rule target can be dynamically changed by node. Static: Only the host IP can be selected, and the collection target will not change. ',
  '动态：只能选择节点，采集目标按节点动态变更。静态：只能选择主机IP，采集目标不会变更。':
    'dynamic: only nodes can be selected, and the collection target can be dynamically changed according to the node. Static: Only the host IP can be selected, and the collection target will not change. ',
  '平均应答时间，从告警真实发生到用户响应的平均时间。平均应答时间=总持续时间/总告警数量':
    "Average response time, the average time from the actual occurrence of the alarm to the user's response. Average response time = total duration/total number of alarms",
  '平均解决时间，从告警真实发生到告警被处理的平均时间。':
    'Average resolution time, the average time from when an alarm actually occurs to when the alarm is processed. ',
  '平均解决时间，从告警真实发生到告警被处理的平均时间。平均解决时间=总持续时间/总告警数量':
    'average resolution time, from The average time from when an alarm actually occurs to when the alarm is processed. Average Resolution Time = Total Duration/Total Number of Alerts',
  '(当前值 - 前一时刻值){0}过去{1}天内任意一天同时刻的 (差值 ×{2}+{3}) 时触发告警':
    '(Current value - Previous value) The alarm is triggered {0} simultaneously (difference ×{2}+{3}) on any day in the past {1}',
  '(总事件数-总告警数)/总事件数 ， 降噪比越大越好':
    '(total number of events - total number of alarms)/total number of events, the larger the noise reduction ratio, the better',
  '降噪比=(总事件数-总告警数) / 总事件数 ， 降噪比越大表示告警收敛效果好':
    'noise reduction ratio=(total number of events-total number of alarms)/total number of events, the larger the noise reduction ratio, the better the alarm convergence effect',
  获取群ID方法: 'Method of Obtaining Group ID',
  "获取会话ID方法:<br/>1.群聊列表右键添加群机器人: {name}<br/>2.手动 @{name} 并输入关键字'会话ID'<br/>3.将获取到的会话ID粘贴到输入框，使用逗号分隔":
    "How to get the session ID:<br/>1. Right click on group chat list to add group robots: {name}<br/>2. Manually @{name} and enter the keyword'The session ID'<br/>3. The group that will be obtained Paste the ID into the input box, separated by commas",
  '编辑/增加/删除/启动/停用指标？': 'Edit/add/delete/start/stop metrics?',
  '编辑指标/维度有风险': 'There are risks in editing metrics/dimensions',
  '编辑指标或维度存在风险，注意在仪表盘和策略中使用了修改前的指标将失效':
    'Editing indicators or dimensions is risky. Note that indicators before modification will become invalid if used in dashboards and strategies',
  'JS散度越大，说明该维度内各维度值的异常分值越离散，越值得排查':
    'The larger the JS divergence, the greater the change in the abnormal score of each dimension value in this dimension, and the more worthy of investigation',
  '总事件数指通过策略检测产生的所有告警明细，具体查看告警事件的关联事件':
    'Total number of events refers to the number of events generated through rule detection For details of all alarms, see the associated events of the alarm event',
  '总持续时间: 所有告警的首次异常时间到告警标记为已解决或已恢复的时间。':
    'Total Duration: Time from the first exception time of all alerts to the time when the alert is marked as resolved or recovered. ',
  '总持续时间：所有告警的首次异常时间到下一个状态变更的时间点，如确认/屏蔽/恢复/关闭/已解决':
    'total duration: the first abnormal time of all alarms to the time point of the next state change, such as confirmation/blocking/recovery/close/resolved',
  '仅展示最近10条，更多详情请{0}': 'Only the latest 10 are displayed, for more details please {0}', // 中文错了 是 详情
  '仅支持导入".gz .tgz .bz2 .tbz2"gzip或bzip2压缩格式文件':
    'Only support importing ".gz .tgz .bz2 .tbz2" gzip or bzip2 compression format files',
  '按通知次数的指数递增，依次按N，2N，4N，8N,...依次类推执行，最大24小时':
    'Increase exponentially by the number of notifications , press N, 2N, 4N, 8N,... and so on, up to 24 hours ',
  '按钮即可开始。': 'Button to start.', // 中文在哪里？ 感觉缺少了词
  '（仅支持查看当前事件中最近一条的原始数据信息）':
    '(Only supports viewing the original data information of the latest event in the current event)',
  '（基于CMDB业务拓扑选择集群、模块、IP等。默认为本业务）': ' (Cluster, module, IP, The default is this business)',
  '（对数据进行筛选过滤）': '(Filter data)',
  '（新建完成后自动获取）': '(Automatically obtained after creation is completed)',
  '（未关联策略配置）': '(Unassociated rules)',
  '（点击跳转到拨测节点页面）': '(Jump to probe node page)',
  '（选择数据汇聚的维度）': '(Select dimension)',
  '(输入并回车即可创建新标签。可使用“/”创建多级分类，如：主机/系统告警)':
    '(Create a new label by enter. You can use "/" to create multi-level classification, such as: host/system alarm)',
  '(变量列表及模板说明详见右侧栏)': '(For variable list and template description, see the right column)',
  '需先停用采集任务，也可同时删除关联的策略':
    'Need to disable the collection task first , you can also delete the associated rule at the same time',
  '需遵循公司规范，禁止对外暴露用户或公司内部敏感信息（用户PII信息、账号密码、云AKSK、内部系统鉴权/Token、保密文档等），若因授权不当造成数据泄露须承担相应责任; ':
    'It is necessary to comply with company regulations and prohibit the disclosure of user or internal sensitive information (such as user PII information, account passwords, cloud AKSK, internal system authentication/Token, confidential documents, etc.). If data leakage is caused by improper authorization, corresponding responsibilities must be borne;',
  '非当前业务，不允许操作': 'Operation not allowed for current business',
  '高危代表执行此类操作影响比较大，在执行处理套餐时需要进行及时的通知。':
    'High risk means that the impact of performing such operations is relatively large, and the solution is executed Timely notification is required. ',
  '默认就是采集目标与采集程序运行在一起，在有单独的采集主机或者权限限制需要远程采集的方式。':
    'The default is that the collection target and the collection program run together, and there is a separate collection host Or permission restrictions require remote collection.',
  '默认录入到蓝鲸配置平台的主机，将会采集操作系统和进程相关的指标数据和事件数据，所以开启主机监控需要关联业务资源。':
    'By default, the host entered into the BlueKing configuration platform will collect metric data and event data related to the operating system and process, so enabling host monitoring requires associated business resources.',
  '默认是开启的，采集周期内默认相同的内容会汇聚到成一条并且计数。':
    'It is enabled by default, and the same content will be aggregated into one and counted by default in the collection cycle. ',
  '默认是所有时间都生效，日历中添加的为不生效时间段':
    'By default, all times are effective, and the ones added in the calendar are ineffective time periods.',
  '提示：通过 {0} 未找到对应的索引集。如果要采集日志可以前往日志平台。':
    'Prompt: No corresponding Indices can be found through {0}. If you want to collect logs, you can go to the log platform. ',
  注意在仪表盘和策略中使用了修改前的指标将失效:
    'Attention If the metric before modification is used in the dashboard and rule, it will be invalid',
  '时间经过校准，注意服务所在时钟是否同步':
    'The time has been calibrated, pay attention to whether the clock of the service is synchronized',
  '该操作仅删除任务组，不会影响组内拨测任务':
    'this operation only deletes the task group and will not affect the dialing within the group Test task',
  '谨慎代表执行此类操作影响比高危小，但是也不可多次反复的执行，一般在失败时需要提示。':
    'Caution means that the impact of performing such operations is less than high-risk, but it cannot be executed repeatedly. Generally, a prompt is required when it fails. ',
  '请遵守公司规范，切勿泄露敏感信息，后果自负！':
    'Please comply with company regulations and do not disclose sensitive information at your own risk!',
  '该插件未定义参数，如需升级请继续！':
    'This plugin has no defined parameters, please continue if you need to upgrade!',
  '该请求不含主体。': 'This Request Does Not Contain a Body.',
  '该请求不需要任何认证。': 'This request does not require any authentication.',
  '轮值功能，可以按不同的时段分配不同的值班成员':
    'Rotation function, you can assign different members on duty according to different time periods',
  执行后不可逆: 'Irreversible after execution',
  使用远程运行主机: 'Use remote host for execution',
  使用选择器: 'Use selector',
  仅保留最近30天的历史记录: 'Only keep the last 30 days of history records',
  '未编辑, 不需要撤销': 'Not edited, no need to undo',
  '测试进行时，请勿关闭弹窗！': 'Do not close the pop-up window during testing!',
  有采集任务时不允许修改: 'Modification is not allowed when there is a collection task',
  '专有采集主机 使用整个服务器的50%的资源,其他情况都只是使用10%的资源并且不超过单CPU资源.':
    'The dedicated acquisition host uses 50% of the resources of the entire server, and in other cases only uses 10% of the resources and does not exceed a single CPU resource .',
  '使用整个服务器的50%的资源，其他情况都只是使用10%的资源并且不超过单CPU资源。':
    'Use 50% of the resources of the entire server, and in other cases only use 10% of resources and do not exceed single CPU resources.',
  '不告警，会生成告警但不进行告警通知等处理。可在{0}进行设置':
    'no alarm, an alarm will be generated but no alarm notification will be processed. It can be set in {0}',
  '当前收藏有更新，点击保存当前修改': 'The current collection has been updated, click Save Current Modifications',
  '自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年':
    'custom input format: such as 1w represents a week m minute h hour d day w week M month y year',
  '若告警未恢复并且未确认，则每隔{count}分钟再进行告警':
    'If the alarm is not recovered and not confirmed, the alarm will be repeated every {count} minutes',
  '若产生相同的告警未确认或者未屏蔽,则{0}间隔{1}分钟再进行告警。':
    'If the same alarm is not confirmed or masked, then {0}interval {1} minutes Then give an alarm. ',
  执行时需谨慎: 'Execute with caution',
  支持变量过滤和数据分组: 'Variable filtering and data grouping are supported',
  支持指标分组和标签配置: 'You can configure metric groups and labels',
  系统事件只支持实时检测: 'System events only support real-time detection',
  '数值越高优先级越高,最大值为10000': 'The higher the value, the higher the priority, the maximum value is 10000',
  所有业务的事件中心列表中的告警事件的总和:
    'The total number of alarm events in the event center list for all businesses',
  所有业务的事件中心里面告警关联的事件的总和:
    'The total number of events associated with alarm events in the event center for all businesses',
  执行数指告警事件中执行记录数量的总和:
    'Execution count refers to the total number of execution records in alarm events.',
  总告警数指告警事件中告警数量的总和:
    'Total number of alarms refers to the sum of the number of alarms in alarm events',
  一个指标一行: 'One Metric Per Line',
  三类监控项可任选其一: 'Any one of the three monitoring items can be selected',
  Y轴固定最小值为0: 'Y-axis fixed minimum value is 0',
  将通过企业微信将相关人员邀请到一个群里面进行讨论:
    'Invite relevant personnel to a group discussion via enterprise WeChat',
  继续添加拨测任务: 'Continue to add probe tasks',
  '实时是基于链路中的数据点（未落地时），直接进行数据的阈值比对，所以只适用于快速的单点的数据检测场景。像系统事件类就是没有落地存储直接在链路中进行检查。':
    'Real-time is based on the data points in the link (when it is not on the ground), and directly compares the threshold of the data, so it is only suitable for fast single-point data detection scenarios. For example, system events are checked directly in the link without landing storage. ',
  '同级别的各算法之间是{0}的关系': 'The relationship between algorithms of the same severity is {0}',
  '告警确认不会影响其他告警，只是避免当前告警的周期间隔发送和处理套餐的执行':
    'alarm confirmation will not affect other alarms, but to avoid the periodic interval sending of the current alarm and the execution of the alarm solution',
  '按{0}即可关闭全屏弹窗': 'Press {n} to close the full screen popup',
  '当告警持续时长每超过{0}分种，将逐个按告警组升级通知':
    'When the duration of the alarm exceeds {0} minutes, the alarm team will be escalated one by one',
  '当告警策略配置了告警处理，可以通过如下的通知方式获取到执行处理套餐的结果':
    'When the alarm rule is configured After alarm processing, you can obtain the results of the execution alarm solution through the following notification methods',
  '当该告警确认需要处理，并且希望该告警不再通知时，可以直接进行告警确认':
    'When the alarm confirmation needs to be processed and you want the alarm to be notified no longer, you can directly confirm the alarm',
  '当没有收到任何数据可以进行告警通知。': 'When no data is received, alarm notification can be performed.',
  '当数据连续丢失{0}个周期时，触发告警通知': 'When data is lost for {0} cycles in a row, trigger an alarm notification',
  '当防御的通知汇总也产生了大量的风暴时，会进行本业务的跨策略的汇总通知。':
    'When the notification summary of the defense also generates a large number of storms, the cross-rule summary notification of this business will be carried out. ',
  '开启全业务作用范围，全部业务都可见属于自身业务的数据，有平台特定的数据格式要求，请联系平台管理员。':
    'Enable the full business scope, all businesses can see the data belonging to their own business, there is a platform For specific data format requirements, please contact the platform administrator. ',
  '其中持续时间指告警的首次异常时间到状态变更的时间段，状态变更如确认/屏蔽/恢复/关闭/已解决等':
    'The duration refers to the time period from the first abnormal time of the alarm to the status change, such as confirmation/blocking/recovery/closed/resolved',
  '关联告警在需要判断多个告警事件关联产生才生效时就可以使用。':
    'Associated alarms can be used when it is necessary to judge the occurrence of multiple alarm event associations to take effect. ',
  选择目标进行对比: 'Select targets for comparison.',
  '在左侧选择主机/节点/动态分组': 'Select host/node/dynamic',
  '当前可能是手动查询，请': 'Currently may be a manual query, please',
  '告警名称通过字段映射可以自动获取到，也可以手动新增。手动新增优先级高于自动获取。':
    'The alarm name can be obtained automatically through field mapping, or it can be added manually. The priority of manual addition is higher than that of automatic acquisition. ',
  '执行了处理套餐（除工单）的致命告警/总致命告警数，自愈率越高越好':
    'Fatal alarms/total number of fatal alarms that have executed the alarm solution (except work orders), self-healing The higher the rate, the better',
  '每个小时整点,半点发送': 'Sent every hour on the hour and at half hour',
  '每天9:00,21:00发送': 'Sent daily at 9:00 and 21:00',
  '从0点开始,每隔2小时整点发送': 'Starting from 0:00, send every 2 hours on the hour',
  '从0点开始,每隔6小时整点发送': 'Starting from 0:00, send every 6 hours on the hour',
  个人有权限查看的空间数: 'The number of spaces that individuals have permission to view',
  其中持续时间指告警的首次异常时间到告警状态变成已解决或已恢复的时间段:
    'The duration refers to the time period from the first abnormal time of the alarm to the time when the alarm status becomes resolved or recovered',
  删除该生效时段将会删除其包含的所有信息: 'Deleting the effective period will delete all the information it contains',
  '解散分组后，原分组内的收藏将移至未分组中。':
    'After the group is dissolved, the collections within the original group will be moved to the ungrouped group.',
  '添加统一设置后，所有规则会默认添加上所设置的条件':
    'After you add a unified setting, all rules add the conditions set on it by default',
  整个策略已被屏蔽: 'The entire rule has been muted',
  '删除该组及组内规则会一起删除,且不可恢复':
    'Deleting the group and the rules within the group are deleted together and are not recoverable',
  '勾选后会精准过滤，不会显示没有该维度的指标图表。':
    'After checking, it will be filtered accurately, and the metric chart without this dimension will not be displayed. ',
  '异常分值范围从0到1，分值越大，说明该维度值的指标异常程度越高。':
    'Outlier scores range from 0 to 1, with larger scores indicating greater metric anomalies for that dimension value.',
  '由匹配规则{0}生成': 'Generated by matching rule {0}',
  '系统会自动创建该告警策略，响应信息匹配失败将会产生告警。':
    'The system will automatically create the alarm rule, and an alarm will be generated if the response information fails to match. ',
  从配置平台过滤地区和运营商: 'Filter regions and operators from the configuration platform',
  依赖历史数据长度: 'Depend on the length of historical data',
  处理记录里面所有的执行记录数量: 'The number of execution records in all handling record',
  当蓝鲸监控的进程状态异常或告警队列拥塞时会通知相关人员:
    'When the process status monitored by BlueKing is abnormal or the alarm queue is congested Notify relevant personnel ',
  手动分配指标数: 'Manually allocate metric numbers',
  蓝鲸监控机器人发送图片全局设置已关闭: 'The global setting of BlueKing Monitor robot sending pictures is closed',
  近3个周期数据: 'Data from the past 3 cycles',
  非当前业务节点: 'Non-current business node',
  批量复制: 'Bulk copy',
  数据时间: 'Data Time',
  '全屏 ctrl + m': 'Full-Screen ctrl+m',
  '快捷键：Ctrl+M': 'Shortcut: Ctrl+M', // 这个是在哪里？
  排序并置顶: 'Sort and Pin',
  智能检测算法不支持实时检测: 'Intelligent detection do not support real-time detection',
  不支持查询数据的来源和类型: 'The source and type of query data are not supported',
  该功能依赖AIOps平台: 'This feature relies on the AIOps platform',
  不支持计算后的查询数据: 'Calculated query data is not supported',
  不支持实时检测: 'Real-time detection is not supported',
  离群检测和其他算法互斥: 'Outlier detection and other algorithms are mutually exclusive.',
  一个策略不能同时添加两个相同的智能检测:
    'One rule cannot have two identical intelligent detections added simultaneously.',
  只支持计算平台的单指标数据: 'Only supports single indicator data for bk base',
  常规算法不同等级只能各添加一种:
    'For regular detections of different levels, only one type can be added for each level.',
  变量示例: 'Example',
  点击复制变量: 'Click to copy variables',
  '已有相同算法,设置为{name}级别': 'Same algorithm already exists, set to {name} level',
  '支持将告警信息发送至外部，包括企业微信群机器人、QQ、Slack、钉钉、飞书、微信公众号以及外部邮箱等多种告警通知方式。':
    'It supports sending alarm information to the outside, including enterprise WeChat group robots, QQ, Slack, nail, fly book, WeChat official account, external mailbox and other alarm notification methods.',
  当前为全局的: 'Currently global',
  存在关联的用户组: 'There are associated user groups',
  起始日: 'Start date',
  设为起始日: 'Set as start date',
  AI设置: 'AI settings',
  '告警生成后，将根据指标的异常程度、发生异常的指标数，为告警自动评级':
    'After the alarm is generated, it will be automatically rated based on the degree of abnormality of the indicators and the number of abnormal indicators that have occurred',
  内置的分派规则组不允许修改: 'The built-in assignment rule group does not allow modification',
  内置策略不允许修改: 'The built-in strategy does not allow modification',
  关注人禁用此操作: 'The follower disables this action',
  暂未开启主机智能异常检测: 'Host intelligent anomaly detection has not been enabled yet',
  '主机场景检测数据源正在接入中，请稍后重试':
    'The host scene detection data source is currently being connected, please try again later',
  '存在关联的策略，不可删除': 'There are associated policies that cannot be deleted',
  '若添加进程，请前往配置平台 - 业务拓扑，在对应模块下新增':
    'If adding a process, please go to the configuration platform - business topology and add it under the corresponding module',
  请求数: 'Request count',
  对比时间: 'Comparison time',
  参照时间: 'Reference time',
  告警系统事件: 'Alarm System Event',
  故障系统事件: 'Fault System Event',
  '关闭 AI 小鲸会话': 'Close the AI ​​Assistant session',
  '打开 AI 小鲸会话': 'Open the AI ​​Assistant session',
  '蓝鲸监控的告警包含哪几个级别？': 'What are the alert levels included in Blue Whale monitoring?',
  '如何在仪表盘中进行指标计算？': 'How to perform metric calculations in the dashboard?',
  '主机监控场景包含哪些指标？': 'What metrics are included in the host monitoring scenario?',
  '如何接入第三方告警源？': 'How to integrate third-party alert sources?',
  '智能检测目前能支持哪些场景？': 'What scenarios are currently supported by intelligent detection?',
  '你好，我是AI小鲸，你可以向我提问蓝鲸监控产品使用相关的问题。':
    'Hello, I am AI ​​Assistant. You can ask me questions related to the use of the Blue Whale monitoring product.',
  地图: 'Map',
  图例: 'Legend',
  下载: 'Download',
  原始大小: 'Original size',
  查看完整接口: 'View complete interface',
  已禁用: 'Disabled',
  '存在表达式依赖，不能删除': 'Expression dependency exists, cannot be deleted',
  '存在表达式,暂不支持转换': 'Expression exists, conversion is not supported temporarily',
  中位数: 'median',
  复制到: 'Copy to',
  上一跳: 'Previous hop',
  下一跳: 'Next hop',
  已经是第一个span: 'It is already the first span',
  已经是最后一个span: 'It is already the last span',
  点击隐藏该指标: 'Click to hide this indicator',
  点击显示该指标: 'Click to display this indicator',
  清空整组筛选项: 'Clear all filter options in the group',
  请先删除子级维度: 'Please delete the child dimension first',
  '该指标在当前级别({0})不可用': 'This indicator is not available at the current level ({0})',
  '新版容器监控尚未完全覆盖旧版功能，如需可切换到旧版查看':
    'The new version of container monitoring does not fully cover the legacy features yet. You can switch to the legacy version to view them if necessary',
  新建收藏分组: 'Add favorite group',
  调整排序: 'Adjust order',
  收起收藏夹: 'Collapse favorite folder',
  展开收藏夹: 'Expand favorite folder',
  收起查询: 'Collapse query',
  即将上线: 'Coming soon',
  '该维度暂无数据，无法进行统计分析': 'This dimension has no data and cannot be statistically analyzed',
  '该字段类型，暂时不支持统计分析': 'This field type does not currently support statistical analysis',
  '新版事件检索尚未完全覆盖旧版功能，如需可切换到旧版查看':
    'New version event search has not fully covered the old version features yet. If needed, you can switch to the old version to view them',
  布尔: 'Boolean',
  请先勾选告警组: 'Please check the alarm group first',
};
