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

export function mapBkButtonProps({ theme, disabled, type } = {}) {
  const gaps = [];
  const props = {};
  if (theme) props.theme = theme;
  else {
    props.theme = 'default';
    props.variant = 'outline';
    gaps.push('no-theme->theme:default,variant:outline');
  }
  if (disabled != null) props.disabled = Boolean(disabled);
  if (type) props.type = type;
  return { props, gaps };
}

export function mapBkInputProps({ value, clearable, placeholder, disabled, rightIcon } = {}) {
  const gaps = [];
  const props = {};
  if (value != null) props.value = value;
  if (clearable) props.clearable = true;
  if (placeholder != null) props.placeholder = placeholder;
  if (disabled != null) props.disabled = Boolean(disabled);
  if (rightIcon) gaps.push('right-icon');
  return { props, gaps };
}

export function mapBkSelectProps({
  value,
  multiple,
  clearable,
  searchable,
  allowCreate,
  disabled,
  placeholder,
} = {}) {
  const props = {};
  if (value != null) props.value = value;
  if (multiple) props.multiple = true;
  if (clearable) props.clearable = true;
  if (searchable) props.filterable = true;
  if (allowCreate) props.creatable = true;
  if (disabled != null) props.disabled = Boolean(disabled);
  if (placeholder != null) props.placeholder = placeholder;
  return { props, gaps: [] };
}

export function mapBkOption({ id, name } = {}) {
  return { props: { value: id, label: name }, gaps: [] };
}
