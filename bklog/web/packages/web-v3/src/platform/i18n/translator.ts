/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { toDisplayString } from 'vue';
export type ApplicationLocale = 'zh-cn' | 'en';
export type TranslationValues = readonly unknown[] | Record<string, unknown>;
export interface TranslationOptions { locale?: string; plural?: number; default?: string; }
export type CompiledMessage = (inputs: Record<string, unknown>, options: { locale: ApplicationLocale }) => string;
export type MessageResolver = (key: string) => CompiledMessage | undefined;

function interpolationValue(value: unknown): unknown {
  return value === undefined || value === null ? '' : typeof value === 'object' ? toDisplayString(value) : value;
}
/** Match source fallback interpolation without interpreting content as HTML. */
export function formatFallbackMessage(message: string, values: Record<string, unknown>): string {
  return message.replace(/\{(?:'([^']*)'|([\w$]+))\}/g, (_, literal: string | undefined, name: string | undefined) =>
    literal ?? String(interpolationValue(name === undefined ? undefined : values[name])));
}

export function createTranslator(resolve: MessageResolver, getLocale: () => ApplicationLocale) {
  return function translate(key: string, values?: TranslationValues | number | string, options?: TranslationOptions): string {
    const normalized: Record<string, unknown> = Object.create(null);
    if (Array.isArray(values)) values.forEach((value, index) => { normalized[index] = interpolationValue(value); });
    else if (values && typeof values === 'object') {
      for (const [name, value] of Object.entries(values)) normalized[name] = interpolationValue(value);
    } else if (typeof values === 'number') { normalized.count = values; normalized.n = values; }
    if (options?.plural !== undefined) {
      normalized.count ??= options.plural;
      normalized.n ??= options.plural;
    }
    // Compiled functions read their declared variables directly. Missing source
    // parameters render empty text, including missing rich-text trailing slots.
    const inputs = new Proxy(normalized, { get: (target, name) => Object.hasOwn(target, name) ? Reflect.get(target, name) : '' });
    const locale = options?.locale === 'en' ? 'en' : options?.locale ? 'zh-cn' : getLocale();
    const message = resolve(key);
    return message ? message(inputs, { locale }) : formatFallbackMessage(options?.default ?? (typeof values === 'string' ? values : key), normalized);
  };
}
export type TranslateFunction = ReturnType<typeof createTranslator>;
