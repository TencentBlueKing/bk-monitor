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
import { Component, Prop } from 'vue-property-decorator';
import { ofType, Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { logServiceRelationBkLogIndexSet } from 'monitor-api/modules/apm_service';

import { Scenario } from '../../my-subscription/mapping';
import { type Report, type ReportQueryType, FrequencyType } from '../../my-subscription/types';
import { getDefaultReportData, getSendFrequencyText } from '../../my-subscription/utils';
import DetailRow from './detail-row';

import './report-detail.scss';

interface IProps {
  detailInfo: Report;
  queryType?: ReportQueryType;
}

@Component
class ReportDetail extends tsc<IProps> {
  @Prop({ type: Object, default: () => getDefaultReportData() })
  detailInfo: Report;

  @Prop({ type: String, default: 'available' })
  queryType: ReportQueryType;

  indexSetIDList = [];

  getYearOnYearHour(hour: number) {
    if (hour) return this.$t('{0}小时前', [hour]).toString();
    return this.$t('不比对').toString();
  }

  get getTimeRange() {
    const startTime = this.detailInfo.start_time
      ? dayjs.unix(this.detailInfo.start_time).format('YYYY-MM-DD HH:mm')
      : '';
    const endTime = this.detailInfo.end_time
      ? dayjs.unix(this.detailInfo.end_time).format('YYYY-MM-DD HH:mm')
      : this.$t('永久');
    return `${startTime} ~ ${endTime}`;
  }

  get indexSetName() {
    return this.indexSetIDList.find(item => item.id === this.detailInfo.scenario_config.index_set_id)?.name || '';
  }

  mounted() {
    logServiceRelationBkLogIndexSet().then(response => {
      this.indexSetIDList = response;
    });
  }

  render() {
    return (
      <div class='subscription-detail-container'>
        <div class='title'>{this.$t('订阅内容')}</div>
        <div>
          <DetailRow
            label={this.$t('订阅场景')}
            value={Scenario[this.detailInfo.scenario]}
          />

          <DetailRow
            label={this.$t('索引集')}
            value={this.indexSetName}
          />

          <DetailRow
            label='Pattern'
            value={this.detailInfo.scenario_config.pattern_level}
          />

          <DetailRow
            label={this.$t('最大展示')}
            value={this.detailInfo.scenario_config.log_display_count}
          />

          {this.detailInfo.scenario_config.year_on_year_hour !== 0 && (
            <DetailRow
              label={this.$t('展示同比')}
              value={this.getYearOnYearHour(this.detailInfo.scenario_config.year_on_year_hour)}
            />
          )}

          <DetailRow
            label={this.$t('生成附件')}
            value={this.$t(this.detailInfo.scenario_config.generate_attachment ? '是' : '否').toString()}
          />

          <DetailRow
            label={this.$t('只展示新类')}
            value={this.$t(this.detailInfo.scenario_config.is_show_new_pattern ? '是' : '否').toString()}
          />
        </div>

        <div class='title'>{this.$t('邮件配置')}</div>
        <div>
          <DetailRow
            label={this.$t('邮件标题')}
            value={this.detailInfo.content_config.title}
          />

          <DetailRow
            label={this.$t('附带链接')}
            value={this.$t(this.detailInfo.content_config.is_link_enabled ? '是' : '否').toString()}
          />
        </div>

        <div class='title'>{this.$t('发送配置')}</div>
        <div>
          <DetailRow
            label={this.$t('订阅名称')}
            value={this.detailInfo.name}
          />

          {/* 特殊节点 订阅人里有其他要展示的内容 */}
          <div
            style={{
              paddingBottom: this.detailInfo.channels
                .find(item => item.channel_name === 'user')
                ?.subscribers.filter(item => item.is_enabled).length
                ? '13px'
                : '20px',
            }}
            class='row subscribers'
          >
            <div class='label'>
              <span>{this.$t('订阅人')}</span>
            </div>
            <span class='value'>
              {this.queryType !== 'cancelled' ? (
                <div class='subscribers-row'>
                  <span class='subscribers-label'>{this.$t('内部用户')}</span>
                  <span class='subscribers-value'>
                    {this.detailInfo.channels
                      .find(item => item.channel_name === 'user')
                      ?.subscribers.filter(item => item.is_enabled)
                      ?.map?.(item => {
                        return (
                          <div style='display: inline-flex;margin-right: 24px;margin-bottom: 7px;align-items: center;'>
                            {/* {item.src && (
                          <img
                            src=''
                            alt=''
                            class='avatar'
                          />
                        )} */}
                            <i class='icon-monitor icon-mc-user-one' />
                            <span>{item.id}</span>
                          </div>
                        );
                      })}
                  </span>
                </div>
              ) : (
                <div class='subscribers-row'>
                  <span class='subscribers-value'>-</span>
                </div>
              )}
            </span>
          </div>

          <DetailRow label={this.$t('发送频率')}>
            {this.detailInfo.frequency.type === FrequencyType.onlyOnce ? (
              <span slot='value'>
                <span>{getSendFrequencyText(this.detailInfo)}</span>
                <span style='margin-left: 10px;'>
                  {dayjs(this.detailInfo.frequency.run_time).format('YYYY-MM-DD HH:mm')}
                </span>
              </span>
            ) : (
              <span slot='value'>{getSendFrequencyText(this.detailInfo)}</span>
            )}
          </DetailRow>

          {this.detailInfo.frequency.type !== FrequencyType.onlyOnce && (
            <DetailRow
              label={this.$t('任务有效期')}
              value={this.getTimeRange}
            />
          )}
        </div>
      </div>
    );
  }
}
export default ofType().convert(ReportDetail);
