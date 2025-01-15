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
import { computed, defineComponent } from 'vue';

import { getBoundsofRects, getRectOfNodes, useVueFlow } from '@vue-flow/core';
import { MiniMap } from '@vue-flow/minimap';

import './service-topo-mini-map.scss';
import '@vue-flow/minimap/dist/style.css';

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
  },
  setup(props) {
    /* 以下逻辑来源于 @vue-flow/minimap 仅用于缩略图蓝色窗口的实现 */
    const offsetScale = 5;
    const maskBorderRadius = 0;

    const { getNodesInitialized, viewport, dimensions } = useVueFlow();

    const bb = computed(() => getRectOfNodes(getNodesInitialized.value));

    const viewBB = computed(() => ({
      x: -viewport.value.x / viewport.value.zoom,
      y: -viewport.value.y / viewport.value.zoom,
      width: dimensions.value.width / viewport.value.zoom,
      height: dimensions.value.height / viewport.value.zoom,
    }));

    const boundingRect = computed(() =>
      getNodesInitialized.value?.length ? getBoundsofRects(bb.value, viewBB.value) : viewBB.value
    );

    const viewScale = computed(() => {
      const scaledWidth = boundingRect.value.width / props.width;
      const scaledHeight = boundingRect.value.height / props.height;

      return Math.max(scaledWidth, scaledHeight);
    });

    const viewBox = computed(() => {
      const viewWidth = viewScale.value * props.width;
      const viewHeight = viewScale.value * props.height;
      const offset = offsetScale * viewScale.value;

      return {
        offset,
        x: boundingRect.value.x - (viewWidth - boundingRect.value.width) / 2 - offset,
        y: boundingRect.value.y - (viewHeight - boundingRect.value.height) / 2 - offset,
        width: viewWidth + offset * 2,
        height: viewHeight + offset * 2,
      };
    });

    const d = computed(() => {
      if (!viewBox.value.x || !viewBox.value.y) {
        return '';
      }

      return `
        M${viewBB.value.x + maskBorderRadius},${viewBB.value.y}
        h${viewBB.value.width - 2 * maskBorderRadius}
        a${maskBorderRadius},${maskBorderRadius} 0 0 1 ${maskBorderRadius},${maskBorderRadius}
        v${viewBB.value.height - 2 * maskBorderRadius}
        a${maskBorderRadius},${maskBorderRadius} 0 0 1 -${maskBorderRadius},${maskBorderRadius}
        h${-(viewBB.value.width - 2 * maskBorderRadius)}
        a${maskBorderRadius},${maskBorderRadius} 0 0 1 -${maskBorderRadius},-${maskBorderRadius}
        v${-(viewBB.value.height - 2 * maskBorderRadius)}
        a${maskBorderRadius},${maskBorderRadius} 0 0 1 ${maskBorderRadius},-${maskBorderRadius}z`;
    });

    return {
      viewBox,
      d,
    };
  },
  render() {
    return (
      <div
        style={{
          width: `${this.width}px`,
          height: `${this.height}px`,
        }}
        class='service-topo-mini-map-warp'
      >
        <MiniMap
          width={this.width}
          height={this.height}
          maskColor={'rgb(0 0 0 / 0%)'}
          pannable={true}
        />
        <div
          style={{
            width: `${this.width}px`,
            height: `${this.height}px`,
          }}
          class='mini-map-mask'
        >
          <svg
            width={this.width}
            height={this.height}
            viewBox={[this.viewBox.x, this.viewBox.y, this.viewBox.width, this.viewBox.height].join(' ')}
          >
            <path
              d={this.d}
              fill={'#3a84ff1a'}
              stroke={'#3A84FF'}
              stroke-width={2}
            />
          </svg>
        </div>
      </div>
    );
  },
});
