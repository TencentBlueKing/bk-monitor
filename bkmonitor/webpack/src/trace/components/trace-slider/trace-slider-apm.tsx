/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { defineComponent, inject, onBeforeUnmount, watch } from 'vue';

import TraceSlider from './trace-slider';
import { clearEmbedContext, setEmbedContext } from '@/common/embed-context';

/** 从 trace-slider-apm-entry 注入的宿主属性 */
export const BRIDGE_PROPS_KEY = Symbol('traceSliderBridgeProps');
/** 从 trace-slider-apm-entry 注入的宿主事件发射器 */
export const BRIDGE_EMIT_KEY = Symbol('traceSliderBridgeEmit');

const resolveEmbedBizId = (bizId: unknown): number => {
  if (bizId != null && bizId !== '' && !Number.isNaN(+bizId)) {
    return +bizId;
  }
  return +(window.bk_biz_id || window.cc_biz_id);
};

/**
 * Vue2 宿主用的 Trace 侧滑适配层：把 bridge props 转成 TraceSlider，并标记嵌入态以便复制链接走 /trace/。
 */
export default defineComponent({
  name: 'TraceSliderApm',
  setup() {
    const defaultBridgeProps: Record<string, unknown> = {};
    const defaultBridgeEmit = (_event: string, ..._args: unknown[]) => {};
    const bridgeProps = inject(BRIDGE_PROPS_KEY, defaultBridgeProps);
    const bridgeEmit = inject(BRIDGE_EMIT_KEY, defaultBridgeEmit);

    watch(
      () => resolveEmbedBizId(bridgeProps.bizId),
      bizId => {
        setEmbedContext({ bizId });
      },
      { immediate: true }
    );
    onBeforeUnmount(clearEmbedContext);

    const handleSliderClose = () => {
      bridgeEmit('sliderClose');
    };

    return {
      bridgeProps,
      handleSliderClose,
    };
  },
  render() {
    return (
      <TraceSlider
        appName={this.bridgeProps.appName as string}
        bizId={this.bridgeProps.bizId as number | string | undefined}
        isShow={!!this.bridgeProps.isShow}
        traceId={this.bridgeProps.traceId as string}
        onSliderClose={this.handleSliderClose}
      />
    );
  },
});
