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
import type { IOption, ITimeVal, unitType } from './typings';

/**
 * @description: compose函数
 * @param 传入要执行的function
 */
/** eslint-disable-next-line */
const compose =
  (...args: Function[]) =>
  x =>
    args.reduce((res, bc) => bc(res), x);

/**
 * @description: 秒转分钟
 * @param {ITimeVal} val
 */
const toMin = (val: ITimeVal): ITimeVal => {
  if (val.unit) return val;
  if (val.value % 60) return val;
  val.value = val.value / 60;
  val.unit = 'm';
  return val;
};
/**
 * @description: 秒
 * @param {ITimeVal} val
 */
const toSec = (val: ITimeVal) => {
  if (val.unit) return val;
  val.unit = 's';
  return val;
};

/**
 * @description: 时间格式化
 */
export const secToString = compose(toMin, toSec);

/**
 * @description: 时间转秒
 * @param {ITimeVal} timeVal
 */
export const timeToSec = (timeVal: ITimeVal): number => {
  const unitMap: { [key in unitType]: Function } = {
    m: (val: number) => val * 60,
    s: (val: number) => val,
  };
  const sec = unitMap?.[timeVal.unit]?.(timeVal.value);
  return sec;
};

/** 分钟可选项 */
export const defaultCycleOptionMin: IOption[] = [
  { id: 'auto', name: 'auto' },
  { id: 1, name: 1 },
  { id: 2, name: 2 },
  { id: 5, name: 5 },
  { id: 10, name: 10 },
  { id: 30, name: 30 },
  { id: 60, name: 60 },
  // { id: 120, name: 120 },
  // { id: 300, name: 300 },
  // { id: 600, name: 600 },
  // { id: 30 * 60, name: 30 * 60 },
  // { id: 60 * 60, name: 60 * 60 }
];

/** 秒可选项 */
export const defaultCycleOptionSec: IOption[] = [
  { id: 'auto', name: 'auto' },
  { id: 10, name: 10 },
  { id: 20, name: 20 },
  { id: 30, name: 30 },
  { id: 60, name: 60 },
];
