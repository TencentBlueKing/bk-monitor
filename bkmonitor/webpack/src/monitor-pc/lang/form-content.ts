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
  字符: 'Character',
  截断: 'Truncate',
};
