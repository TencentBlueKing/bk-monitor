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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import CommonDetail from '../common-detail';
import K8sTableNew from '../k8s-table-new/k8s-table-new';

import type { IFilterByItem } from '../filter-by-condition/utils';
import type { K8sTableClickEvent, K8sTableFilterByEvent, K8sTableGroupByEvent } from '../k8s-table-new/k8s-table-new';

import './k8s-detail-slider.scss';

interface IEventDetailSlider {
  isShow?: boolean;
  activeItem: K8sTableClickEvent;
  groupFilters: Array<number | string>;
  filterBy: IFilterByItem[];
}
interface IEvent {
  onShowChange?: boolean;
  onGroupChange: (item: K8sTableGroupByEvent) => void;
  onFilterChange: (item: K8sTableFilterByEvent) => void;
}

// 事件详情 | 处理记录详情
export type TType = 'eventDetail' | 'handleDetail';

@Component
export default class EventDetailSlider extends tsc<IEventDetailSlider, IEvent> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ type: Object, default: () => ({ row: null, column: null }) }) activeItem: K8sTableClickEvent;
  @Prop({ type: Array, default: () => [] }) groupFilters: Array<number | string>;
  @Prop({ type: Array, default: () => [] }) filterBy: IFilterByItem[];

  loading = false;

  get activeTag() {
    return this.activeItem?.column?.id;
  }

  get activeValue() {
    return K8sTableNew.getScopedSlotRowText(this.activeItem.row, this.activeTag) || '--';
  }

  get groupParam() {
    const hasGroup = this.groupFilters.includes(this.activeTag);
    const param = hasGroup
      ? {
          btnText: '移除下钻',
          btnTheme: 'primary',
          textColorClass: '',
        }
      : {
          btnText: '下钻',
          btnTheme: 'default',
          textColorClass: 'is-default',
        };
    return {
      hasGroup,
      btnText: param.btnText,
      btnTheme: param.btnTheme,
      textColorClass: param.textColorClass,
    };
  }

  get filterParams() {
    const id = K8sTableNew.getScopedSlotRowId(this.activeItem.row, this.activeTag);
    const groupItem = this.filterBy?.find?.(v => v.key === this.activeTag);
    const filterIds = (groupItem?.value?.length && groupItem?.value.filter(v => v !== id)) || [];
    const hasFilter = groupItem?.value?.length && filterIds?.length !== groupItem?.value?.length;
    const param = hasFilter
      ? {
          icon: 'icon-sousuo-',
          ids: filterIds,
          btnText: '移除该筛选项',
          btnTheme: 'primary',
          textColorClass: '',
        }
      : {
          icon: 'icon-a-sousuo',
          ids: [...filterIds, id],
          btnText: '添加为筛选项',
          btnTheme: 'default',
          textColorClass: 'is-default',
        };
    return {
      hasFilter,
      ids: param.ids,
      icon: param.icon,
      btnText: param.btnText,
      btnTheme: param.btnTheme,
      textColorClass: param.textColorClass,
    };
  }

  @Emit('showChange')
  emitIsShow(v: boolean) {
    return v;
  }

  @Emit('groupChange')
  groupChange() {
    return { id: this.activeTag, checked: !this.groupParam.hasGroup };
  }

  @Emit('filterChange')
  filterChange() {
    return {
      column: this.activeItem.column,
      row: this.activeItem.row,
      checked: !this.filterParams.hasFilter,
      ids: this.filterParams.ids,
    };
  }

  // 隐藏详情
  handleHiddenSlider() {
    this.emitIsShow(false);
  }

  // 标题
  tplTitle() {
    return (
      <div class='title-wrap'>
        <div class='title-left'>
          <span class='title-tag'>{this.activeTag}</span>
          <span class='title-value'> {this.activeValue}</span>
          <span
            class='icon-monitor icon-copy-link title-icon'
            v-bk-tooltips={{ content: '复制链接', placement: 'right' }}
          />
        </div>
        <div class='title-right'>
          <bk-button
            class={['title-btn', this.filterParams.textColorClass]}
            theme={this.filterParams.btnTheme}
            onClick={this.filterChange}
          >
            <span class={['icon-monitor', this.filterParams.icon]} />
            <span class='title-btn-label'>{this.$t(this.filterParams.btnText)}</span>
          </bk-button>
          <bk-button
            class={['title-btn', this.groupParam.textColorClass]}
            theme={this.groupParam.btnTheme}
            onClick={this.groupChange}
          >
            <span class='icon-monitor icon-xiazuan' />
            <span class='title-btn-label'>{this.$t(this.groupParam.btnText)}</span>
          </bk-button>
        </div>
      </div>
    );
  }

  // 内容
  tplContent() {
    return (
      <div class='k8s-detail-content'>
        <div class='content-left'>left</div>
        <div class='content-right'>
          <CommonDetail
            collapse={false}
            maxWidth={500}
            needShrinkBtn={false}
            panel={null}
            placement={'right'}
            selectorPanelType={''}
            startPlacement={'left'}
            title={this.$tc('详情')}
            toggleSet={true}
            onLinkToDetail={() => {}}
            onShowChange={() => {}}
            onTitleChange={() => {}}
          />
        </div>
      </div>
    );
  }

  render() {
    return (
      <bk-sideslider
        ext-cls='k8s-detail-slider'
        isShow={this.isShow}
        {...{ on: { 'update:isShow': this.emitIsShow } }}
        width={'80vw'}
        quick-close={true}
        onHidden={this.handleHiddenSlider}
      >
        <div
          class='slider-title'
          slot='header'
        >
          {this.tplTitle()}
        </div>
        <div
          slot='content'
          v-bkloading={{ isLoading: this.loading }}
        >
          {this.tplContent()}
        </div>
      </bk-sideslider>
    );
  }
}
