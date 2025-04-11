// OptimizedHighlighter.ts
import Mark from 'mark.js';
import { getTargetElement } from '../hooks/hooks-helper';
import { Ref } from 'vue';
// types.ts
export type ChunkStrategy = 'auto' | 'fixed' | 'custom';
export type ObserverPriority = 'visible-first' | 'order';

export interface ChunkSizeConfig {
  auto?: { maxTextLength: number };
  fixed?: { nodesPerChunk: number };
  custom?: (elements: Element[]) => Element[];
}

export interface ObserverConfig {
  root?: Element | Document | null;
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
    rootMargin: '200px 0px',
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
  private chunkMap = new WeakMap<HTMLElement, { instance: Mark; highlighted: boolean }>();
  private sections: HTMLElement[] = []; // 修正为二维数组
  private pendingQueue: HTMLElement[] = [];
  private isProcessing = false;
  private currentKeywords: KeywordItem[] = [];
  private markKeywords: string[] = [];
  private rootElement: HTMLElement;

  constructor(userConfig: HighlightConfig = { target: document.body }) {
    this.config = this.mergeConfigs(userConfig);
    this.rootElement = getTargetElement(this.config.target);
    this.observer = this.createObserver();
  }

  public highlightElement(target: HTMLElement) {
    if (this.sections.includes(target)) {
      const instance = this.chunkMap.get(target)?.instance;
      instance.unmark();
      this.instanceExecMark(instance);
      return;
    }

    this.sections.push(target);
    const instance = this.initMarkInsntance(target);
    this.chunkMap.set(target, { instance, highlighted: false });
    this.instanceExecMark(instance);
  }

  public async highlight(keywords: KeywordItem[], reset = true): Promise<void> {
    if (reset) {
      this.resetState();
      if (keywords.length === 0) {
        return;
      }
      this.currentKeywords = keywords;
    }

    if (this.currentKeywords.length === 0) {
      return;
    }

    this.markKeywords = this.currentKeywords.map(item => item.text);
    this.prepareSections();
    this.observeSections();
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
  }

  public unmark(
    options: {
      keepObservers?: boolean;
      fastMode?: boolean;
    } = {},
  ): void {
    // 快速模式（仅移除高亮，不恢复DOM）
    if (options.fastMode) {
      this.unmarkChunks();
      this.resetState();
      return;
    }

    // 完整清理
    this.unmarkChunks();
    if (!options.keepObservers) {
      this.observer.disconnect();
    }
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
    return new IntersectionObserver(this.onIntersect.bind(this), {
      root: this.config.observer.root,
      rootMargin: '10% 0px 10% 0px', // 上下扩展 50% 视口
      threshold: Array.from({ length: 101 }, (_, i) => i * 0.01), // 0%-100% 精度1%
    });
  }

  private prepareSections(): void {
    const children = Array.from(this.rootElement.children) as HTMLElement[];

    switch (this.config.chunkStrategy) {
      case 'auto':
        this.sections = this.autoChunk(children);
        break;
      case 'fixed':
        this.sections = this.fixedChunk(children);
        break;
      case 'custom':
        const customChunks = this.config.chunkSize.custom?.(children) || [];
        this.sections = customChunks as HTMLElement[]; // 类型断言
        break;
      default:
        this.sections = [];
    }
  }

  private autoChunk(elements: HTMLElement[]): HTMLElement[] {
    const chunks: HTMLElement[] = [];
    let currentChunk: HTMLElement[] = [];
    let currentLength = 0;

    elements.forEach(el => {
      if (!this.sections.includes(el)) {
        const textLength = el.textContent?.length || 0;
        if (currentLength + textLength > this.config.chunkSize.auto.maxTextLength) {
          currentChunk.forEach(el => chunks.push(el));
          currentChunk = [];
          currentLength = 0;
        }
        currentChunk.push(el);
        currentLength += textLength;
      }
    });

    return chunks;
  }

  private fixedChunk(elements: HTMLElement[]): HTMLElement[] {
    const chunkSize = this.config.chunkSize.fixed.nodesPerChunk;
    const chunks: HTMLElement[] = [];

    for (let i = 0; i < elements.length; i += chunkSize) {
      elements.slice(i, i + chunkSize).forEach(el => {
        if (!this.sections.includes(el)) {
          chunks.push(el);
        }
      });
    }

    return chunks;
  }

  private observeSections(): void {
    this.observer.disconnect();
    this.sections.forEach((section, index) => {
      if (!section.hasAttribute('data-chunk-id')) {
        section.setAttribute('data-chunk-id', index.toString());
        this.observer.observe(section);
      }
    });
  }

  private onIntersect(entries: IntersectionObserverEntry[]): void {
    entries.forEach(entry => {
      const wrapper = entry.target as HTMLElement;
      const chunkId = parseInt(wrapper.dataset.chunkId);

      if (chunkId === -1) return;

      if (entry.isIntersecting) {
        this.addToQueue(wrapper);
        if (!this.isProcessing) this.processQueue();
      }
    });
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
      const element = this.pendingQueue.shift()!;
      if (this.chunkMap.get(element)?.highlighted) continue;

      if (!this.chunkMap.get(element)?.instance) {
        const instance = this.initMarkInsntance(element);

        this.chunkMap.set(element, { instance, highlighted: true });
      }

      await this.highlightChunk(element, this.chunkMap.get(element).instance);
    }

    this.isProcessing = false;
  }

  private instanceExecMark(instance: Mark, resolve?: Function) {
    instance.mark(this.markKeywords, {
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
  }

  private async highlightChunk(element: HTMLElement, instance: Mark): Promise<void> {
    if (!element) return;

    return new Promise(resolve => {
      this.instanceExecMark(instance, resolve);
    });
  }

  private getBackgroundColor(keyword: string | RegExp): string {
    return this.currentKeywords.find(k => k.text === keyword)?.backgroundColor || '';
  }

  private resetState(): void {
    this.pendingQueue = [];
    this.unmarkChunks();
    this.sections = [];
    this.currentKeywords = [];
    this.markKeywords = [];
  }

  private unmarkChunks(): void {
    this.sections.forEach(chunk => {
      if (this.chunkMap.has(chunk)) {
        chunk.removeAttribute('data-chunk-id');
        const { instance } = this.chunkMap.get(chunk)!;
        instance.unmark();

        this.chunkMap.get(chunk).highlighted = false;
        this.chunkMap.delete(chunk);
      }
    });
  }
}
