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

type FeatureToggleValue = number | string;
type FeatureToggleValues = FeatureToggleValue | FeatureToggleValue[];

interface FeatureToggleOptions {
  defaultEnabled?: boolean;
}

const normalizeFeatureToggleList = (list?: FeatureToggleValue[]) => {
  return (list ?? []).map(id => `${id}`);
};

const normalizeFeatureToggleValues = (value?: FeatureToggleValues) => {
  if (Array.isArray(value)) {
    return value.map(id => `${id}`);
  }

  if (value === undefined || value === null) {
    return [];
  }

  return [`${value}`];
};

const isHitList = (list: string[], values: string[]) => {
  return values.length > 0 && values.some(value => list.includes(value));
};

export const getFeatureToggleStatus = (key: string) => {
  return window.FEATURE_TOGGLE?.[key];
};

export const isFeatureToggleOn = (
  key: string,
  value?: FeatureToggleValues,
  options: FeatureToggleOptions = {},
) => {
  const status = getFeatureToggleStatus(key);
  const values = normalizeFeatureToggleValues(value);
  const whiteList = normalizeFeatureToggleList(window.FEATURE_TOGGLE_WHITE_LIST?.[key]);
  const blackList = normalizeFeatureToggleList(window.FEATURE_TOGGLE_BLACK_LIST?.[key]);

  if (status === 'on') {
    return true;
  }

  if (status === 'off') {
    return false;
  }

  if (status === 'debug') {
    if (whiteList.length > 0) {
      return isHitList(whiteList, values);
    }

    if (blackList.length > 0) {
      return !isHitList(blackList, values);
    }

    return false;
  }

  return options.defaultEnabled ?? false;
};
