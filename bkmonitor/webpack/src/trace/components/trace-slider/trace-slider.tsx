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
import { defineAsyncComponent, defineComponent, toRef } from 'vue';

import { Sideslider } from 'bkui-vue';

import { useTraceSlider } from './hooks/use-trace-slider';
import { TRACE_SLIDER_Z_INDEX } from '@/pages/main/constants';
import TraceDetailHeader from '@/pages/main/inquire-content/trace-detail-header';

import './trace-slider.scss';

const TraceDetail = defineAsyncComponent(
  () => import(/* webpackChunkName: "trace-slider-detail" */ '@/pages/main/inquire-content/trace-detail')
);

export default defineComponent({
  name: 'TraceSlider',
  props: {
    isShow: {
      type: Boolean,
      required: true,
    },
    appName: {
      type: String,
      default: '',
    },
    bizId: {
      type: [Number, String],
      default: undefined,
    },
    traceId: {
      type: String,
      default: '',
    },
  },
  emits: {
    sliderClose: () => true,
  },
  setup(props, { emit }) {
    const { fullscreen, handleFullscreenChange, handleSliderClose, traceDetailRef } = useTraceSlider({
      isShow: toRef(props, 'isShow'),
      appName: toRef(props, 'appName'),
      bizId: toRef(props, 'bizId'),
      traceId: toRef(props, 'traceId'),
    });

    const handleClosed = () => {
      handleSliderClose();
      emit('sliderClose');
    };

    return {
      fullscreen,
      handleClosed,
      handleFullscreenChange,
      traceDetailRef,
    };
  },
  render() {
    const { appName, bizId, isShow, traceId } = this.$props;
    return (
      <Sideslider
        width={this.fullscreen ? '100%' : '85%'}
        class='trace-slider'
        v-slots={{
          header: () => (
            <TraceDetailHeader
              appName={appName}
              bizId={bizId}
              fullscreen={this.fullscreen}
              traceId={traceId}
              isInTable
              onFullscreenChange={this.handleFullscreenChange}
            />
          ),
        }}
        esc-close={false}
        is-show={isShow}
        render-directive='if'
        zIndex={TRACE_SLIDER_Z_INDEX}
        transfer
        onClosed={this.handleClosed}
        onUpdate:isShow={(visible: boolean) => {
          if (!visible) this.handleClosed();
        }}
      >
        <div class='trace-slider-main'>
          {isShow ? (
            <TraceDetail
              key={`${appName}-${traceId}`}
              ref='traceDetailRef'
              appName={appName}
              bizId={bizId}
              traceID={traceId}
              isInTable
            />
          ) : undefined}
        </div>
      </Sideslider>
    );
  },
});
