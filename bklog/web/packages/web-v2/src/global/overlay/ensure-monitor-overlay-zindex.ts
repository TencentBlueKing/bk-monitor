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

import type VueType from 'vue';

import { MONITOR_OVERLAY_ZINDEX_BASE } from './overlay-registry';

export { MONITOR_OVERLAY_ZINDEX_BASE };

interface VueConstructor {
  prototype: VueType & {
    $BK_EL?: { zIndex?: number };
  };
}

/**
 * 把 magicbox / zIndex manager 抬到监控侧滑之上。仅应在 monitor 入口 initWindowState 调用，幂等。
 */
export const ensureMonitorOverlayZIndex = (VueCtor: VueConstructor) => {
  const current = VueCtor.prototype.$BK_EL?.zIndex ?? 0;
  VueCtor.prototype.$BK_EL = {
    ...(VueCtor.prototype.$BK_EL || {}),
    zIndex: Math.max(current, MONITOR_OVERLAY_ZINDEX_BASE),
  };

  const manager = window.__bk_zIndex_manager;
  if (manager && typeof manager.zIndex === 'number' && manager.zIndex < MONITOR_OVERLAY_ZINDEX_BASE) {
    manager.zIndex = MONITOR_OVERLAY_ZINDEX_BASE;
  }
};
