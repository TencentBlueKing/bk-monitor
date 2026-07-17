/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import JSONBigNumber from 'json-bignumber';

import { retrieveRowRepository } from '../repositories/retrieve-row.repository';
import { cloneSearchMeta } from '../utils/clone-search-value';
import { isSearchJsonEnvelope, parseNDJSONByteStream, shouldUseNDJSONStream } from '../utils/ndjson-stream';
import {
  categorizeIngestError,
  // logRetrieveSearchIngest,
  type RetrieveSearchIngestStage,
} from '../utils/retrieve-search-ingest.logger';
import { sanitizeBidi } from '../utils/sanitize-bidi';

interface SearchStreamMessage {
  body?: Record<string, any>;
  fieldMetadata?: Record<string, any>;
  fieldNames?: string[];
  headers?: Record<string, string>;
  id: string;
  method?: string;
  pageInstanceId?: string;
  queryKey?: string;
  startSeq?: number;
  type: 'cancel' | 'ping' | 'search-stream';
  url?: string;
  writeMode?: 'append' | 'replace';
}

interface ActiveSearchTask {
  abortController: AbortController;
}

const activeTasks = new Map<string, ActiveSearchTask>();

const taskKey = (message: Pick<SearchStreamMessage, 'id' | 'pageInstanceId'>) => [message.pageInstanceId || 'legacy', message.id].join(':');

const postMessageSafe = (payload: Record<string, any>) => {
  self.postMessage(payload);
};

const postProgress = (id: string, stage: string, extra: Record<string, any> = {}) => {
  postMessageSafe({ id, ok: true, progress: true, stage, ...extra });
};

const postFailure = (
  id: string,
  error: any,
  stage: RetrieveSearchIngestStage,
  context: Record<string, any> = {},
) => {
  const errorCategory = categorizeIngestError(error);
  const message = error?.message || String(error);
  // logRetrieveSearchIngest('error', `worker search failed at ${stage}: ${message}`, {
  //   ...context,
  //   errorCategory,
  //   source: 'worker',
  //   stage,
  // });
  postMessageSafe({
    id,
    ok: false,
    error: `[${stage}] ${message}`,
    errorCategory,
    stage,
    ...context,
  });
};

const parseJsonEnvelope = async (response: Response) => {
  const text = sanitizeBidi(await response.text());
  return JSONBigNumber.parse(text);
};

const ingestJsonEnvelopeRows = async (
  message: SearchStreamMessage,
  envelope: Record<string, any>,
  timings: Record<string, number>,
) => {
  const data = envelope?.data;
  if (!envelope?.result || !data) {
    return {
      response: {
        code: envelope?.code,
        data: cloneSearchMeta(data),
        message: envelope?.message,
        permission: cloneSearchMeta(envelope?.permission),
        result: !!envelope?.result,
      },
      rowKeys: [] as string[],
      size: 0,
      timings,
    };
  }

  const renderRows = data.list;
  const originRows = data.origin_log_list;
  if (!Array.isArray(renderRows) || !Array.isArray(originRows)) {
    throw Object.assign(new Error('Invalid search response: list and origin_log_list are required'), { stage: 'parse' });
  }

  const writeStartedAt = Date.now();
  const rowKeys = message.writeMode === 'append'
    ? await retrieveRowRepository.appendRows(message.queryKey!, originRows, message.startSeq || 0, {
      fieldMetadata: message.fieldMetadata || {},
      fieldNames: message.fieldNames || [],
      renderRows,
    })
    : await retrieveRowRepository.replaceRows(message.queryKey!, originRows, message.startSeq || 0, {
      fieldMetadata: message.fieldMetadata || {},
      fieldNames: message.fieldNames || [],
      renderRows,
    });
  timings.write = Date.now() - writeStartedAt;

  const meta = { ...data };
  delete meta.list;
  delete meta.origin_log_list;

  return {
    response: {
      code: envelope.code,
      data: cloneSearchMeta(meta),
      message: envelope.message,
      permission: cloneSearchMeta(envelope.permission),
      result: true,
    },
    rowKeys,
    size: originRows.length,
    timings,
  };
};

const ingestNDJSONStream = async (
  message: SearchStreamMessage,
  response: Response,
  timings: Record<string, number>,
) => {
  if (!response.body) {
    throw Object.assign(new Error('Search stream response body is empty'), { stage: 'fetch' });
  }

  const writer = retrieveRowRepository.createStreamWriter(message.queryKey!, message.startSeq || 0, {
    fieldMetadata: message.fieldMetadata || {},
    fieldNames: message.fieldNames || [],
    writeMode: message.writeMode || 'replace',
  });

  let metaPayload: Record<string, any> | null = null;
  let rowCount = 0;
  const streamStartedAt = Date.now();

  for await (const event of parseNDJSONByteStream(response.body)) {
    if (!event || typeof event !== 'object') continue;

    // 兜底：响应实际不是 NDJSON（后端未流式返回或 content-type 丢失），
    // 在尚未处理任何 meta/row 事件时探测到 JSON envelope，则按整包解析，避免数据被静默丢弃。
    if (metaPayload === null && rowCount === 0 && isSearchJsonEnvelope(event)) {
      // logRetrieveSearchIngest('warn', 'search response is JSON envelope, fallback from NDJSON parsing', {
      //   queryKey: message.queryKey,
      //   source: 'worker',
      //   stage: 'parse',
      // });
      timings.stream = Date.now() - streamStartedAt;
      return ingestJsonEnvelopeRows(message, event, timings);
    }

    if (event.event === 'meta') {
      const { event: _event, ...meta } = event;
      metaPayload = meta;
      await writer.init();
      postProgress(message.id, 'meta', {
        meta: cloneSearchMeta(metaPayload),
        queryKey: message.queryKey,
        rowCount: 0,
        rowKeys: [],
      });
      continue;
    }

    if (event.event === 'row') {
      const pageIndex = Number(event.index);
      const originRow = event.origin_data ?? event.data;
      const renderRow = event.data;
      if (!Number.isFinite(pageIndex) || !originRow) {
        continue;
      }
      await writer.appendRow(pageIndex, originRow, renderRow);
      rowCount += 1;
      // 首行尽快反馈用于列宽布局；完整行列表在 done 后一次性提交，避免流式过程中反复重排表格。
      if (rowCount === 1) {
        postProgress(message.id, 'row', {
          queryKey: message.queryKey,
          rowCount,
          rowKeys: writer.getPartialRowKeys(),
        });
      }
      continue;
    }

    if (event.event === 'done') {
      break;
    }
  }

  timings.stream = Date.now() - streamStartedAt;
  const writeStartedAt = Date.now();
  const rowKeys = await writer.finish();
  timings.write = Date.now() - writeStartedAt;

  return {
    response: {
      code: undefined,
      data: cloneSearchMeta(metaPayload || {}),
      message: undefined,
      permission: undefined,
      result: true,
    },
    rowKeys,
    size: rowKeys.length,
    timings,
  };
};

const runSearchStream = async (message: SearchStreamMessage) => {
  const startedAt = Date.now();
  const timings: Record<string, number> = {};
  const abortController = new AbortController();
  activeTasks.set(taskKey(message), { abortController });

  // logRetrieveSearchIngest('info', 'worker search stream started', {
  //   queryKey: message.queryKey,
  //   source: 'worker',
  //   stage: 'start',
  //   writeMode: message.writeMode,
  // });

  try {
    if (!message.url || !message.queryKey) {
      throw Object.assign(new Error('Invalid search-stream message: missing url or queryKey'), { stage: 'prepare' });
    }

    postProgress(message.id, 'fetching', { queryKey: message.queryKey });
    const fetchStartedAt = Date.now();
    const response = await fetch(message.url, {
      body: JSON.stringify(message.body || {}),
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(message.headers || {}),
      },
      method: message.method || 'POST',
      signal: abortController.signal,
    });
    timings.fetch = Date.now() - fetchStartedAt;

    const contentType = response.headers.get('content-type') || '';
    if (!response.ok) {
      const envelope = await parseJsonEnvelope(response);
      postMessageSafe({
        id: message.id,
        ok: true,
        response: {
          code: envelope?.code,
          data: cloneSearchMeta(envelope?.data),
          message: envelope?.message || `Search request failed with status ${response.status}`,
          permission: cloneSearchMeta(envelope?.permission),
          result: !!envelope?.result,
        },
        rowKeys: [],
        size: 0,
        timings: { ...timings, total: Date.now() - startedAt },
      });
      return;
    }

    let resultPayload;
    if (shouldUseNDJSONStream(message.url, contentType)) {
      resultPayload = await ingestNDJSONStream(message, response, timings);
    } else {
      const envelope = await parseJsonEnvelope(response);
      resultPayload = await ingestJsonEnvelopeRows(message, envelope, timings);
    }

    postMessageSafe({
      id: message.id,
      ok: true,
      ...resultPayload,
      timings: {
        ...resultPayload.timings,
        total: Date.now() - startedAt,
      },
    });

    // logRetrieveSearchIngest('info', 'worker search stream completed', {
    //   durationMs: Date.now() - startedAt,
    //   queryKey: message.queryKey,
    //   rowCount: resultPayload.size,
    //   source: 'worker',
    //   stage: 'complete',
    //   timings: resultPayload.timings,
    //   writeMode: message.writeMode,
    // });
  } catch (error) {
    if ((error as Error)?.name === 'AbortError') {
      postFailure(message.id, new Error('Search request canceled'), 'fetch', {
        durationMs: Date.now() - startedAt,
        queryKey: message.queryKey,
        timings,
      });
      return;
    }
    const stage = (error as { stage?: RetrieveSearchIngestStage })?.stage || 'fetch';
    postFailure(message.id, error, stage, {
      durationMs: Date.now() - startedAt,
      queryKey: message.queryKey,
      timings,
    });
  } finally {
    activeTasks.delete(taskKey(message));
  }
};

self.onmessage = (event: MessageEvent<SearchStreamMessage>) => {
  const message = event.data;
  if (!message?.type) return;

  if (message.type === 'ping') {
    postMessageSafe({
      id: message.id,
      ok: true,
      type: 'pong',
      workerLocation: self.location?.href,
    });
    return;
  }

  if (message.type === 'cancel') {
    activeTasks.get(taskKey(message))?.abortController.abort();
    activeTasks.delete(taskKey(message));
    return;
  }

  if (message.type === 'search-stream') {
    runSearchStream(message);
  }
};
