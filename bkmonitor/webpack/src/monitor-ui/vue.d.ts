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
/* eslint-disable camelcase */
import VueI18n from 'vue-i18n';
import * as base from 'vue-tsx-support/types/base';
import * as builtin from 'vue-tsx-support/types/builtin-components';

interface IBkInfoProps {
  title: unknown;
  zIndex: number;
  width: string | number;
  type: string;
  maskClose: boolean;
  confirmLoading: boolean;
  subHeader?: any;
  subTitle?: any;
  escClose?: any;
  confirmFn: (v: unknown) => void;
  cancelFn: (v: unknown) => void;
}
declare module 'vue/types/vue' {
  interface Vue {
    $bkInfo?: (p: Partial<IBkInfoProps>) => void;
    $bkMessage?: (p: Partial<{}>) => void;
    $bkToPinyin?: (str: string, lowerCase?: boolean, separator?: string) => string;
    $bkPopover?: (e: any, p: any) => void;
    $api?: any;
  }
}

declare global {
  interface Window {
    site_url: string;
    static_url: string;
    user_name: string;
    username: string;
    uin: string;
    csrf_cookie_name: string;
    cc_biz_id: string | number;
    bk_biz_id: string | number;
    Vue?: any;
    i18n: VueI18n;
    enable_aiops: boolean;
    enable_apm: boolean;
    ce_url?: string;
    timezone?: string;
    LoginModal?: any;
    enable_message_queue: boolean;
    is_superuser: boolean;
    job_url: string;
    bk_job_url: string;
    bk_url: string;
    userInfo: { isSuperuser: boolean };
    message_queue_dsn: string;
    max_available_duration_limit: number;
    bk_log_search_url: string;
    bk_nodeman_host: string;
    collecting_config_file_maxsize: string;
    enable_cmdb_level: string;
    bkPaasHost: string;
    mail_report_biz: string;
    platform: string;
    slimit: number;
    source_app: string;
    bk_bcs_url: string;
    graph_watermark: string;
    __BK_WEWEB_DATA__: Record<string, any>;
    __POWERED_BY_BK_WEWEB__?: boolean;
    token?: string;
  }
  namespace VueTsxSupport.JSX {
    type Element = base.Element;
    type ElementClass = base.ElementClass;
    type LibraryManagedAttributes<C, P> = C extends new () => infer V
      ? base.CombinedTsxComponentAttrs<
          base.AttributesOf<V>,
          base.PropsOf<V>,
          base.PrefixedEventsOf<V>,
          base.OnOf<V>,
          V extends { $scopedSlots: infer X } ? X : {},
          base.IsPropsObjectAllowed<V>
        > &
          (V extends { _tsxattrs: infer T } ? T : {})
      : P;

    interface IntrinsicElements extends base.IntrinsicElements {
      // allow unknown elements
      [name: string]: any;

      // builtin components
      transition: base.CombinedTsxComponentAttrs<builtin.TransitionProps, {}, {}, {}, {}, true>;
      'transition-group': base.CombinedTsxComponentAttrs<builtin.TransitionGroupProps, {}, {}, {}, {}, true>;
      'keep-alive': base.CombinedTsxComponentAttrs<builtin.KeepAliveProps, {}, {}, {}, {}, true>;
    }
  }
}
