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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

type CompareGraphToolsEvent = {
  onDownloadImage: () => void;
  onResetCenter: () => void;
  onScaleChange: (scaleValue: number) => void;
  onShowLegend: () => void;
  onShowThumbnail: () => void;
};
type CompareGraphToolsProps = {
  maxScale?: number;
  minScale?: number;
  originScaleValue?: number;
  scaleStep?: number;
  scaleValue?: number;
  showLegend?: boolean;
  showThumbnail?: boolean;
};

import './compare-graph-tools.scss';
@Component
export default class CompareGraphTools extends tsc<CompareGraphToolsProps, CompareGraphToolsEvent> {
  @Prop({ default: 50 }) originScaleValue!: number;
  @Prop({ default: 1 }) scaleValue!: number;
  @Prop({ default: 100 }) maxScale!: number;
  @Prop({ default: 1 }) minScale!: number;
  @Prop({ default: 0.1 }) scaleStep!: number;
  @Prop({ default: false }) showThumbnail!: boolean;
  @Prop({ default: false }) showLegend!: boolean;

  @Emit('showThumbnail')
  handleShowThumbnail() {}

  @Emit('showLegend')
  handleShowLegend() {}

  @Emit('downloadImage')
  handleDownloadImage() {}

  @Emit('scaleChange')
  handleScaleChange(scale: number) {
    if (scale > this.maxScale) {
      return this.maxScale;
    }
    if (scale < this.minScale) {
      return this.minScale;
    }
    return scale;
  }

  @Emit('resetCenter')
  handleResetCenter() {}

  render() {
    return (
      <div class='compare-graph-tools'>
        <div class='tools-menu'>
          <i
            class={`icon-monitor icon-minimap item-store ${this.showThumbnail ? 'is-active' : ''}`}
            v-bk-tooltips={{ content: this.$t('地图') }}
            onClick={this.handleShowThumbnail}
          />
          <i
            class={`icon-monitor icon-legend ${this.showLegend ? 'is-active' : ''}`}
            v-bk-tooltips={{ content: this.$t('图例') }}
            onClick={this.handleShowLegend}
          />
          <i
            class='icon-monitor icon-xiazai1 item-store'
            v-bk-tooltips={{ content: this.$t('下载') }}
            onClick={this.handleDownloadImage}
          />
          <i
            class='icon-monitor icon-mc-position-tips item-store'
            v-bk-tooltips={{ content: this.$t('回中') }}
            onClick={this.handleResetCenter}
          />
        </div>
        <div class='tools-scale'>
          <i
            class='icon-monitor icon-mc-restoration-ratio item-icon'
            v-bk-tooltips={{ content: this.$t('原始大小') }}
            onClick={() => {
              this.handleScaleChange(this.originScaleValue);
            }}
          />
          <i
            class='icon-monitor icon-minus-line item-icon scale-icon'
            onClick={() => {
              this.handleScaleChange(this.scaleValue - this.scaleStep);
            }}
          />
          <bk-slider
            class='scale-slider'
            max-value={this.maxScale}
            min-value={this.minScale}
            show-tip={false}
            step={this.scaleStep}
            value={this.scaleValue}
            onInput={this.handleScaleChange}
          />
          <i
            class='icon-monitor icon-plus-line item-icon scale-icon'
            onClick={() => {
              this.handleScaleChange(this.scaleValue + this.scaleStep);
            }}
          />
        </div>
      </div>
    );
  }
}
