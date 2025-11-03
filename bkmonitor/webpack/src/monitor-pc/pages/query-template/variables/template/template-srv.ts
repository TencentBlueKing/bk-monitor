/* eslint-disable @typescript-eslint/naming-convention */
/** biome-ignore-all lint/complexity/noBannedTypes: <explanation> */
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

import { xssFilter } from 'monitor-common/utils';

import { getFieldAccessor } from './field-accessor';
import { formatVariableValue } from './format-variable-value';
import { setTemplateSrv, VariableFormatID } from './index';
// import { macroRegistry } from './macroRegistry';
import { ALL_VARIABLE_TEXT, ALL_VARIABLE_VALUE } from './types/constants';
import { variableRegex } from './utils';

import type { ScopedVar, ScopedVars, TimeRange } from './types/scoped-var';
import type { BaseTemplateSrv, VariableInterpolation } from './types/template';
import type { VariableCustomFormatterFn } from './types/variable';

/**
 * Internal regex replace function
 */
export type ReplaceFunction = (fullMatch: string, variableName: string, fieldPath: string, format: string) => string;

export class TemplateSrv implements BaseTemplateSrv {
  _variables: any[];
  grafanaVariables = new Map<string, any>();
  index: any = {};
  regex = variableRegex;
  timeRange?: null | TimeRange = null;
  constructor() {
    this._variables = [];
  }

  _evaluateVariableExpression(
    match: string,
    variableName: string,
    fieldPath: string,
    format: string | undefined | VariableCustomFormatterFn,
    scopedVars: ScopedVars | undefined
  ) {
    const variable = this.getVariableAtIndex(variableName);
    const scopedVar = scopedVars?.[variableName];

    if (scopedVar) {
      const value = this.getVariableValue(scopedVar, fieldPath);
      const text = this.getVariableText(scopedVar, value);

      if (value !== null && value !== undefined) {
        return formatVariableValue(value, format, variable, text);
      }
    }

    if (!variable) {
      // const macro = macroRegistry[variableName];
      // if (macro) {
      //   return macro(match, fieldPath, scopedVars, format);
      // }

      return match;
    }

    // if (format === VariableFormatID.QueryParam) {
    //   const value = variableAdapters.get(variable.type).getValueForUrl(variable);
    //   const text = variable.current.text;

    //   return formatVariableValue(value, format, variable, text);
    // }

    const systemValue = this.grafanaVariables.get(variable.current.value);
    if (systemValue) {
      return formatVariableValue(systemValue, format, variable);
    }

    let value = variable.current.value;
    let text = variable.current.text;

    if (this.isAllValue(value)) {
      value = this.getAllValue(variable);
      text = ALL_VARIABLE_TEXT;
      // skip formatting of custom all values unless format set to text or percentencode
      if (variable.allValue && format !== VariableFormatID.Text && format !== VariableFormatID.PercentEncode) {
        return this.replace(value);
      }
    }

    if (fieldPath) {
      const fieldValue = this.getVariableValue({ value, text }, fieldPath);
      if (fieldValue !== null && fieldValue !== undefined) {
        return formatVariableValue(fieldValue, format, variable, text);
      }
    }

    return formatVariableValue(value, format, variable, text);
  }

  /**
   * Tries to unify the different variable format capture groups into a simpler replacer function
   */
  _replaceWithVariableRegex(text: string, format: Function | string | undefined, replace: ReplaceFunction) {
    this.regex.lastIndex = 0;

    return text.replace(this.regex, (match, var1, var2, fmt2, var3, fieldPath, fmt3) => {
      const variableName = var1 || var2 || var3;
      const fmt = fmt2 || fmt3 || format;
      return replace(match, variableName, fieldPath, fmt);
    });
  }

  containsTemplate(target: string | undefined): boolean {
    if (!target) {
      return false;
    }
    const name = this.getVariableName(target);
    const variable = name && this.getVariableAtIndex(name);
    return variable !== null && variable !== undefined;
  }

  getAllValue(variable: any) {
    if (variable.allValue) {
      return variable.allValue;
    }
    const values = [];
    for (let i = 1; i < variable.options.length; i++) {
      values.push(variable.options[i].value);
    }
    return values;
  }

  getVariableAtIndex(name: string) {
    if (!name) {
      return;
    }

    return this.index[name];
  }

  getVariableName(expression: string) {
    this.regex.lastIndex = 0;
    const match = this.regex.exec(expression);
    if (!match) {
      return null;
    }
    const variableName = match.slice(1).find(match => match !== undefined);
    return variableName;
  }

  getVariableText(scopedVar: ScopedVar, value: any) {
    if (scopedVar.value === value || typeof value !== 'string') {
      return scopedVar.text;
    }

    return value;
  }

  getVariableValue(scopedVar: ScopedVar, fieldPath: string | undefined) {
    if (fieldPath) {
      return getFieldAccessor(fieldPath)(scopedVar.value);
    }

    return scopedVar.value;
  }

  highlightVariablesAsHtml(str: string) {
    if (!str) {
      return str;
    }

    str = xssFilter(str);
    return this._replaceWithVariableRegex(str, undefined, (match, variableName) => {
      if (this.getVariableAtIndex(variableName)) {
        return '<span class="template-variable">' + match + '</span>';
      }
      return match;
    });
  }

  init(variables: any, timeRange?: TimeRange) {
    this._variables = variables;
    this.timeRange = timeRange;
    this.updateIndex();
  }

  isAllValue(value: unknown) {
    return value === ALL_VARIABLE_VALUE || (Array.isArray(value) && value[0] === ALL_VARIABLE_VALUE);
  }

  replace(
    target?: string,
    scopedVars?: ScopedVars,
    format?: Function | string | undefined,
    interpolations?: VariableInterpolation[]
  ): string {
    if (!target) {
      return target ?? '';
    }

    this.regex.lastIndex = 0;

    return this._replaceWithVariableRegex(target, format, (match, variableName, fieldPath, fmt) => {
      const value = this._evaluateVariableExpression(match, variableName, fieldPath, fmt, scopedVars);

      // If we get passed this interpolations map we will also record all the expressions that were replaced
      if (interpolations) {
        interpolations.push({ match, variableName, fieldPath, format: fmt, value, found: value !== match });
      }

      return value;
    });
  }

  setGrafanaVariable(name: string, value: any) {
    this.grafanaVariables.set(name, value);
  }

  updateIndex() {
    const existsOrEmpty = (value: unknown) => value || value === '';

    this.index = this._variables.reduce((acc, currentValue) => {
      if (currentValue.current && (currentValue.current.isNone || existsOrEmpty(currentValue.current.value))) {
        acc[currentValue.name] = currentValue;
      }
      return acc;
    }, {});

    if (this.timeRange) {
      const from = this.timeRange.from.valueOf().toString();
      const to = this.timeRange.to.valueOf().toString();

      this.index = {
        ...this.index,
        ['__from']: {
          current: { value: from, text: from },
        },
        ['__to']: {
          current: { value: to, text: to },
        },
      };
    }
  }

  updateTimeRange(timeRange: TimeRange) {
    this.timeRange = timeRange;
    this.updateIndex();
  }

  variableExists(expression: string): boolean {
    return this.containsTemplate(expression);
  }

  variableInitialized(variable: any) {
    this.index[variable.name] = variable;
  }
}

// Expose the template srv
const srv = new TemplateSrv();

setTemplateSrv(srv);

export const getTemplateSrv = () => srv;
