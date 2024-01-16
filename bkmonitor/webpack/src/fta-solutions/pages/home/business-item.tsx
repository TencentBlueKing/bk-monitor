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

import { favorite, sticky } from '../../../monitor-api/modules/home';
import { SPACE_TYPE_MAP } from '../../../monitor-pc/common/constant';
import MonitorPieEchart from '../../../monitor-ui/monitor-echarts/monitor-echarts-new.vue';

import { initUnit } from './home';

import './business-item.scss';

export const spaceTypeTexts = (obj: {
  space_type_id: string;
  space_code: any;
}): {
  name: string;
  light: { color: string; backgroundColor: string };
}[] => {
  if (obj?.space_type_id && SPACE_TYPE_MAP[obj.space_type_id]) {
    if (obj.space_type_id === 'bkci' && !!obj.space_code) {
      return [SPACE_TYPE_MAP.bkci, SPACE_TYPE_MAP.bcs];
    }
    return [SPACE_TYPE_MAP[obj.space_type_id]];
  }
  return [];
};

interface ISeriesData {
  count: number;
  level: number;
}

export interface IData {
  name: string;
  id: string;
  eventCounts: { id: string; name: string; count: number; unit: string }[];
  seriesData: ISeriesData[];
  dataCounts: { id: string; name: string; count: number; unit: string; allowHtml: boolean; tip: string }[];
  isFavorite: boolean;
  isSticky?: boolean;
  isDemo: boolean;
  countSum: number;
  isAllowed?: boolean;
  space_info?: {
    space_type_id?: string;
    space_code?: any;
    space_id?: string;
  };
}
interface BusinessItemProps {
  data: IData;
  isMakeTop?: boolean;
}

export interface BusinessItemEvent {
  onFavorite?: boolean;
  onToEvent?: {
    activeFilterId: any;
    id: string;
  };
}
@Component({
  name: 'BusinessItem'
})
export default class BusinessItem extends tsc<BusinessItemProps, BusinessItemEvent> {
  @Prop({
    type: Object,
    default: () => ({
      name: '',
      id: '0',
      eventCounts: [
        { id: 'event', name: '', count: 0, unit: '' },
        { id: 'alert', name: '', count: 0, unit: '' },
        { id: 'action', name: '', count: 0, unit: '' }
      ],
      seriesData: [
        { level: 2, count: 1 },
        { level: 3, count: 1 },
        { level: 1, count: 1 }
      ],
      countSum: 0,
      dataCounts: [
        { id: 'noise_reduction_ratio', name: '', count: 0, unit: '', tip: '' },
        { id: 'auto_recovery_ratio', name: '', count: 0, unit: '', tip: '' },
        { id: 'mtta', name: 'MTTA', count: 0, unit: '', tip: '' },
        { id: 'mttr', name: 'MTTR', count: 0, unit: '', tip: '' }
      ],
      isFavorite: false,
      isDemo: false
    })
  })
  data: IData;
  @Prop({ default: false, type: Boolean }) isMakeTop: boolean; // 是否包含置顶操作(与收藏互斥)
  seriesDataMap = {
    1: {
      name: window.i18n.t('致命'),
      color: '#EA3636'
    },
    2: {
      name: window.i18n.t('预警'),
      color: '#FF9C01'
    },
    3: {
      name: window.i18n.t('提醒'),
      color: '#ffd695'
    },
    4: {
      name: window.i18n.t('无数据'),
      color: '#2dcb56'
    }
  };
  loading = false;
  get series() {
    return [
      {
        label: { show: false },
        cursor: 'pointer',
        top: -20,
        radius: ['45%', '60%'],
        data: this.data.seriesData.length
          ? this.data.seriesData.map(item => {
              const seriesMapData = this.seriesDataMap[item.level];
              return {
                value: item.count,
                name: seriesMapData.name,
                level: item.level,
                itemStyle: {
                  color: seriesMapData.color
                },
                tooltip: {
                  formatter: () => `<span style="color:${seriesMapData.color}">\u25CF</span> <b> ${
                    seriesMapData.name
                  }</b>
            <br/>${this.$t('告警数量')}: <b>${item.count}</b><br/>`,
                  textStyle: {
                    fontSize: 12
                  }
                }
              };
            })
          : [
              {
                value: 0,
                name: this.seriesDataMap[4].name,
                level: 4,
                itemStyle: {
                  color: this.seriesDataMap[4].color
                },
                tooltip: {
                  formatter: () => `<span style="color:${this.seriesDataMap[4].color}">\u25CF</span> <b> ${
                    this.seriesDataMap[4].name
                  }</b>
            <br/>${this.$t('告警数量')}: <b>${0}</b><br/>`,
                  textStyle: {
                    fontSize: 12
                  }
                }
              }
            ]
      }
    ];
  }

  @Emit('favorite')
  async handleFavorite() {
    this.loading = true;
    const isActive = this.isMakeTop ? this.data.isSticky : this.data.isFavorite;
    const params = {
      op_type: isActive ? 'remove' : 'add',
      bk_biz_ids: [this.data.id]
    };
    const api = this.isMakeTop ? sticky : favorite;
    const res = await api(params).catch(() => false);
    this.loading = false;
    if (res) {
      return !this.data.isFavorite;
    }
    return this.data.isFavorite;
  }
  /**
   *
   * @param e 事件对象
   * @returns
   */
  handleFavoriteClick(e: MouseEvent) {
    e.stopPropagation();
    if (this.loading) return;
    this.handleFavorite();
  }

  // 跳转至事件中心
  @Emit('toEvent')
  handleToEvent(activeFilterId = null) {
    return {
      activeFilterId,
      id: this.data.id
    };
  }

  // 未恢复告警
  getAlarmNum() {
    const numObj = initUnit(this.data.countSum, 'num');
    return (
      <div class='alarm-num'>
        {Number(numObj.num).toFixed(0)}
        <span class='unit'>{numObj.unit}</span>
      </div>
    );
  }

  getOperation() {
    if (this.isMakeTop) {
      return this.$store.getters.bizId !== this.data.id ? (
        <span
          class={['zhiding', 'icon-monitor', this.data.isSticky ? 'icon-yizhiding' : 'icon-zhiding']}
          v-bk-tooltips={{
            content: this.$t(this.data.isSticky ? '取消置顶' : '置顶'),
            delay: 200,
            appendTo: 'parent'
          }}
          onClick={this.handleFavoriteClick}
        ></span>
      ) : undefined;
    }
    return this.$store.getters.bizId !== this.data.id ? (
      <span
        class={['favorite', 'icon-monitor', this.data.isFavorite ? 'icon-shoucang' : 'icon-mc-uncollect']}
        onClick={this.handleFavoriteClick}
      ></span>
    ) : undefined;
  }

  // 判断当前业务，并返回tag
  getCurrentBizTag() {
    if (this.$store.getters.bizId === this.data.id) {
      return (
        <div class='current-tag-wrap'>
          <div class='slope-tag'>
            <span class='slope-tag-text'>{window.i18n.tc('当前')}</span>
          </div>
        </div>
      );
    }
  }
  // 项目类型tag
  typeLabelTag(item) {
    const tags = spaceTypeTexts(item);
    return tags.map(tag => (
      <div
        class='type-tag'
        style={{
          color: tag.light.color,
          backgroundColor: tag.light.backgroundColor
        }}
      >
        {tag.name}
      </div>
    ));
  }
  // id显示逻辑
  getIdStr() {
    if (this.data?.space_info?.space_type_id === 'bkcc') {
      return `#${this.data.id}`;
    }
    return this.data?.space_info?.space_id || `#${this.data.id}`;
  }

  render() {
    return (
      <div
        class='business-item-component'
        onClick={() => this.handleToEvent()}
      >
        {this.getCurrentBizTag()}
        <div class='item-head'>
          <span class='title-wrap'>
            <span
              class='name'
              v-bk-overflow-tips
            >
              {this.data.name}
            </span>
            <span
              class='subtitle'
              v-bk-overflow-tips
            >
              ({this.getIdStr()})
            </span>
          </span>
          {this.typeLabelTag(this.data.space_info)}
          {this.data.isDemo ? <span class='demo'>DEMO</span> : this.getOperation()}
        </div>
        <div class='item-body'>
          <div class='top'>
            {this.data.eventCounts.map(item => (
              <span class='item-num'>{`${item.name}：${item.count}${item.unit}`}</span>
            ))}
          </div>
          <div class='bottom'>
            <div
              class='view'
              style={'width: 130px'}
            >
              <MonitorPieEchart
                height='130'
                backgroundUrl={'none'}
                chartType={'pie'}
                series={this.series}
                options={{
                  legend: { show: false },
                  tooltip: {
                    show: true,
                    appendToBody: true
                  }
                }}
                onClick={() => {
                  this.handleToEvent('NOT_SHIELDED_ABNORMAL');
                }}
              >
                <div
                  class='slot-center'
                  slot='chartCenter'
                  onClick={(e: Event) => {
                    e.stopPropagation();
                    this.handleToEvent('NOT_SHIELDED_ABNORMAL');
                  }}
                >
                  {this.getAlarmNum()}
                </div>
              </MonitorPieEchart>
              <div
                class='view-title'
                onClick={(e: Event) => {
                  e.stopPropagation();
                  this.handleToEvent('NOT_SHIELDED_ABNORMAL');
                }}
              >
                {this.data.seriesData.length ? this.$t('未恢复告警(实时)') : this.$t('告警空空')}
              </div>
            </div>
            <div style={{ display: 'none' }}>
              <div id='mttaTipRef'>
                <div>
                  {window.i18n.tc(
                    '平均应答时间，从告警真实发生到用户响应的平均时间。平均应答时间=总持续时间/总告警数量'
                  )}
                </div>
                <div>
                  {window.i18n.tc(
                    '总持续时间：所有告警的首次异常时间到下一个状态变更的时间点，如确认/屏蔽/恢复/关闭/已解决'
                  )}
                </div>
              </div>
            </div>
            <div style={{ display: 'none' }}>
              <div id='mttrTipRef'>
                <div>
                  {window.i18n.tc(
                    '平均解决时间，从告警真实发生到告警被处理的平均时间。平均解决时间=总持续时间/总告警数量'
                  )}
                </div>
                <div>{window.i18n.tc('总持续时间: 所有告警的首次异常时间到告警标记为已解决或已恢复的时间。')}</div>
              </div>
            </div>
            <div class='count-panles'>
              {this.data.dataCounts.map((item, index) => (
                <div
                  class='count-panle'
                  key={index}
                  v-bk-tooltips={{
                    content: item.allowHtml ? `#${item.tip}` : item.tip,
                    allowHTML: item.allowHtml,
                    delay: [500, 0],
                    theme: 'light',
                    placements: ['top'],
                    boundary: 'window',
                    maxWidth: 250
                  }}
                >
                  <span class='panle-count'>
                    <span class='count'>{item.count}</span>
                    <span class='unit'>{item.unit}</span>
                  </span>
                  <span class='panle-title'>{item.name}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }
}
