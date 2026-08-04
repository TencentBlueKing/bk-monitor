/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

export type ShieldSlot = { id: string; value: string; kind: 'quoted' | 'json' | 'regex' };

export interface ShieldResult {
  text: string;
  slots: ShieldSlot[];
}

const SLOT = (index: number) => `§${index}`;

/**
 * Shield：保护引号串 / 简单 JSON 片段，避免后续空白切分破坏。
 */
export const shieldProtectedSpans = (input: string): ShieldResult => {
  const slots: ShieldSlot[] = [];
  let text = String(input ?? '');
  let i = 0;
  let out = '';

  while (i < text.length) {
    const ch = text[i];

    // 引号串
    if (ch === '"') {
      let j = i + 1;
      let raw = '"';
      while (j < text.length) {
        if (text[j] === '\\' && j + 1 < text.length) {
          raw += text[j] + text[j + 1];
          j += 2;
          continue;
        }
        raw += text[j];
        if (text[j] === '"') {
          j += 1;
          break;
        }
        j += 1;
      }
      const id = SLOT(slots.length);
      slots.push({ id, value: raw, kind: 'quoted' });
      out += id;
      i = j;
      continue;
    }

    // 简单 JSON object/array（平衡括号，长度受限）
    if ((ch === '{' || ch === '[') && text.slice(i, i + 80).includes(ch === '{' ? '}' : ']')) {
      const open = ch;
      const close = ch === '{' ? '}' : ']';
      let depth = 0;
      let j = i;
      let inStr = false;
      while (j < text.length && j - i < 2000) {
        const c = text[j];
        if (c === '"' && text[j - 1] !== '\\') inStr = !inStr;
        if (!inStr) {
          if (c === open) depth += 1;
          if (c === close) {
            depth -= 1;
            if (depth === 0) {
              j += 1;
              break;
            }
          }
        }
        j += 1;
      }
      if (depth === 0) {
        const raw = text.slice(i, j);
        // 仅当像 JSON 结构时保护
        if (/^[\{\[]/.test(raw) && /[\}\]]$/.test(raw) && /[:,"]/.test(raw)) {
          const id = SLOT(slots.length);
          slots.push({ id, value: raw, kind: 'json' });
          out += id;
          i = j;
          continue;
        }
      }
    }

    out += ch;
    i += 1;
  }

  return { text: out, slots };
};

export const restoreShieldSlots = (text: string, slots: ShieldSlot[]): string => {
  let result = text;
  // 倒序替换，避免 §1 误伤 §10
  for (let i = slots.length - 1; i >= 0; i--) {
    const slot = slots[i];
    result = result.split(slot.id).join(slot.value);
  }
  return result;
};
