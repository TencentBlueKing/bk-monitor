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
import { Component, Prop, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { AiopsTopo, createApp, h as vue2CreateElement } from '@blueking/aiops-topo/vue2';
import { resize } from 'monitor-pc/components/ip-selector/common/observer-directive';
import { throttle } from 'throttle-debounce';

import type { IIncidentDetail } from './types';

import './troubleshooting-collapse.scss';
import '@blueking/aiops-topo/vue2/vue2.css';
interface IProps {
  data?: IIncidentDetail;
  errorData?: {
    isError: boolean;
    message: string;
  };
  loading: boolean;
  onToIncidentDetail: Function;
}

// 最大做小缩放倍率
const MIN_SCALE = 0.5;
const MAX_SCALE = 3;
@Component({
  directives: {
    resize,
  },
})
export default class AiopsTroubleshootingCollapse extends tsc<IProps> {
  @Prop({ type: Object, default: () => ({}) }) data: IIncidentDetail;
  @Prop({ type: Object, default: () => ({ isError: false, message: '' }) }) errorData: {
    isError: boolean;
    message: string;
  };
  @Prop({ type: Boolean, default: false }) loading: boolean;
  imgUrl = '';
  app = null;
  infoConfig = {
    alert_name: {
      label: this.$t('故障名称'),
      renderFn: alert_name => (
        <span
          class='blue-txt'
          v-bk-overflow-tips
          onClick={this.goToIncidentDetail}
        >
          {alert_name}
        </span>
      ),
    },
    status: {
      label: this.$t('故障状态'),
      renderFn: status => (
        <span class={`info-status ${status}`}>
          <i class='icon-monitor icon-mind-fill' />
          {status}
        </span>
      ),
    },
    time: { label: this.$t('持续时间') },
    bk_biz_name: { label: this.$t('影响业务') },
    // metric: { label: '故障总结' },
    // assignee: { label: '处置指引' },
  };
  isNoData = false;
  detailConfig = {
    alert_name: '',
    status: '',
    time: '',
    bk_biz_name: '',
    // metric: '根因和影响范围（结合图谱的实体回答：服务、模块），触发告警情况文本文本文本文本。',
    // assignee: '该故障内您共有 3 个未恢复告警待处理，建议处理指引XXXXXXXXX XXXXXXX。',
  };
  graphData: any = {};
  get zoomImage() {
    return this.$refs.zoomImage as unknown as {
      showImg: () => void;
      scrollImage: (e: Event) => any;
      width: number;
      height: number;
      left: number;
      top: number;
    };
  }
  get imageStyle() {
    return {
      display: this.imgUrl ? 'block' : 'none',
    };
  }
  beforeDestroy() {
    this.app?.unmount();
  }

  handleImgUrl(url) {
    // 处理AiopsTopo组件传递过来的数据
    this.imgUrl = url;
  }
  handleClick() {
    this.zoomImage.showImg();
  }

  @Emit('toIncidentDetail')
  goToIncidentDetail() {}

  async mounted() {
    this.detailConfig.alert_name = this.data.incident_name;
    this.detailConfig.status = this.data.status_alias;
    this.detailConfig.time = this.data.duration;
    this.detailConfig.bk_biz_name = this.data.bk_biz_name;
    this.graphData = this.data.current_topology;
    this.isNoData = !this.errorData.isError && Object.keys(this.graphData ?? {}).length === 0;
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    const that = this;
    // 限制缩放频率
    const scrollImage = that.zoomImage.scrollImage.bind(this.$refs.zoomImage);
    const w = document.body.offsetWidth / 2;
    that.zoomImage.scrollImage = throttle(50, (event: any) => {
      const deltaY = Math.max(-1, Math.min(1, event.wheelDeltaY || -event.detail));
      if (deltaY > 0 && that.zoomImage.width > 0 && that.zoomImage.width / w > MAX_SCALE) return;
      if (deltaY < 0 && that.zoomImage.width > 0 && that.zoomImage.width / w < MIN_SCALE) return;
      scrollImage(event);
    });
    this.app = createApp({
      render() {
        return vue2CreateElement(AiopsTopo, {
          graphData: that.graphData,
          errorMessage: that.errorData.message,
          isNoData: that.isNoData,
          message: that.isNoData ? that.$t('暂无数据') : that.$t('查询异常'),
          onImgUrl(url) {
            that.handleImgUrl(url);
          },
        } as any);
      },
    });
    this.$nextTick(() => {
      this.app?.mount(this.$el.querySelector('.aiops-troubleshooting-topo'));
    });
  }

  render() {
    return (
      <div class='aiops-troubleshooting'>
        <div class='aiops-troubleshooting-info'>
          <div class='info-title'>{this.$t('故障详情')}</div>
          {Object.keys(this.infoConfig).map(key => {
            const info = this.infoConfig[key];
            return (
              <div
                key={key}
                class='info-item'
              >
                <span class='info-label'>{this.$t(info.label)}：</span>
                <span class='info-txt'>
                  {info?.renderFn ? info.renderFn(this.detailConfig[key]) : this.detailConfig[key] || '--'}
                </span>
              </div>
            );
          })}
        </div>
        <div
          v-bkloading={{
            isLoading: this.loading,
            color: '#292A2B',
            size: 'mini',
            extCls: 'topo_loading',
          }}
        >
          <div
            key='aiops-troubleshooting-topo'
            class='aiops-troubleshooting-topo'
            onClick={this.handleClick}
          />
          <bk-zoom-image
            key='aiops-topo-zoom-image'
            ref='zoomImage'
            style={this.imageStyle}
            class='aiops-topo-zoom-image'
            ext-cls='aiops-topo-full-image'
            src={this.imgUrl}
            transfer={true}
          />
        </div>
      </div>
    );
  }
}
