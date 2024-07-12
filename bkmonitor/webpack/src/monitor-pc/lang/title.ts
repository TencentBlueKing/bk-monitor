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
// 标题 相关的词条 tab title, form title, 弹窗 title
export default {
  // 规范：驼峰

  '包括{0}个指标,{1}个维度': 'includes {0} metrics, {1} dimensions',
  '可选图表({num})': 'Optional charts ({num})',
  '标准化事件-字段映射': 'Standardized Event-Field Mapping',
  业务独享集群: 'Exclusive Cluster',
  关联的处理套餐: 'Associated Alarm Solution',
  关联的资源实例: 'Associated Resource Instances',
  删除当前分类: 'Delete current category',
  删除采集任务: 'Delete collection task',
  判断最终是否要产生告警: 'Determine whether to generate an alarm in the end',
  剩下的告警基于当前规则发送通知: 'The remaining alarms send notifications based on the current rules',
  场景智能异常检测: 'Intelligent Anomaly Detection in Scenarios',
  如标准输出: 'Such as Standard Output', // 查看语境
  实例名配置: 'Instance Name Configuration',
  待升级目标: 'Targets to be Upgraded',
  已停用配置: 'Configuration disabled',
  已启用配置: 'Configuration enabled',
  异常采集目标: 'Abnormal collection target',
  所含内容文件: 'Content file included',
  未分组的指标: 'Ungrouped Metrics',
  未分组视图: 'Ungrouped View',
  查询结果统计: 'Query result statistics',
  端口运行状态: 'Port Running Status',
  被选对象将会关闭页面通知: 'The selected object will close the page notification',
  该实例下的错误列表: 'List of errors under this instance',
  远程服务调用次数: 'Remote service call count',
  通过查询的数据按检测规则判断是否需要进行告警:
    'Use the queried data to determine whether an alarm is required according to the detection rules',
  配置与流程指引: 'Configuration and process guide',
  配置升级向导: 'Configuration Upgrade Wizard',
  配置项编辑器: 'Configuration item editor',
  防御的告警: 'Defended Alert',
  概览: 'Summary',
  个人收藏: 'My Favorite',
  存储信息: 'Storage Information',
  集群选择: 'Cluster selection',
  数据采样: 'Data Sampling',
  数据量趋势: 'Data Volume Trend',
  告警策略: 'Alert Rules',
  查询设置: 'Query Settings',
  分享链接: 'Copy Link',
  数据来源: 'Data Source',
  建议字段: 'Suggested Fields',
  最近搜索: 'Recent Searches',
  // 首页
  '配置 Dashboard': 'Dashboard',
  '综合拨测 - 未配置': 'Synthetic Monitoring - Not configured',
  '服务监控 - 未配置': 'Service Monitoring - Not configured',
  '进程监控 - 未配置': 'Process Monitoring - Not configured',
  '主机监控 - 未配置': 'Host Monitoring - Not configured',
  默认显示最近20条: 'The latest 20 items',
  '告警空空，一身轻松': 'No Alarms, Easy Going',
  '告警中，告警数量：{0}': 'Alarming, alarms: {0}',
  业务DEMO: 'Business Demo',
  '服务质量较差，请及时处理': 'The service quality is poor, please handle it in time',
  '未发现有异常运行的进程。': 'No abnormal running processes found.',
  '检测到你对“CPU使用率、应用内容使用量、磁盘利用率”未做全局告警策略配置':
    'It is detected that you have not configured a global alarm rule for "CPU usage, application content usage, and disk utilization"',
  '检测到当前仅配置了1个运营商节点，为了更全面的反应不同网络环境用户的访问质量，建议您接入更多其他类型的网络运营商节点，覆盖更全面。':
    'It is detected that only 1 is currently configured Operator nodes, in order to more comprehensively reflect the access quality of users in different network environments, it is recommended that you access more other types of network operator nodes for more comprehensive coverage. ',
  '创建一个私有或云拨测节点，用于探测服务的质量与可用性':
    'Create a private or cloud dial test node to detect the quality and availability of services',
  AI小鲸发现当前有: 'AI assistant found ',
  '主机智能异常检测发现最近{0}{1}台主机异常':
    'Host intelligent anomaly detection found {0} abnormal hosts in the recent {1}.',
  监控资源概览: 'Monitoring Resource Overview',
  基于告警事件进行屏蔽: 'Mute by Alarms',
  基于策略进行屏蔽: 'Mute by Rules',
  基于维度进行屏蔽: 'Mute by Dimensions',
  基于范围进行屏蔽: 'Mute by Range',
  主机智能异常检测结果: 'Host intelligent abnormal detection results',
  耗时区间: 'Time-consuming interval',
  异常事件: 'Events',
  选择算法: 'Select algorithm',
  算法说明: 'Algorithm Description',
  白名单: 'White List',
  黑名单: 'Black List',
  指标维度设置: 'Metric / Dimension Setting',
  此操作存在危险: 'This operation is dangerous',
  DB设置: 'DB settings',
  DB类型: 'DB type',
  '{0}月': '{0} month',
  轮值规则: 'Rotation Rules',
  轮值详情: 'Details of rotation',
  配置信息: 'Configuration information',
  链路状态: 'Link state',
  字段详情: 'Field details',
  当前暂无告警: 'No warning at this time',
  当前有告警: 'current warning',
  可接收告警: 'Can receive warning',
  总告警: 'General warning',
  近一小时: 'Almost an hour',
  分钟数据量: 'Minute data volume',
  日数据量: 'Daily data volume',
  小时数据量: 'Hour data volume',
  集群状态: 'Cluster status',
  索引状态: 'Index status',
  '主机智能异常检测发现{0}个主机异常': 'Host intelligent exception detection found {0} host exceptions',
  '上传 Profiling': 'Upload Profiling',
  '持续 Profiling': 'Continuous profiling',
  有数据应用: 'Has data applied',
  无数据应用: 'No data applied',
  订阅详情: 'Subscription details',
  '暂未开启 Profiling 功能': 'Profiling is not enabled yet',
  '暂无 Profiling 数据': 'No profiling data yet',
  关闭目标: 'Close target',
  测试执行: 'Test execution',
  配置选择: 'Configuration selection',
  流程指引: 'Process guidance',
  关联设置: 'Related settings',
  URI规则设置: 'URI rule settings',
};
