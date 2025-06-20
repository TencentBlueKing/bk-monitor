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
import { type PropType, computed, defineComponent, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import dayjs from 'dayjs';
import { logServiceRelationBkLogIndexSet } from 'monitor-api/modules/apm_service';

import { Scenario } from '../mapping';
import { FrequencyType, type Report } from '../types';
import { getDefaultReportData, getSendFrequencyText } from '../utils';
import DetailRow from './detail-row';

import './subscription-detail.scss';

export default defineComponent({
  name: 'SubscriptionDetail',
  props: {
    detailInfo: {
      type: Object as PropType<Report>,
      default() {
        return getDefaultReportData();
      },
    },
  },
  setup(props) {
    const { t } = useI18n();
    // 索引集 列表
    const indexSetIDList = ref([]);

    function getYearOnYearHour(type: number) {
      if (type === 0) return t('不比对');
      return t('{0}小时前', [type]);
    }

    const getTimeRange = computed(() => {
      const startTime = props.detailInfo.start_time
        ? dayjs.unix(props.detailInfo.start_time).format('YYYY-MM-DD HH:mm')
        : '';
      const endTime = props.detailInfo.end_time
        ? dayjs.unix(props.detailInfo.end_time).format('YYYY-MM-DD HH:mm')
        : t('永久');
      return `${startTime} ~ ${endTime}`;
    });

    // 查询 索引集 名称
    const indexSetName = computed(() => {
      return indexSetIDList.value.find(item => item.id === props.detailInfo.scenario_config.index_set_id)?.name || '';
    });

    const userChannel = computed(() => {
      return props.detailInfo.channels.find(item => item.channel_name === 'user');
    });

    const emailChannel = computed(() => {
      return props.detailInfo.channels.find(item => item.channel_name === 'email');
    });

    const wxgroupChannel = computed(() => {
      return props.detailInfo.channels.find(item => item.channel_name === 'wxbot');
    });

    onMounted(() => {
      logServiceRelationBkLogIndexSet().then(response => {
        indexSetIDList.value = response;
      });
    });
    return {
      t,
      getSendFrequencyText,
      getTimeRange,
      indexSetName,
      getYearOnYearHour,
      userChannel,
      emailChannel,
      wxgroupChannel,
    };
  },
  render() {
    return (
      <div class='subscription-detail-container'>
        <div class='title'>{this.t('订阅内容')}</div>
        <div>
          <DetailRow
            label={this.t('订阅场景')}
            value={this.t(Scenario[this.detailInfo.scenario])}
          />

          <DetailRow
            label={this.t('索引集')}
            value={this.indexSetName}
          />

          <DetailRow
            label='Pattern'
            value={this.detailInfo.scenario_config.pattern_level}
          />

          <DetailRow
            label={this.t('最大展示')}
            value={`${this.detailInfo.scenario_config.log_display_count} ${this.t('条')}`}
          />

          {this.detailInfo.scenario_config.year_on_year_hour !== 0 && (
            <DetailRow
              label={this.t('展示同比')}
              value={this.getYearOnYearHour(this.detailInfo.scenario_config.year_on_year_hour)}
            />
          )}

          <DetailRow
            label={this.t('生成附件')}
            value={this.detailInfo.scenario_config.generate_attachment ? this.t('是') : this.t('否')}
          />

          <DetailRow
            label={this.t('只展示新类')}
            value={this.detailInfo.scenario_config.is_show_new_pattern ? this.t('是') : this.t('否')}
          />
        </div>

        <div class='title'>{this.t('邮件配置')}</div>
        <div>
          <DetailRow
            label={this.t('邮件标题')}
            value={this.detailInfo.content_config.title}
          />

          <DetailRow
            label={this.t('附带链接')}
            value={this.detailInfo.content_config.is_link_enabled ? this.t('是') : this.t('否')}
          />
        </div>

        <div class='title'>{this.t('发送配置')}</div>
        <div>
          <DetailRow
            label={this.t('订阅名称')}
            value={this.detailInfo.name}
          />

          {/* 特殊节点 订阅人里有其他要展示的内容 */}
          <div
            style='padding-bottom: 13px;'
            class='row subscribers'
          >
            <div class='label'>
              <span>{this.t('订阅人')}</span>
            </div>
            <span
              style='display: flex;flex-direction: column;row-gap: 13px;'
              class='value'
            >
              {this.userChannel?.is_enabled && (
                <div class='subscribers-row'>
                  <span
                    style='margin-bottom: 7px;'
                    class='subscribers-label'
                  >
                    {this.t('内部用户')}
                  </span>
                  <span class='subscribers-value'>
                    {this.userChannel?.subscribers?.map?.(item => {
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
                          <bk-user-display-name
                            style='margin-left: 5px;'
                            user-id={item.id}
                          />
                        </div>
                      );
                    })}
                  </span>
                </div>
              )}

              {this.emailChannel?.is_enabled && (
                <div class='subscribers-row'>
                  <span
                    style='margin-bottom: 7px;'
                    class='subscribers-label'
                  >
                    {this.t('外部邮件')}
                  </span>
                  <span class='subscribers-value'>
                    {this.emailChannel?.subscribers?.map?.(item => {
                      return (
                        <span
                          style='display: inline-flex;height: 16px;align-items: center;margin-bottom: 7px;'
                          class='email'
                        >
                          {item.id}
                        </span>
                      );
                    })}
                  </span>
                </div>
              )}

              {this.wxgroupChannel?.is_enabled && (
                <div class='subscribers-row'>
                  <span
                    style='margin-bottom: 7px;'
                    class='subscribers-label'
                  >
                    {this.t('企业微信群')}
                  </span>
                  <span class='subscribers-value'>
                    {this.wxgroupChannel?.subscribers?.map?.(item => {
                      return (
                        <span
                          style='display: inline-flex;height: 16px;align-items: center;margin-bottom: 7px;'
                          class='group-id'
                        >
                          {item.id}
                        </span>
                      );
                    })}
                  </span>
                </div>
              )}
            </span>
          </div>

          <DetailRow
            v-slots={{
              value: () => {
                return this.detailInfo.frequency.type === FrequencyType.onlyOnce ? (
                  <span>
                    <span>{this.getSendFrequencyText(this.detailInfo)}</span>
                    <span style='margin-left: 10px;'>
                      {dayjs(this.detailInfo.frequency.run_time).format('YYYY-MM-DD HH:mm')}
                    </span>
                  </span>
                ) : (
                  this.getSendFrequencyText(this.detailInfo)
                );
              },
            }}
            label={this.t('发送频率')}
          />

          {this.detailInfo.frequency.type !== FrequencyType.onlyOnce && (
            <DetailRow
              label={this.t('任务有效期')}
              value={this.getTimeRange}
            />
          )}
        </div>
      </div>
    );
  },
});
