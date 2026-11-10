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
import { debounce } from 'lodash-es';
export class TaskPool {
  public poolList: [() => void, ...args: any, mark?: unknown][];
  public isRunning: boolean;
  public runningTask: () => void;
  private clearingPromise?: Promise<any>;
  private clearingDebounce: (resolve) => Promise<any>;
  private clearingNext: (() => Promise<any>)[];

  constructor() {
    this.poolList = [];
    this.isRunning = false;
    this.clearingNext = [];
    this.clearingDebounce = debounce(resolve => {
      resolve();
    });
    this.runningTask = debounce(() => {
      if (!this.isRunning) {
        this.isRunning = true;
        this.deepRunning();
      }
    }, 60);
  }

  public clear(next) {
    this.clearingNext.push(next);
    this.poolList.length = 0;

    this.clearingPromise = new Promise(r1 => {
      this.clearingDebounce(r1);
      this.isRunning = false;
    });

    return this.clearingPromise.finally(() => {
      this.clearingPromise = undefined;
      while (this.clearingNext.length) {
        const fn = this.clearingNext.shift();
        fn();
      }
    });
  }

  private deepRunning() {
    const result = this.executePoolTask();
    result
      ?.then(() => {
        this.deepRunning();
      })
      .catch(() => {
        this.isRunning = false;
      });
  }

  private executePoolTask() {
    const task = this.poolList.shift();
    if (task) {
      return new Promise((resolve, reject) => {
        requestAnimationFrame(() => {
          try {
            const args = task[1]?.[0];
            const selfThis = args?.slice(-1)?.[0] ?? null;
            Reflect.apply(task[0], selfThis, task[1] ?? []);
            this.clearingPromise?.then(() => {
              resolve(true);
            }) ?? resolve(true);
          } catch (e) {
            console.error(e);
            reject(false);
          }
        });
      });
    }

    return Promise.reject(false);
  }
}

const SegmentTask = new TaskPool();
export default (task, ...args) => {
  SegmentTask.poolList.push([task, args]);
  SegmentTask.runningTask();
};
