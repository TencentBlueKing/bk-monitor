/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

import {
  isBigNumberValue,
  normalizeBigNumberForStorage,
  normalizeStorageValue,
} from '../utils/normalize-storage-value';

export interface RetrieveRowProjectionField {
  fieldName: string;
  value: any;
  preview: any;
  type: string;
  bytes: number;
  isLarge: boolean;
}

export interface RetrieveRowProjection {
  key: string;
  queryKey: string;
  seq: number;
  fields: Record<string, RetrieveRowProjectionField>;
  meta: Record<string, any>;
  bytes: number;
  hasLargeFields: boolean;
}

export interface RetrieveRowStorageValue {
  row: Record<string, any>;
  projection: RetrieveRowProjection;
  bytes: number;
}

const LARGE_FIELD_BYTES = 64 * 1024;
const PREVIEW_STRING_LENGTH = 4096;

const META_FIELD_NAMES = [
  'dtEventTimeStamp',
  '__id__',
  'index',
  '__result_table__',
  '__result_table',
  '__index_set_id__',
  'index_set_id',
  'gseIndex',
  'iterationIndex',
  '_time',
  'time',
  'bk_host_id',
  'serverIp',
  'cloudId',
  'path',
];

const getValueType = (value: any) => {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'array';
  return typeof value;
};

export const estimateValueBytes = (value: any): number => {
  if (value === null || value === undefined) return 0;
  if (typeof value === 'string') return value.length * 2;
  if (typeof value === 'number') return 8;
  if (typeof value === 'boolean') return 4;
  if (isBigNumberValue(value)) return String(value.toString()).length * 2;

  try {
    return JSON.stringify(value).length * 2;
  } catch (error) {
    return String(value).length * 2;
  }
};

const createPreview = (value: any, bytes: number) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') {
    return value.length > PREVIEW_STRING_LENGTH ? `${value.slice(0, PREVIEW_STRING_LENGTH)}...` : value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  if (isBigNumberValue(value)) {
    return normalizeBigNumberForStorage(value);
  }

  try {
    const jsonValue = JSON.stringify(value);
    return bytes > LARGE_FIELD_BYTES || jsonValue.length > PREVIEW_STRING_LENGTH
      ? `${jsonValue.slice(0, PREVIEW_STRING_LENGTH)}...`
      : jsonValue;
  } catch (error) {
    return String(value);
  }
};

const normalizePrimitiveForRender = (value: any) => {
  if (value === null || value === undefined) return '';
  if (isBigNumberValue(value)) {
    return normalizeBigNumberForStorage(value);
  }
  return value;
};

export class RetrieveRowProjectionService {
  createStorageValue(
    row: Record<string, any>,
    queryKey: string,
    seq: number,
    fieldNames: string[] = [],
  ): RetrieveRowStorageValue {
    const normalizedRow = normalizeStorageValue(this.normalizeShallowRow(row));
    const projection = this.createProjection(normalizedRow, queryKey, seq, fieldNames);
    return {
      row: normalizedRow,
      projection,
      bytes: projection.bytes,
    };
  }

  normalizeShallowRow(row: Record<string, any>) {
    if (!row || Object.prototype.toString.call(row) !== '[object Object]') return row;
    let changed = false;
    const output: Record<string, any> = {};

    Object.keys(row).forEach((key) => {
      const value = row[key];
      const normalizedValue = normalizePrimitiveForRender(value);
      output[key] = normalizedValue;
      changed = changed || normalizedValue !== value;
    });

    return changed ? output : row;
  }

  createProjection(
    row: Record<string, any>,
    queryKey: string,
    seq: number,
    fieldNames: string[] = [],
  ): RetrieveRowProjection {
    const key = `${queryKey}:${seq}`;
    const names = Array.from(new Set([...META_FIELD_NAMES, ...fieldNames].filter(Boolean)));
    const fields: Record<string, RetrieveRowProjectionField> = {};
    const meta: Record<string, any> = {};
    let totalBytes = 0;
    let hasLargeFields = false;

    names.forEach((fieldName) => {
      if (!Object.prototype.hasOwnProperty.call(row ?? {}, fieldName)) return;
      const value = normalizeStorageValue(row[fieldName]);
      const bytes = estimateValueBytes(value);
      totalBytes += bytes;
      const isLarge = bytes > LARGE_FIELD_BYTES;
      hasLargeFields = hasLargeFields || isLarge;
      fields[fieldName] = {
        fieldName,
        value: isLarge ? undefined : value,
        preview: createPreview(value, bytes),
        type: getValueType(value),
        bytes,
        isLarge,
      };
      if (META_FIELD_NAMES.includes(fieldName)) {
        meta[fieldName] = isLarge ? fields[fieldName].preview : value;
      }
    });

    return {
      key,
      queryKey,
      seq,
      fields,
      meta,
      bytes: totalBytes || estimateValueBytes(row),
      hasLargeFields,
    };
  }
}

export const retrieveRowProjectionService = new RetrieveRowProjectionService();
