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
let intervalId = null; // 定时器ID
let hasShownConfirm = false; // 是否已经弹出过提示
import Vue from 'vue';

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
  return await new Promise(resolve => {
    Vue.prototype.$bkInfo({
      title: window.i18n.tc('检测到蓝鲸监控版本更新'),
      subTitle: window.i18n.tc('请点击“确定”刷新页面，保证数据准确性。'),
      maskClose: false,
      extCls: 'check-version-wrapper',
      width: '480px',
      confirmFn: () => {
        window.location.reload();
      },
      cancelFn: () => {
        hasShownConfirm = false;
        addVisibilityChangeListener();
        resolve(true);
      },
      closeFn: () => {
        hasShownConfirm = false;
        addVisibilityChangeListener();
        resolve(true);
      },
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
