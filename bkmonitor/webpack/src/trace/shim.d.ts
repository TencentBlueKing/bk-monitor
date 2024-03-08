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
/* eslint-disable camelcase */
import type { Composer } from 'vue-i18n';
import type { Dayjs } from 'dayjs';

import type { IBizItem, ISpaceItem } from './typings';

declare global {
  interface Window {
    site_url: string;
    static_url: string;
    user_name: string;
    username: string;
    timezone: string;
    uin: string;
    space_list: ISpaceItem[];
    bk_biz_list: IBizItem[];
    csrf_cookie_name: string;
    cc_biz_id: string | number;
    bk_biz_id: string | number;
    bk_log_search_url: string;
    bklogsearch_host: string;
    bk_url: string;
    source_app: 'trace';
    i18n: Composer;
    __BK_WEWEB_DATA__?: Record<string, any>;
    __POWERED_BY_BK_WEWEB__?: boolean;
    mermaidClick?: (id: string) => void;
    apm_ebpf_enabled: boolean;
    dayjs?: Dayjs;
    enable_apm_profiling: boolean;
    bk_docs_site_url: string;
  }
}
