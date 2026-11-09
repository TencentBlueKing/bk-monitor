/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
declare module 'js-cookie' {
  interface Attributes { expires?: number | Date; path?: string; domain?: string; secure?: boolean; sameSite?: 'strict' | 'lax' | 'none' | 'Strict' | 'Lax' | 'None'; }
  interface Cookies {
    get(): Record<string, string>;
    get(name: string): string | undefined;
    set(name: string, value: string, attributes?: Attributes): string | undefined;
    remove(name: string, attributes?: Attributes): void;
  }
  const cookies: Cookies;
  export default cookies;
}
declare module 'throttle-debounce' {
  type Callback = (...args: never[]) => unknown;
  type Cancelable<T extends Callback> = T & { cancel(options?: { upcomingOnly?: boolean }): void };
  export function debounce<T extends Callback>(delay: number, callback: T, options?: { atBegin?: boolean }): Cancelable<T>;
  export function throttle<T extends Callback>(delay: number, callback: T, options?: { noTrailing?: boolean; noLeading?: boolean; debounceMode?: boolean }): Cancelable<T>;
}
declare module 'json-bigint' {
  interface JSONBig { parse: typeof JSON.parse; stringify: typeof JSON.stringify; }
  function create(options?: { strict?: boolean; storeAsString?: boolean; alwaysParseAsBig?: boolean; useNativeBigInt?: boolean }): JSONBig;
  namespace create { const parse: typeof JSON.parse; const stringify: typeof JSON.stringify; }
  export default create;
}
declare module 'json-bignumber' {
  const json: { parse: typeof JSON.parse; stringify: typeof JSON.stringify };
  export default json;
}
declare module 'vue-text-highlight' {
  import type { DefineComponent } from 'vue';
  const TextHighlight: DefineComponent<{ queries?: string | string[]; caseSensitive?: boolean; highlightStyle?: object; highlightClass?: string; wholeWordMatch?: boolean }>;
  export default TextHighlight;
}
declare module '@blueking/log-web' {
  const manifest: Record<string, string | string[]>;
  export default manifest;
}
declare module 'tiny-pinyin/dist/patchers/56l.js' {
  const patcher: import('tiny-pinyin').Patcher & { shouldPatch(toToken: (text: string) => unknown): boolean };
  export = patcher;
}
declare module '@blueking/notice-component' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<{ apiUrl?: string; onShowAlertChange?: (isShow: boolean) => void }>;
  export default component;
}
declare module '@blueking/platform-config' {
  export interface PlatformConfig { name?: string; nameEn?: string; brandName?: string; brandNameEn?: string; favicon?: string; i18n?: { name?: string }; [key: string]: unknown; }
  export function getPlatformConfig(url: string, initial: PlatformConfig): Promise<PlatformConfig>;
  export function getPlatformConfig(initial: PlatformConfig): Promise<PlatformConfig>;
  export function setShortcutIcon(url?: string): void;
  export function setDocumentTitle(i18n?: { name?: string }): void;
}
declare module 'mark.js' {
  interface MarkOptions { className?: string; element?: string; separateWordSearch?: boolean; caseSensitive?: boolean; accuracy?: string | object; acrossElements?: boolean; exclude?: string[]; diacritics?: boolean; done?: (count: number) => void; each?: (element: HTMLElement) => void; filter?: (...args: unknown[]) => boolean; }
  class Mark {
    constructor(context: Element | Element[] | NodeList | string);
    mark(keyword: string | string[], options?: MarkOptions): void;
    markRegExp(expression: RegExp, options?: MarkOptions): void;
    unmark(options?: Pick<MarkOptions, 'element' | 'className' | 'exclude'> & { done?: () => void }): void;
  }
  export default Mark;
}
declare module '@blueking/user-selector' {
  import type { DefineComponent } from 'vue';
  const UserSelector: DefineComponent<{ value?: string | string[]; api?: string; multiple?: boolean; placeholder?: string; disabled?: boolean; fixedHeight?: boolean; emptyText?: string; onChange?: (value: string[]) => void; onInput?: (value: string[]) => void }>;
  export default UserSelector;
}
declare module '@blueking/ip-selector/dist/vue3.x' {
  import type { DefineComponent } from 'vue';
  const IpSelector: DefineComponent<{ value?: object; config?: object; onChange?: (value: object) => void; onConfirm?: (value: object) => void }> & { compatConfig?: { MODE: number } };
  export default IpSelector;
}

// The bare entry exposes the original pure matcher without document/style
// injection. Only this computed function is reused; its Vue2 renderer is not.
declare module 'vue-text-highlight/dist/component.js' {
  const source: {
    computed: {
      highlights: (this: {
        text: string;
        queries: string | RegExp | Array<string | RegExp>;
        caseSensitive?: boolean;
        diacriticsSensitive?: boolean;
      }) => Array<{text: string; isHighlighted: boolean; highlightIndex?: number}>;
    };
  };
  export default source;
}
