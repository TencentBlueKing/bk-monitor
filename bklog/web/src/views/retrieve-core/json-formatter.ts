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
/**
 * 检索结果JSON格式化辅助类
 * 用于处理JSON格式化时的展开节点点击事件
 */
export default class JsonFormatter {
  isExpandNodeClick: boolean;
  private abortController: AbortController | null = null;
  private timeoutId: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    this.isExpandNodeClick = false;
  }

  /**
   * 设置是否展开节点点击
   * @param isExpandNodeClick
   */
  setIsExpandNodeClick(isExpandNodeClick: boolean) {
    this.isExpandNodeClick = isExpandNodeClick;

    // 取消之前未执行的任务
    if (this.abortController) {
      this.abortController.abort();
    }
    if (this.timeoutId !== null) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }

    // 创建新的 AbortController
    this.abortController = new AbortController();

    // 使用 scheduler 的 postTask 来延迟设置 isExpandNodeClick 为 false
    // 以避免在展开节点时，快速点击其他节点导致展开节点的点击事件被触发
    // 100ms 的延迟时间经验值，可以根据实际情况调整
    // 使用 signal 来取消任务
    if (window.scheduler?.postTask) {
      try {
        window.scheduler.postTask(
          () => {
            try {
              // 检查任务是否已被取消
              if (!this.abortController?.signal.aborted) {
                this.isExpandNodeClick = false;
              }
            } catch (error) {
              console.warn('JsonFormatter: Error in postTask callback:', error);
            }
          },
          {
            priority: 'background',
            delay: 100,
            signal: this.abortController.signal,
          },
        );
      } catch (error) {
        console.warn('JsonFormatter: Error scheduling task:', error);
        // 降级处理：直接使用 setTimeout
        this.timeoutId = setTimeout(() => {
          if (!this.abortController?.signal.aborted) {
            this.isExpandNodeClick = false;
          }
          this.timeoutId = null;
        }, 100);
      }
    } else {
      // 降级处理：使用 setTimeout 当 scheduler 不可用时
      this.timeoutId = setTimeout(() => {
        if (!this.abortController?.signal.aborted) {
          this.isExpandNodeClick = false;
        }
        this.timeoutId = null;
      }, 100);
    }
  }
}
