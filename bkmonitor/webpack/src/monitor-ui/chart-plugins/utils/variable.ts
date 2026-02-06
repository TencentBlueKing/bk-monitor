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
    target.replace(this.regex, (match: any, var1: any, var2: any, fmt2: any, var3: any) => {
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
   * @return {*}
   */
  public transformVariables(source: Record<string, any> | string, scopedVars?: ScopedVars, noTransform = false) {
    if (noTransform) {
      return source;
    }
    if (typeof source === 'string') {
      return this.replace(source);
    }
    const newData = deepClone(source);
    const mergeVars = { ...this.index, ...scopedVars };
    const setVariables = (data: Record<string, any>) => {
      for (const [key, val] of Object.entries(data)) {
        if (typeof val === 'string') {
          if (this.hasVariables(val)) {
            const v = this.replaceString(val.toString(), mergeVars);
            data[key] = v ?? undefined;
          }
        } else if (Array.isArray(val)) {
          if (this.hasVariables(val)) {
            val.forEach((item, index) => {
              if (typeof item === 'string') {
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
                this.hasVariables(item) && setVariables(item);
              }
            });
          }
        } else if (Object.prototype.toString.call(val) === '[object Object]') {
          this.hasVariables(val) && setVariables(val);
        }
      }
    };
    setVariables(newData);
    return newData;
  }
}

const singletonVariablesServiceInstance = new VariablesService({});

export const getVariablesService = () => singletonVariablesServiceInstance;
