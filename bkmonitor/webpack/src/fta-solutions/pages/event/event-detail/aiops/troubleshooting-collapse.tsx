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

import { AiopsTopo, createApp, h as vue2CreateElement } from '@blueking/aiops-topo/vue2';
import { resize } from 'monitor-pc/components/ip-selector/common/observer-directive';
import { throttle } from 'throttle-debounce';

import type { IIncidentDetail } from './types';

import './troubleshooting-collapse.scss';
import '@blueking/aiops-topo/vue2/vue2.css';
interface IProps {
  data?: IIncidentDetail;
  loading: boolean;
  spaceId: string;
  onToIncidentDetail: () => void;
  errorData?: {
    isError: boolean;
    message: string;
  };
}

// 最大做小缩放倍率
const MIN_SCALE = 0.5;
const MAX_SCALE = 3;
const STATUS_MAP = {
  recovered: {
    iconName: 'icon-mc-check-fill',
    iconColor: '#2dcb56',
    iconText: '已恢复',
  },
  abnormal: {
    iconName: 'icon-mind-fill',
    iconColor: '#ff5656',
    iconText: '未恢复',
  },
  closed: {
    iconName: 'icon-mc-close-fill',
    iconColor: '#979BA5',
    iconText: '已失效',
  },
};
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
  @Prop({ type: String, default: '' }) spaceId: string;
  imgUrl = '';
  app = null;
  infoConfig = {
    alert_name: {
      label: this.$t('故障名称'),
      renderFn: (alert_name: any) => (
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
      renderFn: (status: any, detail: Record<string, any>) => {
        console.log(status, 'statusstatus', detail, this.data);
        if (!status) return '';
        const statusInfo = STATUS_MAP[detail.status];
        return (
          <span
            style={{ color: statusInfo.iconColor }}
            class={`status-icon info-status ${status}`}
          >
            <i class={['icon-monitor', statusInfo.iconName]} />
            <span class='status-text'>{detail.status_alias}</span>
          </span>
        );
      },
    },
    time: {
      label: this.$t('持续时间'),
    },
    bk_biz_name: {
      label: this.$t('影响业务'),
      renderFn: (bk_biz_name: any) => {
        const data = bk_biz_name.split('-');
        return (
          <span>
            {data[0]}
            <span class='info-business'>{data[1]}</span>
          </span>
        );
      },
    },
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
      height: number;
      left: number;
      scrollImage: (e: Event) => any;
      showImg: () => void;
      top: number;
      width: number;
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

  handleImgUrl(url: string) {
    // 处理AiopsTopo组件传递过来的数据
    this.imgUrl = url;
  }
  handleClick() {
    this.zoomImage.showImg();
  }
  formatTimestamp(timestamp: Date | number | string) {
    // 将时间戳从秒转换为毫秒
    const date = new Date(timestamp);
    // 获取年月日时分秒
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0'); // 月份从0开始
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  }

  /** 持续时间 */
  handleShowTime() {
    const { begin_time, end_time, duration } = this.data;
    if (!begin_time) {
      return duration;
    }
    const beginTime = this.formatTimestamp(begin_time * 1000);
    const endTime = this.formatTimestamp(end_time ? end_time * 1000 : new Date().getTime());

    return `${duration} (${beginTime} ~ ${endTime})`;
  }

  @Emit('toIncidentDetail')
  goToIncidentDetail() {}

  async mounted() {
    const timeRange = this.handleShowTime();
    this.detailConfig.alert_name = this.data.incident_name;
    this.detailConfig.status = this.data.status_alias;
    this.detailConfig.time = timeRange;
    this.detailConfig.bk_biz_name = `${this.data.bk_biz_name}-${this.spaceId}`;
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
          onImgUrl(url: string) {
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
                  {info?.renderFn ? info.renderFn(this.detailConfig[key], this.data) : this.detailConfig[key] || '--'}
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
