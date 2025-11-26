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
type ScrollDirection = 'down' | 'none' | 'up';

class LazyTaskManager {
  private static instance: LazyTaskManager;
  static getInstance() {
    if (!LazyTaskManager.instance) {
      LazyTaskManager.instance = new LazyTaskManager();
    }
    return LazyTaskManager.instance;
  }
  tasks: Map<number, (isInBuffer: boolean, direction: ScrollDirection) => void> = new Map();
  visibleIndexes: Set<number> = new Set();
  bufferCount = 20;
  batchSize = 10;
  observer: IntersectionObserver;
  scheduledTasks: Map<number, number> = new Map();
  debounceTimeout: null | number = null;
  maxVisibleIndex = Number.NEGATIVE_INFINITY;
  minVisibleIndex: number = Number.POSITIVE_INFINITY;

  private constructor() {
    this.observer = new IntersectionObserver(this.handleIntersections.bind(this), {
      rootMargin: '200px',
    });
  }

  observeElement(element: HTMLElement, index: number) {
    element.dataset.index = index.toString();
    this.observer.observe(element);
  }

  unobserveElement(element: HTMLElement) {
    this.observer.unobserve(element);
  }

  addTask(index: number, task: (isInBuffer: boolean, direction: ScrollDirection) => void) {
    if (!this.tasks.has(index)) {
      this.tasks.set(index, task);
    }
  }

  executeBufferTasks(direction: ScrollDirection) {
    const indexes = Array.from(this.tasks.keys()).sort((a, b) => a - b);
    const visibleIndexes = Array.from(this.visibleIndexes).sort((a, b) => a - b);
    if (visibleIndexes.length === 0) {
      return;
    }

    const minIndex = visibleIndexes[0];
    const maxIndex = visibleIndexes.at(-1);

    let currentBatchStart = 0;

    const executeBatch = () => {
      const batchEnd = Math.min(currentBatchStart + this.batchSize, indexes.length);

      for (let i = currentBatchStart; i < batchEnd; i++) {
        const index = indexes[i];
        const isInBuffer = index >= minIndex - this.bufferCount && index <= maxIndex + this.bufferCount;

        if (!isInBuffer && this.scheduledTasks.has(index)) {
          if (this.scheduledTasks.get(index) !== undefined) {
            cancelAnimationFrame(this.scheduledTasks.get(index));
          }
          this.scheduledTasks.delete(index);
          continue;
        }

        const task = this.tasks.get(index);
        if (task) {
          const taskId = requestAnimationFrame(() => {
            task(isInBuffer, direction);
            this.scheduledTasks.delete(index);
          });
          this.scheduledTasks.set(index, taskId);
        }
      }

      currentBatchStart += this.batchSize;

      if (currentBatchStart < indexes.length) {
        requestAnimationFrame(executeBatch);
      }
    };

    requestAnimationFrame(executeBatch);
  }

  removeTask(index: number) {
    this.tasks.delete(index);
    const scheduledTaskId = this.scheduledTasks.get(index);
    if (scheduledTaskId !== undefined) {
      cancelAnimationFrame(scheduledTaskId);
      this.scheduledTasks.delete(index);
    }
  }

  private handleIntersections(entries: IntersectionObserverEntry[]) {
    for (const entry of entries) {
      const index = Number.parseInt((entry.target as HTMLElement).dataset.index || '-1', 10);
      if (index !== -1) {
        if (entry.isIntersecting) {
          this.visibleIndexes.add(index);
        } else {
          this.visibleIndexes.delete(index);
          const scheduledTaskId = this.scheduledTasks.get(index);
          if (scheduledTaskId !== undefined) {
            cancelAnimationFrame(scheduledTaskId);
            this.scheduledTasks.delete(index);
          }
        }
      }
    }
    // Determine the new direction based on updated visible indexes
    const visibleArray = Array.from(this.visibleIndexes);
    const newMax = Math.max(...visibleArray);
    const newMin = Math.min(...visibleArray);
    let newDirection: ScrollDirection = 'none';

    if (this.visibleIndexes.size > 0) {
      if (newMax > this.maxVisibleIndex) {
        newDirection = 'down';
      } else if (newMin < this.minVisibleIndex) {
        newDirection = 'up';
      }

      // Update the max and min visible indices
      this.maxVisibleIndex = newMax;
      this.minVisibleIndex = newMin;
    }

    if (newDirection !== 'none') {
      this.executeBufferTasks(newDirection);
    }
  }
}

// 获取全局 LazyTaskManager 实例
const lazyTaskManager = LazyTaskManager.getInstance();
export default lazyTaskManager;
