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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { loadApp, mount, unmount } from '@blueking/bk-weweb';
import EventDetailSlider from 'fta-solutions/pages/event/event-detail/event-detail-slider';
import { random } from 'monitor-common/utils';

import type { IShowDetail } from 'fta-solutions/pages/event/event-table';

import './incident-detail.scss';

@Component
export default class IncidentDetail extends tsc<{ id: string }> {
  @Ref('incidentDetailRef') incidentDetailRef: HTMLDivElement;
  @Prop({ default: '' }) readonly id!: string;
  // 侧栏详情信息
  detailInfo: { isShow: boolean; id: string; type: 'eventDetail'; bizId: number } = {
    isShow: false,
    id: '',
    type: 'eventDetail',
    bizId: +window.bk_biz_id,
  };
  randomKey = `trace_${random(4)}`;
  unmountCallback: () => void;
  get incidentDetailHost() {
    return process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7002` : location.origin;
  }
  get incidentDetailUrl() {
    return process.env.NODE_ENV === 'development'
      ? `${this.incidentDetailHost}/?bizId=${this.$store.getters.bizId}&key=${random(4)}/#/trace/incident/detail/${this.id}`
      : `${location.origin}${window.site_url}trace/?bizId=${this.$store.getters.bizId}/#/trace/incident/detail/${this.id}`;
  }
  get incidentDetailData() {
    return {
      host: this.incidentDetailHost,
      baseroute: '/trace/',
      showDetailSlider: this.handleShowDetail,
    };
  }
  created() {
    if (!window.customElements.get('custom-incident-detail')) {
      class IncidentDetailElement extends HTMLElement {
        async connectedCallback() {
          if (!this.shadowRoot) {
            this.attachShadow({ delegatesFocus: true, mode: 'open' });
          }
        }
      }
      window.customElements.define('custom-incident-detail', IncidentDetailElement);
    }
  }
  async mounted() {
    const data = {
      host: this.incidentDetailHost,
      baseroute: '/trace/',
      showDetailSlider: this.handleShowDetail,
      setUnmountCallback: (callback: () => void) => {
        this.unmountCallback = callback;
      },
    };
    this.randomKey = `trace_${random(4)}`;
    this.$nextTick(async () => {
      await loadApp({
        container: this.incidentDetailRef.shadowRoot,
        data,
        id: this.randomKey,
        setShodowDom: true,
        showSourceCode: false,
        url: this.incidentDetailUrl,
      });
      mount(this.randomKey, this.incidentDetailRef.shadowRoot);
    });
  }
  beforeDestroy() {
    this.detailInfo.isShow = false;
    this.unmountCallback?.();
    unmount(this.randomKey);
  }
  beforeRouterLeave(next) {
    next(() => {
      this.detailInfo.isShow = false;
    });
  }
  /**
   * @description: 显示详情数据
   * @param {IShowDetail}
   * @return {*}
   */
  handleShowDetail(data: IShowDetail & { bk_biz_id: number }) {
    this.detailInfo.id = data.id;
    this.detailInfo.isShow = true;
    this.detailInfo.bizId = data.bk_biz_id;
  }
  handleShowDetailNew(data: IShowDetail & { bk_biz_id: number }) {
    this.detailInfo.id = data.id;
    this.detailInfo.isShow = true;
    this.detailInfo.bizId = data.bk_biz_id;
  }
  render() {
    return (
      <div class='incident-detail-wrap'>
        <custom-incident-detail ref='incidentDetailRef' />
        <EventDetailSlider
          bizId={this.detailInfo.bizId}
          eventId={this.detailInfo.id}
          isShow={this.detailInfo.isShow}
          type={this.detailInfo.type}
          onShowChange={v => (this.detailInfo.isShow = v)}
        />
      </div>
    );
  }
}
