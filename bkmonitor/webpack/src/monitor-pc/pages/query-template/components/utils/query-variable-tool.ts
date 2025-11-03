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

import type { VariableModelType } from '../../variables';

export interface QueryVariablesTransformResult<T = unknown> {
  /** 是否包含变量 */
  isVariable: boolean;
  /** 转换后的变量值 */
  value: T;
  /** 变量名 */
  variableName: string;
}
type ScopedVariable = Record<string, VariableModelType>;

export const variableRegex = /^\$\{([\w.]{1,50})}$/;

/**
 * @class VariablesTool
 * @description 查询模板变量工具类
 */
export class QueryVariablesTool {
  /**
   * @property regex
   * @description 变量匹配规则(正则表达式)
   */
  protected regex = variableRegex;

  /**
   * @description 获取变量别名，如别名不存在则显示原始变量名
   * @param source 变量格式字符串 例如：${variable}
   * @param {ScopedVars} scopedVariable 变量详情信息映射表
   */
  getVariableAlias(source: string, scopedVariable?: ScopedVariable) {
    if (!this.hasVariables(source)) {
      return source;
    }
    const variableName = this.getVariableName(source);
    const alias = scopedVariable?.[variableName]?.alias;
    if (!alias) {
      return source;
    }
    return alias;
  }

  /**
   * @description 获取变量名 - 例如：输入 ${variable}  ==> variable
   * @param source 变量格式字符串 例如：${variable}
   */
  public getVariableName(source: string) {
    this.regex.lastIndex = 0;
    return this.regex.exec(source)?.[1];
  }
  /**
   * @method getVariableValue
   * @description 获取变量值
   * @param source 变量格式字符串 例如：${variable}
   * @param {ScopedVars} scopedVariable 变量详情信息映射表
   */
  public getVariableValue(source: string, scopedVariable?: ScopedVariable) {
    const variableName = this.getVariableName(source);
    const variableValue = scopedVariable?.[variableName];
    if (!variableValue) {
      return null;
    }
    return variableValue;
  }

  /**
   * @method hasVariables
   * @description 判断输入是否包含变量
   * @param input 输入
   */
  hasVariables(input: unknown): input is string {
    if (typeof input !== 'string') {
      return false;
    }
    this.regex.lastIndex = 0;
    return variableRegex.test(input);
  }

  /**
   * @method replace
   * @description 变量替换
   * @param source 变量格式字符串 例如：${variable}
   * @param {ScopedVars} scopedVariable 变量详情信息映射表
   */
  public replace(source: string, scopedVariable?: ScopedVariable): { value: unknown; variableName: string } {
    const value = this.getVariableValue(source, scopedVariable);
    return { value: value ?? source, variableName: this.getVariableName(source) };
  }

  /**
   * @method transformVariables
   * @description 变量翻译
   * @param {Record} source 含有变量的一个元数据
   * @param {ScopedVars} scopedVariable 变量详情信息映射表
   * @return {*}
   */
  public transformVariables(source: unknown, scopedVariable?: ScopedVariable): QueryVariablesTransformResult {
    // 如果不存在变量，则直接返回
    if (!this.hasVariables(source)) {
      return {
        value: source,
        isVariable: false,
        variableName: '',
      };
    }
    const result = this.replace(source, scopedVariable);
    return {
      ...result,
      isVariable: true,
    };
  }
}

const singletonVariablesToolInstance = new QueryVariablesTool();

export const getQueryVariablesTool = () => singletonVariablesToolInstance;
