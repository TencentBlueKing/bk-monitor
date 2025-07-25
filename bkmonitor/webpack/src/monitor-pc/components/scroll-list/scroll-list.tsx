import { Component, Prop, Ref } from 'vue-property-decorator';
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
import { Component as tsc } from 'vue-tsx-support';

import { type IScrollListItem, ScrollPageMode } from './type';

import './scroll-list.scss';
export interface IScrollListEvents {
  pageChange: (page: number) => void;
}
export interface IScrollListProps {
  /** 列表数据**/
  data: IScrollListItem[];
  /** 分页类型 async 异步 sync 同步 noPaging 不分页**/
  mode: ScrollPageMode;
  /** 当前页码**/
  page: number;
  /** 每页条数**/
  pageSize: number;
  /** 总条数**/
  total: number;
  /** 获取列表数据的方法**/
  getData: (page: number) => Promise<IScrollListItem[]>;
}
@Component
export default class ScrollList extends tsc<object> {
  @Ref('anchorRef') anchorRef!: HTMLDivElement;
  @Prop({ type: Object, default: () => [] }) data: IScrollListItem[];
  @Prop({ type: String, default: ScrollPageMode.NoPaging }) mode: ScrollPageMode;
  @Prop({ type: Number, default: 0 }) total: number;
  @Prop({ type: Number, default: 1 }) page: number;
  @Prop({ type: Function }) getData: (page: number) => Promise<IScrollListItem[]>;
  loading = false;
  intersectionObserver: IntersectionObserver;
  renderData: IScrollListItem[] = [];
  hiddenAnchor = true;
  isInViewport(element: Element) {
    const rect = element.getBoundingClientRect();
    return (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
  }
  observerScrollAnchor() {
    if (this.mode === ScrollPageMode.NoPaging) return;
    if (!this.anchorRef) return;
    this.intersectionObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.intersectionRatio <= 0) return;
        if (this.mode === ScrollPageMode.Sync) {
          if (this.renderData.length >= this.data.length) return;
          this.renderData.push(...this.data.slice(this.renderData.length, this.renderData.length + 2));
          this.$nextTick(() => {
            if (this.isInViewport(this.anchorRef) && this.renderData.length < this.data.length) {
              this.handleTriggerObserver();
            }
          });
        } else if (this.mode === ScrollPageMode.Async) {
          if (this.data.length >= this.total) return;
          this.loading = true;
          this.getData(this.page + 1)
            .catch(() => [])
            .finally(() => {
              this.loading = false;
            });
        }
      }
    });
    this.intersectionObserver.observe(this.anchorRef);
  }
  /**
   * 用于触发 IntersectionObserver 监听
   */
  handleTriggerObserver() {
    this.hiddenAnchor = true;
    window.requestIdleCallback(() => {
      this.hiddenAnchor = false;
    });
  }
  mounted() {
    this.observerScrollAnchor();
  }
  render() {
    let data = this.data;
    if (this.mode === ScrollPageMode.Sync) {
      data = this.renderData;
    }
    return (
      <div class='scroll-list'>
        {data.map(item => (
          <div
            key={item.id}
            class={'scroll-list-item'}
          >
            {item.name}
          </div>
        ))}
        {this.data?.length < 1 && (
          <bk-exception
            class='scroll-list-empty'
            scene='part'
            type='empty'
          >
            {this.$t('暂无数据')}
          </bk-exception>
        )}
        <div
          ref='anchorRef'
          style={{ display: this.hiddenAnchor ? 'none' : 'flex' }}
          class='scroll-list-anchor'
        >
          <bk-loading
            isLoading={this.loading}
            mode='spin'
            size='mini'
            theme='primary'
          />
        </div>
      </div>
    );
  }
}
