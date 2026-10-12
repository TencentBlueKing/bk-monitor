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

// 策略模块个性化的词条
export default {
  'strategy-目标IP': 'Target IP',
  'strategy-云区域ID': 'Cloud ID',
  'strategy-主机ID': 'Host ID',
  // 策略多 PromQL 查询
  添加查询: 'Add query',
  请填写计算表达式: 'Please enter the expression',
  '查询 {0} 不能为空，请填写 PromQL 或删除该查询。':
    'Query {0} cannot be empty. Please enter the PromQL or delete the query.',
  '表达式引用了不存在的查询 {0}，请选择 {1} 或添加查询。':
    'The expression references query {0}, which does not exist. Please choose from {1} or add a query.',
  无法无损切换为表单: 'Cannot switch to the form view losslessly',
  '当前查询包含表单无法完整表达的内容。':
    'The current query contains content that cannot be fully expressed in the form view.',
  '已保留全部 PromQL 与表达式，请继续在当前模式编辑。':
    'All PromQL queries and the expression are preserved. Please continue editing in the current mode.',
  '继续编辑 PromQL': 'Continue editing PromQL',
  '已添加 {0} 条查询，可继续添加；表达式可引用所需查询的别名。':
    '{0} queries have been added, and more can be added; the expression can reference the aliases of the queries.',
  '新增查询 {0}；填写后可在表达式中引用，原表达式保持不变。':
    'Query {0} is added; it can be referenced in the expression once filled in, and the original expression remains unchanged.',
  '单查询默认使用 {0} 的结果；可继续添加查询并设置表达式。':
    'A single query uses the result of {0} by default; more queries can be added and the expression can be set.',
};
