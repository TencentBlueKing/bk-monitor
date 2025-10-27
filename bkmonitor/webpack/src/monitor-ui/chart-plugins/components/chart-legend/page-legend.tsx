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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import CommonLegend from './common-legend';

import './page-legend.scss';

interface PageLegendProps {
  wrapHeight: number;
}

/** 折线图分页的高度 */
@Component
class PageLegend extends CommonLegend {
  @Prop({ type: Number, default: 40 }) wrapHeight!: number;

  @Ref('commonLegend') commonLegendRef!: HTMLDivElement;

  /** 当前页 */
  currentPageNum = 1;
  /** 所有页 */
  legendMaxPageNum = 1;
  /** 是否展示分页ICON */
  isShowPageIcon = false;

  @Watch('legendData', { immediate: true })
  handleLegendDataChange() {
    this.$nextTick(() => {
      const comLegRef = this.commonLegendRef;
      this.isShowPageIcon = comLegRef.scrollHeight > comLegRef.clientHeight;
      if (this.isShowPageIcon) {
        comLegRef.addEventListener('wheel', this.legendWheel);
        this.legendMaxPageNum = Math.ceil(comLegRef.scrollHeight / this.wrapHeight);
      } else {
        comLegRef.removeEventListener('wheel', this.legendWheel);
      }
    });
  }

  legendWheel(event: WheelEvent) {
    event.preventDefault();
    // 根据 event.deltaY 判断滚动方向
    if (event.deltaY < 0) {
      // 向上滚动
      if (this.currentPageNum > 1) this.currentPageNum -= 1;
    } else {
      // 向下滚动
      if (this.currentPageNum < this.legendMaxPageNum) this.currentPageNum += 1;
    }
  }

  @Watch('currentPageNum')
  watchPageNum(v: number) {
    this.commonLegendRef.scrollTo({
      top: (v - 1) * this.wrapHeight,
    });
  }

  beforeDestroy() {
    this.commonLegendRef?.removeEventListener('wheel', this.legendWheel);
  }

  render() {
    return (
      <div
        style={{ height: `${this.wrapHeight}px` }}
        class='page-legend-box-component'
      >
        <div
          ref='commonLegend'
          class='common-legend'
        >
          {this.legendData.map((legend, index) => {
            return (
              <div
                key={index}
                class='common-legend-item'
                onClick={e => this.handleLegendEvent(e, 'click', legend)}
              >
                <span
                  style={{ backgroundColor: legend.show ? legend.color : '#ccc' }}
                  class='legend-icon'
                />
                <div
                  style={{ color: legend.show ? '#63656e' : '#ccc' }}
                  class='legend-name'
                  v-bk-overflow-tips
                >
                  {legend.name}
                </div>
              </div>
            );
          })}
        </div>
        {this.isShowPageIcon && (
          <div class='legend-icon-box'>
            <i
              class={{
                'bk-select-angle bk-icon icon-angle-up-fill last-page-up': true,
                disabled: this.currentPageNum === 1,
              }}
              onClick={() => {
                if (this.currentPageNum > 1) this.currentPageNum -= 1;
              }}
            />
            <i
              class={{
                'bk-select-angle bk-icon icon-angle-up-fill': true,
                disabled: this.currentPageNum === this.legendMaxPageNum,
              }}
              onClick={() => {
                if (this.currentPageNum < this.legendMaxPageNum) this.currentPageNum += 1;
              }}
            />
          </div>
        )}
      </div>
    );
  }
}

export default ofType<PageLegendProps>().convert(PageLegend);
