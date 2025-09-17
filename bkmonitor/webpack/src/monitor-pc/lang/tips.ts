/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

// 提示 解释 相关的词条
export default {
  // 规范： 仅首字母大写
  // - Hint Text：提示文本，用于提示用户一些操作技巧或注意事项，例如“按住 Shift 键可以多选”等。
  通过左侧添加查询项: 'Add an query item through the left',
  来自配置平台主机的主维护人: 'Main maintainer of the host from the configuration platform',
  来自配置平台主机的备份维护人: 'Backup maintainer of the host from the configuration platform',
  需要查看历史导入任务详情: 'Need to view details of historical import tasks',
  新建项目将会同步创建蓝盾项目: 'A new project will synchronize the creation of a Blue Ocean project',
  '注意：ip查找索引集依赖节点管理版本>=2.1': 'Note: IP lookup Indices depends on NodeMan version >=2.1',
  '注意：单图中的数据量过多!!!': 'Attention: Too much data in single graph!!!',
  '注意：批量设置会覆盖原有的已选择的告警策略模版配置。':
    'Note: Bulk settings will overwrite the original selected alarm rule template configuration. ',
  '注意：此智能异常检测需要先学习{0}天才会生效，已经学习{1}天啦！':
    'Note: This intelligent anomaly detection needs to learn {0} before it will take effect, and it has been learned for {1} days!',
  可以从配置平台获取相应主机的字段追加到采集的数据里当成维度:
    'The field of the corresponding host can be obtained from the configuration platform and appended to the collected data as a dimension',
  指定需要注入维度的值: 'Specify the value to be injected as a dimension',
  可以从配置平台获取相应服务实例的标签追加到采集的数据里当成维度:
    'The label of the corresponding service instance can be obtained from the configuration platform and added to the collected data as a dimension',
  可以基于不同的数据维度进行告警分派: 'Alarms can be dispatched based on different data dimensions',
  可以对本订阅内容进行修改的人员: 'Personnel who can modify the subscription content',
  可以拖动拨测任务至此: 'You can drag the probe task here',
  可以按集群和模块拓扑进行数据的汇总: 'Data can be aggregated by cluster and module topology',
  可以添加告警即时的发现问题: 'Alarms can be added to detect problems immediately',
  可重复执行: 'Repeatable Execution',
  默认为本业务: 'Default is this business',
  默认展示最近20条: 'The latest 20 items',
  默认策略不允许删除: 'Default rule cannot be deleted',
  该功能暂不可用: 'This Function is Currently Unavailable',
  该操作需要以下权限: 'This operation requires the following permissions',
  '基于以下维度{0}进行判断': 'Judgment based on the following dimensions {0}',
  满足以上条件的拨测节点数: 'Number of probe nodes that meet the above conditions',
  满足以下条件时触发: 'Trigger when the following conditions are met',
  '您没有业务{0}的权限,请联系运维!': 'You do not have permission for business {0}, please contact administrator!',
  '您没有业务{name}的权限': 'You currently do not have permission for the business {name}',
  '您没有业务权限，请先申请！': 'You do not have business permissions, please apply first!',
  '您没有该业务的权限，请先申请!': 'You do not have business permissions, please apply first!',
  '您没有该资源的权限，请先申请!': 'You do not have resource permissions, please apply first!',
  '您没有业务权限，请先联系对应的业务运维同学进行添加!':
    'You do not have business permission, please contact administrator!',
  '您没有该资源的权限，请先申请或联系管理员!':
    'You do not have business permissions, please apply first or contact administrator!',
  您可以按照以下方式优化检索结果: 'You can optimize your search results as follows',
  您可以按照以下方式进行检索: 'You can search as follows',
  您当前想快速体验下平台的功能: "You currently want to quickly experience the platform's functions", // 确定中文位置
  您没有业务: 'You have no business',
  您没有权限导入官方插件: 'You do not have permission to import official plugins',
  您没有该资源的查看权限: 'You do not have permission to view this resource',
  切换将不保存当前内容: 'Switching will not save current content',
  以下为最近24小时分析: 'The following is analysis of the last 24 hours',
  '当前页面暂不支持该功能，如需使用请联系管理员':
    'The current space does not support this function. If you need to use it, please contact the administrator',
  '有关联的{0}个策略，请先删除策略。': '{0} rules are associated, please delete the rules first.',
  '检测到有新版本，点击确定刷新页面': 'A new version is detected, click OK to refresh the page',
  文件已损坏: 'File Corrupted',
  '对该配置编辑,成功{0}台主机,失败{1}台主机': 'Edit configuration, {0} hosts succeeded, {1} hosts failed',
  '对该配置编辑,成功{0}个实例,失败{1}个实例': 'Edit configuration, {0} instances succeeded, {1} instances failed',
  '对该配置增/删目标,成功{0}台主机,失败{1}台主机':
    'adding/deleting targets to this configuration, {0} hosts successfully, {1} hosts failed',
  '对该配置增/删目标,成功{0}个实例,失败{1}个实例':
    'adding/deleting targets to this configuration, {0} instances succeeded, failed{ 1} instances',
  '即将上线，敬请期待': 'Coming soon, stay tuned',
  '组合策略功能暂未开放，敬请期待！': 'The combined rule function is not yet open, please look forward to it!',
  '邮件任务已生成，请一分钟后到邮箱查看': 'The email task has been generated, please check your mailbox in one minute',
  '迁移完成，请确认迁移结果': 'Migration completed, please confirm the migration result',
  '策略迁移完成，请确认迁移结果': 'The rule migration is complete, please confirm the migration result',
  '经过努力，终于拥有了完全属于你自己的插件，加油': 'After hard work, you finally have your own plugin, keep it up',
  '当前数据还未加载完成，如数据长时间未加载出来请查看以下说明。':
    'The current data has not been loaded yet. If the data has not been loaded for a long time, please check the following instructions. ',
  已复制到剪贴板: 'Copied to clipboard',
  该主机已创建节点: 'Node Already Created on Host',
  采集任务已停用: 'Collection task has been disabled',
  '{0}/{1} 条记录中数量排名前 {2} 的数': 'The number ranked {2} in quantity among {0}/{1} records',
  '上次变更，版本号': 'Last Change, Version Number',
  '告警策略配置、处理套餐、告警组、屏蔽等各种配置管理操作':
    'alarm rule, alarm solution, alarm team, mute and other configuration management operations',
  '导入的采集配置和策略配置处于停用状态，需到列表页单独设置后才可以使用！':
    'Imported collection configuration and rule are disabled, and can only be used after setting separately on the list page! ',
  '将回滚本次的所有配置变更和目标机器的内容。回滚只能回滚上一次的状态，并且只能进行一次。':
    'will roll back all configuration changes and the content of the target machine. Rollback can only roll back the last state, and can only be done once.',
  '当前是否有数据源，如果没有请通过{0}和{1}添加': 'If there is currently a data source, if not, add it via {0} and {1}',
  '当前还没有共享集群，请联系平台管理员提供':
    'There is currently no shared cluster, please contact the platform administrator to provide.',
  '授权人的空间权限会影响被授权人，被授权人的权限范围<=授权人的权限范围，请谨慎变更。':
    "The spatial permissions of the authorizer will affect the authorized person. The authorized person's permission range is less than or equal to the authorized person's permission range. Please change it carefully.",
  '提供单点可用率、响应时长、期望响应码等指标':
    'Provides metrics such as single point availability, response time, and expected response code',
  '直接进行{0}，定位到 Trace 详情': 'Directly perform {0}, locate Trace details',
  '自定义上报指标和插件采集指标请勾选映射规则，K8S系统指标可以不勾选。':
    'Please check the mapping rules for custom reporting metrics and plugin collection metrics, and K8s system metrics can not be checked. ', // 确定位置
  '若不同时删除掉，相关联的策略配置则会成为失效策略':
    'if not deleted at the same time, the associated rule will become an invalid rule',
  '该指标需设置期望返回码/期望响应信息后才可选取':
    'This metric can only be selected after setting expected return code/expected response information',
  '该迁移工具用于协助Prometheus的grafana仪表盘、告警策略迁移，具备promql转换能力。':
    "This migration tool is used to assist Prometheus's grafana dashboard and alarm rule migration. Capable of promql conversion. ",
  '通过目标{0}，找到日志检索集可以进行检索': 'Find log search sets through target {0} for searching',
  优化查询语句: 'Optimize query statements',
  关联多个策略判断: 'Associated with multiple rule judgments',
  删除相关联的策略配置: 'Delete associated alert rules',
  双引号匹配完整字符串: 'Double quotes match full string',
  可输入SQL语句进行快速查询: 'SQL statements can be entered for quick queries',
  同时删除相关联的策略配置: 'Also delete related alert rules',
  '{0}秒后将自动跳转至{1}': 'After {0} seconds, it will automatically jump to {1}',
  在下方自定义添加或: 'Customize Adding Below or',
  基于数据源提供默认的数据可视化: 'Provides default data visualization based on data source',
  '如有其他问题,可选择:': 'If you have other questions, you can choose:',
  带字段全文检索更高效: 'Full-text search with fields is more efficient',
  '磁盘空间使用率超80%': 'Disk space utilization rate > 80%',
  '应用内存使用率超80%': 'Application memory usage > 80%',
  'CPU使用率超80%': 'CPU usage > 80%',
  当前还没有业务独享集群: 'There is currently no business exclusive cluster',
  拖拽到此处上传或点击上传: 'Drag and drop here to upload or click to upload',
  '数据格式需遵循{0},如下': 'The data format needs to follow {0}, as follows',
  本次下发覆盖: 'This Issuance Overwrites',
  监控项为策略配置: 'Monitoring items are alert rules',
  '空间数量指个人有权限的空间数量，包含业务、研发项目、容器项目、蓝鲸应用四种类型':
    'The number of spaces refers to the number of spaces that an individual has permission to use, including business, R&D projects, container projects, and Blue Whale applications',
  联系系统管理员升级至最新版本: 'Contact the system administrator to upgrade to the latest version',
  调整关键词: 'Adjusting keywords',
  配置管理业务: 'Configuration management business',
  修改或删除分类请: 'To modify or delete the classification, please',
  当前: 'Current',
  '除了通知套餐外其他都是可以设置套餐的敏感度，通知套餐基于不同的敏感度可以配置不同的通知方式。':
    'In addition to the notification solution, the sensitivity can be set, and the notification solution can be configured with different notification methods based on different sensitivities. ',
  '电话通知的拨打顺序是按通知对象顺序依次拨打。注意用户组内无法保证顺序。':
    "The telephone notification's dialing sequence is based on the order of the notification recipients. Please note that the order cannot be guaranteed within a user group.",
  编辑指标或维度存在风险: 'There are risks in editing metrics or dimensions',
  '异常分值范围从0～1，越大越异常': 'The abnormal score ranges from 0 to 1, the greater the abnormality',
  检查应用选择是否正确: 'Check that the application selection is correct',
  智能检测一切正常: 'Intelligent detection is normal',
  '当前空间暂不支持该功能，如需使用请联系管理员':
    'The current space does not support this function. If you need to use it, please contact the administrator',
  '当前空间未开启故障诊断功能, 请联系': 'The current space does not support this function. please contact',
  BK助手: 'BK Assistant',
  当前告警关联故障: 'Current alarm associated fault',
  当前告警无关联故障: 'The current alarm has no associated faults',
  当前无异常事件: 'Currently no abnormal events',
  '异常事件获取来源\n1. events.attributes.exception_stacktrace 字段\n2. status.message 字段':
    'Abnormal event acquisition source\n1. events.attributes.exception_stacktrace field\n2. status.message field',
  '已折叠 {count} 个相同"Service + Span name + status"的 Span':
    "Collapsed {count} Spans with the same 'Service+Span name+status'",
  '处理套餐中使用了电话语音通知，拨打的顺序是按通知对象顺序依次拨打，用户组内无法保证顺序':
    'Telephone voice notifications were used in the processing of the package, and the order of calls is based on the order of the notification objects. The order cannot be guaranteed within the user group',
  '不监控，就是不进行告警策略判断。可在{0}进行设置。':
    'Not monitoring means not judging the alarm strategy. Can be set in {0}.',
  '目前仅支持{0}切换PromQL': 'Currently, only {0} is supported to switch PromQL',
  '只有停用的指标不会进行采集。': 'Only deactivated indicators will not be collected.',
  '只有启用的指标才会进行采集。': 'Only enabled indicators will be collected.',
  '此项为规则匹配结果，不可移动': 'This item is a rule matching result and cannot be moved',
  安装了eBPF的采集服务就可以展示eBPF相关的数据:
    'eBPF-related data can be displayed after installing the eBPF collection service',
  '通过Span信息推断出DB、中间件、第三方等服务':
    'Infer services such as DB, middleware, and third parties through Span information',
  对比的TraceID相同: 'The compared TraceID is the same',
  '打开后，除了采集启用的指标还会采集未来新增的指标。':
    'After opening, in addition to collecting enabled indicators, future new indicators will also be collected.',
  '因为当前是旧的存储模式，开启采集新增指标后会切换成新的存储模式，旧的历史数据会丢失，请确认是否继续。':
    'Because the current storage mode is old, after enabling the collection of new indicators, it will switch to the new storage mode, and the old historical data will be lost. Please confirm whether to continue.',
  '添加新的屏蔽范围将会覆盖之前的屏蔽内容，确定覆盖？':
    'Adding a new blocking range will overwrite the previous blocked content, are you sure to proceed?',
  '批量粘贴请使用;进行分隔': 'Please use bulk pasting; Separate',
  '本空间屏蔽: 屏蔽告警中包含该空间的所有通知':
    'Local space mask: Mask all notifications that contain this space in an alarm',
  '数值越大，优先级越高，完全相同的一条数据检测到异常时以优先级高的策略为主。':
    'The larger the value, the higher the priority. When an abnormality is detected in the same piece of data, the strategy with the higher priority will be used.',
  排在前面的规则优先级高: 'The rule that comes first has a high priority',
  '时间段冲突，优先执行节假日排班': 'Time conflict, priority for the implementation of the holiday schedule',
  主机当前状态: 'Host current status',
  可对当前采集内容进行检索: 'The current collection can be retrieved',
  去检索: 'To retrieve',
  '监控数据维度未配置("目标IP"和"云区域ID")，监控目标无法命中目标':
    'The monitoring data dimensions are not configured ("target IP" and "cloud region ID"), and the monitoring target cannot hit the target',
  '监控数据维度未配置("服务实例")， 监控目标无法命中目标':
    'The monitoring data dimension is not configured ("service instance"), and the monitoring target cannot hit the target',
  存在关联的告警组: 'There is an associated alarm group',
  已选: 'selected',
  设置展示类型: 'Set display type',
  取消反馈根因: 'Cancel feedback root cause',
  反馈根因: 'Feedback root cause',
  '共 {slot0} 条边': 'There are {slot0} edges',
  '共 {slot0} 个 {type}节点': 'There are {slot0} {type} nodes in total',
  '共 {slot0} 个 {type}节点，其中 {slot1} 个异常':
    'There are {slot0} {type} nodes in total, of which {slot1} are abnormal.',
  '10分钟内无数据': 'No data within 10 minutes',
  '直接进行 精准查询，定位到 Trace 详情': 'Directly perform precise queries and locate Trace details',
  '查看关联 Trace': 'View associated Trace',
  '可以切换到 范围查询，根据条件筛选 Trace': 'You can switch to range query, filter Trace according to conditions',
  点击上传或将文件拖到此处: 'Click to upload or drag the file here',
  '文件解析可能耗费较长时间，可先选择已解析文件查看':
    'File parsing may take a long time, you can select the parsed file first to view',
  请上传文件后查看: 'Please upload the file and view it after that',
  'tips-采集状态': 'Collection Status',
  '已成功发送 {0} 个内部用户': '{0} internal users successfully sent',
  '已成功发送 {0} 个外部邮件': '{0} external messages sent successfully',
  '已成功发送 {0} 个企业微信群': '{0} enterprise WeChat groups sent successfully',
  '已成功发送 {0} 个，失败 {1} 个内部用户': '{0} successfully sent, {1} failed internal users',
  '已成功发送 {0} 个，失败 {1} 个外部邮件': '{0} successfully sent, {1} failed external messages',
  '已成功发送 {0} 个，失败 {1} 个企业微信群': '{0} successfully sent, {1} failed enterprise WeChat groups',
  '当前已存在相同索引集的订阅 {btn} ，请确认是否要创建新订阅或是直接修改已有订阅内容？':
    'There is currently a subscription {btn} for the same index set. Please confirm whether you want to create a new subscription or directly modify the existing subscription content?',
  请输入搜索条件: 'Please enter the search condition',
  确定重新发送给以下用户: 'Confirm to resend to the following users:',
  确定重新发送给以下邮件: 'Confirm to resend to the following emails:',
  确定重新发送给以下企业微信群: 'Confirm to resend to the following enterprise WeChat groups:',
  确定重新发送给以下失败用户: 'Confirm to resend to the following failed users:',
  确定重新发送给以下失败邮件: 'Confirm to resend to the following failed emails:',
  确定重新发送给以下失败企业微信群: 'Confirm to resend to the following failed enterprise WeChat groups:',
  必需为正整数: 'Must be a positive integer',
  请至少选择一种订阅方式: 'Please select at least one subscription method',
  请选择: 'please choose',
  主动订阅: 'Actively subscribe',
  他人订阅: 'Others subscribe',
  内部邮件不可为空: 'Internal email cannot be empty',
  外部邮件不可为空: 'External email cannot be empty',
  企业微信群不可为空: 'Enterprise WeChat group cannot be empty',
  '是否发送给自己?': 'Send to yourself?',
  更新人: 'Updater',
  更新时间: 'Update time',
  '输入自定义小时，按 Enter 确认': 'Enter custom hours and press Enter to confirm',
  '有效期内，订阅任务将正常发送；超出有效期，则任务失效，停止发送。':
    'Within the validity period, the subscription task will be sent normally; beyond the validity period, the task will become invalid and the sending will stop.',
  当前日志查询时间范围不支持静态区间: 'The current log query time range does not support static intervals.',
  '开启中，请耐心等待...': 'Opening, please wait patiently...',
  '该服务所在 APM 应用未开启 Profiling 功能':
    'The APM application where this service is located does not have the profiling function enabled.',
  '已开启 Profiling 功能，请参考接入指引进行数据上报':
    'The Profiling has been turned on, please refer to the access guide for data reporting.',
  显示完整信息: 'Show full information',
  '注意，该功能会调实际套餐去执行，请确认测试变量后再进行测试执行。':
    'Note that this feature will execute the actual package, please confirm the test variable before testing execution.',
  请确认是否导出: 'Please confirm whether to export',
  '导出Yaml功能用于 As Code，如需进行策略导入导出，请前往{0}进行操作':
    'The export YAML function is used for As Code. If you need to import and export policies, please go to {0} to perform operations.',
  // 故障
  节点图例: 'Node Legend',
  标签图例: 'Tag Legend',
  反馈的根因: 'Feedback Root',
  边图例: 'Edge Legend',
  从属关系: 'Subordinate',
  调用关系: 'Call',
  故障传播: 'Incident Spread',
  无故障传播: 'No Incident Spread',
  指向性: 'Directional',
  线型: 'Line Type',
  显示图例: 'Show Legend',
  显示小地图: 'Show Mini Map',
  重置比例: 'Reset Scale',
  自动聚合: 'Auto',
  按从属关系聚合: 'Aggregate by Dependency',
  按调用关系聚合: 'Aggregate by call relationship',
  '如果同时开启了 按从属关系聚合，将先进行从属边的聚合，再进行调用边的聚合':
    'If Aggregate by Dependency is enabled at the same time, subordinate edges will be aggregated first, followed by calling edges.',
  不聚合: 'No',
  聚合异常: 'Error ',
  查看资源: 'View Resource',
  查看从属: 'View Dependencies',
  查看Span: 'View Span',
  '查看 Span': 'View Span',
  反馈新根因: 'New Feedback',
  所属业务: 'Business',
  '已恢复 / 已解决 / 已失效告警': 'Recovered / Resolved / Expired Alerts',
  '已恢复...告警': 'Recovered...Alerts',
  包含告警: 'Alarm',
  '等共 {slot0} 个同类告警': 'And {slot0} Same Alerts',
  '等共 {0} 个同类告警': 'And {0} Same Alerts',
  异常信息: 'Exception Message',
  展开资源拓扑: 'Expand resource topology',
  收起资源拓扑: 'Collapse resource topology',
  '展开节点/边概览': 'Expand node/edge overview',
  '收起节点/边概览': 'Collapse node/edge overview',

  // 故障
  搜索数据为空: 'No search results',
  已展开全部: 'All items expanded',
  名称重复: 'Name duplication',
  '请输入请求 URL': 'Enter request URL',
  对象筛选: 'Space filter',
  '标题 A-Z': 'Name A-Z',
  暂无其他告警负责人: 'No other alarm responsible person',
  '当前数据还未加载完成，如数据长时间未加载出来可{0}':
    'The current data has not been loaded yet. If the data has not been loaded for a long time, {0}',
  '默认取URL中的URI进行统计，实际生产中有很多将ID应用到URI中，所以需要通过手动设置将同一类URI进行归类统计。 如： /user/{ID}/index.html':
    'By default, the URI in the URL is taken for statistics. In actual production, many IDs are applied to the URI, so it is necessary to manually set and classify the same type of URI for statistics. For example:/user/{ID}/index.com',
  选择任一图并点选所需对比时间和参照时间:
    'Select any graph and click on the desired comparison time and reference time',
  '在“故障处理”展开折叠告警拓扑，会对应展开收起时序图块；在“故障流转”点击事件，会高亮对应的时间节点。':
    'Expanding the folded alarm topology in "Incident Handling" will expand and collapse the timing diagram accordingly; clicking an event in "Incident Flow" will highlight the corresponding time node.',
  '故障内的告警：共': 'Alarm in Incident: ',
  个: ' in total',
  请选择非接口节点: 'Please select a non-interface node',
  请选择节点: 'Please select a node',
  接口概览: 'Interface Overview',
  烦躁: 'be agitated',
  可容忍: 'tolerableness',
  满意: 'satisfaction',
  日志数: 'Log count',
  可通过关联另一个应用来实现不同应用间调用问题的定位:
    'You can locate the call problem between different applications by associating another application.',
  暂无匹配: 'No match found',
  右键更多操作: 'Right-click for more actions',
  在节点右键进行更多操作: 'Right-click on the node for more actions',
  指标数据未开启: 'Metric data is not enabled',
  日志数据未开启: 'Log data is not enabled',
  调用链数据未开启: 'Trace data is not enabled',
  性能分析数据未开启: 'Profiling data is not enabled',
  '尚未接入服务{0}': 'Service {0} has not been accessed',
  '数据统计中，请耐心等待': 'Data statistics in progress, please wait patiently',
  'Grafana已经升级到10版本，来看看有哪些功能差异':
    'Grafana has been upgraded to version 10.1. What are the differences in functions?',
  '稍等几分钟后，前往 {0} 查看相关数据': 'Wait a few minutes and go to {0} to view related data',
  移除下钻: 'Remove drill down',
  添加为筛选项: 'Add as filter',
  移除该筛选项: 'Remove this filter',
  查看该对象的其他场景: 'View other scenarios of this object',
  点击加载更多: 'Click to load more',
  '当前空间未开启{0}功能': 'The current space has not enabled the {0} feature',
  '当前告警不支持{0}功能': 'The current alarm does not support the {0} feature',
  '{0}不支持{1}功能': '{0} does not support the {1} feature',
  '当前空间「{0}」 使用了 BCS 集群，已自动关联；':
    'Current space " {0} project " uses BCS cluster, has been automatically associated;',
  '如需精确，用户可 {0}': 'If you need to be accurate, users can {0}',
  移动光标: 'Move the cursor',
  选中: 'Select',
  提交查询: 'Submit query',
  '异常事件 ({0})': 'Exception event ({0})',
  '全部事件 ({0})': 'All events ({0})',
  '确定删除选中的收藏项?': 'Are you sure you want to delete the selected favorite item?',
  '删除后，无法恢复，请谨慎操作!': 'After deletion, it cannot be recovered, please operate carefully!',
  '暂无数据，请输入生成': 'No data, please enter to generate',
  '请输入1~100的数字': 'Please enter a number between 1 and 100',
  服务下其他图表一并生效: 'Other charts under the service will take effect at the same time',
  通过正则提取值作为进程名: 'Extract values through regular expressions as process names',
  如果想区分是worker还是master进程: 'If you want to distinguish between worker and master processes',
  此时应该填写正则: 'At this time, you should fill in the regular expression',
  直接填写名称: 'Directly fill in the name',
  此时默认进程名为: 'At this time, the default process name is',
  可以直接填写: 'You can directly fill in',
  作为进程名: 'as the process name',
  '则进程名为（从cmdline提取）': 'Then the process name is (extracted from cmdline)',
  则匹配结果为: 'Then the matching result is',
  默认取: 'Default to take',
  对应的二进制名称: 'The corresponding binary name.',
  暂无匹配结果: 'No matching results',
  编辑通知对象: 'Edit Notify Target',
  修改通知对象: 'Modify Notify Target',
  通知对象不能为空: 'Notify target cannot be empty',
  暂无选项: 'No options',
  PromQL助手: 'PromQL Helper',
  '指标/PromQL语句': 'Metric/PromQL',
  用户指令: 'User Instruction',
  '请输入指标/PromQL语句': 'Please enter the metric/PromQL statement',
  请输入用户指令: 'Please enter the user instruction',
  请先打开事件分析: 'Please open event analysis first',
  暂无关联的事件数据: 'No related event data',
  '应安全需求，公共拨测节点需经过审核方可使用': 'The public testing nodes must undergo a review process before they can be used, in accordance with security requirements',
  点击申请业务权限: 'Click to apply for business privileges',
  '调试数据范围取当前时间窗口前1000条数据': 'The debugging data range takes the previous 1000 entries from the current time window',
  只有数值类型的字段可作为监控指标: 'Only fields of numeric type can be used as monitoring indicators',

  // 查询模板
  无法删除: 'Cannot delete',
  无法编辑: 'Cannot edit',
  '当前仍然有关联的消费场景，无法编辑':
    'Currently there are still associated consumption scenarios and cannot be edited',
  '当前仍然有关联的消费场景，无法删除':
    'Currently there are still associated consumption scenarios and cannot be deleted',
  全局模板无法删除: 'Global template cannot be deleted',
  全局模板无法编辑: 'Global template cannot be edited',
  '模板属于业务 {0}，无法删除': 'The template belongs to the business {0} and cannot be deleted',
  '模板属于业务 {0}，无法编辑': 'The template belongs to the business {0} and cannot be edited',
  '输入框：直接输入 {0} 即可新建变量': 'Input box: Enter {0} directly to create a new variable',
  '选择框：在选项中选择 {0} 然后输入变量名': 'Select box: Select {0} in the options and then enter the variable name',
  '新建后，右侧会出现 {0}': 'After creating, {0} will appear on the right side',
  '可以定义 {0} {1}': 'You can define {0} {1}',
  '在各消费场景，选择 {0} 后，可填入 {1}': 'In various consumption scenarios, after selecting {0}, you can fill in {1}',
  '仪表盘 Panel 级别的定位，需要一定的时间同步，如有需要请点击':
    'The positioning at the panel level of the dashboard requires a certain amount of time to synchronize. If necessary, please click',
  '应用一般是拥有独立的站点，由多个 Service 共同组成，提供完整的产品功能，拥有独立的软件架构。从技术方面来说应用是 Trace 数据的存储隔离，在同一个应用内的数据将进行统计和观测。{0}': 'An application generally has an independent site, composed of multiple services working together to provide complete product functionalities, with a standalone software architecture. From a technical perspective, an application represents the storage isolation of trace data, where data within the same application will be aggregated and observed.{0}',
  '更多请': 'For more',
  查看产品文档: 'please refer to the product documentation',
  '配置修改保存后，需 5 分钟左右生效': 'After the configuration modification is saved, it will take about 5 minutes to take effect',
};
