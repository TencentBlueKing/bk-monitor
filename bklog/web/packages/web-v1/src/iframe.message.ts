// 添加一个消息处理函数，用于处理 iframe 和父级窗口之间的消息通信
// 这个函数主要用于监听父级窗口的 message 事件，监听事件更新当前窗口信息
// 1、处理路由参数更新，同步 spaceUid、bkBizId 参

import { Store } from 'vuex';
import { BK_LOG_STORAGE } from './store/store.type';

/**
 * 处理 iframe 和父级窗口之间的消息通信
 * @param store vuex 实例
 */
export function iframeMessageHandler(store: Store<any>) {
  const updateRouteParams = (payload: any) => {
    const { spaceUid, bkBizId } = payload;
    store.commit('updateState', {
      spaceUid,
      bkBizId,
    });

    store.commit('updateStorage', {
      [BK_LOG_STORAGE.BK_SPACE_UID]: spaceUid,
      [BK_LOG_STORAGE.BK_BIZ_ID]: bkBizId,
    });
  };

  const handleIframeMessage = (event: MessageEvent) => {
    const { type, payload } = event.data;
    switch (type) {
      case 'update-route-params':
        updateRouteParams(payload);
        break;
    }
  };

  window.addEventListener('message', handleIframeMessage);
}

/**
 * 同步路由参数到 iframe 父级窗口
 * @param payload { swtichVersion: boolean, query: Record<string, string>, params: Record<string, string> }
 */
export function sendIframeMessage(payload: any) {
  if (window.parent && window.parent !== window) {
    window.parent.postMessage(
      {
        type: 'sync-route-params',
        source: 'vue2-container',
        payload,
      },
      '*',
    );
  }
}
