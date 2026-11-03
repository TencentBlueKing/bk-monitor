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

/** 菜单关闭后延迟去掉 Hover，避免移入菜单时闪烁 */
const FAVORITE_MENU_HIDE_DELAY = 160;

function createFavoriteMenuHoverState({ delay = FAVORITE_MENU_HIDE_DELAY } = {}) {
  let openId = null;
  let hideTimer = null;

  const clearHideTimer = () => {
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
  };

  return {
    delay,
    getOpenId() {
      return openId;
    },
    isMenuOpen(id) {
      return openId === id;
    },
    shown(id) {
      clearHideTimer();
      openId = id;
    },
    hidden(id) {
      clearHideTimer();
      hideTimer = setTimeout(() => {
        if (openId === id) {
          openId = null;
        }
        hideTimer = null;
      }, delay);
    },
    dispose() {
      clearHideTimer();
    },
  };
}

module.exports = {
  FAVORITE_MENU_HIDE_DELAY,
  createFavoriteMenuHoverState,
};
