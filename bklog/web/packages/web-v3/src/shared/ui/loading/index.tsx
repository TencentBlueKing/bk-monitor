/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company. All rights reserved.
 *
 * Licensed under the MIT License.
 */

import { Loading as TLoading } from '@/shared/ui/loading/native';

import { computed, defineComponent, type CSSProperties } from 'vue';


import { Z_INDEX_LAYERS } from '@/shared/global/overlay/z-index-manager.js';

import './index.scss';

const toOverlayColor = (color: string, opacity: number) => {
  const alpha = Math.min(Math.max(opacity, 0), 1);
  const value = color.trim();
  const shortHex = value.match(/^#([\da-f])([\da-f])([\da-f])$/i);
  const longHex = value.match(/^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i);
  const channels = shortHex
    ? shortHex.slice(1).map(channel => Number.parseInt(`${channel}${channel}`, 16))
    : longHex?.slice(1).map(channel => Number.parseInt(channel, 16));

  if (channels) {
    return `rgba(${channels.join(', ')}, ${alpha})`;
  }
  return `color-mix(in srgb, ${value} ${alpha * 100}%, transparent)`;
};

export default defineComponent({
  name: 'BklogLoading',
  props: {
    color: {
      type: String,
      default: '#fff',
    },
    loading: {
      type: Boolean,
      default: false,
    },
    opacity: {
      type: Number,
      default: 0.9,
    },
    size: {
      type: String,
      default: 'large',
    },
    title: {
      type: String,
      default: '',
    },
    zIndex: {
      type: Number,
      default: Z_INDEX_LAYERS.PAGE,
    },
  },
  setup(props, { attrs, slots }) {
    const loadingSize = computed(() => (props.size === 'mini' ? '16px' : props.size));
    const rootStyle = computed(
      () =>
        [
          attrs.style,
          {
            '--bklog-loading-overlay-color': toOverlayColor(props.color, props.opacity),
          },
        ] as CSSProperties[],
    );

    return () => (
      <TLoading
        {...attrs}
        class={['bklog-loading', attrs.class]}
        loading={props.loading}
        showOverlay
        size={loadingSize.value}
        style={rootStyle.value}
        text={props.title}
        zIndex={props.zIndex}
      >
        {slots.default?.()}
      </TLoading>
    );
  },
});
