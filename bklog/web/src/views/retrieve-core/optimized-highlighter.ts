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
import Mark from 'mark.js';

import { getTargetElement } from '../../hooks/hooks-helper';
import StaticUtil from './static.util';

import type { Ref } from 'vue';
// types.ts
export type ChunkStrategy = 'auto' | 'custom' | 'fixed';
export type ObserverPriority = 'order' | 'visible-first';

export interface ChunkSizeConfig {
  auto?: { maxTextLength: number };
  fixed?: { nodesPerChunk: number };
  custom?: (elements: Element[]) => Element[];
}

export interface ObserverConfig {
  root?: Document | Element | null;
  rootMargin?: string;
  thresholds?: number | number[];
  priority?: ObserverPriority;
}

export interface PreloadConfig {
  enable: boolean;
  ahead: number;
}

export interface HighlightConfig {
  chunkStrategy?: ChunkStrategy;
  chunkSize?: ChunkSizeConfig;
  observer?: ObserverConfig;
  preload?: PreloadConfig;
  target: (() => HTMLElement) | HTMLElement | Ref<HTMLElement> | string;
}

export interface KeywordItem {
  text: string;
  className: string;
  backgroundColor: string;
  textReg: RegExp;
}

const DEFAULT_CONFIG: Required<HighlightConfig> = {
  target: document.body,
  chunkStrategy: 'auto',
  chunkSize: {
    auto: { maxTextLength: 5000 },
    fixed: { nodesPerChunk: 15 },
    custom: undefined,
  },
  observer: {
    root: null,
    rootMargin: '0px 0px',
    thresholds: [0, 0.5, 1],
    priority: 'visible-first',
  },
  preload: {
    enable: true,
    ahead: 2,
  },
};

export default class OptimizedHighlighter {
  // private markInstance: Mark;
  private observer: IntersectionObserver;
  private config: Required<HighlightConfig>;
  private chunkMap = new WeakMap<HTMLElement, { instance: Mark; highlighted: boolean; isIntersecting: boolean }>();
  private sections: HTMLElement[] = []; // 修正为二维数组
  private pendingQueue: HTMLElement[] = [];
  private isProcessing = false;
  private currentKeywords: KeywordItem[] = [];
  private markKeywords: string[] = [];
  private rootElement: () => HTMLElement;

  // 是否区分大小写
  private caseSensitive = false;
  private afterMarkFn: (() => void) | undefined;
  // 正则表达式标记
  private regExpMark = false;
  private accuracy: 'exactly' | 'partially' = 'partially';

  constructor(userConfig: HighlightConfig = { target: document.body }) {
    this.config = this.mergeConfigs(userConfig);
    this.rootElement = () => getTargetElement(this.config.target);
    this.observer = this.createObserver();
  }

  /**
   * 获取当前标记选项
   * @description 获取当前标记选项，包括大小写敏感、正则表达式标记和精确度
   * @returns
   */
  public getMarkOptions() {
    return {
      caseSensitive: this.caseSensitive,
      regExpMark: this.regExpMark,
      accuracy: this.accuracy,
    };
  }

  /**
   * 设置是否区分大小写
   * @param caseSensitive - 是否区分大小写
   * @param caseSensitive
   */
  public setCaseSensitive(caseSensitive: boolean): void {
    if (this.caseSensitive !== caseSensitive) {
      // 如果大小写敏感状态发生变化，重置当前关键词
      this.caseSensitive = caseSensitive;
      this.highlight(this.currentKeywords, true, this.afterMarkFn);
    }
  }

  public setRegExpMode(regExpMark: boolean): void {
    if (this.regExpMark !== regExpMark) {
      // 如果正则表达式标记状态没有变化，则不需要重新标记
      this.regExpMark = regExpMark;
      this.highlight(this.currentKeywords, true, this.afterMarkFn);
    }
  }

  public setAccuracy(accuracy: 'exactly' | 'partially'): void {
    if (this.accuracy !== accuracy) {
      // 如果精确度状态没有变化，则不需要重新标记
      this.accuracy = accuracy;
      this.highlight(this.currentKeywords, true, this.afterMarkFn);
    }
  }

  public setObserverConfig(observerConfig: ObserverConfig): void {
    Object.assign(this.config.observer, observerConfig);
  }

  public highlightElement(target: HTMLElement) {
    if (this.currentKeywords.length === 0) {
      return;
    }

    if (this.sections.includes(target)) {
      const instance = this.chunkMap.get(target)?.instance;
      instance.unmark();
      this.instanceExecMark(instance);
      return;
    }

    this.sections.push(target);
    const instance = this.initMarkInsntance(target);
    this.chunkMap.set(target, { instance, highlighted: false, isIntersecting: true });
    this.instanceExecMark(instance);
  }

  public unMarkElement(target: HTMLElement) {
    const chunk = this.chunkMap.get(target);
    if (chunk) {
      chunk.instance?.unmark();
      chunk.isIntersecting = false;
    }
  }
  public highlight(keywords: KeywordItem[], reset = true, afterMarkFn?: () => void): Promise<void> {
    this.afterMarkFn = afterMarkFn;
    if (reset) {
      this.resetState();
      if (keywords.length === 0) {
        return Promise.resolve();
      }
      this.currentKeywords = keywords;
    }

    if (this.currentKeywords.length === 0) {
      return Promise.resolve();
    }

    this.markKeywords = this.currentKeywords.map(item => item.text);
    this.prepareSections();
    this.observeSections();
    for (const element of this.sections) {
      const chunk = this.chunkMap.get(element);
      if (chunk && !chunk.highlighted && chunk.isIntersecting) {
        this.instanceExecMark(chunk.instance);
        this.afterMarkFn?.();
      }
    }
    return Promise.resolve();
  }

  /**
   * 增量更新
   */
  public incrementalUpdate() {
    this.prepareSections();
    this.observeSections();
  }

  public destroy(): void {
    this.observer.disconnect();
    this.unmarkChunks();
    this.resetState();
    this.caseSensitive = false;
    this.regExpMark = false;
    this.accuracy = 'partially';
  }

  public unmark(): void {
    // 完整清理
    this.unmarkChunks();
    this.resetState();
  }

  private initMarkInsntance(target: HTMLElement) {
    return new Mark(target, {
      acrossElements: true, // 允许跨元素匹配
      separateWordSearch: false, // 禁用单词拆分
    });
  }

  private mergeConfigs(userConfig: HighlightConfig): Required<HighlightConfig> {
    return {
      ...DEFAULT_CONFIG,
      ...userConfig,
      chunkSize: {
        ...DEFAULT_CONFIG.chunkSize,
        ...userConfig.chunkSize,
      },
      observer: {
        ...DEFAULT_CONFIG.observer,
        ...userConfig.observer,
      },
      preload: {
        ...DEFAULT_CONFIG.preload,
        ...userConfig.preload,
      },
    };
  }

  private createObserver(): IntersectionObserver {
    return new IntersectionObserver(this.onIntersect.bind(this), { ...this.config.observer });
  }

  private prepareSections(): void {
    const children = Array.from(this.rootElement()?.children || []) as HTMLElement[];
    for (const el of children) {
      if (!this.sections.includes(el)) {
        this.sections.push(el);
      }
    }
  }

  private observeSections(): void {
    this.sections.forEach((section, index) => {
      if (!section.hasAttribute('data-chunk-id')) {
        section.setAttribute('data-chunk-id', index.toString());
        this.observer.observe(section);
      }
    });
  }

  private onIntersect(entries: IntersectionObserverEntry[]): void {
    for (const entry of entries) {
      const wrapper = entry.target as HTMLElement;
      const chunkId = Number.parseInt(wrapper.dataset.chunkId, 10);

      if (chunkId === -1) {
        continue;
      }

      if (entry.isIntersecting) {
        this.addToQueue(wrapper);
        if (!this.isProcessing) {
          this.processQueue();
        }
      }

      const chunk = this.chunkMap.get(wrapper);
      if (chunk) {
        chunk.isIntersecting = entry.isIntersecting;
      }
    }
  }

  private addToQueue(target: HTMLElement): void {
    if (this.config.observer.priority === 'visible-first') {
      this.pendingQueue.unshift(target);
    } else {
      this.pendingQueue.push(target);
    }
  }

  private async processQueue(): Promise<void> {
    this.isProcessing = true;

    while (this.pendingQueue.length > 0) {
      const element = this.pendingQueue.shift();
      if (element) {
        if (this.chunkMap.get(element)?.highlighted) {
          continue;
        }

        if (!this.chunkMap.get(element)?.instance) {
          const instance = this.initMarkInsntance(element);
          this.chunkMap.set(element, { instance, highlighted: true, isIntersecting: true });
        }

        await this.highlightChunk(element, this.chunkMap.get(element).instance);
      }
    }

    this.isProcessing = false;
  }

  private instanceExecMark(instance: Mark, resolve?: () => void): void {
    if (this.regExpMark) {
      const flag = this.caseSensitive ? 'g' : 'gi';
      const fullMatch = this.accuracy === 'exactly';
      const formatRegStr = false;
      const regList = this.markKeywords.map(keyword => StaticUtil.getRegExp(keyword, flag, fullMatch, formatRegStr));
      instance.markRegExp(regList[0], {
        element: 'mark',
        exclude: ['mark'],
        done: resolve ?? (() => {}),
        each: (element: HTMLElement) => {
          if (element.parentElement?.classList.contains('valid-text')) {
            element.classList.add('valid-text');
          }
          const backgroundColor = this.getBackgroundColor(element.textContent);
          if (backgroundColor) {
            element.style.backgroundColor = backgroundColor;
          }
        },
      });

      return;
    }

    instance.mark(this.markKeywords, {
      element: 'mark',
      exclude: ['mark'],
      caseSensitive: this.caseSensitive ?? false,
      accuracy: this.accuracy ?? 'partially',
      acrossElements: true,
      done: resolve ?? (() => {}),
      each: (element: HTMLElement) => {
        if (element.parentElement?.classList.contains('valid-text')) {
          element.classList.add('valid-text');
        }
        const backgroundColor = this.getBackgroundColor(element.textContent);
        if (backgroundColor) {
          element.style.backgroundColor = backgroundColor;
        }
      },
    });
  }

  private highlightChunk(element: HTMLElement, instance: Mark): Promise<void> {
    if (!element) {
      return Promise.resolve();
    }

    return new Promise(resolve => {
      this.instanceExecMark(instance, resolve);
    });
  }

  private getBackgroundColor(keyword: string): string {
    return this.currentKeywords.find(k => k.textReg.test(keyword))?.backgroundColor || '';
  }

  private resetState(): void {
    this.pendingQueue = [];
    this.unmarkChunks();
    this.currentKeywords = [];
    this.markKeywords = [];
  }

  private unmarkChunks(): void {
    for (const chunk of this.sections) {
      if (this.chunkMap.has(chunk)) {
        const chunkInfo = this.chunkMap.get(chunk);
        if (chunkInfo) {
          const { instance } = chunkInfo;
          instance.unmark();
          this.chunkMap.get(chunk).highlighted = false;
        }
      }
    }
  }
}
