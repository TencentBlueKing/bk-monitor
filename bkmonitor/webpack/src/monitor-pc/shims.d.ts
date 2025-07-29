import type * as base from 'vue-tsx-support/types/base';
import type * as builtin from 'vue-tsx-support/types/builtin-components';

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
import 'xss/typings/xss';

import type { IBizItem, ISpaceItem } from './types';
import type VueI18n from 'vue-i18n';
import type { TranslateResult } from 'vue-i18n';

interface IBkInfoProps {
  cancelText?: string | TranslateResult;
  confirmLoading: boolean;
  container: Element | string;
  escClose?: any;
  extCls?: string;
  maskClose: boolean;
  okText?: string | TranslateResult;
  showFooter?: boolean;
  subHeader?: any;
  subTitle?: any;
  title: unknown;
  type: string;
  width: number | string;
  zIndex: number;
  cancelFn: (v: unknown) => void;
  confirmFn: (v: unknown) => void;
}
declare module 'vue/types/vue' {
  interface Vue {
    $api?: any;
    $bkLoading?: any;
    $bkInfo?: (p: Partial<IBkInfoProps>) => { close: () => void };
    $bkMessage?: (p: Partial<object>) => void;
    $bkPopover?: (...object) => void;
    $bkToPinyin?: (str: string, lowerCase?: boolean, separator?: string) => string;
  }
}
declare module '*/store';
declare module '*.svg';
interface ShowLoginModalOption {
  height?: number;
  loginUrl: string;
  maskColor?: string;
  maskZIndex?: number;
  width?: number;
}
declare global {
  interface HTMLElement {
    ___zrEVENTSAVED?: Record<string, any>; // echarts zrender instance
  }
  interface Window {
    __AuthMap__: Map<string, Map<string, boolean>>;
    __BK_WEWEB_DATA__: Record<string, any>;
    __POWERED_BY_BK_WEWEB__?: boolean;
    agent_setup_url: string;
    // ai小鲸鱼 api base url
    ai_xiao_jing_base_url?: string;
    AJAX_URL_PREFIX: string;
    bk_bcs_url: string;
    bk_biz_id: number | string;
    bk_biz_list: IBizItem[];
    bk_cc_url: string;
    bk_component_api_url: string;
    BK_DOC_URL?: string;
    bk_doc_version: string;
    bk_docs_site_url: string;
    bk_domain: string;
    bk_job_url: string;
    bk_log_search_url: string;
    bk_nodeman_host: string;
    bk_paas_host: string;
    bk_shared_res_url: string;
    // 多租户租户id
    bk_tenant_id?: string;
    bk_url: string;
    // 多租户用户中心接口地址
    bk_user_web_api_url?: string;
    bkchat_manage_url: string;
    bkPaasHost: string;
    BLUEKING?: Record<string, any>;
    cc_biz_id: number | string;
    ce_url?: string;
    cluster_setup_url: string;
    collecting_config_file_maxsize: string;
    csrf_cookie_name: string;
    csrf_token: string;
    default_biz_id: number | string;
    docUrlMap: Record<string, string>;
    enable_ai_assistant?: boolean;
    enable_aiops: boolean;
    /*
     * 灰度业务是否开启故障事件中心
     */
    enable_aiops_event_center_biz_list?: number[];
    enable_apm: boolean;
    enable_cmdb_level: string;
    enable_create_chat_group: boolean;
    enable_message_queue: boolean;
    // 多租户用户中心是否开启
    enable_multi_tenant_mode?: boolean;
    FEATURE_TOGGLE?: Record<string, 'off' | 'on'>;
    footer_version: string;
    graph_watermark?: boolean;
    host_data_fields: string[];
    i18n: VueI18n;
    is_superuser: boolean;
    job_url: string;
    k8s_v2_biz_list?: number[]; // 开启 k8s v2 版本的业务列表
    mail_report_biz: string;
    // 以下为日志全局变量配置
    mainComponent: any;
    max_available_duration_limit: number;
    message_queue_dsn: string;
    monitor_managers: string[];
    page_title: string;
    rawDocument: Document;
    rawWindow: Window;
    show_realtime_strategy: boolean;
    site_url: string;
    slimit: number;
    source_app: string;
    space_list: ISpaceItem[];
    space_uid: string;
    static_url: string;
    timezone: string;
    token?: string;
    uin: string;
    uptimecheck_output_fields: string[];
    user_name: string;
    userInfo: { isSuperuser: boolean };
    username: string;
    Vue?: any;
    wxwork_bot_send_image?: boolean;
    showLoginModal: (option: ShowLoginModalOption) => void;
    __bk_zIndex_manager: {
      nextZIndex: () => number;
    };
    platform: {
      ce: boolean; // 社区版
      ee: boolean; // 企业版
      te: boolean; // 内部版
    };
  }
  namespace VueTsxSupport.JSX {
    type Element = base.Element;
    type ElementClass = base.ElementClass;
    interface IntrinsicElements extends base.IntrinsicElements {
      // allow unknown elements
      [name: string]: any;

      'keep-alive': base.CombinedTsxComponentAttrs<builtin.KeepAliveProps, object, object, object, object, true>;
      // builtin components
      transition: base.CombinedTsxComponentAttrs<builtin.TransitionProps, object, object, object, object, true>;
      'bk-user-display-name': base.CombinedTsxComponentAttrs<
        | base.KnownAttrs
        | {
            user_id: string;
          },
        object,
        object,
        object,
        object,
        false
      >;
      'transition-group': base.CombinedTsxComponentAttrs<
        builtin.TransitionGroupProps,
        object,
        object,
        object,
        object,
        true
      >;
    }

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
  }
}
