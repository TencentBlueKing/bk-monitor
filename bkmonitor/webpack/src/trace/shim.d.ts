/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import type i18n from './i18n/i18n';

import 'vue/dist/vue.d.ts';
import 'vue/jsx.d.ts';

import type { IBizItem, ISpaceItem } from './typings';
import type { Dayjs } from 'dayjs';
import type { HTMLAttributes, ReservedProps } from 'vue/dist/vue.d.ts';

declare global {
  interface Window {
    __BK_WEWEB_DATA__?: Record<string, any>;
    __POWERED_BY_BK_WEWEB__?: boolean;
    AJAX_URL_PREFIX: string;
    apm_ebpf_enabled: boolean;
    bk_biz_id: number | string;
    bk_biz_list: IBizItem[];
    BK_DOC_URL?: string;
    bk_doc_version: string;
    bk_docs_site_url: string;
    bk_log_search_url: string;
    bk_url: string;
    bkchat_manage_url: string;
    bklogsearch_host: string;
    cc_biz_id: number | string;
    csrf_cookie_name: string;
    dayjs?: Dayjs;
    enable_apm_profiling: boolean;
    enable_create_chat_group?: boolean;
    // 多租户用户中心是否开启
    enable_multi_tenant_mode?: boolean;
    FEATURE_TOGGLE?: Record<string, 'off' | 'on'>;
    graph_watermark: boolean;
    i18n: typeof i18n.global;
    // 以下为日志全局变量配置
    mainComponent: any;
    rawWindow?: Window;
    site_url: string;
    source_app: string;
    space_list: ISpaceItem[];
    static_url: string;
    timezone: string;
    traceLogComponent: any;
    uin: string;
    user_name: string;
    username: string;
    mermaidClick?: (id: string) => void;
  }
}

declare global {
  namespace JSX {
    interface IntrinsicElements {
      'bk-user-display-name': HTMLAttributes &
        ReservedProps & {
          'user-id': string;
        };
    }
  }
}
