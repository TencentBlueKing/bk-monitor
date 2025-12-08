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
 * 事件发射器基类
 * 提供通用的事件监听和触发功能
 * @template TEvent 事件类型，可以是 string 或 string literal union
 */
export class EventEmitter<TEvent extends string = string> {
  // 事件监听器：事件类型 -> 回调函数数组
  protected events: Map<TEvent, Array<(...args: any[]) => void>> = new Map();

  /**
   * 监听事件
   * @param event 事件类型（可以是单个事件或事件数组）
   * @param callback 回调函数
   * @returns this，支持链式调用
   */
  on(event: TEvent | TEvent[], callback: (...args: any[]) => void): this {
    const targetEvents = Array.isArray(event) ? event : [event];
    for (const eventName of targetEvents) {
      if (!this.events.has(eventName)) {
        this.events.set(eventName, []);
      }

      const listeners = this.events.get(eventName)!;
      if (!listeners.includes(callback)) {
        listeners.push(callback);
      }
    }

    return this;
  }

  /**
   * 移除事件监听
   * @param event 事件类型（可以是单个事件或事件数组）
   * @param callback 回调函数（可选，不传则移除该事件的所有监听器）
   */
  off(event: TEvent | TEvent[], callback?: (...args: any[]) => void): void {
    const targetEvents = Array.isArray(event) ? event : [event];
    for (const eventName of targetEvents) {
      if (!this.events.has(eventName)) {
        continue;
      }

      if (typeof callback === 'function') {
        const listeners = this.events.get(eventName)!;
        const index = listeners.indexOf(callback);
        if (index !== -1) {
          listeners.splice(index, 1);
        }
      } else {
        // 移除该事件的所有监听器
        this.events.delete(eventName);
      }
    }
  }

  /**
   * 触发事件
   * @param event 事件类型
   * @param args 事件参数
   */
  protected emit(event: TEvent, ...args: any[]): void {
    const listeners = this.events.get(event);
    if (listeners && listeners.length > 0) {
      // 复制数组，避免在执行过程中修改原数组导致的问题
      const listenersCopy = [...listeners];
      listenersCopy.forEach((callback) => {
        try {
          callback(...args);
        } catch (err) {
          console.error(`Error in event listener for ${event}:`, err);
        }
      });
    }
  }

  /**
   * 触发指定事件（别名方法，用于兼容 base.ts 中的 fire 方法）
   * @param event 事件类型
   * @param args 事件参数
   */
  fire(event: TEvent, ...args: any[]): void {
    this.emit(event, ...args);
  }

  /**
   * 运行事件（别名方法，用于兼容 base.ts 中的 runEvent 方法）
   * @param event 事件类型
   * @param args 事件参数
   */
  runEvent(event: TEvent, ...args: any[]): void {
    this.emit(event, ...args);
  }

  /**
   * 批量移除事件监听
   * @param events 事件类型数组
   * @param callback 回调函数（可选）
   */
  batchOff(events: TEvent[], callback?: (...args: any[]) => void): void {
    for (const event of events) {
      this.off(event, callback);
    }
  }

  /**
   * 清除所有事件监听器
   */
  clearEvents(): void {
    this.events.clear();
  }

  /**
   * 获取指定事件的监听器数量
   * @param event 事件类型
   * @returns 监听器数量
   */
  listenerCount(event: TEvent): number {
    return this.events.get(event)?.length || 0;
  }
}

