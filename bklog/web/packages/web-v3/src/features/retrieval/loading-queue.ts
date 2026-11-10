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

/** 数字越小越先盖住页面。上层还在队列中时，下层不绘制自己的骨架。 */
const LAYER_RANK = {
  page: 0,
  trend: 1,
} as const;

export type RetrieveLoadingLayer = keyof typeof LAYER_RANK;

interface LoadingTask {
  id: number;
  layer: RetrieveLoadingLayer;
}

const tasks: LoadingTask[] = [];
const listeners = new Set<() => void>();
let nextId = 1;

const emit = () => {
  listeners.forEach(listener => listener());
};

/** 登记一层加载。返回的函数只释放这一次登记，重复调用无效果。 */
export const acquireRetrieveLoading = (layer: RetrieveLoadingLayer) => {
  const id = nextId;
  nextId += 1;
  tasks.push({ id, layer });
  emit();
  let released = false;
  return () => {
    if (released) {
      return;
    }
    released = true;
    const index = tasks.findIndex(task => task.id === id);
    if (index >= 0) {
      tasks.splice(index, 1);
      emit();
    }
  };
};

export const isRetrieveLoadingActive = (layer: RetrieveLoadingLayer) => tasks.some(task => task.layer === layer);

/** 有更靠前的层还在队列里，当前层的覆盖层需要让开。 */
export const isRetrieveLoadingCovered = (layer: RetrieveLoadingLayer) => {
  const rank = LAYER_RANK[layer];
  return tasks.some(task => LAYER_RANK[task.layer] < rank);
};

/** 当前层已登记，且没有更靠前的层挡住它。 */
export const shouldPaintRetrieveLoading = (layer: RetrieveLoadingLayer) =>
  isRetrieveLoadingActive(layer) && !isRetrieveLoadingCovered(layer);

export const subscribeRetrieveLoading = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

export const resetRetrieveLoadingQueue = () => {
  if (!tasks.length) {
    return;
  }
  tasks.length = 0;
  emit();
};
