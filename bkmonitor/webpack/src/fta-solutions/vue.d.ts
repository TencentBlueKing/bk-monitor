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

import { IVueI18n } from 'vue-i18n';

import * as base from 'vue-tsx-support/types/base';
import * as builtin from 'vue-tsx-support/types/builtin-components';

import { IBizItem, ISpaceItem } from './typings';

declare global {
  namespace VueTsxSupport.JSX {
    type Element = base.Element;
    type ElementClass = base.ElementClass;
    type LibraryManagedAttributes<C, P> = C extends new () => infer V
      ? base.CombinedTsxComponentAttrs<
          base.AttributesOf<V>,
          base.PropsOf<V>,
          base.PrefixedEventsOf<V>,
          base.OnOf<V>,
          V extends { $scopedSlots: infer X } ? X : object,
          base.IsPropsObjectAllowed<V>
        > &
          (V extends { _tsxattrs: infer T } ? T : object)
      : P;

    interface IntrinsicElements extends base.IntrinsicElements {
      // allow unknown elements
      [name: string]: any;

      // builtin components
      transition: base.CombinedTsxComponentAttrs<builtin.TransitionProps, object, object, object, object, true>;
      'transition-group': base.CombinedTsxComponentAttrs<
        builtin.TransitionGroupProps,
        object,
        object,
        object,
        object,
        true
      >;
      'keep-alive': base.CombinedTsxComponentAttrs<builtin.KeepAliveProps, object, object, object, object, true>;
    }
  }
}
interface IBkInfoProps {
  title: unknown;
  subTitle: unknown;
  width: number | string;
  type: string;
  confirmLoading: boolean;
  subHeader?: any;
  maskClose?: boolean;
  escClose?: boolean;
  confirmFn: (v: unknown) => void;
  cancelFn: (v: unknown) => void;
}

declare module 'vue/types/vue' {
  interface Vue {
    $bkInfo?: (p: Partial<IBkInfoProps>) => void;
    $bkMessage?: (p: Partial<object>) => void;
    $bkPopover?: (...Object) => void;
  }
}
declare global {
  interface Window {
    site_url: string;
    static_url: string;
    user_name: string;
    username: string;
    uin: string;
    space_list: ISpaceItem[];
    bk_biz_list: IBizItem[];
    csrf_cookie_name: string;
    cc_biz_id: number | string;
    bk_biz_id: number | string;
    bk_log_search_url: string;
    bklogsearch_host: string;
    Vue?: any;
    i18n: IVueI18n;
    bk_url: string;
    timezone: string;
    __POWERED_BY_BK_WEWEB__?: boolean;
    __BK_WEWEB_DATA__: Record<string, any>;
    __bk_zIndex_manager: {
      nextZIndex: () => number;
    };
    source_app: string;
    enable_create_chat_group: boolean;
    bkchat_manage_url: string;
    aegis?: {
      report: (p: any) => void;
      infoAll: (p: any) => void;
    };
  }
}
