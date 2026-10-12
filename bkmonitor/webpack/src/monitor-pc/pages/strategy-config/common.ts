import { RecoveryConfigStatusSetter } from './strategy-config-set-new/judging-condition/judging-condition';
import { type MetricDetail, MetricType } from './strategy-config-set-new/typings';

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
const { i18n } = window;
// 编辑时设置监控目标描述
export const handleSetTargetDesc = (
  targetList: { all_host: any[]; bk_obj_id: string; count: number; instances_count?: number; nodes_count?: number }[],
  bkTargetType: string,
  objectType: string,
  nodeCount = 0,
  instance_count = 0
) => {
  const targetResult = {
    message: '',
    subMessage: '',
  };
  // const [{ objectType }] = this.metricData;
  const allHost = new Set();
  if (targetList?.length) {
    const len = nodeCount || targetList.length;
    let count = 0;
    let instanceCount = 0;
    if (['TOPO', 'SERVICE_TEMPLATE', 'SET_TEMPLATE', 'DYNAMIC_GROUP'].includes(bkTargetType)) {
      for (const item of targetList) {
        item?.all_host?.forEach(id => allHost.add(id));
        count = allHost.size;
        instanceCount += item?.instances_count || 0;
      }
      count = instance_count || instanceCount || count;
      const textMap = {
        TOPO: '{0}个拓扑节点',
        SERVICE_TEMPLATE: '{0}个服务模板',
        SET_TEMPLATE: '{0}个集群模板',
        DYNAMIC_GROUP: '{0}个动态分组',
      };
      targetResult.message = i18n.t(textMap[bkTargetType], [len]) as string;
      const subText = objectType === 'SERVICE' ? '{0}个实例' : '{0}台主机';
      targetResult.subMessage = count > 0 ? `（${i18n.t(subText, [count])}）` : '';
    } else {
      targetResult.message = i18n.t('{0}台主机', [len]) as string;
    }
  } else {
    targetResult.message = '';
    targetResult.subMessage = '';
  }
  return targetResult;
};

// 判断 是否非时序数据（指标数据）
export const IS_TIME_SERIES = [MetricType.TimeSeries];
export const isRecoveryDisable = (metricData: MetricDetail[]) => {
  return !(metricData.length && metricData.some(v => IS_TIME_SERIES.includes(v?.data_type_label as MetricType)));
};

// 判断 恢复条件是否选择 无数据
export const isStatusSetterNoData = (v: RecoveryConfigStatusSetter) => {
  return v === RecoveryConfigStatusSetter.RECOVERY_NODATA;
};

/* 多 PromQL 计算表达式的运算关键字与向量匹配修饰符（与后端 compile_promql_expression 保持一致） */
const EXPRESSION_OPERATORS = new Set(['and', 'or', 'unless', 'bool', 'offset']);
const EXPRESSION_LABEL_MODIFIERS = new Set(['on', 'ignoring', 'group_left', 'group_right', 'by', 'without']);

/**
 * @description 提取计算表达式中未被声明为查询别名的标识符
 * 词法规则与后端 bkmonitor.data_source.promql_expression.compile_promql_expression 保持一致，
 * 用于前端在保存前给出与后端一致的行内校验提示。
 */
export const getUnknownExpressionAliases = (expression: string, aliases: string[]): string[] => {
  const cleaned = expression.replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`[^`]*`/g, ' ');
  const aliasSet = new Set(aliases);
  const tokenRe = /\s+|\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+|[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|[()+\-*/%^,<>]/g;
  const unknownSet = new Set<string>();
  let labelList = false;
  let pendingModifier = '';
  let match = tokenRe.exec(cleaned);
  while (match) {
    const token = match[0];
    const tokenEnd = tokenRe.lastIndex;
    match = tokenRe.exec(cleaned);
    if (!token.trim()) continue;
    if (pendingModifier) {
      if (token === '(') {
        pendingModifier = '';
        labelList = true;
        continue;
      }
      // on/ignoring/by/without 缺少标签列表属于语法错误，交由后端校验，这里宽松处理
      pendingModifier = '';
    }
    if (labelList) {
      // 标签列表内（如 on(service, code)）的标识符是标签名而非查询别名
      if (token === ')') {
        labelList = false;
      }
      continue;
    }
    if (!/[A-Za-z_]/.test(token[0])) continue;
    const keyword = token.toLowerCase();
    if (EXPRESSION_OPERATORS.has(keyword)) continue;
    if (EXPRESSION_LABEL_MODIFIERS.has(keyword)) {
      pendingModifier = keyword;
      continue;
    }
    if (aliasSet.has(token)) continue;
    const rest = cleaned.slice(tokenEnd);
    // 函数调用（如 clamp_min(...)）与聚合器（如 sum by(...)）不属于查询别名
    if (/^\s*\(/.test(rest) || /^\s*(?:by|without)\b/.test(rest)) continue;
    unknownSet.add(token);
  }
  return [...unknownSet];
};
