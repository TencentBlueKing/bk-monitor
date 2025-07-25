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
import { Component, Emit, InjectReactive, Mixins, Prop, Ref } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import { detectOS } from 'monitor-common/utils';

import { DEFAULT_TIME_RANGE } from '../../../components/time-range/utils';
import UserConfigMixin from '../../../mixins/userStoreConfig';
import DashboardTools from '../../monitor-k8s/components/dashboard-tools';
import GotoOldVersion from '../../monitor-k8s/components/k8s-nav-bar/goto-old';

import type { TimeRangeType } from '../../../components/time-range/time-range';
import type { HideFeatures, IDataIdItem } from '../typing';

import './event-explore-header.scss';
interface EventRetrievalNavBarEvents {
  onDataIdChange(val: string): void;
  onEventTypeChange(val: { data_source_label: string; data_type_label: string }): void;
  onFavoriteShowChange(show: boolean): void;
  onImmediateRefresh(): void;
  onRefreshChange(val: number): void;
  onTimeRangeChange(val: TimeRangeType): void;
  onTimezoneChange(val: string): void;
}

interface EventRetrievalNavBarProps {
  dataId: string;
  dataIdList?: IDataIdItem[];
  dataSourceLabel: string;
  dataTypeLabel: string;
  isShowFavorite?: boolean;
  refreshInterval?: number;
  timeRange?: TimeRangeType;
  timezone?: string;
}

/** 置顶的data_id */
const EVENT_RETRIEVAL_DATA_ID_THUMBTACK = 'event_retrieval_data_id_thumbtack';

@Component
class EventRetrievalHeader extends Mixins(UserConfigMixin) {
  @InjectReactive('hideFeatures') hideFeatures: HideFeatures;
  @InjectReactive('needMenu') needMenu: boolean;
  @Prop({ default: () => [] }) dataIdList: IDataIdItem[];
  // 数据间隔
  @Prop({ default: () => DEFAULT_TIME_RANGE, type: Array }) timeRange: TimeRangeType;
  // 自动刷新数据间隔
  @Prop({ default: -1 }) readonly refreshInterval: number;
  @Prop({ default: true }) readonly isShowFavorite: boolean;
  // 时区
  @Prop({ type: String }) timezone: string;
  @Prop({ type: String }) dataId: string;
  @Prop({ type: String }) dataSourceLabel: string;
  @Prop({ type: String }) dataTypeLabel: string;

  @Ref('dataIdSelect') dataIdSelectRef: any;

  /** 排序后的数据id列表 */
  get sortDataIdList(): IDataIdItem[] {
    const thumbtackList = [];
    const other = [];
    for (const item of this.dataIdList) {
      if (this.thumbtackList.includes(item.id)) {
        thumbtackList.push({
          ...item,
          isTop: true,
        });
      } else {
        other.push({
          ...item,
          isTop: false,
        });
      }
    }
    return [...thumbtackList, ...other];
  }

  dataIdToggle = false;

  /** 置顶的数据id列表 */
  thumbtackList: string[] = [];

  get selectDataIdName() {
    return this.dataIdList.find(item => item.id === this.dataId)?.name || '';
  }

  mounted() {
    document.addEventListener('keydown', this.handleDocumentClick);
    this.handleGetUserConfig<string[]>(EVENT_RETRIEVAL_DATA_ID_THUMBTACK).then(res => {
      this.thumbtackList = res || [];
    });
  }

  beforeDestroy() {
    document.removeEventListener('keydown', this.handleDocumentClick);
  }

  handleDocumentClick(e: KeyboardEvent) {
    const isKeyO = e.key.toLowerCase() === 'o';
    // 检测是否按下 Ctrl 或 Command 键（跨平台兼容）
    const isCtrlOrMeta = e.ctrlKey || e.metaKey;
    if (isKeyO && isCtrlOrMeta) {
      e.preventDefault();
      this.dataIdSelectRef.show();
    }
  }

  handleDataIdToggle(toggle: boolean) {
    this.dataIdToggle = toggle;
  }

  @Emit('timeRangeChange')
  handleTimeRangeChange(val: TimeRangeType) {
    return val;
  }

  @Emit('timezoneChange')
  handleTimezoneChange(v: string) {
    return v;
  }

  @Emit('immediateRefresh')
  handleImmediateRefresh() {}

  @Emit('refreshChange')
  handleRefreshChange(v: number) {
    return v;
  }

  @Emit('favoriteShowChange')
  handleFavoriteShowChange() {
    return !this.isShowFavorite;
  }

  @Emit('dataIdChange')
  handleDataIdChange(dataId: string) {
    return dataId;
  }

  handleEventTypeChange(type: 'bk_monitor' | 'custom') {
    if (this.dataSourceLabel === type) return;
    if (type === 'custom') {
      this.$emit('eventTypeChange', { data_source_label: 'custom', data_type_label: 'event' });
      return;
    }
    this.$emit('eventTypeChange', { data_source_label: 'bk_monitor', data_type_label: 'log' });
  }
  // 跳转旧版版本事件检索
  handleGotoOldVersion() {
    this.$router.push({
      name: 'event-retrieval',
      query: {
        ...this.$route.query,
      },
    });
  }

  async handleThumbtack(e: Event, item: IDataIdItem) {
    e.stopPropagation();
    if (item.isTop) {
      this.thumbtackList = this.thumbtackList.filter(id => id !== item.id);
    } else {
      this.thumbtackList.push(item.id);
    }
    await this.handleSetUserConfig(EVENT_RETRIEVAL_DATA_ID_THUMBTACK, JSON.stringify(this.thumbtackList));
  }

  render() {
    return (
      <div class='event-explore-header'>
        <div class='header-left'>
          {this.hideFeatures.includes('favorite') ? null : (
            <div class='favorite-container'>
              <div
                class={['favorite-btn', { active: this.isShowFavorite }]}
                onClick={this.handleFavoriteShowChange}
              >
                <i
                  class='icon-monitor icon-shoucangjia'
                  v-bk-tooltips={{ content: this.$t(this.isShowFavorite ? '收起收藏夹' : '展开收藏夹') }}
                />
              </div>
            </div>
          )}
          {this.hideFeatures.includes('title') ? null : <div class='header-title'>{this.$t('route-事件检索')}</div>}
          {this.hideFeatures.includes('title') ? null : (
            <div class='event-type-select'>
              <div
                class={{ item: true, active: this.dataSourceLabel === 'custom' }}
                onClick={() => this.handleEventTypeChange('custom')}
              >
                {this.$t('自定义上报事件')}
              </div>
              <div
                class={{ item: true, active: this.dataSourceLabel === 'bk_monitor' }}
                onClick={() => this.handleEventTypeChange('bk_monitor')}
              >
                {this.$t('日志关键字')}
              </div>
            </div>
          )}
          {this.hideFeatures.includes('dataId') ? null : (
            <bk-select
              ref='dataIdSelect'
              class='data-id-select'
              clearable={false}
              ext-popover-cls={'new-event-retrieval-data-id-select-popover'}
              value={this.dataId}
              searchable
              onSelected={this.handleDataIdChange}
              onToggle={this.handleDataIdToggle}
            >
              <div
                class='data-id-select-trigger'
                slot='trigger'
              >
                <span class='data-prefix'>{this.$t('数据ID')}：</span>
                <span
                  class='data-name'
                  v-bk-overflow-tips
                >
                  {this.selectDataIdName}
                </span>
                <div class='select-shortcut-keys'>{detectOS() === 'Windows' ? 'Ctrl+O' : 'Cmd+O'}</div>
                <span class={`icon-monitor icon-mc-arrow-down ${this.dataIdToggle ? 'expand' : ''}`} />
              </div>
              {this.sortDataIdList.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                >
                  <div class={['event-item-name', { is_top: item.isTop }]}>
                    <i
                      class={['icon-monitor', 'thumbtack', item.isTop ? 'icon-a-pinnedtuding' : 'icon-a-pintuding']}
                      onClick={e => this.handleThumbtack(e, item)}
                    />
                    <span
                      class='name-text'
                      v-bk-overflow-tips
                    >
                      {item.name}
                    </span>
                    {item?.is_platform && <span class='platform-tag'>{this.$t('平台数据')}</span>}
                  </div>
                </bk-option>
              ))}
            </bk-select>
          )}
        </div>
        <div class='header-tools'>
          {this.hideFeatures.includes('dateRange') ? null : (
            <DashboardTools
              isSplitPanel={false}
              menuList={[]}
              refreshInterval={this.refreshInterval}
              showDownSampleRange={false}
              showFullscreen={false}
              showListMenu={false}
              showSplitPanel={false}
              timeRange={this.timeRange}
              timezone={this.timezone}
              onImmediateRefresh={this.handleImmediateRefresh}
              onRefreshChange={this.handleRefreshChange}
              onTimeRangeChange={this.handleTimeRangeChange}
              onTimezoneChange={this.handleTimezoneChange}
            >
              {this.$slots.dashboardTools}
            </DashboardTools>
          )}
        </div>
        {!this.needMenu ? null : (
          <GotoOldVersion
            tips={this.$tc('新版事件检索尚未完全覆盖旧版功能，如需可切换到旧版查看')}
            onClick={this.handleGotoOldVersion}
          />
        )}
      </div>
    );
  }
}

export default tsx.ofType<EventRetrievalNavBarProps, EventRetrievalNavBarEvents>().convert(EventRetrievalHeader);
