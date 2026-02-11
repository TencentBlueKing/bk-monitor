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

export enum EClickMenuType {
  Copy = 'copy',
  Exclude = 'exclude',
  ExcludeLink = 'excludeLink',
  Include = 'include',
  IncludeLink = 'includeLink',
  Link = 'link',
}

export type IFieldInfo = {
  description: string;
  es_doc_values: boolean;
  field_alias: string;
  field_name: string;
  field_operator: string[]; // 使用 `any[]` 可以存储任意类型的数组，如果有特定类型可以进一步细化
  field_type: string;
  filterVisible: boolean;
  is_analyzed: boolean;
  is_built_in: boolean;
  is_case_sensitive: boolean;
  is_display: boolean;
  is_editable: boolean;
  is_virtual_obj_node: boolean;
  origin_field: string;
  query_alias: string;
  tag: string;
  tokenize_on_chars: string;
};

export type TClickMenuOpt = {
  field: IFieldInfo;
  type: EClickMenuType;
  value: string;
};
