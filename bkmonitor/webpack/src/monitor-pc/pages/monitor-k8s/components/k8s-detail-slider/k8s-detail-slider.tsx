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

import type { K8sTableColumnKeysEnum } from '../k8s-table-new/k8s-table-new';

import './k8s-detail-slider.scss';

interface IEventDetailSlider {
  isShow?: boolean;
  activeGroup: K8sTableColumnKeysEnum;
  //   podId: string;
  //   type: TType;
}
interface IEvent {
  onShowChange?: boolean;
}

// 事件详情 | 处理记录详情
export type TType = 'eventDetail' | 'handleDetail';

@Component
export default class EventDetailSlider extends tsc<IEventDetailSlider, IEvent> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ type: String, default: '' }) activeGroup: K8sTableColumnKeysEnum;
  // @Prop({ type: String, default: '' }) podId: string;

  loading = false;

  @Emit('showChange')
  emitIsShow(v: boolean) {
    return v;
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
          <span class='title-tag'>Pod</span>
          <span class='title-value'> bkbase-puller-datanode-inland-bcs1-1</span>
          <span class='icon-monitor icon-copy-link title-icon' />
        </div>
        <div class='title-right'>
          <bk-button class='title-btn'>
            <span class='icon-monitor icon-a-sousuo ' />
            <span class='title-btn-label'>{this.$t('添加为筛选项')}</span>
          </bk-button>
          <bk-button class='title-btn'>
            <span class='icon-monitor icon-xiazuan ' />
            <span class='title-btn-label'>{this.$t('下钻')}</span>
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
        width={1280}
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
