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
  custom?: (_elements: Element[]) => Element[];
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

  /**
   * 检查关键字是否包含可能导致 mark.js 拆分的特殊字符
   * @param keyword 关键字
   * @returns 是否包含特殊字符
   */
  private hasSpecialChars(keyword: string): boolean {
    // 检查是否包含可能被 mark.js 当作单词边界处理的字符
    // 包括 : - _ 等，这些字符可能导致关键字被拆分成多个部分
    return /[:;_-|]/.test(keyword);
  }

  /**
   * 检查文本是否匹配某个关键词
   * @param text 要检查的文本
   * @returns 匹配的关键词项，如果没有匹配则返回 null
   */
  private findMatchedKeyword(text: string): KeywordItem | null {
    if (!text) {
      return null;
    }

    const normalizedText = text.trim();
    // 首先尝试精确匹配
    const exactMatch = this.currentKeywords.find((k) => {
      const normalizedKeyword = k.text.trim();
      return normalizedText === normalizedKeyword || normalizedText.toLowerCase() === normalizedKeyword.toLowerCase();
    });

    if (exactMatch) {
      return exactMatch;
    }

    // 如果没有精确匹配，尝试正则匹配
    return this.currentKeywords.find(k => k.textReg.test(normalizedText)) || null;
  }

  /**
   * 处理连续的 mark 元素，统一应用颜色
   * 当文本被拆分成多个 span 元素时（如 19:06:24 被拆成 19, :, 06, :, 24），
   * 需要检测连续的 mark 元素，组合它们的内容来匹配完整的关键字
   * 对于独立的相邻关键词（如 INFO 和 Error），即使它们在 DOM 中连续，也应该分别处理
   * @param container 包含 mark 元素的容器
   */
  private processConsecutiveMarks(container: HTMLElement): void {
    if (!container) {
      return;
    }

    const markElements = Array.from(container.querySelectorAll('mark')) as HTMLElement[];
    if (markElements.length === 0) {
      return;
    }

    // 按 DOM 顺序排序
    const sortedMarks = markElements.sort((a, b) => {
      const position = a.compareDocumentPosition(b);
      if (position & Node.DOCUMENT_POSITION_FOLLOWING) {
        return -1;
      }
      if (position & Node.DOCUMENT_POSITION_PRECEDING) {
        return 1;
      }
      return 0;
    });

    // 第一步：找出所有连续的区域（不考虑匹配）
    const consecutiveRanges: Array<{ start: number; end: number }> = [];
    let rangeStart = 0;

    for (let i = 0; i < sortedMarks.length; i++) {
      if (i === 0) {
        rangeStart = 0;
      } else {
        const previous = sortedMarks[i - 1];
        const current = sortedMarks[i];
        if (!this.areConsecutiveElements(previous, current)) {
          // 不连续，保存之前的范围
          if (i > rangeStart) {
            consecutiveRanges.push({ start: rangeStart, end: i - 1 });
          }
          rangeStart = i;
        }
      }
    }
    // 保存最后一个范围
    if (rangeStart < sortedMarks.length) {
      consecutiveRanges.push({ start: rangeStart, end: sortedMarks.length - 1 });
    }

    // 第二步：对每个连续范围进行智能分组（使用动态规划找到最优分组）
    const finalGroups: HTMLElement[][] = [];

    for (const range of consecutiveRanges) {
      const rangeMarks = sortedMarks.slice(range.start, range.end + 1);
      if (rangeMarks.length === 0) {
        continue;
      }

      // 使用动态规划找到最优分组
      // dp[i] 表示处理到第 i 个元素时的最优分组方案
      interface DpState {
        groups: HTMLElement[][];
        matchedCount: number;
        score: number; // 综合评分：匹配数量 + 优先级
      }

      const dp: DpState[] = [];
      dp[0] = { groups: [], matchedCount: 0, score: 0 };

      for (let i = 1; i <= rangeMarks.length; i++) {
        let best: DpState = { groups: [], matchedCount: 0, score: -1 };

        // 尝试所有可能的结束位置 j，将 [j, i) 作为一个组
        for (let j = 0; j < i; j++) {
          const group = rangeMarks.slice(j, i);
          const groupText = group.map(el => el.textContent || '').join('');
          const match = this.findMatchedKeyword(groupText);

          const prevState = dp[j];
          const newGroups: HTMLElement[][] = [...prevState.groups];
          let newMatchedCount = prevState.matchedCount;
          let newScore = prevState.score;

          if (match) {
            // 这个组能匹配一个关键词，加入分组
            newGroups.push(group);
            newMatchedCount += 1;
            newScore += 10000; // 匹配的关键词优先级最高
          } else {
            // 这个组不能匹配
            if (group.length === 1) {
              // 单个元素
              const singleMatch = this.findMatchedKeyword(group[0].textContent || '');
              if (singleMatch) {
                // 单个元素能匹配，加入分组
                newGroups.push(group);
                newMatchedCount += 1;
                newScore += 10000;
              } else {
                // 单个元素不能匹配，也要加入（可能是分隔符等）
                newGroups.push(group);
              }
            } else {
              // 多个元素且不能匹配
              // 检查是否每个元素单独都能匹配（独立关键词的情况）
              const allSeparateMatch = group.every((el) => {
                const elText = el.textContent || '';
                return this.findMatchedKeyword(elText) !== null;
              });

              if (allSeparateMatch) {
                // 每个元素单独都能匹配，应该分开处理
                for (const el of group) {
                  newGroups.push([el]);
                }
                newMatchedCount += group.length;
                newScore += group.length * 10000;
              } else {
                // 不是所有元素都能单独匹配，可能是被拆分的关键词的一部分
                // 暂时作为一个组，但不增加匹配计数（可能是部分匹配）
                newGroups.push(group);
                // 不增加匹配计数，也不增加评分
              }
            }
          }

          // 更新最佳方案：优先匹配数量，其次评分
          if (newMatchedCount > best.matchedCount || (newMatchedCount === best.matchedCount && newScore > best.score)) {
            best = {
              groups: newGroups,
              matchedCount: newMatchedCount,
              score: newScore,
            };
          }
        }

        dp[i] = best;
      }

      // 将最优分组加入最终结果
      finalGroups.push(...dp[rangeMarks.length].groups);
    }

    // 第三步：为每个组应用颜色
    for (const group of finalGroups) {
      const combinedText = group.map(el => el.textContent || '').join('');
      const matchedKeywordItem = this.findMatchedKeyword(combinedText);

      if (matchedKeywordItem?.backgroundColor) {
        for (const element of group) {
          element.style.backgroundColor = matchedKeywordItem.backgroundColor;
        }
      }
    }
  }

  /**
   * 判断两个元素是否连续（相邻）
   * @param el1 第一个元素
   * @param el2 第二个元素
   * @returns 是否连续
   */
  private areConsecutiveElements(el1: HTMLElement, el2: HTMLElement): boolean {
    // 检查是否是同一个父元素的相邻子节点
    if (el1.parentElement === el2.parentElement) {
      let node = el1.nextSibling;
      while (node) {
        if (node === el2) {
          return true;
        }
        // 跳过文本节点（即使包含非空白字符，只要不是其他元素节点就继续）
        if (node.nodeType === Node.TEXT_NODE) {
          node = node.nextSibling;
        } else if (node.nodeType === Node.ELEMENT_NODE) {
          // 如果是 mark 元素，继续查找（因为可能跨多个 mark 元素）
          if ((node as HTMLElement).tagName === 'MARK') {
            node = node.nextSibling;
          } else {
            // 遇到非 mark 元素节点，说明不连续
            break;
          }
        } else {
          break;
        }
      }
    }

    // 如果 el1 和 el2 不在同一个父元素下，检查 el1 的最后一个文本节点是否紧接着 el2
    // 这种情况可能发生在跨元素匹配时
    const range = document.createRange();
    range.setStartAfter(el1);
    range.setEndBefore(el2);
    const text = range.toString();
    // 如果两个元素之间的文本只包含空白字符或空，则认为连续
    return !text || !text.trim();
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

    // 检查是否有包含特殊字符的关键字
    const hasSpecialCharKeywords = this.markKeywords.some(keyword => this.hasSpecialChars(keyword));

    // 如果有包含特殊字符的关键字，使用正则表达式模式来确保完整匹配
    if (hasSpecialCharKeywords) {
      const flag = this.caseSensitive ? 'g' : 'gi';

      // 将多个关键字合并成一个正则表达式，使用 | 分隔
      // 使用命名捕获组来标识匹配的关键字
      // 手动转义特殊字符，确保完整匹配（不拆分）
      const combinedPattern = this.currentKeywords
        .map((keywordItem, index) => {
          const escapedKeyword = keywordItem.text.replace(/([.*+?^${}()|[\]\\])/g, '\\$1');
          return `(?<keyword${index}>${escapedKeyword})`;
        })
        .join('|');

      const combinedRegex = new RegExp(combinedPattern, flag);

      instance.markRegExp(combinedRegex, {
        element: 'mark',
        exclude: ['mark'],
        acrossElements: true,
        done: () => {
          // 在所有标记完成后，处理连续的 mark 元素
          // 从 sections 中查找对应的容器元素
          let container: HTMLElement | null = null;
          for (const section of this.sections) {
            const chunk = this.chunkMap.get(section);
            if (chunk?.instance === instance) {
              container = section;
              break;
            }
          }

          // 如果找不到，尝试从第一个 mark 元素获取容器
          // 检查 instance.context 是否存在，可能在处理过程中 DOM 已被移除或替换
          if (!container && instance.context) {
            const firstMark = instance.context.querySelector('mark') as HTMLElement;
            if (firstMark) {
              container = (firstMark.closest('[data-chunk-id]') as HTMLElement) || (instance.context as HTMLElement);
            } else {
              // 如果找不到 mark 元素，使用 context 本身作为容器
              container = instance.context as HTMLElement;
            }
          }

          if (container) {
            this.processConsecutiveMarks(container);
          }
          resolve?.();
        },
        each: (element: HTMLElement) => {
          if (element.parentElement?.classList.contains('valid-text')) {
            element.classList.add('valid-text');
          }

          // 初始颜色设置，后续会在 processConsecutiveMarks 中统一处理
          const matchedText = element.textContent || '';
          const matchedKeywordItem = this.currentKeywords.find((k) => {
            const normalizedText = matchedText.trim();
            const normalizedKeyword = k.text.trim();
            return (
              normalizedText === normalizedKeyword || normalizedText.toLowerCase() === normalizedKeyword.toLowerCase()
            );
          });

          const keywordItem = matchedKeywordItem || this.currentKeywords.find(k => k.textReg.test(matchedText));

          if (keywordItem?.backgroundColor) {
            element.style.backgroundColor = keywordItem.backgroundColor;
          }
        },
      });

      return;
    }

    // 没有特殊字符时，使用原来的字符串匹配方式
    instance.mark(this.markKeywords, {
      element: 'mark',
      exclude: ['mark'],
      caseSensitive: this.caseSensitive ?? false,
      accuracy: this.accuracy ?? 'partially',
      acrossElements: true,
      done: () => {
        // 在所有标记完成后，处理连续的 mark 元素
        // 获取容器元素（通过查找第一个 mark 元素的根容器）
        // 检查 instance.context 是否存在，可能在处理过程中 DOM 已被移除或替换
        if (instance.context) {
          const firstMark = instance.context.querySelector('mark') as HTMLElement;
          if (firstMark) {
            // 获取包含所有 mark 元素的容器
            const container = instance.context as HTMLElement;
            this.processConsecutiveMarks(container);
          }
        }
        resolve?.();
      },
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

    return new Promise((resolve) => {
      this.instanceExecMark(instance, resolve);
    });
  }

  private getBackgroundColor(keyword: string): string {
    if (!keyword) {
      return '';
    }

    // 首先尝试精确匹配（文本内容与关键字文本完全相等）
    const exactMatch = this.currentKeywords.find((k) => {
      const normalizedText = keyword.trim();
      const normalizedKeyword = k.text.trim();
      return normalizedText === normalizedKeyword || normalizedText.toLowerCase() === normalizedKeyword.toLowerCase();
    });

    if (exactMatch) {
      return exactMatch.backgroundColor;
    }

    // 如果没有精确匹配，按关键字在数组中的顺序查找第一个匹配的正则表达式
    // 这样可以保持用户输入的顺序，确保颜色匹配的一致性
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
