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
import { defineComponent } from 'vue';

import './graph-tools.scss';

export default defineComponent({
  name: 'GraphTools',
  props: {
    scaleValue: {
      default: 100,
    },
    maxScale: {
      default: 100,
    },
    minScale: {
      default: 1,
    },
    scaleStep: {
      default: 1,
    },
    showThumbnail: {
      type: Boolean,
      default: true,
    },
    thumbnailActive: {
      type: Boolean,
      default: false,
    },
    legendActive: {
      type: Boolean,
      default: false,
    },
    showLegend: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['scaleChange', 'storeImg', 'showThumbnail', 'showLegend'],
  setup(props, { emit }) {
    function handlePlus() {
      emit('scaleChange', Math.min(props.maxScale, props.scaleValue + props.scaleStep));
    }
    function handleMinus() {
      emit('scaleChange', Math.max(props.scaleValue - props.scaleStep, props.minScale));
    }
    function handleStoreImg() {
      emit('storeImg');
    }
    function handleShowLegend() {
      emit('showLegend');
    }
    /**
     * @description: 显示缩略图
     */
    function handleShowThumbnail() {
      emit('showThumbnail');
    }
    return {
      handlePlus,
      handleMinus,
      handleStoreImg,
      handleShowThumbnail,
      handleShowLegend,
    };
  },
  render() {
    return (
      <div class='graph-tools'>
        <div class='tools-menu'>
          {this.showThumbnail && (
            <i
              class={`icon-monitor icon-minimap item-store ${this.thumbnailActive ? 'is-active' : ''}`}
              onClick={this.handleShowThumbnail}
            />
          )}
          {this.showLegend && (
            <i
              class={`icon-monitor icon-legend ${this.legendActive ? 'is-active' : ''}`}
              onClick={this.handleShowLegend}
            />
          )}
          <i
            class='icon-monitor icon-xiazai1 item-store'
            onClick={this.handleStoreImg}
          />
        </div>
        {
          <div class='tools-scale'>
            <i
              class='icon-monitor icon-plus-line item-icon'
              onClick={this.handlePlus}
            />
            <span class='scale-text'>{this.scaleValue}%</span>
            <i
              class='icon-monitor icon-minus-line item-icon'
              onClick={this.handleMinus}
            />
          </div>
        }
      </div>
    );
  },
});
