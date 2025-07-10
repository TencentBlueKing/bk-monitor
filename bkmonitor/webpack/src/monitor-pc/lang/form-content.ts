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

// 表单内容相关的词条
export default {
  // 规范：仅首字母大写
  // 规范：占位使用整条

  数据抓取限时: 'Data capture time limit',
  '{0}满足下列条件时触发告警': 'Trigger an alarm when {0} meets the following conditions',
  '{count}次被屏蔽': '{count} muted',
  '{count}次部分失败': '{count} Partial Failures',
  '变量为“${host}”': 'The variable is "${host}"',
  '基于维度{0},当前策略异常告警达到比例{1}%才进行发送通知。':
    'Based on dimension {0}, notifications are sent only when the proportion of abnormal alarms in the current rule reaches {1}%. ',
  '当{0}分钟内执行{1}次时，防御动作{2}': 'When executed {1} times within {0} minutes, defense action {2}',
  '当首次异常时间超过{0}分钟时不执行该套餐': 'Do not execute this plan if the first abnormal time exceeds {0} minute',
  只能填写大于0的值: 'Only values greater than 0 can be filled in',
  '较前{0}个时间点的{1}{2}时触发告警': 'The alarm is triggered at {1}{2} earlier than {0} time points',
  '较前{0}天同一时刻绝对值的{1}{2}时触发告警':
    'The alarm is triggered when the absolute value is {1}{2} higher than the same time on the previous {0} day.',
  CMDB中定义的字段名: 'Field Name Defined in CMDB',
  PID文件: 'PID file',
  Ping不可达算法: 'Ping Unreachable Algorithm',
  当前工作安排较多: 'There are many current work arrangements', // 确定位置
  不在职责范围内: 'Not Within the Scope of Responsibility',
  启用后可在监控策略中配置此类告警: 'After enabling, this type of alarm can be configured in monitoring rules',
  固定N分钟间隔进行通知: 'Fixed notification interval of N minutes',
  开始指标数据采集: 'The metric data collection starts',
  此事项为不工作时间事项: 'This is a non-working time item',
  策略配置文件: 'Alert rule files',
  自动关联插件文件: 'Automatically Associate Plugin Files',
  自动关联采集配置文件: 'Automatically associate collection configuration files',
  连接字符串: 'Connection String',
  隐藏高级选项: 'Hide Advanced Options', // 查看位置，需要明确
  全部: 'All',
  置顶: 'Pin',
  修改监控目标: 'Change Scope',
  有更新: 'Updated',
  更多: 'More',
  清除所有: 'Clear all',
  复制所有: 'Copy all',
  仅本人: 'Private',
  执行成功: 'Hand successful',
  执行失败: 'Hand failed',
  执行前: 'Start hand',
  生效: 'Available',
  告警恢复中: 'Alarm recovery in progress',
  告警流控: 'Alarm flow control',
  事件忽略: 'Ignore related event',
  套餐: 'Package',

  // "[功能名称] (enable)"
  是否开启通知: 'Notify (enable)',
  是否周期回调: 'Periodic Callback (enable)',
  支持远程采集: 'Remote Collection',
  当前业务可见: 'Current service visibility',
  多业务选择: 'Multi-service selection',
  按业务属性选择: 'Select by service attribute',
  资源类别: 'Resource class',
  '{0}当数据连续丢失{1}个周期时，触发告警通知基于以下维度{2}进行判断，告警级别{3}':
    '{0} When data is lost for {1} consecutive periods, an alarm notification is triggered based on the following dimensions {2}, alarm severity {3}',
  '{0}当数据连续丢失{1}个周期时，触发告警通知，告警级别{2}':
    '{0} When data is lost for {1} consecutive periods, an alarm notification is triggered. Alarm severity {2}',

  轮值: 'Rotation',
  内部通知对象: 'notify object',
  群机器人: 'Group robots',
  同比策略: 'YoY Strategy',
  环比策略: 'MoM Strategy',
  预测下界: 'lower',
  阈值: 'threshold',
  简易: 'Simple',
  高级: 'Advanced',
  振幅: 'Amplitude',
  区间: 'Range',
  蓝鲸信息流: 'Bkchat',
  '查看{0}条数据': 'View data in {0} bar',
  查看指定数据: 'View specified data',
  '已选择{0}个静态主机': '{0} static hosts selected',
  '已动态选择{0}个节点': '{0} nodes have been dynamically selected',
  '已选择{0}个服务模板': '{0} service templates selected',
  '已选择{0}个集群模板': '{0} cluster templates selected',
  '日志文件为绝对路径，可使用通配符': 'The log file is an absolute path, wildcards can be used',
  '如何开启持续 Profiling ，请查看 {0}': 'How to enable continuous profiling, please see {0}',
  '更多功能，请前往 {0}': 'For more features, please go to {0}',
  固定值班: 'Fixed Duty',
  交替轮值: 'Alternate Shifts',
  日常值班: 'Daily Duty',
  '近{0}天的排班结果': 'The result of scheduling for nearly {0} days',
  '值班开始前{0}天收到通知': 'Received notice {0} days before shift start',
  至: 'to',
  人: 'People',
  未来: 'Next',
  已停止: 'Stop',
  已上传: 'Uploaded',
  已解析: 'Parsed',
  已存储: 'Stored',
  存储失败: 'Storage Failed',
  解析成功: 'Parsed Successfully',
  包名称: 'Package name',
  业务名称: 'Business name',
  业务ID: 'Business ID',
  消息内容: 'Message content',
  根因: 'Root cause',
  敏感信息: 'Sensitive data',
  // 故障
  '生成故障，包含{alert_count}个告警，故障负责人：{assignees}':
    'Generated incident, contains {alert_count} alarms, incident person in charge: {assignees}',
  '故障观察中，剩余观察时间{last_minutes}分钟':
    'Incident under observation, remaining observation time: {last_minutes} minutes',
  '故障通知已发送（接收人：{receivers}）': 'Incident notification sent (recipients: {receivers})',
  故障已恢复: 'Incident restored',
  '故障{merged_incident_name}被合并入当前故障': 'Incident {merged_incident_name} merged into the current incident',
  '{operator}故障属性{incident_key_alias}: 从{from_value}被修改为{to_value}':
    '{operator} incident attribute {incident_key_alias}: changed from {from_value} to {to_value}',
  '检测到新告警（{alert_name}）': 'New alarm detected ({alert_name})',
  '告警通知已发送（{alert_name}；接收人：{receivers}）':
    'The notification has been sent (alert name: {alert_name}; receivers: {receivers})',
  '告警已收敛（{alert_name}，共包含{converged_count}个关联的告警事件）':
    'Alarm converged ({alert_name}), contains {converged_count} related alarm events',
  '反馈根因：{feedback_incident_root}': 'Feedback root cause: {feedback_incident_root}',
  故障已关闭: 'Incident closed',
  '告警已确认（{alert_name}）': 'Alarm acknowledged ({alert_name})',
  '告警已屏蔽（{alert_name}）': 'Alarm muted ({alert_name})',
  '告警已被手动处理（{alert_name}）': 'Alarm manually handled ({alert_name})',
  '告警已被关闭（{alert_name}）': 'Alarm closed ({alert_name})',
  '告警已分派（{alert_name}；处理人：{handlers}）': 'Alarm dispatched ({alert_name}; handlers: {handlers})',
  '故障聚集在{0}，影响{1}': 'Incident aggregated at {0}, affecting {1}',
  字符: 'Character',
  截断: 'Truncate',
  '按 {0} 聚合': 'Aggregate by {0}',
  '告警已失效（{alert_name}）': ' Alarm expired ({alert_name})',
  '告警已恢复（{alert_name}）': 'Alarm restored ({alert_name})',
  '告警已收敛（共包含{converged_count}个关联的告警事件）':
    'Alarm converged (contains {converged_count} related alarm events)',
  '一键拉群（{group_name}）': 'One-click group ({group_name})',
  '错误率 < 10%': 'Error rate < 10%',
  '错误率 ≥ 10%': 'Error rate ≥ 10%',
  '请求数 0~200': 'Requests 0~200',
  '请求数 200~1k': 'Requests 200~1k',
  '请求数 1k 以上': 'Requests > 1k',
  'P99 耗时': 'P99 time',
  'P95 耗时': 'P95 time',
  请求量少: 'Fewer requests',
  请求量多: 'More requests',
  可疑程度: 'Suspicious degree',
  诊断分析: 'Diagnosis analysis',
  故障总结: 'Incident summary',
  告警异常维度分析: 'Alarm abnormal dimension analysis',
  '故障关联的告警，统计出最异常的维度（组合）：':
    'Alarms related to the fault, statistics are the most abnormal dimension (combination):',
};
