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

export type FieldKind = 'text' | 'keyword' | 'date' | 'integer';

export interface LogField {
  name: string;
  type: 'string' | 'number';
  kind: FieldKind;
  alias: string;
  visible: boolean;
  analyzable: boolean;
}

export interface FieldSnapshot {
  uiState: 'idle' | 'error';
  error: string;
  filterQuery: string;
  fields: LogField[];
}

export const DEFAULT_FIELDS: LogField[] = [
  { name: 'id', type: 'string', kind: 'keyword', alias: 'ID', visible: true, analyzable: false },
  { name: 'dtEventTimeStamp', type: 'number', kind: 'date', alias: '时间', visible: true, analyzable: false },
  { name: 'log', type: 'string', kind: 'text', alias: '日志', visible: true, analyzable: true },
  { name: 'serverIp', type: 'string', kind: 'keyword', alias: 'IP', visible: false, analyzable: true },
  { name: 'path', type: 'string', kind: 'text', alias: '路径', visible: false, analyzable: false },
  { name: 'status', type: 'number', kind: 'integer', alias: '状态码', visible: false, analyzable: true },
];

export class FieldController {
  private snapshot: FieldSnapshot;

  constructor(fields: LogField[] = DEFAULT_FIELDS) {
    this.snapshot = { uiState: 'idle', error: '', filterQuery: '', fields: fields.map(item => ({ ...item })) };
  }

  getState(): FieldSnapshot {
    return { ...this.snapshot, fields: this.snapshot.fields.map(item => ({ ...item })) };
  }

  getVisibleFields(): LogField[] {
    return this.snapshot.fields.filter(item => item.visible);
  }

  getFilteredFields(): LogField[] {
    const query = this.snapshot.filterQuery.toLowerCase();
    return this.snapshot.fields.filter(item => (
      !query
      || item.name.toLowerCase().includes(query)
      || item.alias.toLowerCase().includes(query)
    ));
  }

  replaceFields(fields: LogField[]): FieldSnapshot {
    this.snapshot = {
      ...this.snapshot,
      uiState: 'idle',
      error: '',
      fields: fields.length ? fields.map(item => ({ ...item })) : this.snapshot.fields,
    };
    return this.getState();
  }

  setError(error: string): FieldSnapshot {
    this.snapshot = { ...this.snapshot, uiState: 'error', error };
    return this.getState();
  }

  setFilterQuery(value: string): FieldSnapshot {
    this.snapshot = { ...this.snapshot, filterQuery: String(value ?? '').trim(), error: '' };
    return this.getState();
  }

  toggle(name: string, visible?: boolean): FieldSnapshot {
    const target = this.snapshot.fields.find(item => item.name === name);
    if (!target) {
      this.snapshot = { ...this.snapshot, uiState: 'error', error: 'field not found' };
      return this.getState();
    }
    const nextVisible = visible ?? !target.visible;
    if (!nextVisible && this.getVisibleFields().length === 1 && target.visible) {
      this.snapshot = { ...this.snapshot, uiState: 'error', error: 'at least one field required' };
      return this.getState();
    }
    this.snapshot = {
      uiState: 'idle',
      error: '',
      filterQuery: this.snapshot.filterQuery,
      fields: this.snapshot.fields.map(item => (item.name === name ? { ...item, visible: nextVisible } : item)),
    };
    return this.getState();
  }
}
