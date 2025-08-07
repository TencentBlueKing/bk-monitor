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

/** 查询模板列表-表格固定展示字段 */
export const TABLE_FIXED_DISPLAY_FIELDS = ['name', 'operator'];
/** 查询模板列表-表格默认展示字段 */
export const TABLE_DEFAULT_DISPLAY_FIELDS = [
  'name',
  'description',
  'create_time',
  'update_user',
  'update_time',
  'relevance_configs',
  'operator',
];

/** 查询模板 侧弹详情抽屉面板 Tab 枚举 */
export const QueryTemplateSliderTabEnum = {
  /** 配置信息 */
  CONFIG: 'configPanel',
  /** 消费场景 */
  CONSUME: 'consumePanel',
} as const;

/** 变量类型枚举 */
export const VariableTypeEnum = {
  FUNCTION: 'function',
  DIMENSION: 'dimension',
  DIMENSION_VALUE: 'dimension_value',
  AGG_METHOD: 'agg_method',
  CONDITION: 'condition',
  GENERAL: 'general',
} as const;

export const VariableTypeMap = {
  [VariableTypeEnum.FUNCTION]: window.i18n.tc('函数变量'),
  [VariableTypeEnum.DIMENSION]: window.i18n.tc('维度变量'),
  [VariableTypeEnum.DIMENSION_VALUE]: window.i18n.tc('维度值变量'),
  [VariableTypeEnum.AGG_METHOD]: window.i18n.tc('汇聚变量'),
  [VariableTypeEnum.CONDITION]: window.i18n.tc('条件变量'),
  [VariableTypeEnum.GENERAL]: window.i18n.tc('常规变量'),
};
