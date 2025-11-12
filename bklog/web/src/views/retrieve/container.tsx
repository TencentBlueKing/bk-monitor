/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { defineComponent, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router/composables';

import logWebManifest from '@blueking/log-web';
import { generateIframeSrcdoc } from './helper';

/**
 * Vue2 挂载容器组件
 * 使用 iframe 做隔离，加载 @blueking/log-web 包中的 Vue2 应用
 * iframe 中的 location 直接代理父级的 location，保证 URL 一致
 */
export default defineComponent({
  name: 'Vue2Container',
  setup() {
    const route = useRoute();
    const router = useRouter();

    const iframeRef = ref<HTMLIFrameElement | null>(null);
    const loading = ref(true);
    const error = ref<string | null>(null);
    let messageHandler: ((_evt: MessageEvent) => void) | null = null;

    // 解析 hash 中的查询参数
    const parseHashQuery = (hash: string) => {
      const query: Record<string, string> = {};
      if (!hash) {
        return query;
      }

      const hashParts = hash.split('?');
      if (hashParts.length > 1) {
        const queryString = hashParts[1];
        const params = new URLSearchParams(queryString);
        for (const [key, value] of params) {
          query[key] = value;
        }
      }
      return query;
    };


    // 同步 hash 到 iframe（仅在初始化时使用）
    const syncHashToIframe = (iframeWindow: Window, hash: string) => {
      const iframeWin = iframeWindow as any;
      if (!iframeWin.updateHashRoute) {
        return;
      }

      const hashPath = hash.startsWith('#') ? hash.substring(1) : hash;
      const query = parseHashQuery(hash);

      iframeWin.updateHashRoute({
        hash: hashPath,
        path: hashPath.split('?')[0],
        query,
        state: window.history.state,
      });
    };


    // 初始化 iframe
    const initIframe = () => {
      try {
        const manifest = logWebManifest;
        if (!manifest || !manifest.entryJs || !manifest.entryCss) {
          throw new Error('无法获取资源清单或资源清单不完整');
        }

        if (!iframeRef.value) {
          return;
        }

        // 生成 srcdoc 内容
        const srcdoc = generateIframeSrcdoc();

        // 使用 srcdoc 模式
        iframeRef.value.srcdoc = srcdoc;

        // 设置消息监听和初始化同步
        const setupIframeSync = (iframeWindow: Window) => {
          // 监听来自 iframe 的消息
          messageHandler = (evt: MessageEvent) => {
            // 验证消息来源是否是 iframe 窗口，且消息包含正确的 source 标识
            const isFromIframe = evt.source === iframeWindow;
            const hasValidSource = evt.data?.source === 'vue2-container';

            // 处理来自 iframe 的消息
            if (isFromIframe && hasValidSource) {
              if (evt.data.type === 'vue2-app-loaded') {
                loading.value = false;
                error.value = null;
              }

              if (evt.data.type === 'vue2-app-error') {
                loading.value = false;
                error.value = evt.data.error || '加载失败';
              }

              if (evt.data.type === 'sync-route-params') {
                const { swtichVersion, query, params } = evt.data.payload;

                router.replace({
                  query: { ...route.query, ...(query || {}) },
                  params: { ...route.params, ...(params || {}) },
                }).then(() => {
                  if (swtichVersion) {
                    localStorage.setItem('retrieve_version', 'v3');
                    window.location.reload();
                  }
                });
              }
            }
          };

          window.addEventListener('message', messageHandler);

          // 初始化时同步一次父级 URL 到 iframe（延迟执行，确保 iframe 已完全加载）
          setTimeout(() => {
            const currentHash = route.hash;
            if (currentHash) {
              syncHashToIframe(iframeWindow, currentHash);
            }
          }, 500);
        };

        // 等待 iframe 加载后设置初始同步
        iframeRef.value.onload = () => {
          const iframeWindow = iframeRef.value?.contentWindow;
          if (iframeWindow) {
            setupIframeSync(iframeWindow);
          }
          loading.value = false;
        };
      } catch (err: any) {
        loading.value = false;
        error.value = err.message || '初始化失败';
        console.error('初始化 iframe 失败:', err);
      }
    };

    watch(() => [route.query.spaceUid, route.query.bizId], ([spaceUid, bkBizId], [oldSpaceUid, oldBkBizId]) => {
      if (spaceUid !== oldSpaceUid || bkBizId !== oldBkBizId) {
        const iframeWindow = iframeRef.value?.contentWindow;
        // 转发消息到 iframe
        iframeWindow?.postMessage(
          {
            type: 'update-route-params',
            payload: { spaceUid, bkBizId },
          },
          '*',
        );
      }
    });

    onMounted(() => {
      initIframe();
    });

    onUnmounted(() => {
      // 清理事件监听器
      if (messageHandler) {
        window.removeEventListener('message', messageHandler);
        messageHandler = null;
      }
    });

    return () => (
      <div class='vue2-container' style='width: 100%; height: 100%; position: relative;'>
        {loading.value && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: '#f5f6fa',
              zIndex: 10,
            }}
          >
            <div style={{ fontSize: '14px', color: '#63656e' }}>加载中...</div>
          </div>
        )}
        {error.value && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: '#f5f6fa',
              zIndex: 10,
            }}
          >
            <div style={{ fontSize: '14px', color: '#ea3636' }}>加载失败: {error.value}</div>
          </div>
        )}
        <iframe
          ref={iframeRef}
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
            display: loading.value || error.value ? 'none' : 'block',
          }}
          sandbox='allow-same-origin allow-scripts allow-forms allow-popups allow-modals'
        />
      </div>
    );
  },
});
