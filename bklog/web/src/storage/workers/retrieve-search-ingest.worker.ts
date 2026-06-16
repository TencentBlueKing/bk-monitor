/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import JSONBigNumber from 'json-bignumber';

import { retrieveRowRepository } from '../repositories/retrieve-row.repository';

interface IngestMessage {
  id: string;
  buffer: ArrayBuffer;
  fieldNames?: string[];
  queryKey: string;
  startSeq?: number;
  type: 'ingest-search-response';
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
  if (message?.type !== 'ingest-search-response') return;

  try {
    const text = new TextDecoder().decode(message.buffer);
    const response = JSONBigNumber.parse(text);
    const data = response?.data;

    if (response?.result && data) {
      const rows = Array.isArray(data.list) ? data.list : [];
      const rowKeys = message.writeMode === 'append'
        ? await retrieveRowRepository.appendRows(message.queryKey, rows, message.startSeq || 0, {
          fieldNames: message.fieldNames || [],
        })
        : await retrieveRowRepository.replaceRows(message.queryKey, rows, message.startSeq || 0, {
          fieldNames: message.fieldNames || [],
        });

      const meta = { ...data };
      delete meta.list;

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
