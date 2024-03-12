/* eslint-disable codecc/comment-ratio */
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
export default {
  /*
   #### 常用简短

 - Empty Text：空数据文本，用于描述数据为空的情况，例如“暂无数据”等。
 - Search Text：搜索文本，用于描述搜索框的作用，例如“请输入关键词”等。
 - Progress Text：进度文本，用于描述正在进行的操作的进度状态，例如“上传中，请稍候”等。
 - Tooltip：鼠标悬停在某个元素上时显示的文本提示，例如图标、按钮等。
 - Placeholder：输入框中的提示文本，例如“请输入您的用户名”、“请输入您的密码”等。
 - Validation Text：验证文本，用于提示用户输入内容是否符合规范，例如“请输入正确的邮箱地址”、“密码长度不能少于6位”等。
 - Pagination Text：分页文本，用于描述当前页数和总页数等信息，例如“第 1 页 / 共 10 页”等。
 */

  //  - Pagination Text：分页文本，用于描述当前页数和总页数等信息，例如“第 1 页 / 共 10 页”等。
  ' {num} 个': '{0}',
  ' {0} 次': '{0} times',
  ' {n} 秒': '{n} seconds',
  ' {n} 天': '{n} days',
  '每 {0} 天': 'Every {0} days',
  '第 {0} 组': 'Group {0}',
  '每 {0} 年': 'Every {0} years',
  '每 {0} 周': 'Every {0} weeks',
  '每 {0} 月': 'Every {0} months',
  ' {0} 周前': '{0} weeks ago',
  '（共100条）': ' (Total 100)',
  '（已确认）': ' (Confirmed)',
  '（已屏蔽）': ' (Muted)',
  '（已修改）': ' (Modified)',
  '（已删除）': ' (Deleted)',
  '（已停用）': ' (Disabled)',
  '（当前值）': ' (Value) ',
  '（查询项）': ' (Query Item)',
  '（表达式）': ' (Expression)',
  '（已抑制）': ' (Suppressed)',
  '（已创建节点）': '(Node created)',
  '# 告警确认 # ': '# Alert Confirmation # ',
  '# 告警通知 # ': '# Alert Notification # ',
  '# 告警触发 # ': '# Alert Triggered # ',
  '# 告警收敛 # ': '# Alert Convergence # ',
  '# 告警恢复 # ': '# Alert Recovered # ',
  '# 告警关闭 # ': '# Alarm Closed # ',
  '第 {n} 次': ' {n} ',
  '更新于 {0} ': 'Last updated {0} ',
  '{0}次成功': ' successes: {0} ',
  '{0}次失败': ' failures: {0} ',
  '{0}台主机': ' hosts: {0} ',
  '{0}个实例': ' instances: {0} ',
  '已选{0}个{1}': 'Selected {0}/{1}',
  '{0}等主机': '{0} hosts', // 这个位置占位不对，需要覆盖整个有提示语。
  '{0}个成功': ' successes: {0}',
  '{0}个失败': ' failed: {0}',
  '{0}个导入中': 'Importing: {0}',
  '已选{0}项': 'Selected {0} Items',
  '展开 1 层': 'Expand 1 Layer',
  '收起 1 层': 'Collapse 1 Layer',
  '{0} 于 {1} 更新': '{0} updated at {1}',
  '{0} 于 {1} 创建': '{0} created at {1}',
  '协议（必填）': 'Protocol (Required)',
  '{0}个执行中': '{0} running',
  '检查{0}情况': ' checked: {0}',
  '( 公共插件 )': ' (Public)',
  '(共{0}台主机)': ' ({0} hosts)',
  '{0}版本低于{1}': '{0} version is lower than {1}',
  '已选【{0}-{1}】指标': 'Selected [{0}-{1}] metrics',
  '{0}个指标，{1}个维度': '{0} metric(s), {1} Dimension(s)',
  '命中{0}条': 'hit: {0}',
  '{0}次部分失败': 'failed(partial): {0}',
  '可{0}完整查看': 'View fully {0}', // 查看语境
  '{0}个拓扑节点': '{0} topology nodes',
  '{0}个服务模板': '{0} service templates',
  '{0}个集群模板': '{0} set templates',
  '指标值,数值 ； ': 'Metric value, Numeric;',
  '失败{0}台主机': 'hosts(failed: {0})',
  '失败{0}个实例': 'instances(failed: {0})',
  '关于{0}的描述': 'Description about {0}',
  '可以尝试{0}或{1}': 'You can try {0} or {1}',
  '最大{max}个': 'Max {max}',
  '最大{max}天': 'Max {max} Days',
  '触发次数(近 7 天)': 'Trigger times (last 7 days)',
  '剩余 {n} 条数据': 'Remaining {n} pieces of data',
  '已设置 {0} 个策略': 'Already Set {0} Strategy',
  '从 {0} 至 {1}': 'From {0} to {1}',
  '有{n}个关联的策略': '{n} associated rules',
  '已选{count}个': 'selected: {count}',
  '{count}次失败': ' failures: {count}',
  '{count}次成功': ' successes: {count}',
  '共 {0} 个': 'Total {0}',
  '共 {num} 条': 'Total {num}',
  '共计{0}项': 'Total {0} ',
  '共{0}台主机': 'hosts: {0}',
  '共{0}个实例': ' instances: {0}',
  '共{0}个收藏': ' favorites: {0} ',
  '共成功{0}了{1}台主机': 'Successfully completed {0} for {1} hosts',
  '共成功{0}了{1}个实例': 'A total of {0} instances were successfully {1}',
  '共{0}个指标，{1}个维度': 'A total of {0} metrics, {1} dimensions',
  '共{0}条': 'total: {0}',
  '共成功{type}了': 'Successfully completed {type}', // 看语境
  '共 {slot0} 个维度': 'Dimensions: {slot0}  ',
  '共 {slot0} 个指标': 'Metrics: {slot0} ',
  '{slot0} 个维度': 'Dimensions: {slot0}  ',
  '{slot0} 个指标': 'Metrics: {slot0} ',
  '共成功{0}了{1}个节点内的{2}台主机': 'Successfully completed {0} on {2} hosts in {1} nodes', // 看语境
  '共成功{0}了{1}个节点内的{2}个实例': 'Successfully {0} {2} instances in {1} nodes', // 看语境
  '共产生{count}个高危告警': 'high-risk alarms : {count}',
  '共产生{0}个高危告警和{1}个其他告警': 'high-risk alarms : {0}, other alarm : {1}',
  '已选择 {n}': 'selected {n}',
  '已选择{0}个策略': '{0} rules selected',
  '已选择 {n} 个主机': 'Selected {n} hosts',
  '已选择{count}条': 'Selected {count} Items',
  '当前已选择{0}条数据': 'Currently selected {0} pieces of data',
  '第{step}步，共{total}步': 'Step {step} of {total}',
  已经选择了: 'Selected',
  '{0} 个指标': '{0} Metrics',
  '{0} 个维度': '{0} Dimensions',
  '{0} 个检测成功': '{0} Detection successful',
  '{0} 个检测失败': '{0} Detection failed',
  '{num} 个': '{num}',
  '查询结果(找到 {0} 条，用时 {1} 毫秒)，将搜索条件 {2}{3}':
    'Query results (found {0} , cost {1} milliseconds), add search criteria {2}{3}',
  '成功复制{0}个IP': 'Successfully Copied {0} IPs',
  '您一共选择了{0}条告警': 'You have selected a total of {0} alarms',
  '已停用{0}个节点内的{1}台主机': '{1} hosts in {0} nodes have been disabled',
  '已经选择了{0}个告警事件,将通过企业微信将相关人员邀请到一个群里面进行讨论':
    '{0} alarms have been selected For events, relevant personnel will be invited to a group for discussion through corporate WeChat',
  '已经选择了{0}告警事件,将通过企业微信将相关人员邀请到一个群里面进行讨论':
    'Already selected {0} alarm event, and relevant personnel will be invited to a group for discussion through corporate WeChat',
  '已设置{0}个条件': '{0} conditions have been set',
  '已隐藏{count}项': 'Hidden {count} items',
  '当前有 {0} 个未恢复告警的通知人是空的': 'There are currently {0} empty notifiers for active alarms',
  '当前有{0}个告警事件': 'There are {0} alarm events currently',
  '当前有{n}个已屏蔽事件': 'There are {n} events currently muted',
  '当前有{n}个未恢复事件': 'There are {n} active events',
  '当执行{0}分钟 未结束按失败处理': 'If not completed after {0} minutes, consider it a failure',
  '当执行{0}分钟未结束按失败处理。': 'If not completed after {0} minutes, consider it a failure.',
  '当前空间 ( [{0}] {1} )下总共有未恢复告警{1}条':
    'There are a total of {1} active alarms in the current space ([{0}] {1})',
  '当前空间下总共有未恢复告警{0}条': 'There are a total of {0} active alarms in this space',
  '找到 {count} 条结果 , 耗时  {time} ms': 'Found {count} results, cost {time} ms',
  '{0}台主机Agent异常': '{0} agents abnormal',
  '已勾选{count}个': '{count} checked',
  '监控的数据主体、查询方式': 'Data subject and query method to be monitored',
  已选择更低级告警级别: 'A lower alarm level is selected',
  '针对 综合拨测、APM、主机、K8s 等场景，提供该场景定制化的异常发现和告警功能':
    'For scenarios such as comprehensive dialing, APM, host, and K8s, it provides customized exception discovery and alarm functions',
  '以 主机 场景为例，将会对指定的主机下的 CPU使用率、网卡入流量、物理内存空闲 等多个关键指标进行智能异常检测，如果检出多个指标异常，将以发生异常的主机为单位生成告警':
    'Taking the host scenario as an example, intelligent anomaly detection is performed on key indicators such as CPU Usage, NIC Traffic, and Physical Memory Idle under the specified host(s). If multiple metric anomalies are detected, an alarm is generated on a per-host basis for the host where the exception occurred',
  '该数据是internal类型，没有对应的观测场景。':
    'The data is of internal type, and there is no corresponding observation scenario.',
  '你当前暂无 {0} 业务权限': 'You currently do not have {0} business authority',
  可以按照以下方式进行申请: 'You can apply in the following ways',
  '推荐加入该业务的用户组，查询': 'Recommended user groups to join the service, query',
  '{0} 用户组': 'User Group {0}',
  '找不到相应用户组时，请联系管理员：':
    'If you cannot find the corresponding user group, please contact the administrator:',
  权限申请文档: 'Permission Application Document',
  均值: 'Avg',
  瞬间值: 'Last',
  '来源：{0}': 'Source: {0}',
  内部通知人: 'Internal Notifier',
  '支持{0}等文件格式': 'File formats such as {0} are supported',
  通知人员类型: 'Notification person type',
  到底了: 'In the end'
};
