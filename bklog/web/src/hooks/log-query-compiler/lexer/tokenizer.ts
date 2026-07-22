/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import {
  createTokenFromMatch,
  DEFAULT_DETECTOR_REGISTRY,
  type TokenDetector,
} from '../detectors';
import { restoreShieldSlots, type ShieldSlot } from './shield';
import type { LexToken } from '../types';

const OPERATORS = [':', '=', '!=', '>=', '<=', '>', '<', '|', '(', ')', '[', ']', '{', '}', ',', ';'];
const BOOL_OPS = new Set(['AND', 'OR', 'NOT', 'and', 'or', 'not']);

const isIdentStart = (ch: string) => /[A-Za-z_\u4e00-\u9fff]/.test(ch);
const isIdentPart = (ch: string) => /[A-Za-z0-9_\-./\u4e00-\u9fff]/.test(ch);

export interface LexerOptions {
  detectors?: TokenDetector[];
  slots?: ShieldSlot[];
}

/**
 * 字符扫描 Lexer：Detector Registry + 手工扫描，禁止 split 空格。
 * 仅首个 `:` 在 field:value 语义中由 Parser 解释；Lexer 只产出 Operator(':')。
 */
export const tokenize = (input: string, options: LexerOptions = {}): LexToken[] => {
  const detectors = options.detectors ?? DEFAULT_DETECTOR_REGISTRY;
  const slots = options.slots ?? [];
  const source = String(input ?? '');
  const tokens: LexToken[] = [];
  let i = 0;

  const pushSymbolRun = (start: number) => {
    // 已 shield 的 §N 当作 Identifier
    if (source[start] === '§') {
      let j = start + 1;
      while (j < source.length && /\d/.test(source[j])) j += 1;
      const raw = source.slice(start, j);
      const restored = restoreShieldSlots(raw, slots);
      tokens.push({
        kind: restored.startsWith('"') ? 'QuotedString' : 'JSON',
        value: restored.startsWith('"') && restored.endsWith('"')
          ? restored.slice(1, -1)
          : restored,
        raw: restored,
        start,
        end: j,
      });
      return j;
    }
    return start;
  };

  while (i < source.length) {
    const ch = source[i];

    if (ch === ' ' || ch === '\t' || ch === '\n') {
      const start = i;
      while (i < source.length && /\s/.test(source[i])) i += 1;
      tokens.push({ kind: 'Whitespace', value: ' ', raw: source.slice(start, i), start, end: i });
      continue;
    }

    if (ch === '§') {
      i = pushSymbolRun(i);
      continue;
    }

    // 多字符 / 单字符算子
    let opHit = '';
    for (const op of OPERATORS) {
      if (source.startsWith(op, i) && op.length > opHit.length) {
        opHit = op;
      }
    }
    if (opHit) {
      tokens.push({ kind: 'Operator', value: opHit, raw: opHit, start: i, end: i + opHit.length });
      i += opHit.length;
      continue;
    }

    // Detector registry
    let detected = false;
    for (const detector of detectors) {
      const match = detector.detect(source, i);
      if (match && match.length > 0) {
        // 避免把 field 名里的数字误判：若前后是 ident 字符则跳过
        const prev = source[i - 1];
        const next = source[i + match.length];
        const glued = (prev && isIdentPart(prev)) || (next && isIdentPart(next) && match.kind === 'Number');
        if (!glued || ['IP', 'UUID', 'URL', 'Email', 'DateTime', 'MAC', 'Hash'].includes(match.kind)) {
          tokens.push(createTokenFromMatch(match, i));
          i += match.length;
          detected = true;
          break;
        }
      }
    }
    if (detected) continue;

    // Identifier / Keyword
    if (isIdentStart(ch) || ch === '*' || ch === '?') {
      const start = i;
      // wildcard 片段
      if (ch === '*' || ch === '?') {
        while (i < source.length && (source[i] === '*' || source[i] === '?' || isIdentPart(source[i]))) {
          i += 1;
        }
        const raw = source.slice(start, i);
        tokens.push({
          kind: raw.includes('*') || raw.includes('?') ? 'Wildcard' : 'Identifier',
          value: raw,
          raw,
          start,
          end: i,
        });
        continue;
      }

      while (i < source.length && isIdentPart(source[i])) i += 1;
      const raw = source.slice(start, i);
      tokens.push({
        kind: BOOL_OPS.has(raw) ? 'Keyword' : 'Identifier',
        value: raw,
        raw,
        start,
        end: i,
      });
      continue;
    }

    // 其它符号
    tokens.push({ kind: 'Symbol', value: ch, raw: ch, start: i, end: i + 1 });
    i += 1;
  }

  return tokens;
};

export const tokensWithoutWhitespace = (tokens: LexToken[]) =>
  tokens.filter(token => token.kind !== 'Whitespace');
