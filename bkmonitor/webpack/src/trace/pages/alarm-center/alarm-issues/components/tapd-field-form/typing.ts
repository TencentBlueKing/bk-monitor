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

/**
 * 处理人（current_owner）抄送（cc）
 * 迭代（iteration_id）
 * 标题（title）
 * 描述（description）
 */
export const EditType = {
  treeSelect: 'treeselect',
  tSelect: 'tselect', //
  pinyinUserChooser: 'pinyinuserchooser', // 处理人（current_owner）抄送 字段
  mixChooser: 'mixchooser',
  textarea: 'textarea',
  text: 'text',
} as const;

export interface IField {
  editabled_type: TEditType;
  fieldName?: string;
  formula_field_tip: string;
  id: string;
  options?: { label: string; value: string }[];
  placeholder?: string;
  required?: string;
  /** 字段布局宽度：full 占整行 / half 占半行（两个 half 并排），默认 full */
  span?: 'full' | 'half';
  system_name: string;
  text?: string;
}

export type TEditType = (typeof EditType)[keyof typeof EditType];
