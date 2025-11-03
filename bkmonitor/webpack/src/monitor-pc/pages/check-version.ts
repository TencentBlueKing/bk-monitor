/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
let staticVersion = ''; // 静态资源版本号
let intervalId = null; // 定时器ID
let hasShownConfirm = false; // 是否已经弹出过提示
import Vue from 'vue';

import { getLinkMapping } from 'monitor-api/modules/commons';
// 使用箭头函数简化代码，并添加注释来提高可读性
export const checkForNewVersion = (checkInterval = 5 * 60 * 1000) => {
  clearTimeout(intervalId); // 清除现有的定时器
  intervalId = setTimeout(async () => {
    try {
      const recheck = await fetchStaticVersion(false);
      if (recheck) await checkForNewVersion(checkInterval);
    } catch {
      await checkForNewVersion(checkInterval);
    }
  }, checkInterval);
};

// 优化 fetchCheckVersion 方法名称，使其更直观
const fetchStaticVersion = async (clearInterval = true) => {
  if (clearInterval) clearTimeout(intervalId);
  if (hasShownConfirm) return false;

  const urlPrefix = process.env.APP === 'external' ? 'external' : 'monitor';
  const response = await fetch(`${window.static_url}/${urlPrefix}/static_version.txt`.replace(/\/\//g, '/'));
  const newVersion = await response.text();

  if (!staticVersion) {
    staticVersion = newVersion;
    return true;
  }
  if (staticVersion !== newVersion) {
    return await promptForReload();
  }
  return true;
};

// 将确认框和刷新页面逻辑抽出单独的函数
const promptForReload = async () => {
  if (hasShownConfirm) return false;
  removeVisibilityChangeListener();
  hasShownConfirm = true;
  const data = await getLinkMapping().catch(() => {});
  const publishUrl = data?.publish_docs || {};
  return await new Promise(resolve => {
    const vm = new Vue();
    const h = vm.$createElement;
    let notify = null;
    const confirmFn = () => {
      window.location.reload();
    };
    const cancelFn = () => {
      notify.close();
      hasShownConfirm = false;
      addVisibilityChangeListener();
      resolve(true);
    };
    notify = Vue.prototype.$bkNotify({
      title: window.i18n.tc('监控版本已更新'),
      message: h(
        'div',
        {
          class: {
            'check-version-txt': true,
          },
        },
        [
          h('div', window.i18n.tc('建议「刷新页面」体验新的特性，「暂不刷新」可能会遇到未知异常，可手动刷新解决。')),
          h(
            'div',
            {
              class: {
                'check-version-btn': true,
                'check-version-btn-single': !publishUrl?.value,
              },
            },
            [
              h(
                'bk-button',
                {
                  props: {
                    theme: 'primary',
                    size: 'small',
                  },
                  on: {
                    click: confirmFn,
                  },
                },
                window.i18n.tc('刷新页面')
              ),
              h(
                'bk-button',
                {
                  props: {
                    size: 'small',
                  },
                  on: {
                    click: cancelFn,
                  },
                },
                window.i18n.tc('暂不刷新')
              ),
              h(
                'bk-button',
                {
                  style: {
                    display: publishUrl?.value ? 'inline-block' : 'none',
                  },
                  props: {
                    outline: true,
                    theme: 'primary',
                    size: 'small',
                  },
                  on: {
                    click: () => {
                      cancelFn();
                      /** 跳转到wiki */
                      publishUrl.value && window.open(publishUrl.value);
                    },
                  },
                },
                window.i18n.tc('查看新特性')
              ),
            ]
          ),
        ]
      ),
      delay: 0,
      offsetY: 46,
      extCls: 'check-version-wrapper',
    });
  });
  // return true;
  // if (confirm(window.i18n.tc('检测到监控平台有新版本更新，点击确定刷新页面'))) {
  //   window.location.reload();
  //   return false;
  // }
  // hasShownConfirm = false;
  // window.requestIdleCallback(() => {
  //   addVisibilityChangeListener();
  // });
  // return true;
};

const handleVisibilityChange = () => {
  console.info(Date.now(), hasShownConfirm, document.visibilityState);
  if (!hasShownConfirm && document.visibilityState === 'visible') {
    fetchStaticVersion()
      .catch(() => false)
      .finally(() => checkForNewVersion());
  } else {
    clearInterval(intervalId);
  }
};

export const useCheckVersion = () => {
  fetchStaticVersion()
    .catch(() => false)
    .finally(() => checkForNewVersion());
  addVisibilityChangeListener();
};

export const addVisibilityChangeListener = () => {
  document.addEventListener('visibilitychange', handleVisibilityChange);
};

export const removeVisibilityChangeListener = () => {
  document.removeEventListener('visibilitychange', handleVisibilityChange);
};
