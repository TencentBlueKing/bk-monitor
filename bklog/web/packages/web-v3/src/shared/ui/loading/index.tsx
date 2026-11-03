/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company. All rights reserved.
 *
 * Licensed under the MIT License.
 */

import { computed, defineComponent, type CSSProperties } from 'vue';
import { Loading as TLoading } from 'tdesign-vue-next';

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
  inheritAttrs: false,
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
      default: 1000,
    },
  },
  setup(props, { attrs, slots }) {
    const indicatorSize = computed(() => (['mini', 'small'].includes(props.size) ? props.size : 'large'));
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

    const renderIndicator = () => (
      <span class={['bklog-loading-dots', `bklog-loading-dots--${indicatorSize.value}`]}>
        {[0, 1, 2, 3].map(index => <span key={index} />)}
      </span>
    );

    return () => (
      <TLoading
        {...attrs}
        class={['bklog-loading', attrs.class]}
        indicator={renderIndicator}
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
