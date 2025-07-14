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

import type { IBizItem, ISpaceItem } from './types';
import type VueI18n from 'vue-i18n';
import type { TranslateResult } from 'vue-i18n';
import type * as base from 'vue-tsx-support/types/base';
import type * as builtin from 'vue-tsx-support/types/builtin-components';

interface IBkInfoProps {
  title: unknown;
  zIndex: number;
  width: number | string;
  type: string;
  container: Element | string;
  maskClose: boolean;
  confirmLoading: boolean;
  subHeader?: any;
  subTitle?: any;
  escClose?: any;
  showFooter?: boolean;
  extCls?: string;
  okText?: string | TranslateResult;
  cancelText?: string | TranslateResult;
  confirmFn: (v: unknown) => void;
  cancelFn: (v: unknown) => void;
}
declare module 'vue/types/vue' {
  interface Vue {
    $bkInfo?: (p: Partial<IBkInfoProps>) => { close: () => void };
    $bkMessage?: (p: Partial<object>) => void;
    $bkPopover?: (...object) => void;
    $bkToPinyin?: (str: string, lowerCase?: boolean, separator?: string) => string;
    $bkLoading?: any;
    $api?: any;
  }
}
declare module '*/store';
declare module '*.svg';
interface ShowLoginModalOption {
  loginUrl: string;
  width?: number;
  height?: number;
  maskColor?: string;
  maskZIndex?: number;
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
    default_biz_id: number | string;
    space_uid: string;
    Vue?: any;
    i18n: VueI18n;
    enable_aiops: boolean;
    enable_apm: boolean;
    ce_url?: string;
    enable_message_queue: boolean;
    is_superuser: boolean;
    job_url: string;
    bk_job_url: string;
    bk_url: string;
    userInfo: { isSuperuser: boolean };
    message_queue_dsn: string;
    max_available_duration_limit: number;
    bk_cc_url: string;
    bk_log_search_url: string;
    cluster_setup_url: string;
    bk_docs_site_url: string;
    bk_doc_version: string;
    agent_setup_url: string;
    bk_component_api_url: string;
    bk_domain: string;
    monitor_managers: string[];
    uptimecheck_output_fields: string[];
    bk_nodeman_host: string;
    collecting_config_file_maxsize: string;
    enable_cmdb_level: string;
    bkPaasHost: string;
    mail_report_biz: string;
    platform: {
      ce: boolean; // 社区版
      ee: boolean; // 企业版
      te: boolean; // 内部版
    };
    slimit: number;
    source_app: string;
    bk_bcs_url: string;
    __BK_WEWEB_DATA__: Record<string, any>;
    __POWERED_BY_BK_WEWEB__?: boolean;
    rawDocument: Document;
    rawWindow: Window;
    token?: string;
    enable_create_chat_group: boolean;
    __bk_zIndex_manager: {
      nextZIndex: () => number;
    };
    host_data_fields: string[];
    bkchat_manage_url: string;
    timezone: string;
    show_realtime_strategy: boolean;
    bk_paas_host: string;
    docUrlMap: Record<string, string>;
    page_title: string;
    wxwork_bot_send_image?: boolean;
    showLoginModal: (option: ShowLoginModalOption) => void;
    BLUEKING?: Record<string, any>;
    bk_shared_res_url: string;
    footer_version: string;
    __AuthMap__: Map<string, Map<string, boolean>>;
    csrf_token: string;
    enable_ai_assistant?: boolean;
    graph_watermark?: boolean;
    k8s_v2_biz_list?: number[]; // 开启 k8s v2 版本的业务列表
    // 以下为日志全局变量配置
    mainComponent: any;
    AJAX_URL_PREFIX: string;
    BK_DOC_URL?: string;
    FEATURE_TOGGLE?: Record<string, 'off' | 'on'>;
    /*
     * 灰度业务是否开启故障事件中心
     */
    enable_aiops_event_center_biz_list?: number[];
    // 多租户用户中心接口地址
    bk_user_web_api_url?: string;
    // 多租户用户中心是否开启
    enable_multi_tenant_mode?: boolean;
    // 多租户租户id
    bk_tenant_id?: string;
    // ai小鲸鱼 api base url
    ai_xiao_jing_base_url?: string;
  }
  interface HTMLElement {
    ___zrEVENTSAVED?: Record<string, any>; // echarts zrender instance
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
      'bk-user-display-name': base.CombinedTsxComponentAttrs<
        | {
            user_id: string;
          }
        | base.KnownAttrs,
        object,
        object,
        object,
        object,
        false
      >;
    }
  }
}
