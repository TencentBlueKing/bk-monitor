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

import VueType from 'vue';

declare global {
  interface Window {
    mainComponent: any;
    bus: VueType;
    timezone: string;
    MONITOR_URL: string;
    BK_LOGIN_URL: string;
    BK_SHARED_RES_URL: string;
    VERSION: string;
    AJAX_URL_PREFIX: string;
    FEATURE_TOGGLE_WHITE_LIST: Record<string, (number | string)[]>;
    FEATURE_TOGGLE: Record<string, 'debug' | 'off' | 'on'>;
    __IS_MONITOR_COMPONENT__?: boolean; // 是否是监控组件
    __IS_MONITOR_TRACE__?: boolean; // 是否是监控Trace组件
    __IS_MONITOR_APM__?: boolean; // 是否是监控APM组件
    IS_EXTERNAL: boolean | string; // 开发环境是 'false'，生产环境是 boolean
    bk_log_search_url: string;
    BKDATA_URL: string;
    $t: (key: string, params?: Record<string, any>) => string;
    scheduler?: Scheduler;
    RUN_VER: string;
  }

  interface Scheduler {
    postTask(callback: () => void, options?: SchedulerPostTaskOptions): SchedulerTask;
  }

  interface SchedulerPostTaskOptions {
    priority?: 'background' | 'user-blocking' | 'user-visible';
    delay?: number;
    signal?: AbortSignal;
  }

  interface SchedulerTask {
    readonly priority: 'background' | 'user-blocking' | 'user-visible';
    abort(): void;
  }

  interface WorkerGlobalScope {
    scheduler?: Scheduler;
  }
}

declare module 'vue/types/vue' {
  interface Vue {
    $bkMessage?: (p: Partial<object>) => void;
    $bkPopover?: (...args: any[]) => void;
  }
}
