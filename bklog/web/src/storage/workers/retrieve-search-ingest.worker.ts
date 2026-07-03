/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import JSONBigNumber from 'json-bignumber';

import { retrieveRowRepository } from '../repositories/retrieve-row.repository';
import { createRetrieveRowRenderMeta } from '../utils/retrieve-render-meta';

interface IngestMessage {
  id: string;
  buffer?: ArrayBuffer;
  fieldNames?: string[];
  queryKey?: string;
  startSeq?: number;
  type: 'ingest-search-response' | 'ping';
  writeMode?: 'append' | 'replace';
}

const bigNumberToCloneable = (value: any) => {
  if (value?._isBigNumber) {
    const stringValue = value.toString();
    return stringValue.length < 16 ? Number(value) : stringValue;
  }
  return value;
};

const toCloneable = (value: any): any => {
  const normalized = bigNumberToCloneable(value);
  if (normalized !== value) return normalized;
  if (Array.isArray(value)) return value.map(item => toCloneable(item));
  if (value && Object.prototype.toString.call(value) === '[object Object]') {
    return Object.keys(value).reduce((output, key) => {
      output[key] = toCloneable(value[key]);
      return output;
    }, {} as Record<string, any>);
  }
  return value;
};

const postSuccess = (id: string, payload: Record<string, any>) => {
  self.postMessage({ id, ok: true, ...payload });
};

const postFailure = (id: string, error: any) => {
  self.postMessage({
    id,
    ok: false,
    error: error?.message || String(error),
  });
};

self.onmessage = async (event: MessageEvent<IngestMessage>) => {
  const message = event.data;
  if (message?.type === 'ping') {
    self.postMessage({
      id: message.id,
      ok: true,
      type: 'pong',
      workerLocation: self.location?.href,
    });
    return;
  }

  if (message?.type !== 'ingest-search-response') return;

  try {
    if (!message.buffer || !message.queryKey) {
      throw new Error('Invalid WebWorker ingest message: missing buffer or queryKey');
    }
    const text = new TextDecoder().decode(message.buffer);
    const response = JSONBigNumber.parse(text);
    const data = response?.data;

    if (response?.result && data) {
      if (!Array.isArray(data.list) || !Array.isArray(data.origin_log_list)) {
        throw new Error('Invalid search response: list and origin_log_list are required');
      }
      if (data.list.length !== data.origin_log_list.length) {
        throw new Error(`Invalid search response: list length ${data.list.length} !== origin_log_list length ${data.origin_log_list.length}`);
      }
      const renderRows = data.list;
      const rows = data.origin_log_list;
      const renderMetas = rows.map((row: Record<string, any>, index: number) => createRetrieveRowRenderMeta(row, renderRows[index]));
      const rowKeys = message.writeMode === 'append'
        ? await retrieveRowRepository.appendRows(message.queryKey, rows, message.startSeq || 0, {
          fieldNames: message.fieldNames || [],
          renderRows,
          renderMetas,
        })
        : await retrieveRowRepository.replaceRows(message.queryKey, rows, message.startSeq || 0, {
          fieldNames: message.fieldNames || [],
          renderRows,
          renderMetas,
        });

      const meta = { ...data };
      delete meta.list;
      delete meta.origin_log_list;

      postSuccess(message.id, {
        response: {
          code: response.code,
          data: toCloneable(meta),
          message: response.message,
          permission: toCloneable(response.permission),
          result: response.result,
        },
        rowKeys,
        size: rows.length,
      });
      return;
    }

    postSuccess(message.id, {
      response: {
        code: response?.code,
        data: toCloneable(data),
        message: response?.message,
        permission: toCloneable(response?.permission),
        result: response?.result,
      },
      rowKeys: [],
      size: 0,
    });
  } catch (error) {
    postFailure(message.id, error);
  }
};
