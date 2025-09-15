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
import { Application } from 'pixi.js';
export default class PixiAppPool {
  maxConcurrentApps: number;
  activeApps: Application[];
  queue: (() => void)[];
  constructor(maxConcurrentApps = 5) {
    this.maxConcurrentApps = maxConcurrentApps;
    this.activeApps = [];
    this.queue = [];
  }

  createApp(taskFunction: (app: Application) => Promise<void>) {
    return new Promise<void>((resolve, reject) => {
      const runTask = () => {
        const app = new Application();
        this.activeApps.push(app);

        // 执行任务
        taskFunction(app)
          .then(() => {
            this.releaseApp(app);
            resolve();
          })
          .catch(reject);
      };

      if (this.activeApps.length < this.maxConcurrentApps) {
        runTask();
      } else {
        this.queue.push(runTask);
      }
    });
  }

  releaseApp(app) {
    const index = this.activeApps.indexOf(app);
    if (index !== -1) {
      this.activeApps.splice(index, 1);
      app.destroy(true, { children: true });

      if (this.queue.length > 0) {
        const nextTask = this.queue.shift();
        nextTask();
      }
    }
  }
}

export const PixiAppPoolInstance = new PixiAppPool();
