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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { addListener, removeListener } from '@blueking/fork-resize-detector';

import { Debounce } from '../../../../monitor-common/utils/utils';

import './cards-container.scss';

interface ICardsContainerProps {
  title?: string;
  showSeeAll?: boolean;
}

@Component({
  name: 'CardsContainer'
})
export default class CardsContainer extends tsc<ICardsContainerProps> {
  @Prop({ type: String, default: '' }) title: string;
  @Prop({ type: Boolean, default: false }) showSeeAll: boolean;

  @Ref('content') contentRef: HTMLDivElement;

  isSeeAll = false;
  seeAllDisable = true;

  mounted() {
    if (this.showSeeAll) {
      addListener(this.contentRef as HTMLDivElement, this.handleResize);
      this.handleResize();
    }
  }
  beforeDestroy() {
    removeListener(this.contentRef as HTMLDivElement, this.handleResize);
  }

  @Debounce(300)
  handleResize() {
    if (this.showSeeAll) {
      const rect = (this.contentRef as Element).getBoundingClientRect();
      const width = rect?.width || 0;
      const len = this.contentRef.children?.length || 0;
      if (!!len && !!width) {
        const itemRect = (this.contentRef.children[0] as Element).getBoundingClientRect();
        const itemWidth = itemRect?.width || 0;
        this.seeAllDisable = !(itemWidth * len > width);
      }
    }
  }

  handleClickSeeAll() {
    this.isSeeAll = !this.isSeeAll;
  }

  render() {
    return (
      <div class='uptime-check-cards-container'>
        <div class='title'>
          <div class='left'>
            {this.title}
            {this.$slots.title}
          </div>
          {this.showSeeAll && !this.seeAllDisable ? (
            <bk-button
              text
              title='primary'
              class='right-btn'
              on-click={this.handleClickSeeAll}
            >
              {this.isSeeAll ? this.$t('收起') : this.$t('显示全部')}
            </bk-button>
          ) : undefined}
        </div>
        <div
          class={['content', { 'pack-up': !this.isSeeAll && this.showSeeAll }]}
          ref='content'
        >
          {this.$slots.default}
        </div>
      </div>
    );
  }
}
