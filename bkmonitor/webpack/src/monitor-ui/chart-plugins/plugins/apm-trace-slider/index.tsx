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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import '@blueking/apm-vue3-for-vue2/index.css';

interface ApmTraceSliderEvents {
  onSliderClose: () => void;
}

interface ApmTraceSliderProps {
  slideDetail?: null | {
    appName: string;
    bizId?: number;
    traceId: string;
  };
}

interface TraceSliderMountHandle {
  unmount: () => void;
  update: (props: Record<string, unknown>) => void;
}

/** 避免 Vue2 把句柄做成响应式，也避开 any */
const sliderHandles = new WeakMap<object, TraceSliderMountHandle>();

/**
 * Vue2 宿主里的 Trace 详情侧滑。
 * 第一次打开才动态加载 Vue3 子应用，关闭只把 isShow 设为 false，页面卸载时再 unmount。
 */
@Component
export default class ApmTraceSlider extends tsc<ApmTraceSliderProps, ApmTraceSliderEvents> {
  @Prop({ type: Object, default: null }) readonly slideDetail: ApmTraceSliderProps['slideDetail'];

  private isUnmounted = false;
  private mounting = false;

  get sliderProps() {
    const detail = this.slideDetail;
    return {
      isShow: Boolean(detail?.traceId),
      appName: detail?.appName || '',
      bizId: detail?.bizId,
      traceId: detail?.traceId || '',
    };
  }

  @Watch('slideDetail', { immediate: true, deep: true })
  async handleSlideDetailChange() {
    const handle = sliderHandles.get(this);
    if (!this.slideDetail?.traceId) {
      handle?.update({ isShow: false, traceId: '', appName: '', bizId: undefined });
      return;
    }
    if (!handle) {
      await this.mountSlider();
    }
    sliderHandles.get(this)?.update({ ...this.sliderProps });
  }

  async mountSlider() {
    if (this.mounting || sliderHandles.has(this) || this.isUnmounted) return;
    this.mounting = true;
    await this.$nextTick();
    const el = this.$refs.root as HTMLElement;
    if (!el || this.isUnmounted) {
      this.mounting = false;
      return;
    }

    const savedI18n = window.i18n;
    const { mountTraceSlider: mount } = (await import('@blueking/apm-vue3-for-vue2')) as unknown as {
      mountTraceSlider: (
        el: HTMLElement | string,
        options?: {
          onEvent?: (event: string, ...args: unknown[]) => void;
          props?: Record<string, unknown>;
        }
      ) => TraceSliderMountHandle;
    };
    window.i18n = savedI18n;

    if (this.isUnmounted) {
      this.mounting = false;
      return;
    }

    sliderHandles.set(
      this,
      mount(el, {
        props: { ...this.sliderProps },
        onEvent: (event: string) => {
          if (event === 'sliderClose') {
            this.$emit('sliderClose');
          }
        },
      })
    );
    this.mounting = false;
  }

  beforeDestroy() {
    this.isUnmounted = true;
    sliderHandles.get(this)?.unmount();
    sliderHandles.delete(this);
  }

  render() {
    return (
      <div
        ref='root'
        class='apm-trace-slider-host'
      />
    );
  }
}
