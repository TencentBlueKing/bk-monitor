/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import JSONBigNumber from 'json-bignumber';

import { sanitizeBidi } from './sanitize-bidi';

export type SearchStreamEvent =
  | { event: 'meta'; [key: string]: any }
  | { event: 'row'; index: number; data: Record<string, any>; origin_data: Record<string, any> }
  | { event: 'done' };

const parseLine = (line: string) => {
  const sanitized = sanitizeBidi(line.trim());
  if (!sanitized) return null;
  return JSONBigNumber.parse(sanitized);
};

// 每处理 LINES_PER_YIELD 行让出一次事件循环，兼顾解析吞吐与不阻塞 worker。
// 逐行 setTimeout(0) 会给每行引入 ~4ms 宏任务延迟，数百行即累计数秒，故改为按批让出。
const LINES_PER_YIELD = 200;
const yieldToLoop = () => new Promise<void>(resolve => setTimeout(resolve, 0));

/**
 * 从字节流按行解析 NDJSON，每行独立 JSON.parse，避免整包落地。
 */
export async function* parseNDJSONByteStream(stream: ReadableStream<Uint8Array>): AsyncGenerator<any> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let linesSinceYield = 0;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let newlineIndex = buffer.indexOf('\n');
      while (newlineIndex >= 0) {
        const line = buffer.slice(0, newlineIndex);
        buffer = buffer.slice(newlineIndex + 1);
        const parsed = parseLine(line);
        if (parsed) {
          yield parsed;
          linesSinceYield += 1;
          if (linesSinceYield >= LINES_PER_YIELD) {
            linesSinceYield = 0;
            await yieldToLoop();
          }
        }
        newlineIndex = buffer.indexOf('\n');
      }
    }

    const tail = parseLine(buffer);
    if (tail) yield tail;
  } finally {
    reader.releaseLock();
  }
}

export const isNDJSONContentType = (contentType = '') =>
  contentType.includes('application/x-ndjson') || contentType.includes('ndjson');

export const isStreamSearchUrl = (url = '') => {
  try {
    return new URL(url).searchParams.get('stream') === 'true';
  } catch {
    return url.includes('stream=true');
  }
};

export const isJsonEnvelopeContentType = (contentType = '') => /application\/json/i.test(contentType);

/**
 * 决定响应体的解析方式。
 *
 * 关键：以「响应真实 content-type」为准，而非请求 URL 的 stream=true 意图。
 * 后端流式响应固定为 application/x-ndjson；若后端实际返回普通 JSON（未走 stream 分支、
 * stream 异常回退、或被中间层缓冲），必须按整包 envelope 解析，否则会把 JSON 当 NDJSON
 * 逐行丢弃，导致 total/took 为 0 且无数据行。
 */
export const shouldUseNDJSONStream = (url = '', contentType = '') => {
  if (isNDJSONContentType(contentType)) {
    return true;
  }
  // 明确是 JSON envelope：即使请求带 stream=true 也按整包解析
  if (isJsonEnvelopeContentType(contentType)) {
    return false;
  }
  // content-type 缺失/不明确时，回退到请求意图
  return isStreamSearchUrl(url);
};

/** 判断解析出的对象是否为普通检索 JSON envelope（非流式 meta/row/done 事件） */
export const isSearchJsonEnvelope = (value: any) =>
  !!value
  && typeof value === 'object'
  && !('event' in value)
  && ('result' in value || 'list' in value || 'origin_log_list' in value || 'data' in value);
