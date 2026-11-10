/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { Fragment, type Slots, type VNodeChild } from 'vue';
import type { TranslateFunction } from './translator';

/** Preserve default/list and named VNode slots without serializing them or using innerHTML. */
export function renderRichTranslation(translate: TranslateFunction, key: string, slots: Slots, locale?: string): VNodeChild[] {
  const slotKeys = Object.keys(slots).filter(name => !name.startsWith('_'));
  const content: Record<string, VNodeChild[]> = {};
  if (slotKeys.length === 1 && slotKeys[0] === 'default') {
    const children = (slots.default?.() ?? []).flatMap(node => node.type === Fragment && Array.isArray(node.children) ? node.children : [node]);
    children.forEach((node, index) => { content[index] = [node]; });
  } else {
    for (const name of slotKeys) content[name] = slots[name]?.() ?? [];
  }
  const markers: Record<string, string> = {};
  const nodes = new Map<string, VNodeChild[]>();
  Object.entries(content).forEach(([name, children], index) => {
    const marker = `\uE000bklog_slot_${index}_\uE001`;
    markers[name] = marker;
    nodes.set(marker, children);
  });
  return translate(key, markers, { locale }).split(/(\uE000bklog_slot_\d+_\uE001)/).flatMap(part => nodes.get(part) ?? [part]);
}
