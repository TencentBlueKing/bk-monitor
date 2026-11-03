/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import 'vue-tsx-support/lib/api';
import type { EventHandlers } from 'vue-tsx-support/types/base';
import type { AllowedComponentProps, VNodeProps } from 'vue';
import type { TranslateFunction } from '@/platform/i18n/translator';
// The compatibility Class keeps its source prop/event interfaces, while Vue3
// JSX reads $props instead of vue-tsx-support's old _tsx marker.
declare module 'vue-tsx-support/lib/api' {
  interface Component<Props, PrefixedEvents, ScopedSlotArgs> {
    // i18n installs this same translator on both the Vue3 app and the compat
    // constructor prototype. Do not include removed legacy UI services here.
    readonly $t: TranslateFunction;
    readonly $props: Props & EventHandlers<PrefixedEvents> & AllowedComponentProps & VNodeProps;
  }
}
