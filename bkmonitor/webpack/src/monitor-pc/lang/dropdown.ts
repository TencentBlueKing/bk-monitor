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

// Dropdown 下拉列表 相关的词条
export default {
  // 规范： 驼峰
  // 规范：批量表现在按钮上 不体现在下拉选项里
  // 规范：内置下拉项 使用 - - 如 - ALL -

  目标对比: 'Targets',
  指标对比: 'Metrics',
  时间对比: 'Time',
  不对比: '- No -',
  '- 空 -': '- NULL -',
  '- 全部 -': '- ALL -',
  '-我有权限的空间-': '-My Spaces-',
  '-我有告警的空间-': '-Alarming Spaces-',
  '-我有故障的空间-': '-Faulty Spaces-',

  // 告警
  修改告警组: 'Edit Alarm Team',
  修改告警模版: 'Edit Notification Templates',
  修改无数据告警: 'Edit No-Data Alarm',
  修改告警恢复通知: 'Edit Alarm-recovery Notification',
  修改告警风暴开关: 'Edit Alarm-storm',
  修改通知升级: 'Edit Notification Upgrade',
  修改算法: 'Modify Algorithm',
  修改检测规则: 'Modify Detection Rule',
  批量删除策略: 'Delete Rules',
  批量修改状态: 'Edit State',
  批量替换成: 'Bulk Replace',
  批量设置通知升级: 'Bulk Setup Notification Upgrade',
  批量追加标签: 'Append Labels',
  批量调整等级: 'Adjustment Severity',
  修改处理套餐: 'Modify Solution',
  修改恢复条件: 'Modify Recovery Conditions',
  修改触发条件: 'Modify Trigger Conditions',
  修改通知场景: 'Modify Notification Scenario',
  修改通知模板: 'Modify Notification Template',
  修改通知间隔: 'Modify Notification Interval',
  增删目标: 'Add / Delete Targets',
  修改流程套餐: 'Modify Flow Solution',
  批量导入: 'Bulk Import',
  '导入/导出': 'Import / Export',
  '批量启用/停用策略': 'On/Off Rules', // 中文改成 启/停策略  有重复的词条
  '同比（高级）': 'YoY (advanced)',
  '同比（简易）': 'YoY (simple)',
  '环比（简易）': 'MoM (simple)',
  '环比（高级）': 'MoM (advanced)',
  同比振幅: 'YoY Amplitude',
  环比振幅: 'Ring Amplitude',
  同比区间: 'YoY Interval',
  静态阈值: 'Static Threshold',
  简易环比: 'MoM (simple)',
  高级环比: 'MoM (advanced)',
  简易同比: 'YoY (simple)',
  高级同比: 'YoY (advanced)',
  主机重启: 'Host Restart',
  进程端口: 'Process Port',
  时序预测: 'Forecasting',
  离群检测: 'Outlier Detection',
  查看告警策略: 'View Rule',
  修改生效时间段: 'Edit Effective Time Period',
  // 管理端
  '1天': '1 day',
  '7天': '7 days',
  '30天': '30 days',
  'Span 详情': 'Span Detail',
  重置图表: 'Reset Chart',
  '高亮相似 Span': 'Highlight Similar Span',
  '高亮相似 Node': 'Highlight Similar Node',
  复制函数名称: 'Copy Function Name',
  内网IPv4: 'Intranet IPv4',
  外网IPv4: 'Extranet IPv4',
  内网IPv6: 'Intranet IPv6',
  外网IPv6: 'Extranet IPv6',

  日期选择: 'Date selection',
  指定时间: 'Specify time',
  我申请的: 'My Application',
  我的订阅: 'My Subscription',
  基本设置: 'Basic Settings',
  已通知: 'Notified',
  已流控: 'Throttled',
  字段设置: 'Field Settings',
  查看拓扑: 'View Topology',
  总请求数: 'Total Requests',
  总错误数: 'Total Errors',
  平均响应耗时: 'Average Response Time',
  主调: 'Caller',
  被调: 'Callee',

  未恢复告警数: 'Unrecovered Alarm Count',
  '名称 A-Z ': 'Name A-Z',
  节点层级: 'Node Level',
  监控数据项: 'Monitor Data Item',
  腾讯云指标采集插件: 'Tencent Cloud Metric Plugin',
  主调错误率: 'Caller Error Rate',
  被调错误率: 'Callee Error Rate',
  性能: 'Performance',
  网络: 'Network',
  存储: 'Storage',
  容量: 'Capacity',
  成本: 'Cost',
  '生成 “{0}” 选项': 'Generate "{0}" Options',
  '直接输入 "{0}"': 'Enter "{0}"',
  新开标签页: 'Open in New Tab',
  另存为新收藏: 'Save as New Favorite',
  覆盖当前收藏: 'Override Current Favorite',
  存在: 'Exists',
  大于: 'Greater than',
  小于: 'Less than',
  大于或等于: 'Greater than or equal to',
  小于或等于: 'Less than or equal to',
  两个参数都: 'Both parameters',
  一个或多个参数: 'One or more parameters',
  全文检索: 'Full-text Search',
  全部来源: 'All Sources',
  分享: 'Share',
  从分组中移除: 'Remove from Group',
  分派给我的: 'Assigned to Me',
  通知给我: 'Notify Me',
  自定义时间: 'Custom time',
};
