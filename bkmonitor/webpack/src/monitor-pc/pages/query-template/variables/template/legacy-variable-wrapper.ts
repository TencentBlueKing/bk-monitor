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

import { ALL_VARIABLE_TEXT, ALL_VARIABLE_VALUE } from './types/constants';

import type { FormatVariable } from './format-registry';
import type { VariableModel, VariableType } from './types/template-vars';
import type { VariableValue } from './types/variable';

export class LegacyVariableWrapper implements FormatVariable {
  state: { name: string; text: VariableValue; type: VariableType; value: VariableValue };

  constructor(variable: VariableModel, value: VariableValue, text: VariableValue) {
    this.state = { name: variable.name, value, text, type: variable.type };
  }

  getValue(_fieldPath: string): VariableValue {
    const { value } = this.state;

    if (value === 'string' || value === 'number' || value === 'boolean') {
      return value;
    }

    return String(value);
  }

  getValueText(): string {
    const { value, text } = this.state;

    if (typeof text === 'string') {
      return value === ALL_VARIABLE_VALUE ? ALL_VARIABLE_TEXT : text;
    }

    if (Array.isArray(text)) {
      return text.join(' + ');
    }

    console.log('value', text);
    return String(text);
  }
}

let legacyVariableWrapper: LegacyVariableWrapper | undefined;

/**
 * Reuses a single instance to avoid unnecessary memory allocations
 */
export function getVariableWrapper(variable: VariableModel, value: VariableValue, text: VariableValue) {
  // TODO: provide more legacy variable properties, i.e. multi, includeAll that are used in custom interpolators,
  // see Prometheus data source for example
  if (!legacyVariableWrapper) {
    legacyVariableWrapper = new LegacyVariableWrapper(variable, value, text);
  } else {
    legacyVariableWrapper.state.name = variable.name;
    legacyVariableWrapper.state.type = variable.type;
    legacyVariableWrapper.state.value = value;
    legacyVariableWrapper.state.text = text;
  }

  return legacyVariableWrapper;
}
