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
import Big from 'big.js';

// drag触发
interface IDragOption {
  max: number;
  min: number;
}
export const handleMouseDown = (e, tag: string, resetWidth = 200, option: IDragOption, setWidth) => {
  let { target } = e;

  while (target && target.dataset.tag !== tag) {
    target = target.parentNode;
  }
  const rect = target.getBoundingClientRect();
  document.onselectstart = function () {
    return false;
  };
  document.ondragstart = function () {
    return false;
  };
  const handleMouseMove = event => {
    if (event.clientX - rect.left < resetWidth) {
      setWidth(0);
    } else {
      const w = Math.min(Math.max(option.min, event.clientX - rect.left), option.max);
      setWidth(w);
    }
  };
  const handleMouseUp = () => {
    document.body.style.cursor = '';
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
    document.onselectstart = null;
    document.ondragstart = null;
  };
  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
};
export const handleMouseMove = e => {
  let { target } = e;
  while (target && target.dataset.tag !== 'resizeTarget') {
    target = target.parentNode;
  }
};

/** 敏感度阈值转换规则 threshold = (1 - sensitivity / 10) * 0.8 + 0.1 */
export const transformSensitivityValue = (val: number): number =>
  new Big(1).minus(new Big(val).div(10)).times(0.8).plus(0.1).toNumber();

export const compareObjectsInArray = arr => {
  return arr.every((obj, index, array) => {
    return Object.keys(obj).every(key =>
      array.every((otherObj, otherIndex) => index === otherIndex || obj[key] === otherObj[key])
    );
  });
};

/**
 * 计算容器中不在第一行的子元素数量
 * @param container - 包含子元素的容器元素
 * @returns 不在第一行的子元素数量
 */
export function countElementsNotInFirstRow(container: HTMLElement): number {
  const children = container.children || [];

  if (children.length === 0) {
    return 0;
  }

  const firstElementTop = (children[0] as HTMLElement).offsetTop;

  return Array.from(children).filter(item => (item as HTMLElement).offsetTop > firstElementTop).length;
}
