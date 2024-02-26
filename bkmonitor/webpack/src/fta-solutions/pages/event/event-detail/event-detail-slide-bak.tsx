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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { actionDetail } from '../../../../monitor-api/modules/alert';
import { copyText } from '../../../../monitor-common/utils/utils';

import ActionDetail from './action-detail';
import EventDetail from './event-detail';

import './event-detail-slider.scss';

interface IEventDetailSlider {
  isShow?: boolean;
  eventId: string;
  type: TType;
  activeTab?: string;
}
interface IEvent {
  onShowChange?: boolean;
}

interface IDetailList {
  label: string;
  key: string;
  value: string | IContent;
  display?: string;
  valueDisplayMap?: object;
}

interface IContent {
  text: string;
  url: string;
}

// 事件详情 | 处理记录详情
export type TType = 'eventDetail' | 'handleDetail';

const { i18n } = window;

@Component
export default class EventDetailSlider extends tsc<IEventDetailSlider, IEvent> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ type: String, default: '' }) eventId: string;
  @Prop({ type: String, default: '' }) activeTab: string;
  @Prop({ default: 'eventDetail', validator: v => ['eventDetail', 'handleDetail'].includes(v) }) type: TType;

  loading = false;

  // 处理详情数据
  handleDetailList: IDetailList[] = [
    { label: '套餐名称', key: 'action_name', value: '' },
    {
      label: '套餐类型',
      key: 'action_plugin_type',
      value: '',
      display: '',
      valueDisplayMap: {
        notice: i18n.t('通知'),
        webhook: i18n.t('HTTP回调'),
        job: i18n.t('作业平台'),
        sops: i18n.t('标准运维'),
        itsm: i18n.t('流程服务'),
        common: i18n.t('通用插件')
      }
    },
    { label: '策略名称', key: 'strategy_name', value: '' },
    {
      label: '策略级别',
      key: 'alert_level',
      value: '',
      display: '',
      valueDisplayMap: { 1: i18n.t('致命'), 2: i18n.t('轻微'), 3: i18n.t('预警') }
    },
    {
      label: '触发信号',
      key: 'signal',
      value: '',
      display: '',
      valueDisplayMap: {
        manual: i18n.t('手动'),
        abnormal: i18n.t('告警产生时'),
        recovered: i18n.t('告警恢复时'),
        closed: i18n.t('告警关闭时')
      }
    },
    { label: '操作人', key: 'operator', value: '' },
    { label: '告警列表', key: 'alert_names', value: '' },
    { label: '告警目标', key: 'bk_target_display', value: '' },
    { label: '业务集群', key: 'bk_set_names', value: '' },
    { label: '业务模块', key: 'bk_module_names', value: '' },
    { label: '开始时间', key: 'create_time', value: '' },
    { label: '执行耗时', key: 'duration', value: '' },
    {
      label: '执行状态',
      key: 'status',
      value: 'error',
      display: '',
      valueDisplayMap: {
        success: i18n.t('成功'),
        failure: i18n.t('失败'),
        running: i18n.t('执行中'),
        shield: i18n.t('已屏蔽'),
        skipped: i18n.t('已收敛')
      }
    },
    { label: '执行内容', key: 'content', value: '' }
    // { label: '作业平台', key: '', value: '' },
    // { label: '标准运维', key: '', value: '' }
  ];

  get width() {
    return this.type === 'handleDetail' ? 956 : 1047;
  }

  created() {
    this.handleI18n();
  }

  @Watch('isShow')
  handleShow(v: boolean) {
    if (v) {
      this.type === 'handleDetail' && this.getHandleDetailData();
    }
  }

  @Emit('showChange')
  emitIsShow(v: boolean) {
    return v;
  }

  handleI18n() {
    this.handleDetailList.forEach(item => {
      item.label = this.$i18n.tc(item.label);
    });
  }

  getHandleDetailData() {
    this.loading = true;
    actionDetail({ id: this.eventId })
      .then(data => {
        this.handleDetailList.forEach(item => {
          const { key } = item;
          item.value = data[key];
          if (key === 'create_time') {
            item.value = dayjs.tz(data[key] * 1000).format('YYYY-MM-DD HH:mm:ss');
          }
          if (['action_plugin_type', 'signal', 'status', 'alert_level'].includes(key)) {
            item.display = item.valueDisplayMap[item.value as string];
          }
          if (key === 'content') {
            // content的格式
            // text: 「作业平台任务」处理成功，$点击 $查看详情
            // url: http://www.baidu.com
            let str = (item.value as IContent)?.text;
            const url = (item.value as IContent)?.url;
            if (url) {
              str = str.replace(
                /([\s\S]?)\$([\s\S]*)\$([\s\S]?)/,
                `$1<a class="link" href="${url}" target="_blank">$2</a>$3`
              );
            }
            item.value = str;
          }
          if (key === 'alert_names' || key === 'operator') {
            item.value = (data[key] || []).join(', ');
          }
        });
      })
      .finally(() => (this.loading = false));
  }

  // 处理执行耗时时长
  handleDuration(start: number, end: number): string {
    const duration = end - start;
    const timeMap = [
      {
        value: 24 * 60 * 60 * 1000,
        unit: this.$t('天')
      },
      {
        value: 60 * 60 * 1000,
        unit: this.$t('小时')
      },
      {
        value: 60 * 1000,
        unit: this.$t('分钟')
      },
      {
        value: 1000,
        unit: this.$t('秒')
      }
    ];
    const resArr = [];
    timeMap.reduce((total, item) => {
      const count = Math.floor(total / item.value);
      resArr.push({
        value: count,
        unit: item.unit
      });
      return total % item.value;
    }, duration);
    while (resArr[0].value === 0 || resArr[resArr.length - 1].value === 0) {
      if (resArr[0].value === 0) resArr.splice(0, 1);
      if (resArr[resArr.length - 1].value === 0) resArr.length = resArr.length - 1;
    }
    const resStr = resArr.map(item => `${item.value} ${item.unit} `).join('');
    return resStr;
  }

  // 隐藏详情
  handleHiddenSlider() {
    this.emitIsShow(false);
  }

  // 复制事件详情连接
  handleToEventDetail() {
    let url = location.href.replace(location.hash, `#/event-center/detail/${this.eventId}`);
    const { bizId } = this.$store.getters;
    url = url.replace(location.search, `?bizId=${bizId}/`);
    copyText(url, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error'
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success'
    });
  }

  // 标题
  tplTitle() {
    const tplMap = {
      eventDetail: () => (
        <div class='title-wrap'>
          <span>{this.$t('告警详情')}</span>
          <i
            class='icon-monitor icon-copy-link'
            onClick={this.handleToEventDetail}
          ></i>
        </div>
      ),
      handleDetail: () => <div class='title-wrap'>{this.$t('处理记录详情')}</div>
    };
    return tplMap[this.type]();
  }

  // 内容
  tplContent() {
    const tplMap = {
      eventDetail: () => (
        <EventDetail
          class='event-detail-content'
          id={this.eventId}
          activeTab={this.activeTab}
          onCloseSlider={() => this.emitIsShow(false)}
        ></EventDetail>
      ),
      // handleDetail: this.tplHandleDetailConent
      handleDetail: () => <ActionDetail id={this.eventId}></ActionDetail>
    };
    return tplMap[this.type]();
  }

  // 处理记录
  tplHandleDetailConent() {
    return (
      <div class='handle-detail-content'>
        <div class='title-h1'>{this.$t('基础信息')}</div>
        <div class='detail-content-main'>
          {this.handleDetailList.map(item => (
            <div class='info-item'>
              <span class='info-label'>{item.label}&nbsp;:&nbsp;</span>
              {(() => {
                if (item.key === 'status') {
                  return (
                    <span class='info-content'>
                      <span class={['status-tag', `status-${item.value}`]}>{item.display}</span>
                    </span>
                  );
                }
                if (item.key === 'content') {
                  return (
                    <span
                      class='info-content key-content'
                      domPropsInnerHTML={(item.value as string) || '--'}
                    >
                      {/* <i class="icon-monitor icon-copy-link"></i> */}
                    </span>
                  );
                }
                if (item.key === 'alert_level') {
                  return (
                    <span class='info-content'>
                      <span class={['level', `level-${item.value}`]}>{item.display}</span>
                    </span>
                  );
                }
                return <span class='info-content'>{item.display || item.value || '--'}</span>;
              })()}
              {/* <span class="info-content">{item.value || '--'}</span> */}
            </div>
          ))}
        </div>
      </div>
    );
  }

  render() {
    return (
      <bk-sideslider
        ext-cls='event-detail-sideslider'
        transfer={true}
        isShow={this.isShow}
        {...{ on: { 'update:isShow': this.emitIsShow } }}
        quick-close={true}
        width={this.width}
        onHidden={this.handleHiddenSlider}
      >
        <div
          slot='header'
          class='sideslider-title'
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
