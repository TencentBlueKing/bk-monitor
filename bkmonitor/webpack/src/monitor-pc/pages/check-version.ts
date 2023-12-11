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
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

let staticVersion = ''; // 静态资源版本号
let interval = null; // 定时器
/**
 * @param {number} checkInterval 检测间隔
 * @description 检测是否有新版本
 */
export const checkHasNewVersion = (checkInterval = 2 * 60 * 1000) => {
  if (interval || document.visibilityState !== 'visible') return;
  function checkVersion() {
    window.requestIdleCallback(() => {
      interval = setTimeout(() => {
        fetchCheckVersion()
          .then(needRecheck => {
            needRecheck && checkVersion();
          })
          .catch(() => {
            checkVersion();
          });
      }, checkInterval);
    });
  }
  checkVersion();
};
/**
 * @description 获取静态资源版本号
 * @returns {Promise<boolean>} 是否需要重新check
 */
function fetchCheckVersion(): Promise<boolean> {
  clearTimeout(interval);
  return fetch(
    `${window.static_url}/${process.env.APP === 'external' ? 'external' : 'monitor'}/static_version.txt`.replace(
      /\/\//g,
      '/'
    )
  ).then(async res => {
    const txt = await res.text();
    if (!staticVersion) {
      staticVersion = txt;
    } else if (document.visibilityState === 'visible' && staticVersion !== txt) {
      if (confirm(window.i18n.tc('检测到有新版本，点击确定刷新页面'))) {
        window.location.reload();
        window.clearTimeout(interval);
        return false;
      }
    }
    return true;
  });
}
function handleVisibilitychange() {
  if (document.visibilityState === 'visible') {
    fetchCheckVersion()
      .catch(() => false)
      .finally(() => {
        checkHasNewVersion();
      });
  } else {
    clearTimeout(interval);
    interval = null;
  }
}
/**
 * @description 监听页面切换
 */
export function useCheckVersion() {
  handleVisibilitychange();
  document.addEventListener('visibilitychange', handleVisibilitychange);
}
