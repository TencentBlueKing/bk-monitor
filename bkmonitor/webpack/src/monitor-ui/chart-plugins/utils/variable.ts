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
import { deepClone } from 'monitor-common/utils/utils';

export const variableRegex = /\$(\w+)|\[\[([\s\S]+?)(?::(\w+))?\]\]|\${(\w+)(?:\.([^:^}]+))?(?::([^}]+))?}/g;
export type ScopedVars = Record<string, any>;

export class VariablesService {
  private index: ScopedVars;
  private regex = variableRegex;
  private getVariableAtIndex(name: string) {
    if (!name) {
      return undefined;
    }
    return this.index[name];
  }
  private getVariableValue(variableName: string, scopedVars: ScopedVars) {
    const scopedVar = scopedVars[variableName];
    if (!scopedVar) {
      return null;
    }
    return scopedVar;
  }
  /** 原生 PromQL 使用字符串分组、offset 与显式正则范围；结构化字段保留原变量类型。 */
  private replacePromql(target: string, scopedVars?: ScopedVars, keepVariables: string[] = []): string {
    this.regex.lastIndex = 0;
    return target.replace(this.regex, (match, var1, var2, fmt2, var3, _path, fmt3) => {
      const variableName = var1 || var2 || var3;
      if (keepVariables.includes(variableName)) return match;
      let value = this.getVariableAtIndex(variableName);
      if (value === undefined && scopedVars) {
        value = this.getVariableValue(variableName, scopedVars);
      }
      if ((fmt2 || fmt3) === 'regex') {
        const values = (Array.isArray(value) ? value : [value]).filter(
          item => item !== undefined && item !== null && item !== ''
        );
        return values.length
          ? values
              .map(item => JSON.stringify(String(item).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).slice(1, -1))
              .join('|')
          : '.*';
      }
      if (variableName === 'group_by') return Array.isArray(value) ? value.join(',') : (value ?? '');
      if (variableName === 'time_shift') {
        const timeShift = String(value || '').trim();
        return !timeShift ? ' ' : /^offset\s/.test(timeShift) ? timeShift : `offset ${timeShift}`;
      }
      return value;
    });
  }
  constructor(variables?: ScopedVars) {
    this.index = variables;
  }
  hasVariables(input: any) {
    return !!JSON.stringify(input).match(variableRegex);
  }
  public replace(target?: string, scopedVars?: ScopedVars): any {
    if (!target) {
      return target ?? '';
    }
    this.regex.lastIndex = 0;
    let value: unknown;
    target.replace(this.regex, (_match: any, var1: any, var2: any, _fmt2: any, var3: any) => {
      const variableName = var1 || var2 || var3;
      value = this.getVariableAtIndex(variableName);
      if (value === undefined && scopedVars) {
        value = this.getVariableValue(variableName, scopedVars);
      }
      return '';
    });
    return value ?? undefined;
  }
  public replaceString(target?: string, scopedVars?: ScopedVars): any {
    if (!target) {
      return target ?? '';
    }
    this.regex.lastIndex = 0;
    let value: string;
    let isObj = true;
    const val = target.replace(this.regex, (_match: any, var1: any, var2: any, _fmt2: any, var3: any) => {
      const variableName = var1 || var2 || var3;
      // 查询当前变量名是否有相关的配置值，有可能返回 undefined 。
      value = this.getVariableAtIndex(variableName);
      if (value === undefined && scopedVars) {
        value = this.getVariableValue(variableName, scopedVars);
      }
      isObj = typeof value === 'object';
      // 如果 value 为 undefined 则 replace 结果值 val 为 'undefined'，这里做一次空值合并，避免返回 'undefined'
      return value;
    });
    return isObj ? value : val;
  }
  /**
   * @description: 变量翻译
   * @param {Record} source 含有变量的一个元数据
   * @param {ScopedVars} scopedVars 自定义变量对应数据
   * @param {string[]} keepPromqlVariables 仅保留原生 PromQL 变量，供大图延后替换方法与时间对比
   * @return {*}
   */
  public transformVariables(
    source: Record<string, any> | string,
    scopedVars?: ScopedVars,
    noTransform = false,
    keepPromqlVariables: string[] = []
  ) {
    if (noTransform) {
      return source;
    }
    if (typeof source === 'string') {
      return this.replace(source);
    }
    const newData = deepClone(source);
    const mergeVars = { ...this.index, ...scopedVars };
    const setVariables = (data: Record<string, any>) => {
      if (typeof data.promql === 'string' && typeof data.pod_promql === 'string') {
        let groupBy = this.index?.group_by;
        if (groupBy === undefined) groupBy = this.getVariableValue('group_by', mergeVars);
        const groups = Array.isArray(groupBy) ? groupBy : typeof groupBy === 'string' ? groupBy.split(',') : [];
        if (!groups.some(group => ['container_name', 'container', 'image'].includes(group.trim()))) {
          data.promql = data.pod_promql;
        }
        delete data.pod_promql;
        delete data.overview_promql;
        delete data.overview_pod_promql;
      }
      for (const [key, val] of Object.entries(data)) {
        if (typeof val === 'string') {
          if (this.hasVariables(val)) {
            const v =
              key === 'promql'
                ? this.replacePromql(val, mergeVars, keepPromqlVariables)
                : this.replaceString(val.toString(), mergeVars);
            data[key] = v ?? undefined;
          }
        } else if (Array.isArray(val)) {
          const hasVariables = this.hasVariables(val);
          val.forEach((item, index) => {
            if (typeof item === 'string') {
              if (!hasVariables) return;
              if (this.hasVariables(item)) {
                const v = this.replaceString(item, scopedVars);
                if (
                  typeof v === 'undefined' ||
                  v === 'undefined' ||
                  (Object.prototype.toString.call(v) === '[object Object]' && Object.keys(v).length === 0)
                ) {
                  val.splice(index, 1, undefined);
                } else {
                  Array.isArray(v) ? val.splice(index, 1, ...v) : val.splice(index, 1, v);
                }
              }
              data[key] = val.filter(v => typeof v !== 'undefined' && v !== null);
            } else if (Object.prototype.toString.call(item) === '[object Object]') {
              setVariables(item);
            }
          });
        } else if (Object.prototype.toString.call(val) === '[object Object]') {
          setVariables(val);
        }
      }
    };
    setVariables(newData);
    return newData;
  }
}

/** 只有实际使用 method 变量的原生 COUNT 查询需要覆盖单位。 */
export const getPromqlUnitOverride = (queryData: { query_configs?: { promql?: string }[] }, method?: string) =>
  method?.toLowerCase() === 'count' &&
  queryData.query_configs?.some(
    config =>
      typeof config.promql === 'string' &&
      [...config.promql.matchAll(variableRegex)].some(match => (match[1] || match[2] || match[4]) === 'method')
  )
    ? 'none'
    : undefined;

const singletonVariablesServiceInstance = new VariablesService({});

export const getVariablesService = () => singletonVariablesServiceInstance;
