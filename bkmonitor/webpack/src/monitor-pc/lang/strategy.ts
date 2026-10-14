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
  添加查询: 'Add query',
  请填写计算表达式: 'Enter an expression',
  'strategy-目标IP': 'Target IP',
  'strategy-云区域ID': 'Cloud ID',
  'strategy-主机ID': 'Host ID',
  '查询 {alias} 不能为空，请填写 PromQL 或删除该查询。': 'Query {alias} is empty. Enter PromQL or delete the query.',
  '查询 {alias} 不能为空，请填写 PromQL。': 'Query {alias} is empty. Enter PromQL.',
  '查询 {alias} 的 PromQL 语法有误，请检查。': 'Invalid PromQL syntax in query {alias}. Please check the query.',
  '表达式语法有误，请检查。': 'Invalid expression syntax. Please check the expression.',
  '时间范围、offset 和标签过滤请填写在各条 PromQL 查询中。':
    'Specify ranges, offset and label filters in individual PromQL queries.',
  '表达式引用了不存在的查询 {alias}，请修改表达式或添加查询。':
    'The expression references unknown query {alias}. Edit the expression or add a query.',
  '单查询表达式应为 {alias}；复杂计算请填写在 PromQL 查询中。':
    'The expression for a single query must be {alias}. Put complex calculations in the PromQL query.',
  '单查询默认使用 {alias} 的结果；可继续添加查询并设置表达式。':
    'A single query uses the result of {alias}. Add more queries to configure an expression.',
  '新增查询 {alias}；填写后可在表达式中引用，原表达式保持不变。':
    'Added query {alias}. Fill it in and reference it in the expression. The original expression remains unchanged.',
  '已添加 {count} 条查询，可继续添加；表达式可引用所需查询的别名。':
    '{count} queries added. You can add more; the expression can reference the aliases of the queries you need.',
  '至少需要有 1 条查询，不能删除': 'At least 1 query is required and cannot be deleted.',
  无法无损切换为表单: 'Cannot switch to form without data loss',
  '当前查询包含表单无法完整表达的内容。': 'The current queries contain content that the form cannot fully represent.',
  '已保留全部 PromQL 与表达式，请继续在当前模式编辑。':
    'All PromQL queries and the expression are preserved. Continue editing in the current mode.',
  '继续编辑 PromQL': 'Continue editing PromQL',
  '历史多 PromQL 查询配置仅可查看；其他策略设置可正常保存。查询请通过 API 或 as-code 修改。':
    'Legacy multi-PromQL queries are read-only. Other strategy settings can be saved. Edit queries through the API or as-code.',
  '当前业务不支持配置多 PromQL，已有查询和表达式仅可查看。':
    'Multi-PromQL is unavailable for this business. Existing queries and the expression are read-only.',
};
