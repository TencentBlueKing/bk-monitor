/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company. All rights reserved.
 *
 * Licensed under the MIT License.
 */

import { getCurrentInstance, h, onBeforeUnmount } from 'vue';
import { LoadingPlugin, type LoadingInstance } from 'tdesign-vue-next';

interface FullscreenLoadingOptions {
  opacity?: number;
  title?: string;
}

interface OwnedLoadingInstance {
  hide: () => void;
}

let loadingOwnerSeed = 0;

export default function useFullscreenLoading() {
  const appContext = getCurrentInstance()?.appContext;
  const instances = new Set<OwnedLoadingInstance>();

  const showFullscreenLoading = (options: FullscreenLoadingOptions = {}) => {
    const opacity = options.opacity ?? 0.9;
    const ownerId = `bklog-fullscreen-loading-${++loadingOwnerSeed}`;
    const loadingInstance: LoadingInstance = LoadingPlugin(
      {
        fullscreen: true,
        indicator: () =>
          h(
            'span',
            {
              'data-loading-owner': ownerId,
              'data-testid': 'fullscreen-loading-indicator',
              style: { display: 'inline-flex' },
            },
            [
              h('span', {
                style: {
                  position: 'fixed',
                  inset: 0,
                  backgroundColor: '#fff',
                  opacity,
                },
              }),
              h(
                'span',
                {
                  class: 'bklog-loading-dots bklog-loading-dots--large',
                  style: { position: 'relative', zIndex: 1 },
                },
                [0, 1, 2, 3].map(index => h('span', { key: index })),
              ),
            ],
          ),
        showOverlay: false,
        text: options.title,
        zIndex: window.__bk_zIndex_manager?.nextMessageZIndex?.(),
      },
      appContext,
    );
    const normalizeOverlay = () => {
      const indicator = document.querySelector(`[data-loading-owner="${ownerId}"]`);
      const overlay = indicator?.closest<HTMLElement>('.t-loading__fullscreen');
      overlay?.style.setProperty('background-color', 'transparent');
    };
    normalizeOverlay();
    queueMicrotask(normalizeOverlay);

    let hidden = false;
    const ownedInstance: OwnedLoadingInstance = {
      hide() {
        if (hidden) return;
        hidden = true;
        loadingInstance.hide();
        instances.delete(ownedInstance);
      },
    };
    instances.add(ownedInstance);
    return ownedInstance;
  };

  onBeforeUnmount(() => {
    for (const instance of [...instances]) {
      instance.hide();
    }
  });

  return {
    showFullscreenLoading,
  };
}
