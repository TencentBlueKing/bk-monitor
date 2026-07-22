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
  '/ 快速唤起，请输入': 'Press / to input',
};
