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
// trace 应用 中英文对照
export default {
  '快捷键 / ，可直接输入': 'Press / to input',
  返回新版: 'Back to new version',
  最小耗时: 'Min Duration',
  容器: 'Container',
  调用次数: 'Call Count',
  跨应用追踪: 'Cross-application tracing',
  最大耗时: 'Max Duration',
  已读: 'Read',
  'Trace 助手': 'Trace Helper',
  请输入应用名称: 'Please enter the application name',
  /** RUM 列表（设计稿文案） */
  '搜索 应用名称（域名）、应用别名、接入状态、应用状态、创建人、最近更新人':
    'Search application name (domain), alias, access status, application status, creator, last updater',
  'LCP P75': 'LCP P75',
  'JS 错误率': 'JS error rate',
  'API 失败率': 'API failure rate',
  /** RUM 创建应用 */
  应用名称已存在: 'Application name already exists',
  应用别名不能为空: 'Application alias is required',
  '应用将创建在当前业务 「蓝鲸」 下，创建后进入 SDK 接入引导':
    'The application will be created under the current business "BlueKing". After creation, you will be guided to access the SDK.',
  '作为唯一标识，创建后不可修改': 'Used as a unique identifier, cannot be modified after creation',
  '请输入可用于识别的别名，可随时修改': 'Please enter an alias for identification, can be modified at any time',
  应用类型: 'Application Type',
  'Web 应用': 'Web Application',
  'PC/移动端网页': 'PC / Mobile Web Page',
  当前仅支持: 'Currently only supports',
  应用描述: 'Application Description',
  创建并进入下一步: 'Create and Proceed',
  /** RUM SDK 上报 */
  '选择 SDK 协议': 'Select SDK Protocol',
  '不同协议的数据格式和上报联路有所差异，请根据技术栈选择':
    'Data format and reporting path vary by protocol. Please select based on your tech stack.',
  选择安装方式: 'Select Installation Method',
  'SDK 上报': 'SDK Reporting',
  '应用创建成功，请根据指引完成上报':
    'Application created successfully. Please follow the guide to complete reporting.',
  检测数据上报: 'Detect Data Reporting',
  '跳过，稍后接入': 'Skip, Access Later',
  重新检测上报: 'Recheck and report again',
  /** RUM SDK 协议 */
  'OT 协议': 'OT Protocol',
  'Aegis 协议': 'Aegis Protocol',
  Aegis: 'Aegis',
  蓝鲸原生: 'BlueKing Native',
  标准格式: 'Standard Format',
  生态兼容: 'Ecosystem Compatible',
  'Trace 关联': 'Trace Correlation',
  '遵循 OpenTelemetry 标准，数据通过 OTLP 格式上报，兼容可观测平台生态，适合已有 OTel 基础设施的团队。':
    'Compliant with OpenTelemetry standard, data is reported via OTLP format, compatible with observability platform ecosystem, suitable for teams with existing OTel infrastructure.',
  轻量接入: 'Lightweight Integration',
  深度优化: 'Deep Optimization',
  配置简单: 'Simple Configuration',
  '蓝鲸监控原生上报协议，接入成本低，数据结构针对 RUM 场景深度优化，适合新项目快速接入':
    'BlueKing monitoring native reporting protocol, low integration cost, data structure deeply optimized for RUM scenarios, suitable for new projects to quickly integrate.',
  总计: 'Total',
  '稍等几分钟后，前往{0}查看相关数据': 'Please wait for a few minutes, then go to {0} to view the related data',
  应用名称不能为空: 'Application name is required',

  // 创建tapd
  单据字段: 'Ticket Field',
  必填项不能为空: 'Required field cannot be empty',
  项目: 'Project',
  'TAPD 单据': 'TAPD Ticket',
  名称变更: 'Name Change',
  需求: 'Story',
  缺陷: 'Bug',
  解除授权: 'Revoke Authorization',
  确认创建: 'Confirm Create',
  项目必填: 'Project is required',
  单据类型必填: 'Ticket Type is required',
  同步单据状态: 'Sync Ticket Status',
  选择单据: 'Select Ticket',
  选择已有单据: 'Select Existing Ticket',
  请选择单据: 'Please select a ticket',
  关联单据: 'Relate Ticket',
  关联已有单据: 'Relate Existing Ticket',
  状态不同步: 'Status is not synced',
  状态同步: 'Status Synced',
  '/ 唤起，输入检索内容': 'Press / to input',
  原始字段: 'Original Field',
  类型选择: 'Type Select',
  'Profiling 检索仅支持标签等值过滤': 'Profiling only supports exact label filters',
  主动采集: 'Active Collection',
  同一标签的检索条件存在冲突: 'Conflicting conditions for the same label',
  '导出当前视图 PNG': 'Export current view as PNG',
  应用服务: 'Application Services',
  '应用服务加载失败，请重试': 'Failed to load application services. Please retry.',
  搜索函数名: 'Search function names',
  收藏配置无效: 'Invalid favorite configuration',
  未设置筛选条件: 'No filters configured',
  放大: 'Zoom in',
  '数据加载失败，请重试': 'Failed to load data. Please retry.',
  文件分析: 'File Analysis',
  文件详情: 'File Details',
  '上传 Profiling 文件': 'Upload Profiling Files',
  '将文件拖到此处，或': 'Drag files here, or',
  '支持 pprof、perf_script 格式': 'Supports pprof and perf_script formats',
  '单个文件不超过 50 MB，支持批量上传': 'Up to 50 MB per file. Multiple files supported.',
  等待上传结果: 'Waiting for upload confirmation',
  上传中: 'Uploading',
  '上传完成后自动关闭窗口，解析进度可在文件列表中查看。':
    'This window closes when uploads complete. View parsing progress in the file list.',
  关闭窗口将取消未完成的上传: 'Closing this window cancels unfinished uploads',
  取消上传并关闭: 'Cancel Uploads and Close',
  选择文件: 'Select File',
  原文件名: 'Original File Name',
  重新上传: 'Upload Again',
  '文件大小不能超过 50 MB': 'File size cannot exceed 50 MB',
  '文件时间范围无效，请重新上传': 'Invalid file time range. Please upload the file again.',
  '文件不存在或已过期，请重新选择或上传':
    'The file is missing or has expired. Please select another file or upload again.',
  '文件列表加载失败，请重试': 'Failed to load files. Please retry.',
  '文件解析失败，请重新上传': 'Failed to parse the file. Please upload it again.',
  暂无可用的数据类型: 'No data types available',
  正在加载文件分析: 'Loading file analysis',
  '暂无 Profiling 文件': 'No profiling files yet',
  '上传文件，开始 Profiling 分析': 'Upload a file to start profiling analysis',
  '通过火焰图和函数列表，定位耗时热点与调用关系':
    'Explore flame graphs and function lists to identify performance hotspots and call relationships',
  '上传后自动解析，完成后即可查看分析结果':
    'Files are parsed automatically after upload. Results appear when parsing completes.',
  '当前服务暂无 Profiling 数据': 'No profiling data for this service yet',
  暂无可分析的应用服务: 'No application services available for analysis',
  '接入 Profiling 并上报数据后，即可分析服务的性能热点':
    'Enable profiling and report data to analyze service performance hotspots',
  '也可以上传本地文件，无需接入应用即可开始分析':
    'You can also upload a local file and start analysis without integrating an application',
  选择应用服务: 'Select Application Service',
  查看接入指引: 'View Integration Guide',
  分析本地文件: 'Analyze Local Files',
  '已上报数据？刷新列表': 'Already reporting data? Refresh the list',
  '上传 pprof 或 perf_script 文件，查看函数耗时与调用关系':
    'Upload a pprof or perf_script file to explore function timings and call relationships',
  文件解析中: 'Parsing file',
  '解析完成后自动展示分析结果，也可在上方选择其他文件':
    'Results will appear automatically after parsing. You can also select another file above.',
  文件分析暂不可用: 'File analysis is temporarily unavailable',
  '可在文件详情中查看失败原因，或重新上传文件': 'View the failure reason in file details, or upload the file again',
  '请选择其他文件，或重新上传后分析': 'Select another file or upload again to start analysis',
  未找到匹配的数据: 'No matching data found',
  请调整时间范围或检索条件后重试: 'Adjust the time range or filters and try again',
  显示开头: 'Show beginning',
  显示结尾: 'Show ending',
  '暂无 Profiling 数据，请选择已上报数据的应用服务':
    'No profiling data. Select an application service with reported data.',
  查询参数无效: 'Invalid query parameters',
  '标签值加载失败，请重试': 'Failed to load label values. Please retry.',
  '标签加载失败，请重试': 'Failed to load labels. Please retry.',
  检索条件不完整或包含保留字段: 'Incomplete filters or reserved fields',
  请选择应用服务: 'Select an application service',
  请选择有效的时间范围: 'Select a valid time range',
  请选择查询条件: 'Select filter conditions',
  '调用图加载失败，请重试': 'Failed to load the call graph. Please retry.',
  '趋势加载失败，请重试': 'Failed to load trends. Please retry.',
  '选择的应用服务不存在，请重新选择': 'The selected application service does not exist. Please select another.',
  条件对比: 'Condition Comparison',
  差异图例: 'Difference legend',
  复制函数名: 'Copy function name',
  高亮相似堆栈: 'Highlight similar stacks',
  重置视图: 'Reset view',
};
