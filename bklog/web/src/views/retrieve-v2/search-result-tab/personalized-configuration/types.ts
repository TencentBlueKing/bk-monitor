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

/* eslint-disable no-unused-vars */

/**
 * 个性化设置tab枚举
 */
export enum TabType {
  LOG_LEVEL = 'log_level', // 日志分级展示
  LOG_KEYWORD = 'log_keyword', // 日志关键词设置
  LOG_METRIC = 'log_metric', // 日志转指标
}

/**
 * 匹配类型枚举
 * 字段匹配 vs 正则匹配
 */
export enum MatchType {
  FIELD = 'field', // 字段匹配
  REGEX = 'regex', // 正则匹配
}

/**
 * 执行动作枚举
 * 标记、跳转、关联
 */
export enum ActionType {
  MARK = 'mark', // 标记
  JUMP = 'jump', // 跳转
  RELATED = 'related', // 关联
}

/**
 * 关联资源枚举
 * 可关联的不同资源类型
 */
export enum RelatedResource {
  HOST = 'host', // 主机
  CONTAINER = 'container', // 容器
  APM = 'apm', // APM
  TRACE = 'trace', // Trace
  CODE = 'code', // Code
}

/**
 * 关联配置接口
 * 应用实例和服务实例配置
 */
export interface RelatedConfig {
  appInstance: string; // 应用实例
  serviceInstance: string; // 服务实例
}

/**
 * 表单数据接口
 * 日志关键字设置的完整表单数据结构
 */
export interface FormData {
  taskName: string; // 任务名称
  matchType: MatchType; // 匹配类型
  selectField: string; // 选择字段
  regex: string; // 正则表达式
  actionType: ActionType; // 执行动作
  tagName: string; // tag名称
  color: string; // 颜色
  jumpLink: string; // 跳转链接
  relatedResource: RelatedResource; // 关联资源
  relatedConfig: RelatedConfig; // 关联配置
}

/**
 * 日志关键词设置表格数据行接口
 * 用于日志关键词设置表格显示的数据结构
 */
export interface LogKeywordTableRow {
  taskName: string; // 任务名称
  regex: string; // 正则表达式
  type: string; // 类型
  creator: string; // 创建人
  jumpLink: string; // 跳转链接
}

/**
 * 日志转指标表格数据行接口
 * 用于日志转指标表格显示的数据结构
 */
export interface LogMetricTableRow {
  metricName: string; // 指标名称
  alias: string; // 别名
  metricType: string; // 指标类型
  creator: string; // 创建人
  consumptionScenario: number; // 消费场景
}
