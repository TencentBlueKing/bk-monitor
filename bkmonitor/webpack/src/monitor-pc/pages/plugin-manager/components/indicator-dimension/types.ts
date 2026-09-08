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

/** 全部分组标识 */
export const ALL_LABEL = '__all_label__';
/** 默认分组英文名，与设置指标&维度页保持一致 */
export const GROUP_DEFAULT_NAME = 'group_default';
/** 分组英文名校验 */
export const GROUP_NAME_REGX = /^[_|a-zA-Z][a-zA-Z0-9_]*$/;
/** 提交 saveMetric 时需要剔除的前端态字段 */
export const FRONT_END_FIELD_KEYS = [
  'descReValue',
  'errValue',
  'isCheck',
  'isDel',
  'isFirst',
  'id',
  'reValue',
  'showInput',
  'selection',
  'order',
  'uid',
  'originUid',
  'isNew',
  'error',
];

export type MonitorType = 'dimension' | 'metric';

/** 插件指标/维度字段 */
export interface IPluginField {
  description: string;
  dimensions?: Record<string, any>[];
  id?: string;
  is_active: boolean;
  is_diff_metric?: boolean;
  is_manual?: boolean;
  monitor_type: MonitorType;
  name: string;
  selection?: boolean;
  source_name?: string;
  tag_list?: { field_name: string; [key: string]: any }[];
  type: string;
  uid?: string;
  unit: string;
  value?: Record<string, any>;
  [key: string]: any;
}

/** 插件指标分组（metric_json 项） */
export interface IPluginGroup {
  fields: IPluginField[];
  rule_list: string[];
  table_desc: string;
  table_name: string;
}

/** 保存指标所需的插件元信息 */
export interface IPluginMeta {
  config_version: number;
  edit_allowed?: boolean;
  enable_field_blacklist?: boolean;
  info_version: number;
  plugin_id: string;
  plugin_type: string;
}

/** 扁平化后的字段（带所属分组） */
export interface IFlatField extends IPluginField {
  table_desc: string;
  table_name: string;
  uid: string;
}

/** 批量编辑行 */
export interface IBatchField extends IFlatField {
  error?: string;
  isNew?: boolean;
  originUid?: string;
}

/** 当前选中的分组 */
export interface ISelectedGroup {
  name: string;
}

/** 单位列表项 */
export interface IUnitItem {
  children?: { id: string; name: string }[];
  formats?: { id: string; name: string }[];
  id: string;
  name: string;
}

/** 分组提交参数 */
export interface IGroupSubmitPayload {
  fields?: IPluginField[];
  isEdit: boolean;
  oldName?: string;
  rule_list: string[];
  table_desc: string;
  table_name: string;
}
