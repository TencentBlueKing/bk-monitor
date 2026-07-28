/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import type { LexToken, TokenKind } from '../types';

export interface DetectorMatch {
  kind: TokenKind;
  value: string;
  length: number;
}

export type TokenDetector = {
  name: string;
  /** 从 input[offset] 尝试匹配，成功返回 match */
  detect: (input: string, offset: number) => DetectorMatch | null;
};

const IPV4_RE = /^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)/;
const UUID_RE = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/;
const MAC_RE = /^(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}/;
const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;
const URL_RE = /^(?:https?|ftp):\/\/[^\s]+/i;
const PATH_RE = /^(?:\/[\w.-]+)+\/?/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?/;
const FLOAT_RE = /^-?\d+\.\d+/;
const INT_RE = /^-?\d+/;
const BOOL_RE = /^(?:true|false)\b/i;
const HASH_RE = /^(?:sha256:|sha1:|md5:)?[0-9a-fA-F]{32,64}/;

const take = (input: string, offset: number, re: RegExp, kind: TokenKind): DetectorMatch | null => {
  const slice = input.slice(offset);
  const m = re.exec(slice);
  if (!m) return null;
  return { kind, value: m[0], length: m[0].length };
};

export const IpDetector: TokenDetector = {
  name: 'ip',
  detect: (input, offset) => take(input, offset, IPV4_RE, 'IP'),
};

export const UuidDetector: TokenDetector = {
  name: 'uuid',
  detect: (input, offset) => take(input, offset, UUID_RE, 'UUID'),
};

export const MacDetector: TokenDetector = {
  name: 'mac',
  detect: (input, offset) => take(input, offset, MAC_RE, 'MAC'),
};

export const EmailDetector: TokenDetector = {
  name: 'email',
  detect: (input, offset) => take(input, offset, EMAIL_RE, 'Email'),
};

export const UrlDetector: TokenDetector = {
  name: 'url',
  detect: (input, offset) => take(input, offset, URL_RE, 'URL'),
};

export const PathDetector: TokenDetector = {
  name: 'path',
  detect: (input, offset) => take(input, offset, PATH_RE, 'Path'),
};

export const DateDetector: TokenDetector = {
  name: 'date',
  detect: (input, offset) => take(input, offset, DATE_RE, 'DateTime'),
};

export const NumberDetector: TokenDetector = {
  name: 'number',
  detect: (input, offset) => {
    const float = take(input, offset, FLOAT_RE, 'Float');
    if (float) return float;
    return take(input, offset, INT_RE, 'Number');
  },
};

export const BooleanDetector: TokenDetector = {
  name: 'boolean',
  detect: (input, offset) => take(input, offset, BOOL_RE, 'Boolean'),
};

export const HashDetector: TokenDetector = {
  name: 'hash',
  detect: (input, offset) => take(input, offset, HASH_RE, 'Hash'),
};

/** 优先级：更具体的在前 */
export const DEFAULT_DETECTOR_REGISTRY: TokenDetector[] = [
  UrlDetector,
  EmailDetector,
  UuidDetector,
  MacDetector,
  IpDetector,
  DateDetector,
  HashDetector,
  PathDetector,
  BooleanDetector,
  NumberDetector,
];

export const createTokenFromMatch = (
  match: DetectorMatch,
  start: number,
): LexToken => ({
  kind: match.kind,
  value: match.value,
  raw: match.value,
  start,
  end: start + match.length,
});
