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

import { batchUpdate, matchDebug } from '../../../../monitor-api/modules/assign';
import { destroyAssignGroup } from '../../../../monitor-api/modules/model';
import { random } from '../../../../monitor-common/utils';
import TimeRange, { TimeRangeType } from '../../../components/time-range/time-range';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import emptyImageSrc from '../../../static/images/png/empty.png';
import { GROUP_KEYS, IConditionProps } from '../typing/condition';

import CommonCondition from './common-condition-new';

import './debugging-result.scss';

interface IResultGroupItem {
  group_id: string;
  group_name: string;
  priority: string;
  alerts_count?: number;
  rules: any[] | { is_enabled: boolean }[];
  key?: string;
  isExpand: boolean;
}

export interface IRuleGroupsDataItem {
  bk_biz_id: number;
  group_name: string;
  assign_group_id: number;
  priority: number;
  rules: any[];
  settings?: any;
}
interface IProps {
  isShow: boolean;
  isViewDebugEffect?: boolean;
  alarmGroupList: any[];
  ruleGroupsData?: any[];
  conditionProps?: IConditionProps;
  excludeGroups?: string[];
}

interface IEvent {
  onShowChange?: boolean;
  onSaveSuccess?: () => void;
  onDelSuccess?: () => void;
}

@Component
export default class DebuggingResult extends tsc<IProps, IEvent> {
  @Prop({ default: false, type: Boolean }) isShow: boolean;
  @Prop({ default: false, type: Boolean }) isViewDebugEffect: boolean;
  @Prop({ default: () => [], type: Array }) alarmGroupList: any;
  /* 此为调试数据，保存时也用此数据 防止有批量调试，故采用数组格式 此数据为空则为全局调试 */
  @Prop({ default: () => [], type: Array }) ruleGroupsData: IRuleGroupsDataItem[];
  @Prop({ default: () => null, type: Object }) conditionProps: IConditionProps;
  /* 出数据用于删除并调试 点击生效按钮根据此参数删除规则组 */
  @Prop({ default: () => [], type: Array }) excludeGroups: string[];

  resultsGroup: IResultGroupItem[] = [];
  loading = false;
  curTimeRange: TimeRangeType = ['now-7d', 'now'];
  curGroupId = 0;

  @Watch('isShow', { immediate: true })
  handleShow(v: boolean) {
    if (v) {
      this.getRuleMatchDebug();
    }
  }

  @Emit('showChange')
  emitIsShow(v: boolean) {
    return v;
  }

  async getRuleMatchDebug() {
    this.loading = true;
    let params = null;
    if (this.ruleGroupsData.length) {
      // eslint-disable-next-line prefer-destructuring
      params = this.ruleGroupsData[0];
      this.curGroupId = params.assign_group_id;
    } else {
      params = {};
      if (this.excludeGroups.length) {
        params = {
          exclude_groups: this.excludeGroups
        };
      }
    }
    const [startTime, endTime] = handleTransformToTimestamp(this.curTimeRange);
    const res = await matchDebug({
      ...params,
      start_time: startTime,
      end_time: endTime
    }).catch(() => []);
    this.resultsGroup = res.map(item => ({
      ...item,
      key: random(8),
      isExpand: this.curGroupId === item.group_id
    }));
    this.loading = false;
  }
  /**
   *
   * @param groups 规则组id
   * @returns
   */
  getAlarmGroupNames(groups) {
    return this.alarmGroupList
      .filter(item => groups.includes(item.id))
      .map(item => item.name)
      .join('、');
  }
  /**
   *
   * @param item 规则组
   * @param index 规则组索引
   */
  handleExpand(item, index: number) {
    this.resultsGroup[index].isExpand = !item.isExpand;
  }

  /* 保存生效 */
  async handleSave() {
    this.loading = true;
    if (this.excludeGroups.length) {
      const is = await destroyAssignGroup(this.excludeGroups[0])
        .then(() => true)
        .catch(() => false);
      this.loading = false;
      if (is) {
        this.$bkMessage({
          theme: 'success',
          message: this.$t('删除成功')
        });
        this.$emit('delSuccess');
      }
      return;
    }
    const params = this.ruleGroupsData[0];
    const res = await batchUpdate(params).catch(() => false);
    this.loading = false;
    if (res) {
      this.$bkMessage({
        theme: 'success',
        message: this.$t('保存成功')
      });
      this.emitIsShow(false);
      this.$emit('saveSuccess');
    }
  }

  handleTimeRangeChange(val: TimeRangeType) {
    this.curTimeRange = [...val];
    this.getRuleMatchDebug();
  }

  handleToEvent(id) {
    const url = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#/event-center?queryString=id : ${id}`;
    window.open(url);
  }

  render() {
    return (
      <bk-sideslider
        ext-cls='debugging-result-siderlider'
        isShow={this.isShow}
        quick-close={true}
        {...{ on: { 'update:isShow': this.emitIsShow } }}
        width={960}
      >
        <div
          slot='header'
          class='debug-header'
        >
          <span class='left'>{this.$t('调试结果')}</span>
          <TimeRange
            class='right'
            value={this.curTimeRange}
            needTimezone={false}
            onChange={this.handleTimeRangeChange}
          ></TimeRange>
        </div>
        <div slot='content'>
          <div
            class='wrap-content'
            v-bkloading={{ isLoading: this.loading }}
          >
            {this.resultsGroup.length ? (
              this.resultsGroup.map((item, index) => (
                <div
                  class='expand-item'
                  key={item.key}
                >
                  <div
                    class='expand-item-header'
                    onClick={() => this.handleExpand(item, index)}
                  >
                    <div class='header-left'>
                      <div class={['expand-status', { 'is-expand': item.isExpand }]}>
                        <i class='icon-monitor icon-mc-triangle-down'></i>
                      </div>
                      <div class='title-wrap'>
                        <span
                          class='title'
                          v-bk-overflow-tips
                        >
                          {item.group_name}
                        </span>
                      </div>
                      <div class='priority-wrap'>
                        <span class='title'>{this.$t('优先级')}: </span>
                        <span class='count'>{item.priority}</span>
                      </div>
                    </div>

                    <div class='count-warp'>
                      <i18n path='共{0}条'>
                        <span>{item.alerts_count || 0}</span>
                      </i18n>
                    </div>
                  </div>
                  {(item.rules || []).map((config, num) => (
                    <div
                      class={[
                        'expand-item-content',
                        { 'is-expand': item.isExpand },
                        {
                          'is-light':
                            !!config?.is_changed &&
                            !!config.alerts.length &&
                            String(item.group_id) === String(this.curGroupId)
                        },
                        {
                          'mt-1':
                            !!item.rules?.[num - 1]?.is_changed &&
                            !!item.rules?.[num - 1].alerts.length &&
                            !!config.alerts.length
                        },
                        { mb1: !config.alerts.length }
                      ]}
                      key={num}
                    >
                      <div class='alarm-group-header'>
                        <div class='header-left'>
                          <span class='group-title-wrap'>
                            <span
                              class='title'
                              title={this.getAlarmGroupNames(config.user_groups)}
                            >
                              {this.getAlarmGroupNames(config.user_groups)}
                            </span>
                            <bk-tag class={config.is_enabled ? 'start' : 'stop'}>
                              {this.$t(config.is_enabled ? '启用' : '停用')}
                            </bk-tag>
                          </span>
                          <span class='rule'>
                            <span>{this.$t('匹配规则')}: </span>
                            <span class='rule-wrap'>
                              {!!config.conditions?.length ? (
                                <CommonCondition
                                  value={config.conditions}
                                  keyList={this.conditionProps?.keys}
                                  groupKey={GROUP_KEYS}
                                  groupKeys={this.conditionProps.groupKeys}
                                  valueMap={this.conditionProps.valueMap}
                                  readonly={true}
                                ></CommonCondition>
                              ) : (
                                '--'
                              )}
                            </span>
                          </span>
                        </div>
                        {config.is_enabled && (
                          <div class='header-right'>
                            <i18n path='命中{0}条'>
                              <span>{config.alerts?.length || 0}</span>
                            </i18n>
                          </div>
                        )}
                      </div>
                      {!!config.alerts.length && (
                        <bk-table
                          data={config.alerts || []}
                          stripe
                          maxHeight={523}
                        >
                          <bk-table-column
                            label='ID'
                            prop='id'
                            scopedSlots={{
                              default: ({ row }) => (
                                <span
                                  class={`event-status status-${row.severity}`}
                                  onClick={() => this.handleToEvent(row.id)}
                                >
                                  {row.id}
                                </span>
                              )
                            }}
                          ></bk-table-column>
                          <bk-table-column
                            label={this.$t('告警名称')}
                            show-overflow-tooltip
                            prop='alert_name'
                          ></bk-table-column>
                          <bk-table-column
                            label={this.$t('告警指标')}
                            prop='metric'
                            scopedSlots={{
                              default: ({ row }) => {
                                const isEmpt = !row?.metrics?.length;
                                if (isEmpt) return '--';
                                return (
                                  <div class='tag-column-wrap'>
                                    <div
                                      class='tag-column'
                                      v-bk-tooltips={{
                                        content: row.metrics.map(m => m.id).join(','),
                                        placements: ['top'],
                                        allowHTML: false
                                      }}
                                    >
                                      {row.metrics.map(metric => (
                                        <div
                                          key={metric.id}
                                          class='tag-item set-item'
                                        >
                                          {metric.name || metric.id}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                );
                              }
                            }}
                          ></bk-table-column>
                          <bk-table-column
                            label={this.$t('告警内容')}
                            prop='content'
                            show-overflow-tooltip
                          ></bk-table-column>
                        </bk-table>
                      )}
                    </div>
                  ))}
                </div>
              ))
            ) : (
              <div class='debugger-result-empty'>
                {/* 空样式 */}
                <div>
                  <img
                    src={emptyImageSrc}
                    alt=''
                  />
                </div>
                <span class='empty-dispatch-text'>{this.$t('暂无调试结果')}</span>
              </div>
            )}
          </div>
        </div>
        <div slot='footer'>
          {(!!this.ruleGroupsData.length || !!this.excludeGroups.length) && (
            <bk-button
              theme='primary'
              onClick={this.handleSave}
              class='mr10'
            >
              {this.$t('保存')}
            </bk-button>
          )}
          <bk-button
            onClick={() => {
              this.emitIsShow(false);
            }}
          >
            {this.$t(this.isViewDebugEffect ? '关闭' : '取消')}
          </bk-button>
        </div>
      </bk-sideslider>
    );
  }
}
