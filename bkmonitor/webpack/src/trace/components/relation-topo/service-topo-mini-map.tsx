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
import { PropType, defineComponent, onMounted, ref, watch } from 'vue';

import { toCanvas } from 'html-to-image';
import { throttle } from 'throttle-debounce';

import './service-topo-mini-map.scss';

export default defineComponent({
  name: 'ServiceTopoMiniMap',
  props: {
    width: {
      type: Number,
      default: 225,
    },
    height: {
      type: Number,
      default: 148,
    },
    refreshKey: {
      type: [Number, String],
      default: 0,
    },
    getTargetDom: {
      type: Function,
      default: () => {},
    },
    position: {
      type: Object as PropType<{ x: number; y: number; zoom: number }>,
      default: () => ({ x: 0, y: 0, zoom: 1 }),
    },
  },
  setup(props) {
    const canvasRef = ref<HTMLCanvasElement>();
    const throttleInit = throttle(300, init, { noLeading: true });

    onMounted(() => {
      throttleInit();
    });

    watch(
      () => props.refreshKey,
      key => {
        if (!!key) {
          throttleInit();
        }
      }
    );

    function init() {
      const targetEl = props.getTargetDom();
      toCanvas(targetEl).then(canvas => {
        const ctx = canvasRef.value.getContext('2d');
        ctx.clearRect(0, 0, props.width, props.height);
        ctx.drawImage(canvas, 0, 0, props.width, props.height);
      });
    }

    return {
      canvasRef,
    };
  },
  render() {
    return (
      <div class='service-topo-mini-map'>
        <canvas
          ref='canvasRef'
          style={{
            height: `${this.height}px`,
            width: `${this.width}px`,
          }}
          class='mini-map-container'
        ></canvas>
        <div class='mini-map-mask'></div>
      </div>
    );
  },
});
