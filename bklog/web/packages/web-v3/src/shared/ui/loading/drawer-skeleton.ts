/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { h } from 'vue';

import './drawer-skeleton.scss';

const bar = (shape: string) => h('span', { class: `bklog-drawer-skeleton__${shape}` });
const form = (layout: string, fields: string[]) => h('div', {
  class: ['bklog-drawer-skeleton', `bklog-drawer-skeleton--${layout}`],
  'aria-hidden': 'true',
}, fields.map(shape => h('div', { class: 'bklog-drawer-skeleton__field' }, [bar('label'), shape === 'range' ? h('div', { class: 'bklog-drawer-skeleton__range' }, [bar('control'), bar('control')]) : bar(shape)])));

export const renderDrawerFormSkeleton = () => form('stack', ['control', 'control', 'control', 'textarea']);
export const renderDrawerInlineFormSkeleton = () => form('inline', ['control', 'control', 'range', 'control', 'control']);
export const renderDrawerDetailSkeleton = () => h('div', {
  class: 'bklog-drawer-skeleton',
  'aria-hidden': 'true',
}, [bar('summary'), bar('label'), ...Array.from({ length: 4 }, () =>
  h('div', { class: 'bklog-drawer-skeleton__detail-row' }, [bar('dot'), bar('control')]),
)]);
