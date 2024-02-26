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

// Validation Text：验证文本，用于提示用户输入内容是否符合规范，例如“请输入正确的邮箱地址”、“密码长度不能少于6位”等。
export default {
  // 规范：仅首字母大写

  '注意: 必填字段不能为空': 'Waring: Required field cannot be empty.',
  '字段“{key}”必填不能为空': 'The field "{key}" must not be empty', // 看语境
  '{0}的{1}脚本内容不能为空': '{1} script content of {0} cannot be empty', // 看语境

  编辑模式不能切换: 'Cannot switch editing mode',
  动态和静态不能混用: 'Dynamic and Static Cannot be Mixed',
  不能反复执行: 'Cannot execute repeatedly',
  不能进行调试: 'Cannot debug',

  当前不能跨业务批量操作: 'Cannot perform batch operations across businesses',
  '标签名字不能含有分隔符：': 'Tag names cannot contain separators:',
  指标分类不能同名且不能为: 'Metric categories cannot have the same name and cannot be',
  超时时间配置不能大于周期: 'Timeout configuration cannot be greater than cycle',
  显示名不能为空且不能相同: 'Display name cannot be empty and must be unique', // 这两个检验要分开
  '指标分类不能同名且不能为{0}': 'Metric categories cannot have the same name and cannot be {0}',
  正在执行中的配置暂不能升级: 'Configurations in progress cannot be upgraded at the moment',
  '已选群机器人，群ID不能为空': 'Selected group robot, group ID cannot be empty',
  视图标签名不能为空且不能相同: 'View label name cannot be empty and must be unique', // 这两个检验要分开
  '所有的指标/维度的英文名和别名不能重名或为空':
    'All metric/dimension English names and aliases cannot have the same name. Word conflict or empty',
  不能输入emoji表情: 'Can not enter emoji expressions',
  '新建规则不能撤回, 可以删除': 'New rules cannot be withdrawn and can be deleted',

  // 规范： 注意: 最大值为xxx  Warning: The maximum is xxx
  '注意：最大值为6个月': 'Warning: The maximum is 6 months.',
  '注意：最大值为100个字符': 'Warning: The maximum is 100 characters.',
  '注意：最大值为50个字符': 'Warning: The maximum is 50 characters.',
  '注意：最大值为30个字符': 'Warning: The maximum is 30 characters.',
  '注意：最大值为10个字符': 'Warning: The maximum is 10 characters.',
  '注意：最大值为50个字符(10个汉字)': 'Warning: The maximum is 20 characters (10 Chinese).',
  '注意：最大值为90天': 'Warning: The maximum is 90 days.',

  '最大值：{limit}ms': 'Maximum Value: {limit}ms',
  '最大自定义天数为{n}天': 'Maximum custom days is {n} days',
  '最小时间（ms）': 'Min Time (ms)',
  '事件标识名，最大长度128': 'Event identifier name, maximum length 128',
  '文件不能超过{size}MB': 'File cannot exceed {size} MB',
  '文件大小不能超过{num}M！': 'File size cannot exceed {num}M!',
  '提交文件，文件大小不能超过{num}M！': 'Submit the file, the file size cannot exceed {num}M!',
  '长度限制2-32字符': 'Length limit 2-32 characters',
  '最大时间（ms）': 'Max Time (ms)',

  最大副本数不能超过: 'Maximum number of copies cannot exceed', // 查看位置
  最大分片数不能超过: 'Maximum number of shards cannot be exceeded', // 查看位置

  // Warning: The xxx conflict.  中文  注意: xxx冲突
  '注意: 名字冲突': 'Warning: The name conflict.',

  '注意: 优先级冲突': 'Warning: The priority conflict.',
  '注意: 插件冲突': 'Warning: The plugin conflict.',
  '注意: 插件ID冲突': 'Warning: The plugin ID conflict.',
  '冲突： 点击进行转换': 'Conflict: click to convert',

  自定义重复: 'Custom repeat', // 确定词条位置
  必填项: 'Required field',

  检查是否选择数据ID: 'Check whether to select a data ID', // 确定词条位置
  检查是否选择采集ID: 'Check whether to select a collection ID', // 确定词条位置
  '有明确的 ID': 'Has clear TraceID',

  // 规范：仅支持
  '仅支持0-100的数字': 'Only Supports Numbers from 0 to 100',
  仅支持导入: 'Import Only',
  仅支持数字: 'Only supports numbers',
  仅支持整数: 'Only supports integer',
  '插件名称，仅支持以字母开头，仅支持字母、下划线和数字。':
    'plugin name, only supports Start with a letter, only letters, underscores and numbers are supported. ',

  // 规范：不支持
  不支持该协议: 'Protocol not supported',
  不支持查询语句: 'Query statement is not supported',
  '不支持“插件包不完整”的批量导入': 'Bulk import of incomplete plugin packages is not supported',
  '不支持大于、大于等于、小于和小于等于条件':
    'Does not support greater than, greater than or equal to, less than and less than or equal to conditions',
  多指标下不支持cmdb节点维度的聚合: 'Aggregation of CMDB node dimensions is not supported under multiple metrics.',
  多指标暂不支持实时检测: 'Real-time detection is not supported for multiple metrics temporarily',
  '此浏览器不支持全屏操作，请使用chrome浏览器':
    'This browser does not support full screen operations, please use Chrome browser.',
  '当前实时的查询不支持该检测算法，请删除':
    'The current real-time query does not support this detection algorithm, please delete it.',
  源码模式不支持实时检测: 'Source code mode does not support real-time detection', // 确定词条位置
  '不允许包含如下特殊字符：': 'Special characters are not allowed:',
  分片数不能小于1: 'The number of shards cannot be less than 1',
  更新轮值设置时生效时间不能小于当前时间:
    'The effective time for updating the rotation setting cannot be earlier than the current time.',

  // 规范：要求
  '要求: 周期数>=1，且为正整数': 'Requirements: number >=1 and is a positive integer',
  '要求: 周期数>=1，且>=检测数': 'Requirements: Number of cycles>=1, and>=number of tests',
  '要求: 满足次数&lt;=周期数': 'Requirement: number <= cycle number',
  '要求: 触发条件周期数为正整数': 'Requirement: The cycle number is a positive integer',
  '只支持“xlsx”格式的文件': "Only files in the 'xlsx' format are supported",

  // 规范： 至少/必须
  至少填写一条日志路径: 'Please fill in at least one log path',
  至少添加一个通知对象: 'Add at least one notification object',
  每个分组至少设置一个指标并且是启用状态: 'Each group At least one metric must be set and enabled',
  至少选择一种告警等级: 'Select at least one alarm level',
  至少选择一种时间: 'Select at least one time',
  至少选择一种通知方式: 'Select at least one notification method',
  包含至少一个服务的trace: 'Trace containing at least one service',
  每个告警级别至少选择一种通知方式: 'At least one notification method must be selected for each alarm level',
  每个执行阶段至少选择一种通知方式: 'At least one notification method must be selected for each execution stage',
  每个用户组至少需要一个用户: 'Each user group needs at least one user',
  交接时需要至少两个用户组: 'At least two user groups are required during handover',
  关联告警需至少选择2个告警进行管理: 'At least 2 alarms need to be selected for management when associating alarms',
  '创建拨测任务前先要至少有一个拨测节点,拨测节点负责拨测任务的执行.':
    'Before creating a dial test task, there must be at least one dial test node, which is responsible for the execution of the dial test task.',
  '至少填写一条关键字规则，并填写完整': 'At least one keyword rule must be filled in completely',
  '英文缩写必须由小写字母+数字+中划线组成，以小写字母开头，长度限制32字符！':
    'English abbreviations must consist of lowercase letters + numbers + dashes, start with a lowercase letter, and the length is limited to 32 characters ! ',
  必须开启一个采集脚本: 'At least one collection script must be enabled',
  每个告警级别的必须选择一种通知方式: 'One notification method must be selected for each alarm level',
  '开启降噪设置必须设置维度且比例值为1-100之间':
    'Enabling the noise reduction setting must set the dimension and the ratio value is between 1-100',
  多指标维度选择必须是相互包含关系: 'The selection of dimensions for multiple metrics must be mutually inclusive',
  每种默认值类型只能添加一个: 'Only one default value type can be added',
  '监控对象为服务，只能选择动态方式': 'For service monitoring, only dynamic methods can be selected',
  拨测相关指标只能单选: 'Probe-related metrics can only be selected individually',
  只能同时选择同一数据来源下的指标: 'Only metrics from the same data source can be selected simultaneously',
  最少选择一个算法: 'Select at least one algorithm',

  // 规范：无 不存在
  已经没有可用的维度: 'There are no available dimensions',
  指标不存在: 'No metric',
  监控指标不存在: 'Monitoring Metrics Do Not Exist',
  策略所属空间不存在: 'The space to which the rule belongs does not exist',
  'IP格式有误或不存在，检查后重试！': 'IP format is incorrect or does not exist, please check and try again!',
  '变量不存在，请前往编辑套餐': 'Variable does not exist, please go to edit solution',

  多指标的维度需要有包含关系: 'The dimensions of multiple metrics need to have a containment relationship',
  检查右上角的时间范围: 'Check the time range in the upper right corner',
  检查右上角的索时间范围: 'Check the cable time range in the upper right corner',
  检查指标的数据来源是否有数据: 'Check if the data source of the metric has data',
  检查指标的选择是否正确: 'Check if the metric is selected correctly',
  检查查询条件和目标范围是否合理: 'Check whether the query conditions and target range are reasonable',

  检测到你的多个主机监控指标未配置告警策略:
    'It has been detected that you have not configured an alarm rule for multiple host monitoring metrics',
  '当前业务下没有可使用的处理套餐，请前往{0}页面配置':
    'There is no solution available under the current business, please go to the {0} page to configure',
  '退出当前窗口可前往{0}查看结果': 'Exit the current window to view the results on {0}',
  '未选择采集目标，但并不影响本次操作': 'No collection target selected, but it does not affect this operation',
  未选择任何内容: 'No Selection Made',
  未选择监控数据: 'No monitoring data selected',
  已转化成非冲突名字: 'Converted to non-conflicting name',
  '保留名称，不可使用': 'Reserved name, not available',
  该算法已同级别已经存在: 'The algorithm already exists at the severity',
  该规则仅针对重名内容生效: 'This rule only takes effect for content with the same name',
  组合检索注意大写: 'Combined retrieval attention capitalization',
  'SNMP设置指标数量超过{n}，请删减非必要指标':
    'If the number of SNMP setting metrics exceeds {n}, please remove unnecessary metrics.',
  '设置指标数量超过{n}，请删减非必要指标':
    'If the number of metrics set exceeds {n}, please remove unnecessary metrics.',
  'bkmonitorbeat采集器异常或版本过低，请至节点管理处理':
    'The bkmonitorbeat collector is abnormal or the version is too low, please go to the NodeMan to deal with',
  '节点出现异常，请及时排查！': 'Node has an exception, please investigate in a timely manner!',
  '功能依赖1.10.x及以上版本的bkmonitorbeat': 'Function depends on bkmonitorbeat version 1.10.x or higher',
  仅可执行一次: 'Can only be executed once',
  '标签格式不正确,格式为key:value 或 key=value': 'The label format is incorrect, the format is key:value or key=value',
  '超过该时长未正常采集数据时，系统判定该任务为不可用状态！':
    'When the data is not collected normally within this time period, the system judges that the task is unavailable! ',
  '组名不规范, 包含了特殊符号.': 'The group name is irregular and contains special symbols.',
  '缺少URL协议字符，如http://': 'Lack of URL protocol characters, such as http://',
  '分组：{tableName} 别名：{fieldName}重复': 'Grouping: {tableName} Alias: {fieldName} is repeated ',
  '分组：{tableName} 指标名：{fieldName}重复': 'Grouping: {tableName} Index name: {fieldName} Duplicate',
  '分组：{tableName} 第{index}个字段未填写名称': 'Grouping: {tableName} The {index} field is not filled with a name',
  '检测算法填写不完整，请完善后添加': 'Detection algorithm incomplete, please complete before adding',
  '检测到未配置进程/端口监控策略，请尽快配置方能及时的发现风险/故障。':
    'No process/port monitoring rule is detected, please configure it as soon as possible to discover risks/faults in time. ',
  '校验失败，请检查参数': 'Verification failed, please check the parameters',
  '可能存在运行参数变动，请检查并确认运行参数！':
    'There may be changes in operating parameters, please check and confirm the operating parameters! ',
  '插件{name}最新版本{version}可能存在运行参数变动，请检查并确认运行参数！':
    'The latest version {version} of plug-in {name} may have running parameter changes, please check and confirm the running parameters!',
  '插件已变更，请先升级': 'Plugin has been changed, please upgrade first',
  '文本不符合 {type} 格式': 'Text does not conform to {type} format',
  '本次对插件的编辑不影响采集进程，可以跳过调度阶段直接进行保存。':
    'The editing of the plugin does not affect the data collection process, so the scheduling phase can be skipped and saved directly.',
  文件内容不符合规范: 'The file content does not meet the specifications',

  建议检查关键字是否准确: 'Check if the keywords are accurate',

  // 规范：不通过 不符合 不一致
  版本校验不通过: 'Version verification failed',
  监控对象不一致: 'Inconsistent monitoring objects',
  收藏名包含了特殊符号: 'The name contains special symbols.',
  插件包不完整: 'Incomplete plugin package',
  时间格式错误: 'Time format error', // 中文需要调整，正确的格式是什么 , 确定语义位置
  格式错误: 'Format error',
  '字段“{key}”正则匹配错误，正则为：{reg}':
    "The regular expression for field '{key}' is incorrect, the regular expression is: {reg}",
  '分组：{tableName} 字段：{fieldName}填写字段分类错误':
    'Grouping: {tableName} Field: {fieldName} Filled in field classification error',
  '当前有多项{0}存在格式错误，可对指标名称进行统一格式转换':
    'There are format errors in multiple {0}, you can convert the index name to a unified format',
  指标和检测算法的单位类型不一致: 'Inconsistent unit types for metrics and detection algorithms',

  监控目标全部失效: 'All Monitoring Targets are Invalid',
  关联的策略已删除: 'Associated rule has been deleted',
  关联的策略已失效: 'The associated rule has expired',
  结果不准确: 'Inaccurate Results', // 确认位置 语义不明
  问题定位不清晰: 'Unclear Problem Localization', // 确认位置，语义不明
  重名规则: 'Repeat name rules', // 确定词条位置
  未定义: 'Undefined',
  当前未关联任何资源: 'Currently not associated with any resources',
  '未添加检测算法，请添加后再保存': 'No detection algorithm added, please add before saving',
  '您好，订阅邮件模板发送失败，请稍后重试！':
    'Hello, subscription email template sending failed, please try again later!',
  当前采集器版本过低: 'Current collector version is too low',
  '最近10分钟没有获取到数据，请手动测试': 'No data obtained in the last 10 minutes, please test manually',
  '导入的配置有些已经存在监控目标，重新设置会覆盖原来的监控目标，确认覆盖请继续！':
    'Some of the imported configurations already have monitoring targets. Resetting will overwrite the original monitoring targets. Please continue after confirming the coverage! ',
  'IP格式有误或内网IP，检查后重试！': 'IP format is incorrect or intranet network IP, please check and try again!',
  关联告警需选择多个: 'Associated alarm needs to select multiple',
  时间段重叠了: 'Time period overlaps',
  '拨测节点采集器版本低于2.7.3.184时该配置不生效，默认等待响应':
    'This configuration does not take effect when the version of the dial test node collector is lower than 2.7.3.184, and the default is to wait for a response',
  '检查字段类型，不同的字段类型对应的查询语法有差异':
    'Check the field type, different field types have different query syntax',
  '检查查询条件是否完整，是否有报错提示':
    'Check whether the query conditions are complete and whether there is an error prompt',
  已添加该默认值: 'The default value has been added',
  '字段“{key}”请确保大于0': 'Please ensure that field "{key}" is greater than 0',
  '标签格式应为key:value': 'The tag format should be key:value',
  '第{index}个分组未填写字段table_name': 'Field table_name not filled in for group {index}',
  '第{index}个字段未填写名称': 'Name not filled in for the {index} field',
  数值字段范围匹配: 'Numerical field range matching',
  数据获取异常: 'Data acquisition exception',
  标签key值应该保持唯一性: 'The Key Value of Tags Should be Unique',
  模糊检索使用通配符: 'Fuzzy search using wild-card',
  规则名不能为空: 'Rule name cannot be empty',
  匹配规则重复了: 'The matching rule is duplicated',
  '优先级应为 0 - 10000 之间的整数': 'Priority should be an integer between 0 - 10000',
  生效起始时间必填: 'Effective start time is required',
  轮值规则必须添加人员: 'The rotation rule requires adding personnel',
  请选择值班规则: 'Please select the duty rule',
  请输入企业微信群ID: 'Please enter the group ID of enterprise wechat',
  'validate-暂无数据': 'No data available',
  轮值规则必须添加单班时间: 'The rotation rule must add a single shift time',
  轮值规则名称长度不能超过128个字符: 'The length of the rotation rule name cannot exceed 128 characters',
  生效结束时间不能小于生效起始时间: 'The effective end time cannot be less than the effective start time',
  请确保企业微信群ID为32个字符: 'Please ensure that the corporate wechat Group ID is 32 characters',
  生效结束时间不能小于今天: 'The effective end time cannot be less than today',
  通知升级必须填写时间间隔以及用户组: 'Notification upgrade must fill in the time interval and user group',
  通知升级的用户组不能包含第一次接收告警的用户组:
    'The user group notified of the upgrade cannot include the user group that received the alarm for the first time',
  暂不支持设置两个智能算法: 'Setting two intelligent algorithms is currently not supported'
};
