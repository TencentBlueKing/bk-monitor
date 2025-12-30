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
export default {
  运算符: 'Operator',
  筛选值: 'Filter Value',
  覆盖当前视图: 'Cover Current View',
  另存为新视图: 'Save As New View',
  '搜索 指标组、指标': 'Search Metric Groups and Metrics',
  指标计算: 'Metric Calculation',
  取消选中: 'Unselect',
  展示统计值: 'Show Statistics',
  高亮峰谷值: 'Highlight Peaks and Valleys',
  共用维度: 'Shared Dimensions',
  '确定 Ctrl + Enter': 'Confirm Ctrl + Enter',
  '1 列': '1 Column',
  其它维度: 'Other Dimensions',
  维度拆解: 'Dimensions Split',
  '关闭时，默认是根据聚合维度，画出多条线；':
    'When closed, it will draw multiple lines based on aggregated dimensions by default.',
  '开启后，根据聚合维度，生成多张图。':
    'When enabled, it will generate multiple charts based on aggregated dimensions.',
  限制: 'Limit',
  '1小时前': '1 Hour Ago',
  '1 月前': '1 Month Ago',
  '(暂未设置常驻筛选，请前往 {0} 设置)': '(No persistent filters set yet. Please go to {0} to set up)',
  '全选：': 'Select All:',
  编辑指标别名: 'Edit Metric Alias',
  '指标名：': 'Metric Name:',
  '指标别名：': 'Metric Alias:',
  最大值: 'MAX',
  最小值: 'MIN',
  平均值: 'AVG',
  最新值: 'Latest',
  累计值: 'Cumulative',
  多维分析: 'Multi-Dimensional Analysis',
  多选: 'Multi-Select',
  波动: 'Fluctuation',
  '搜索 维度': 'Search Dimensions',
  '指标：': 'Metrics:',
  '已选 {0} 个指标': 'Selected {0} Metrics',
  '2 列': '2 Columns',
  '3 列': '3 Columns',
  '确认删除该视图？': 'Confirm Delete This View?',
  '视图名称：': 'View Name:',
  '删除后，不可恢复，请谨慎操作！': 'After deletion, recovery is not possible. Please be cautious!',
  '删除后不可恢复，请谨慎操作。': 'After deletion, recovery is not possible. Please be cautious.',
  '删除后，不可恢复，请确认。': 'After deletion, recovery is not possible. Please confirm.',
  视图名称重复: 'View Name Duplicate',
  维度管理: 'Dimension Management',
  没有选择任务指标: 'No Task Metrics Selected',
  勾选项: 'Check Option',
  自定义指标管理: 'Custom Metric Management',
  '确认关闭？': 'Confirm Closure?',
  自动发现新增指标: 'Auto-Discover New Metrics',
  关联维度: 'Associated Dimensions',
  上报周期: 'Reporting Cycle',
  指标与维度: 'Metrics and Dimensions',
  '启用后，将自动发现新增指标/维度': 'Once enabled, new metrics/dimensions will be automatically discovered.',
  '分组 用于指标归类，建议拥有相同维度的指标归到一个组里。':
    'Grouping: Categorizes metrics. Group those with shared dimensions.',
  '搜索 自定义分组名称': 'Search Custom Group Names',
  批量编辑维度: 'Batch Edit Dimensions',
  批量编辑指标: 'Batch Edit Metrics',
  搜索维度: 'Search Dimensions',
  是否常用: 'Mark as Frequently Used?',
  暂无自定义分组: 'No Custom Groups Yet',
  常用维度: 'Frequently Used Dimensions',
  编辑分组: 'Edit Group',
  '已有规则，请先预览': 'Existing rules. Please preview first.',
  '匹配规则已变更，请重新预览。': 'Matching rules have been updated. Please re-preview.',
  '仅允许包含字母、数字、下划线，且必须以字母开头 ':
    'Only letters, numbers, and underscores allowed. Must start with a letter.',
  暂无匹配到的指标: 'No Matching Metrics Found',
  名称不能为空: 'Name Cannot Be Empty',
  请输入名称: 'Enter a Name',
  名称已存在: 'Name Already Exists',
  '打开后，可以在 [可视化] 的 [过滤条件] 里快速展开：':
    'After opening, you can quickly expand it in [Visualize] > [Filter Conditions]:',
  没有可选维度: 'No Selectable Dimensions',
  没有可聚合维度: 'No Aggregatable Dimensions',
  '展示/隐藏常用条件': 'Show/Hide Common Conditions',
  '关闭后，在可视化视图里，将被隐藏': 'After closing, it will be hidden in the visual view.',
  数据标签: 'Data Label',
  '自定义指标英文名仅允许包含字母、数字、下划线，且必须以字母开头，前缀不可与插件类型重名':
    'The English name of a custom metric can only contain letters, numbers, and underscores, and must start with a letter. The prefix cannot be the same as the plugin type.',
  手动添加: 'Manually add',
  全局: 'Global',
  指标管理: '',
  '确定 Cmd + Enter': '',
  '暂只支持开启，不支持关闭': 'Currently only supports opening, not closing',
  '已开启自动发现新增指标，无法操作': 'Automatic discovery of new metrics has been enabled and cannot be operated',
  清空关键词: 'Clear keywords',
  '显/隐': 'Show/Hide',
  '仅允许包含字母、数字、下划线，且必须以字母开头':
    'Only letters, numbers, and underscores are allowed, and the name must start with a letter',
  无维度数据可下钻: 'No dimension data available for drilling down',
  维度下钻: '',
  编辑范围: 'Edit Range',
  全量: 'Full',
  '新增 "{0}" 维度': 'Added "{0}" dimension',
  '维度（组合）': 'Dimension (Combination)',
  '1天前': '1 day ago',
  '7天前': '7 days ago',
  '30天前': '30 days ago',
  Time: 'Time',
  type: 'Type',
  视图管理: 'View Management',
};
