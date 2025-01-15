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
import { Component, Emit, Inject, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { collectConfigList } from 'monitor-api/modules/collecting';
import { getDataSourceConfig } from 'monitor-api/modules/grafana';
import { skipToDocsLink } from 'monitor-common/utils/docs';

import EmptyStatus, { defaultTextMap } from '../../../components/empty-status/empty-status';

import type { EmptyStatusOperationType, IEmptyStatusTextMap } from '../../../components/empty-status/types';
import type { IDataRetrievalView } from '../typings';

import './retrieval-empty-show.scss';

@Component
export default class FavoritesList extends tsc<IDataRetrievalView.IEmptyView> {
  @Prop({ default: 'monitor', type: String }) showType: IDataRetrievalView.typeOfView; // 展示类型
  @Prop({ default: false, type: Boolean }) queryLoading: boolean; // 是否正在请求 请求中则不展示空检索
  @Prop({ default: () => ({}), type: Object }) eventMetricParams: object; // 事件检索参数
  @Prop({ default: 'empty', type: String }) emptyStatus: IDataRetrievalView.IEmptyView['emptyStatus']; // 空状态

  @Inject('refreshQueryFn') refreshQueryFn;

  /* 检索语法 **/
  grammarMap = [
    {
      key: this.$t('带字段全文检索更高效'),
      value: 'log:abc',
    },
    {
      key: this.$t('模糊检索使用通配符'),
      value: `abc* ${this.$t('或')} ab?c`,
    },
    {
      key: this.$t('双引号匹配完整字符串'),
      value: 'log:"ERROR MSG"',
    },
    {
      key: this.$t('数值字段范围匹配'),
      value: 'count:[1 TO 5]',
    },
    {
      key: this.$t('正则匹配'),
      value: 'name:/joh?n(ath[oa]n/',
    },
    {
      key: this.$t('组合检索注意大写'),
      value: 'log: (error OR info)',
    },
  ];

  emptyTextMap: IEmptyStatusTextMap = Object.assign({}, defaultTextMap, {
    empty: window.i18n.t('暂未进行检索'),
    'search-empty': window.i18n.t('无数据'),
  });

  @Emit('clickEventBtn')
  handleEventEmit(event: string) {
    return event;
  }

  async handleClickEventBtn(event: string) {
    switch (event) {
      case 'search': // 点击检索
        this.handleEventEmit('query');
        break;
      case 'customizeEvent':
        {
          // 无查询时 跳转自定义事件列表
          const url = location.href.replace(location.hash, '#/custom-event');
          window.open(url, '_blank');
        }
        break;
      case 'logEvent':
        {
          // 无查询时 跳转新建采集
          const url = location.href.replace(location.hash, '#/collect-config/add');
          window.open(url, '_blank');
        }
        break;
      case 'dataSource':
        {
          // 查询后无数据 跳转数据源
          const tableId = this.eventMetricParams?.result_table_id; // 检索的id
          const typeLabel = this.eventMetricParams?.data_type_label; // 检索类型 日志类型 或 自定义事件
          if (!tableId) {
            this.$bkMessage({
              message: typeLabel === 'event' ? this.$t('检查是否选择数据ID') : this.$t('检查是否选择采集ID'),
              theme: 'error',
            });
            return;
          }
          if (typeLabel === 'log') {
            getDataSourceConfig({ data_source_label: 'bk_monitor', data_type_label: 'log' }).then(list => {
              const findItem = list.find(item => item.id === tableId);
              const searchStr = findItem?.name;
              collectConfigList({ refresh_status: false }).then(item => {
                const findItem = item.config_list.find(cItem => cItem.name === searchStr);
                if (!findItem) {
                  this.$bkMessage({
                    message: this.$t('没有找到与采集ID对应的数据源'),
                    theme: 'error',
                  });
                  return;
                }
                const url = location.href.replace(location.hash, `#/collect-config?id=${findItem.id}`);
                window.open(url, '_blank');
              });
            });
          }
          if (typeLabel === 'event') {
            const { list } = await this.$store.dispatch('custom-escalation/getCustomEventList');
            const findItem = list.find(item => item.tableId === tableId);
            if (!findItem) {
              this.$bkMessage({
                message: this.$t('没有找到与数据ID对应的数据源'),
                theme: 'error',
              });
              return;
            }
            const url = location.href.replace(
              location.hash,
              `#/custom-escalation-detail/event/${findItem.bkEventGroupId}`
            );
            window.open(url, '_blank');
          }
        }
        break;
      case 'moreRule':
        {
          // 更多规则
          // const url = location.href.replace(location.hash, '/');
          // window.open(url, '_blank');
          skipToDocsLink('bkLogQueryString');
        }
        break;
    }
  }

  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'refresh') {
      this.refreshQueryFn();
      return;
    }
  }

  render() {
    const monitorSlot = () => {
      if (this.emptyStatus === 'empty')
        return (
          <div class='empty-main'>
            <div class='suggest-title is-center'>{this.$t('通过左侧添加查询项')}</div>
          </div>
        );
      if (this.emptyStatus === 'search-empty')
        return (
          <div class='empty-main'>
            <div class='suggest-title'>{this.$t('您可以按照以下方式优化检索结果')}</div>
            <div class='suggest-list'>
              <span>1. {this.$t('检查指标的选择是否正确')}</span>
              <span>2. {this.$t('检查指标的数据来源是否有数据')}</span>
              <span>3. {this.$t('检查右上角的时间范围')}</span>
              <span>4. {this.$t('检查查询条件和目标范围是否合理')}</span>
            </div>
          </div>
        );
      return undefined;
    };
    const eventSlot = () => {
      if (this.emptyStatus === 'empty') {
        return (
          <div class='empty-main'>
            <div class='suggest-title'>{this.$t('您可以按照以下方式进行检索')}</div>
            <div class='suggest-list'>
              <span>
                1.
                <i18n path='当前是否有数据源，如果没有请通过{0}和{1}添加'>
                  <span
                    class='blue-btn'
                    onClick={() => this.handleClickEventBtn('logEvent')}
                  >
                    {this.$t('日志关键字事件')}
                  </span>
                  <span
                    class='blue-btn'
                    onClick={() => this.handleClickEventBtn('customizeEvent')}
                  >
                    {this.$t('自定义事件')}
                  </span>
                </i18n>
              </span>
              <span> 2. {this.$t('检查查询条件是否完整，是否有报错提示')}</span>
              <span>
                {' '}
                3. {this.$t('当前可能是手动查询，请')}
                <span
                  class='blue-btn'
                  onClick={() => this.handleClickEventBtn('search')}
                >
                  {' '}
                  {this.$t('点击查询')}
                </span>
              </span>
            </div>
          </div>
        );
      }
      if (this.emptyStatus === 'search-empty') {
        return (
          <div>
            <div class='empty-main'>
              <div class='suggest-title'>{this.$t('您可以按照以下方式优化检索结果')}</div>
              <div class='suggest-list'>
                <span>
                  1. {this.$t('检查')}
                  <span
                    class='blue-btn'
                    onClick={() => this.handleClickEventBtn('dataSource')}
                  >
                    {' '}
                    {this.$t('数据源配置')}{' '}
                  </span>
                  {this.$t('情况')}
                </span>
                <span>2. {this.$t('检查右上角的索时间范围')}</span>
                <span>3. {this.$t('检查字段类型，不同的字段类型对应的查询语法有差异')}</span>
                <span>4. {this.$t('优化查询语句')}</span>
                <div class='grammar-list'>
                  {this.grammarMap.map(item => (
                    <span>
                      <span>{item.key}</span>: <span>{item.value}</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <div
              class='more-rule'
              onClick={() => this.handleClickEventBtn('moreRule')}
            >
              {this.$t('查看更多语法规则')}
              <span class='icon-monitor icon-fenxiang' />
            </div>
          </div>
        );
      }

      return undefined;
    };
    return (
      <div
        class='empty-container'
        v-show={!this.queryLoading}
      >
        <EmptyStatus
          textMap={this.emptyTextMap}
          type={this.emptyStatus}
          onOperation={this.handleOperation}
        >
          {this.showType === 'monitor' && monitorSlot()}
          {this.showType === 'event' && eventSlot()}
        </EmptyStatus>
      </div>
    );
  }
}
