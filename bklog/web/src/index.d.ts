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
export {};

declare global {
  interface Window {
    mainComponent: any;
    timezone: string;
    MONITOR_URL: string;
    BK_LOGIN_URL: string;
    BK_SHARED_RES_URL: string;
    VERSION: string;
    AJAX_URL_PREFIX: string;
    FEATURE_TOGGLE_WHITE_LIST: Record<string, (string | number)[]>;
    FEATURE_TOGGLE: Record<string, 'on' | 'debug'>;
    __IS_MONITOR_COMPONENT__?: boolean; // 是否是监控组件
    __IS_MONITOR_TRACE__?: boolean; // 是否是监控Trace组件
    __IS_MONITOR_APM__?: boolean; // 是否是监控APM组件
    $t: (key: string, params?: Record<string, any>) => string;
  }
}

declare module 'vue/types/vue' {
  interface Vue {
    $bkMessage?: (p: Partial<object>) => void;
    $bkPopover?: (...Object) => void;
  }
}
