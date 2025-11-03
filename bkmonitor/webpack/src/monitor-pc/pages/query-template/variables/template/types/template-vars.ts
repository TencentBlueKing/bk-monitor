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

export enum LoadingState {
  Done = 'Done',
  Error = 'Error',
  Loading = 'Loading',
  NotStarted = 'NotStarted',
  Streaming = 'Streaming',
}
export enum VariableHide {
  dontHide,
  hideLabel,
  hideVariable,
}

export enum VariableRefresh {
  never, // removed from the UI
  onDashboardLoad,
  onTimeRangeChanged,
}

export enum VariableSort {
  disabled,
  alphabeticalAsc,
  alphabeticalDesc,
  numericalAsc,
  numericalDesc,
  alphabeticalCaseInsensitiveAsc,
  alphabeticalCaseInsensitiveDesc,
  naturalAsc,
  naturalDesc,
}

export interface AdHocVariableFilter {
  /** @deprecated  */
  condition?: string;
  key: string;
  operator: string;
  value: string;
}

export interface AdHocVariableModel extends BaseVariableModel {
  /**
   * Filters that are always applied to the lookup of keys. Not shown in the AdhocFilterBuilder UI.
   */
  baseFilters?: AdHocVariableFilter[];
  filters: AdHocVariableFilter[];
  type: 'adhoc';
}

export interface BaseVariableModel {
  description: null | string;
  error: any | null;
  global: boolean;
  hide: VariableHide;
  id: string;
  index: number;
  label?: string;
  name: string;
  rootStateKey: null | string;
  skipUrlSync: boolean;
  state: LoadingState;
  type: VariableType;
  usedInRepeat?: boolean;
}

export interface ConstantVariableModel extends VariableWithOptions {
  type: 'constant';
}

export interface CustomVariableModel extends VariableWithMultiSupport {
  type: 'custom';
}

export interface DashboardProps {
  name: string;
  uid: string;
  toString: () => string;
}

export type DashboardVariableModel = SystemVariable<DashboardProps>;

export interface GroupByVariableModel extends VariableWithOptions {
  multi: true;
  type: 'groupby';
}

export interface IntervalVariableModel extends VariableWithOptions {
  auto: boolean;
  auto_count: number;
  auto_min: string;
  refresh: VariableRefresh;
  type: 'interval';
}

export interface OrgProps {
  id: number;
  name: string;
  toString: () => string;
}

export type OrgVariableModel = SystemVariable<OrgProps>;

export interface QueryVariableModel extends VariableWithMultiSupport {
  definition: string;
  query: any;
  queryValue?: string;
  refresh: VariableRefresh;
  regex: string;
  sort: VariableSort;
  type: 'query';
}

export interface SystemVariable<TProps extends { toString: () => string }> extends BaseVariableModel {
  current: { value: TProps };
  type: 'system';
}

export interface TextBoxVariableModel extends VariableWithOptions {
  originalQuery: null | string;
  type: 'textbox';
}

export type TypedVariableModel =
  | AdHocVariableModel
  | ConstantVariableModel
  | CustomVariableModel
  | DashboardVariableModel
  | GroupByVariableModel
  | IntervalVariableModel
  | OrgVariableModel
  | QueryVariableModel
  | TextBoxVariableModel
  | UserVariableModel;

export interface UserProps {
  email?: string;
  id: number;
  login: string;
  toString: () => string;
}

export type UserVariableModel = SystemVariable<UserProps>;

/** @deprecated Use TypedVariableModel instead */
export interface VariableModel {
  label?: string;
  name: string;
  type: VariableType;
}

export interface VariableOption {
  isNone?: boolean;
  selected: boolean;
  text: string | string[];
  value: string | string[];
}

export type VariableType = TypedVariableModel['type'];

export interface VariableWithMultiSupport extends VariableWithOptions {
  allValue?: null | string;
  includeAll: boolean;
  multi: boolean;
}

export interface VariableWithOptions extends BaseVariableModel {
  current: Record<string, never> | VariableOption;
  options: VariableOption[];
  query: string;
}
