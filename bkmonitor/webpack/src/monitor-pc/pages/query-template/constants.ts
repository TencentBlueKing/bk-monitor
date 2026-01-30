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

import { CP_METHOD_LIST, METHOD_LIST, NUMBER_CONDITION_METHOD_LIST } from '../../constant/constant';
import { isEn } from '../../i18n/lang';

/** 查询模板列表-表格固定展示字段 */
export const TABLE_FIXED_DISPLAY_FIELDS = ['name', 'operator'];
/** 查询模板列表-表格默认展示字段 */
export const TABLE_DEFAULT_DISPLAY_FIELDS = [
  'name',
  'alias',
  'description',
  'create_time',
  'update_user',
  'update_time',
  'relation_config_count',
  'operator',
];

/** 查询模板列表-搜索组件下拉选项 */
export const SEARCH_SELECT_OPTIONS = [
  {
    name: window.i18n.t('全文检索'),
    id: 'query',
    multiable: false,
  },
  {
    name: window.i18n.t('模板名称'),
    id: 'name',
    multiable: false,
  },
  {
    name: window.i18n.t('模板别名'),
    id: 'alias',
    multiable: false,
  },
  {
    name: window.i18n.t('模板说明'),
    id: 'description',
    multiable: false,
  },
  {
    name: window.i18n.t('创建人'),
    id: 'create_user',
    multiable: false,
  },
  {
    name: window.i18n.t('更新人'),
    id: 'update_user',
    multiable: false,
  },
];

/** 查询模板 侧弹详情抽屉面板 Tab 枚举 */
export const TemplateDetailTabEnum = {
  /** 配置信息 */
  CONFIG: 'configPanel',
  /** 消费场景 */
  CONSUME: 'consumePanel',
} as const;

/** 变量类型枚举 */
export const VariableTypeEnum = {
  FUNCTIONS: 'FUNCTIONS',
  GROUP_BY: 'GROUP_BY',
  TAG_VALUES: 'TAG_VALUES',
  METHOD: 'METHOD',
  CONDITIONS: 'CONDITIONS',
  CONSTANTS: 'CONSTANTS',
  EXPRESSION_FUNCTIONS: 'EXPRESSION_FUNCTIONS',
} as const;

export const VariableTypeMap = {
  [VariableTypeEnum.FUNCTIONS]: window.i18n.t('函数变量'),
  [VariableTypeEnum.GROUP_BY]: window.i18n.t('维度变量'),
  [VariableTypeEnum.TAG_VALUES]: window.i18n.t('维度值变量'),
  [VariableTypeEnum.METHOD]: window.i18n.t('汇聚变量'),
  [VariableTypeEnum.CONDITIONS]: window.i18n.t('条件变量'),
  [VariableTypeEnum.CONSTANTS]: window.i18n.t('常规变量'),
  [VariableTypeEnum.EXPRESSION_FUNCTIONS]: window.i18n.t('表达式函数变量'),
};

const ConditionMethodNameMap = {
  include: '包含',
  exclude: '不包含',
  reg: '正则等于',
  nreg: '正则不等于',
};

/** 条件方法别名映射 */
export const ConditionMethodAliasMap = NUMBER_CONDITION_METHOD_LIST.reduce((acc, cur) => {
  const name = isEn ? cur.name : ConditionMethodNameMap[cur.id] || cur.name;
  acc[cur.id] = name;
  return acc;
}, {});

/** 汇聚方法别名映射表 */
export const AggMethodMap = [...METHOD_LIST, ...CP_METHOD_LIST].reduce((prev, curr) => {
  prev[curr.id] = curr.name;
  return prev;
}, {});

export const CONDITIONS = [
  {
    id: 'and',
    name: 'AND',
  },
  {
    id: 'or',
    name: 'OR',
  },
];
