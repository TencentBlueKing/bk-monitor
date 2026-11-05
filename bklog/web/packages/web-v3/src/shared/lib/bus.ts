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
 * @file event bus
 * @author  <>
 */

// Vue3 has no instance event API. Preserve the source bus protocol without a Vue2 runtime.
class EventBus {
  constructor() { this.events = Object.create(null); }
  $on(event, callback) {
    if (Array.isArray(event)) event.forEach(name => this.$on(name, callback));
    else (this.events[event] ||= []).push(callback);
    return this;
  }
  $once(event, callback) {
    const once = (...args) => { this.$off(event, once); return callback.apply(this, args); };
    once.original = callback;
    return this.$on(event, once);
  }
  $off(event, callback) {
    if (!arguments.length) { this.events = Object.create(null); return this; }
    if (Array.isArray(event)) { event.forEach(name => this.$off(name, callback)); return this; }
    const handlers = this.events[event];
    if (!handlers) return this;
    if (!callback) { this.events[event] = []; return this; }
    for (let index = handlers.length - 1; index >= 0; index--) {
      if (handlers[index] === callback || handlers[index].original === callback) { handlers.splice(index, 1); break; }
    }
    return this;
  }
  $emit(event, ...args) {
    for (const handler of [...(this.events[event] || [])]) {
      try {
        const result = handler.apply(this, args);
        if (result && typeof result.catch === 'function') result.catch(error => console.error(error));
      } catch (error) { console.error(error); }
    }
    return this;
  }
}
export const bus = new EventBus();
