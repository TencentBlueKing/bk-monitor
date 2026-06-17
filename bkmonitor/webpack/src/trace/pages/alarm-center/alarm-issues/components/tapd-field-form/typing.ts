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
/** TAPD 字段编辑类型枚举（与后端 editabled_type 一一对应） */
export const EditType = {
  input: 'input', // 文本输入框
  select: 'select', // 下拉选择器
  userChooser: 'user_chooser', // 用户选择器
  singleUserChooser: 'single_user_chooser', // 单用户选择器
  richEdit: 'rich_edit', // 富文本编辑器
  datetime: 'datetime', // 日期时间选择器
  mixChooser: 'mix_chooser', // 混合选择器
  dateInput: 'dateinput', // 日期输入框
  multiSelect: 'multi_select', // 多选下拉
  integer: 'integer', // 整数输入
  float: 'float', // 浮点数输入
  int: 'int', // 整型输入
  text: 'text', // 文本
  cascadeRadio: 'cascade_radio', // 级联单选
  file: 'file', // 文件上传
  radio: 'radio', // 单选
  cascadeCheckbox: 'cascade_checkbox', // 级联多选
  textarea: 'textarea', // 多行文本
  checkbox: 'checkbox', // 多选
} as const;

export interface IField {
  bk_biz_id: number;
  field_id: string; // 字段 ID（即 TAPD 字段英文名，如 title、owner）
  field_name: string; // 字段中文名（如「标题」「处理人」）
  field_type: TEditType;
  is_core_field: boolean; // 是否核心字段。核心字段不可取消选中、固定必填
  is_required: boolean; // 是否必填。核心字段固定为 true；可选字段由用户在「管理字段」中配置
  is_selected: boolean; // 是否选中展示在创建tapd单据表单中。核心字段固定为 true；可选字段由用户在「管理字段」中勾选
  options?: { id: string; name: string }[];
  tapd_type: string; // 单据类型（bug / story / task）
  template_id: number; // 模板 ID，0 表示不使用模板
  workspace_id: string; // TAPD 项目 ID
}

export type TEditType = (typeof EditType)[keyof typeof EditType];

export const FULL_FIELD_TYPES = [EditType.input, EditType.richEdit] as TEditType[];
