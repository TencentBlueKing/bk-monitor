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

import dayjs from 'dayjs';
import { isArray, map, replace } from 'lodash';

import { VariableFormatID } from '.';
import { Registry } from './registry';
import { ALL_VARIABLE_VALUE } from './types/constants';
import { escapeRegex } from './utils';

import type { VariableType } from './types/template-vars';
import type { VariableValue, VariableValueSingle } from './types/variable';

export interface FormatRegistryItem extends RegistryItem {
  formatter(value: VariableValue, args: string[], variable: FormatVariable): string;
}
export interface RegistryItem {
  aliasIds?: string[]; // when the ID changes, we may want backwards compatibility ('current' => 'last')
  description?: string;
  /**
   * Some extensions should not be user selectable
   *  like: 'all' and 'any' matchers;
   */
  excludeFromPicker?: boolean;
  id: string; // Unique Key -- saved in configs

  name: string; // Display Name, can change without breaking configs
}

const t = (key: string, defaultValue: string) => defaultValue;
/**
 * Slimmed down version of the SceneVariable interface so that it only contains what the formatters actually use.
 * This is useful as we have some implementations of this interface that does not need to be full scene objects.
 * For example ScopedVarsVariable and LegacyVariableWrapper.
 */
export interface FormatVariable {
  getValue(fieldPath?: string): null | undefined | VariableValue;
  getValueText?(fieldPath?: string): string;
  state: {
    includeAll?: boolean;
    isMulti?: boolean;
    name: string;
    type: string | VariableType;
  };
}

export const formatRegistry = new Registry<FormatRegistryItem>(() => {
  const formats: FormatRegistryItem[] = [
    {
      id: VariableFormatID.Lucene,
      name: 'Lucene',
      description: 'Values are lucene escaped and multi-valued variables generate an OR expression',
      formatter: value => {
        if (typeof value === 'string') {
          return luceneEscape(value);
        }

        if (Array.isArray(value)) {
          if (value.length === 0) {
            return '__empty__';
          }
          const quotedValues = map(value, (val: string) => {
            return '"' + luceneEscape(val) + '"';
          });
          return '(' + quotedValues.join(' OR ') + ')';
        } else {
          return luceneEscape(`${value}`);
        }
      },
    },
    {
      id: VariableFormatID.Raw,
      name: 'raw',
      description: t(
        'grafana-scenes.variables.format-registry.formats.description.keep-value-as-is',
        'Keep value as is'
      ),
      formatter: value => String(value),
    },
    {
      id: VariableFormatID.Regex,
      name: 'Regex',
      description: 'Values are regex escaped and multi-valued variables generate a (<value>|<value>) expression',
      formatter: value => {
        if (typeof value === 'string') {
          return escapeRegex(value);
        }

        if (Array.isArray(value)) {
          const escapedValues = value.map(item => {
            if (typeof item === 'string') {
              return escapeRegex(item);
            } else {
              return escapeRegex(String(item));
            }
          });

          if (escapedValues.length === 1) {
            return escapedValues[0];
          }

          return '(' + escapedValues.join('|') + ')';
        }

        return escapeRegex(`${value}`);
      },
    },
    {
      id: VariableFormatID.Pipe,
      name: 'Pipe',
      description: t(
        'grafana-scenes.variables.format-registry.formats.description.values-are-separated-by-character',
        'Values are separated by | character'
      ),
      formatter: value => {
        if (typeof value === 'string') {
          return value;
        }

        if (Array.isArray(value)) {
          return value.join('|');
        }

        return `${value}`;
      },
    },
    {
      id: VariableFormatID.Distributed,
      name: 'Distributed',
      description: t(
        'grafana-scenes.variables.format-registry.formats.description.multiple-values-are-formatted-like-variablevalue',
        'Multiple values are formatted like variable=value'
      ),
      formatter: (value, args, variable) => {
        if (typeof value === 'string') {
          return value;
        }

        if (Array.isArray(value)) {
          value = map(value, (val: string, index: number) => {
            if (index !== 0) {
              return variable.state.name + '=' + val;
            } else {
              return val;
            }
          });

          return value.join(',');
        }

        return `${value}`;
      },
    },
    {
      id: VariableFormatID.CSV,
      name: 'Csv',
      description: t(
        'grafana-scenes.variables.format-registry.formats.description.commaseparated-values',
        'Comma-separated values'
      ),
      formatter: value => {
        if (typeof value === 'string') {
          return value;
        }

        if (isArray(value)) {
          return value.join(',');
        }

        return String(value);
      },
    },
    {
      id: VariableFormatID.JSON,
      name: 'JSON',
      description: t(
        'grafana-scenes.variables.format-registry.formats.description.json-stringify-value',
        'JSON stringify value'
      ),
      formatter: value => {
        if (typeof value === 'string') {
          return value;
        }
        return JSON.stringify(value);
      },
    },
    {
      id: VariableFormatID.PercentEncode,
      name: 'Percent encode',
      description: t(
        'grafana-scenes.variables.format-registry.formats.description.useful-for-url-escaping-values',
        'Useful for URL escaping values'
      ),
      formatter: value => {
        // like glob, but url escaped
        if (isArray(value)) {
          return encodeURIComponentStrict('{' + value.join(',') + '}');
        }

        return encodeURIComponentStrict(value);
      },
    },
    {
      id: VariableFormatID.SingleQuote,
      name: 'Single quote',
      description: t(
        'grafana-scenes.variables.format-registry.formats.description.single-quoted-values',
        'Single quoted values'
      ),
      formatter: value => {
        // escape single quotes with backslash
        const regExp = /'/g;

        if (isArray(value)) {
          return map(value, (v: string) => `'${replace(v, regExp, `\\'`)}'`).join(',');
        }

        const strVal = typeof value === 'string' ? value : String(value);
        return `'${replace(strVal, regExp, `\\'`)}'`;
      },
    },
    {
      id: VariableFormatID.DoubleQuote,
      name: 'Double quote',
      description: t(
        'grafana-scenes.variables.format-registry.formats.description.double-quoted-values',
        'Double quoted values'
      ),
      formatter: value => {
        // escape double quotes with backslash
        const regExp = /"/g;
        if (isArray(value)) {
          return map(value, (v: string) => `"${replace(v, regExp, '\\"')}"`).join(',');
        }

        const strVal = typeof value === 'string' ? value : String(value);
        return `"${replace(strVal, regExp, '\\"')}"`;
      },
    },
    {
      id: VariableFormatID.SQLString,
      name: 'SQL string',
      description: 'SQL string quoting and commas for use in IN statements and other scenarios',
      formatter: sqlStringFormatter,
    },
    {
      id: 'join', // join not yet available in depended @grafana/schema version
      name: 'Join',
      description: 'Join values with a comma',
      formatter: (value, args) => {
        if (isArray(value)) {
          const separator = args[0] ?? ',';
          return value.join(separator);
        }
        return String(value);
      },
    },
    {
      id: VariableFormatID.Date,
      name: 'Date',
      description: t(
        'grafana-scenes.variables.format-registry.formats.description.format-date-in-different-ways',
        'Format date in different ways'
      ),
      formatter: (value, args) => {
        let nrValue = NaN;

        if (typeof value === 'number') {
          nrValue = value;
        } else if (typeof value === 'string') {
          nrValue = parseInt(value, 10);
        }

        if (isNaN(nrValue)) {
          return 'NaN';
        }

        const arg = args[0] ?? 'iso';
        switch (arg) {
          case 'ms':
            return String(value);
          case 'seconds':
            return `${Math.round(nrValue! / 1000)}`;
          case 'iso':
            return dayjs(nrValue).toISOString();
          default:
            if ((args || []).length > 1) {
              return dayjs(nrValue).format(args.join(':'));
            }
            return dayjs(nrValue).format(arg);
        }
      },
    },
    {
      id: VariableFormatID.Glob,
      name: 'Glob',
      description: t(
        'grafana-scenes.variables.format-registry.formats.description.format-multivalued-variables-using-syntax-example',
        'Format multi-valued variables using glob syntax, example {value1,value2}'
      ),
      formatter: value => {
        if (isArray(value) && value.length > 1) {
          return '{' + value.join(',') + '}';
        }
        return String(value);
      },
    },
    {
      id: VariableFormatID.Text,
      name: 'Text',
      description: 'Format variables in their text representation. Example in multi-variable scenario A + B + C.',
      formatter: (value, _args, variable) => {
        if (variable.getValueText) {
          return variable.getValueText();
        }

        return String(value);
      },
    },
    {
      id: 'customqueryparam',
      name: 'Custom query parameter',
      description:
        'Format variables as URL parameters with custom name and value prefix. Example in multi-variable scenario A + B + C => p-foo=x-A&p-foo=x-B&p-foo=x-C.',
      formatter: (value, args, variable) => {
        const name = encodeURIComponentStrict(args[0] || variable.state.name);
        const valuePrefix = encodeURIComponentStrict(args[1] || '');

        if (Array.isArray(value)) {
          return value.map(v => customFormatQueryParameter(name, v, valuePrefix)).join('&');
        }

        return customFormatQueryParameter(name, value, valuePrefix);
      },
    },
    {
      id: VariableFormatID.UriEncode,
      name: 'Percent encode as URI',
      description: t(
        'grafana-scenes.variables.format-registry.formats.description.useful-escaping-values-taking-syntax-characters',
        'Useful for URL escaping values, taking into URI syntax characters'
      ),
      formatter: (value: VariableValue) => {
        if (isArray(value)) {
          return encodeURIStrict('{' + value.join(',') + '}');
        }

        return encodeURIStrict(value);
      },
    },
  ];

  return formats;
});

/**
 * encode string according to RFC 3986; in contrast to encodeURIComponent()
 * also the sub-delims "!", "'", "(", ")" and "*" are encoded;
 * unicode handling uses UTF-8 as in ECMA-262.
 */
function encodeURIComponentStrict(str: VariableValueSingle) {
  if (typeof str === 'object') {
    str = String(str);
  }

  return replaceSpecialCharactersToASCII(encodeURIComponent(str));
}

function luceneEscape(value: string) {
  if (isNaN(+value) === false) {
    return value;
  }

  return value.replace(/([!*+\-=<>\s&|()[\]{}^~?:\\/"])/g, '\\$1');
}

const encodeURIStrict = (str: VariableValueSingle): string => replaceSpecialCharactersToASCII(encodeURI(String(str)));

const replaceSpecialCharactersToASCII = (value: string): string =>
  value.replace(/[!'()*]/g, c => {
    return '%' + c.charCodeAt(0).toString(16).toUpperCase();
  });

export function isAllValue(value: VariableValueSingle) {
  return value === ALL_VARIABLE_VALUE || (Array.isArray(value) && value[0] === ALL_VARIABLE_VALUE);
}

function customFormatQueryParameter(name: string, value: VariableValueSingle, valuePrefix = ''): string {
  return `${name}=${valuePrefix}${encodeURIComponentStrict(value)}`;
}

const SQL_ESCAPE_MAP: Record<string, string> = {
  "'": "''",
  '"': '\\"',
};

function sqlStringFormatter(value: VariableValue) {
  // escape single quotes by pairing them
  const regExp = /'|"/g;

  if (isArray(value)) {
    return map(value, (v: string) => `'${replace(v, regExp, match => SQL_ESCAPE_MAP[match] ?? '')}'`).join(',');
  }

  const strVal = typeof value === 'string' ? value : String(value);
  return `'${replace(strVal, regExp, match => SQL_ESCAPE_MAP[match] ?? '')}'`;
}
