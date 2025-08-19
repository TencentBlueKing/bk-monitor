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

export interface QueryVariablesTransformResult {
  /** 是否包含变量 */
  isVariable: boolean;
  /** 转换后的变量值 */
  value: unknown;
  /** 变量名 */
  variableName: string;
}
type ScopedVariable = Record<string, any>;

export const variableRegex = /\${(\w+)}/g;

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
   * @method getVariableValue
   * @description 获取变量值
   * @param variableName 变量名
   * @param scopedVariable 自定义变量对应数据
   */
  public getVariableValue(variableName: string, scopedVariable?: ScopedVariable) {
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
   * @param source 目标字符串
   * @param scopedVariable 自定义变量对应数据
   */
  public replace(source: string, scopedVariable?: ScopedVariable): { value: unknown; variableName: string } {
    this.regex.lastIndex = 0;
    const variableName = this.regex.exec(source)?.[1];
    const value = this.getVariableValue(variableName, scopedVariable);
    return { value: value ?? source, variableName };
  }

  /**
   * @method transformVariables
   * @description 变量翻译
   * @param {Record} source 含有变量的一个元数据
   * @param {ScopedVars} scopedVariable 自定义变量对应数据
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
