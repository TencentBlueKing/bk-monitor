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
export const mockFields = [
  {
    bk_biz_id: 0,
    workspace_id: '1000000',
    tapd_type: 'bug',
    template_id: 0,
    field_id: 'title',
    field_name: '标题',
    field_type: 'input',
    is_required: true,
    is_core_field: true,
    is_selected: true,
    options: [],
  },
  {
    bk_biz_id: 0,
    workspace_id: '1000000',
    tapd_type: 'bug',
    template_id: 0,
    field_id: 'description',
    field_name: '描述',
    field_type: 'rich_edit',
    is_required: true,
    is_core_field: true,
    is_selected: true,
    options: [],
  },
  {
    bk_biz_id: 0,
    workspace_id: '1000000',
    tapd_type: 'bug',
    template_id: 0,
    field_id: 'owner',
    field_name: '处理人',
    field_type: 'user_chooser',
    is_required: true,
    is_core_field: true,
    is_selected: true,
    options: [],
  },
  {
    bk_biz_id: 0,
    workspace_id: '1000000',
    tapd_type: 'bug',
    template_id: 0,
    field_id: 'priority',
    field_name: '优先级',
    field_type: 'select',
    is_required: true,
    is_core_field: true,
    is_selected: true,
    options: [
      {
        id: 'urgent',
        name: '紧急',
      },
      {
        id: 'high',
        name: '高',
      },
      {
        id: 'medium',
        name: '中',
      },
      {
        id: 'low',
        name: '低',
      },
      {
        id: 'insignificant',
        name: '无关紧要',
      },
    ],
  },
  {
    bk_biz_id: 0,
    workspace_id: '1000000',
    tapd_type: 'bug',
    template_id: 0,
    field_id: 'iteration_id',
    field_name: '迭代',
    field_type: 'select',
    is_required: true,
    is_core_field: true,
    is_selected: true,
    options: [
      {
        id: '111111111',
        name: '【告警中心】创建tapd单据（当前迭代）',
      },
    ],
  },
];
