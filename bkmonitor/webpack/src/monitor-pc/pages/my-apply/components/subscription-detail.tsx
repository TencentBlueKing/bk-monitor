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
import { computed, defineComponent, onMounted, ref } from 'vue';
import { logServiceRelationBkLogIndexSet } from '@api/modules/apm_service';
import dayjs from 'dayjs';

import './subscription-detail.scss';

export enum Scenario {
  clustering = window.i18n.t('日志聚类'),
  dashboard = window.i18n.t('仪表盘'),
  scene = window.i18n.t('观测场景')
}

enum YearOnYearHour {
  0 = window.i18n.t('不比对'),
  1 = window.i18n.t('1小时前'),
  2 = window.i18n.t('2小时前'),
  3 = window.i18n.t('3小时前'),
  6 = window.i18n.t('6小时前'),
  12 = window.i18n.t('12小时前'),
  24 = window.i18n.t('24小时前')
}

export default defineComponent({
  name: 'SubscriptionDetail',
  props: {
    detailInfo: {
      type: Object,
      default() {
        return {};
      }
    },
    queryType: {
      type: String,
      default: 'available'
    }
  },
  setup(props) {
    function formatFrequency(data) {
      if (!data.frequency) return '';
      const hourTextMap = {
        0.5: window.i18n.t('每个小时整点,半点发送'),
        1: window.i18n.t('每个小时整点发送'),
        2: window.i18n.t('从0点开始,每隔2小时整点发送'),
        6: window.i18n.t('从0点开始,每隔6小时整点发送'),
        12: window.i18n.t('每天9:00,21:00发送')
      };
      const weekMap = [
        window.i18n.t('周一'),
        window.i18n.t('周二'),
        window.i18n.t('周三'),
        window.i18n.t('周四'),
        window.i18n.t('周五'),
        window.i18n.t('周六'),
        window.i18n.t('周日')
      ];
      let str = '';
      switch (data.frequency.type) {
        case 3: {
          const weekStrArr = data.frequency.week_list.map(item => weekMap[item - 1]);
          const weekStr = weekStrArr.join(', ');
          str = `${weekStr} ${data.frequency.run_time}`;
          break;
        }
        case 4: {
          const dayArr = data.frequency.day_list.map(item => `${item}号`);
          const dayStr = dayArr.join(', ');
          str = `${dayStr} ${data.frequency.run_time}`;
          break;
        }
        case 5: {
          str = hourTextMap[data.frequency.hour];
          break;
        }
        default:
          str = data.frequency.run_time;
          break;
      }
      return str;
    }
    const getTimeRange = computed(() => {
      if (!props?.detailInfo?.start_time) return '';
      const startTime = dayjs.unix(props.detailInfo.start_time).format('YYYY-MM-DD HH:mm:ss');
      const endTime = dayjs.unix(props.detailInfo.end_time).format('YYYY-MM-DD HH:mm:ss');
      return `${startTime} ~ ${endTime}`;
    });

    const indexSetIDList = ref([]);
    const indexSetName = computed(() => {
      return indexSetIDList.value.find(item => item.id === props.detailInfo?.scenario_config?.index_set_id)?.name || '';
    });

    onMounted(() => {
      logServiceRelationBkLogIndexSet()
        .then(response => {
          indexSetIDList.value = response;
        })
        .catch(console.log);
    });

    return {
      formatFrequency,
      getTimeRange,
      indexSetName
    };
  },
  render() {
    return (
      <div class='subscription-detail-container'>
        <div class='title'>{window.i18n.t('订阅内容')}</div>
        <div>
          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('订阅场景')}</span>
            </div>
            <span class='value'>{Scenario[this.detailInfo?.scenario]}</span>
          </div>

          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('索引集')}</span>
            </div>
            <span class='value'>{this.indexSetName}</span>
          </div>

          {/* 暂时不显示 */}
          {false && (
            <div class='row'>
              <div class='label'>
                <span>{window.i18n.t('展示范围')}</span>
              </div>
              {/* 需要转义 */}
              <span class='value'>{this.detailInfo?.scenario_config?.year_on_year_change}</span>
            </div>
          )}

          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('敏感度')}</span>
            </div>
            <span class='value'>{this.detailInfo?.scenario_config?.pattern_level}</span>
          </div>

          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('最大展示')}</span>
            </div>
            <span class='value'>{this.detailInfo?.scenario_config?.log_display_count}</span>
          </div>

          {this.detailInfo?.scenario_config?.year_on_year_hour !== 0 && (
            <div class='row'>
              <div class='label'>
                <span>{window.i18n.t('展示同比')}</span>
              </div>
              <span class='value'>{YearOnYearHour[this.detailInfo?.scenario_config?.year_on_year_hour]}</span>
            </div>
          )}

          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('生成附件')}</span>
            </div>
            <span class='value'>
              {this.detailInfo?.scenario_config?.generate_attachment ? window.i18n.t('是') : window.i18n.t('否')}
            </span>
          </div>
        </div>

        {/* <div class='title'>{window.i18n.t('邮件配置')}</div>
        <div>
          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('邮件标题')}</span>
            </div>
            <span class='value'>{this.detailInfo?.content_config?.title}</span>
          </div>

          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('附带链接')}</span>
            </div>
            <span class='value'>
              {this.detailInfo?.content_config?.is_link_enabled ? window.i18n.t('是') : window.i18n.t('否')}
            </span>
          </div>
        </div> */}

        <div class='title'>{window.i18n.t('发送配置')}</div>
        <div>
          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('邮件标题')}</span>
            </div>
            <span class='value'>{this.detailInfo?.content_config?.title}</span>
          </div>

          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('附带链接')}</span>
            </div>
            <span class='value'>
              {this.detailInfo?.content_config?.is_link_enabled ? window.i18n.t('是') : window.i18n.t('否')}
            </span>
          </div>

          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('订阅名称')}</span>
            </div>
            <span class='value'>{this.detailInfo?.name}</span>
          </div>

          {/* 特殊节点 订阅人里有其他要展示的内容 */}
          <div class='row subscribers'>
            <div class='label'>
              <span>{window.i18n.t('订阅人')}</span>
            </div>
            <span class='value'>
              {this.queryType !== 'cancelled' ? (
                <div class='subscribers-row'>
                  <span
                    class='subscribers-label'
                    style='padding-top: 3px;'
                  >
                    {window.i18n.t('内部用户')}
                  </span>
                  <span
                    class='subscribers-value'
                    style='padding-top: 3px;'
                  >
                    {this.detailInfo?.channels
                      ?.find?.(item => item.channel_name === 'user')
                      ?.subscribers?.filter(item => item.is_enabled)
                      ?.map?.(item => {
                        return (
                          <div style='display: inline-flex;align-items: center;margin-right: 24px;height: 100%;'>
                            {/* {item.src && (
                            <img
                              src=''
                              alt=''
                              class='avatar'
                            />
                          )} */}
                            <span>{item.id}</span>
                          </div>
                        );
                      })}
                  </span>
                </div>
              ) : (
                <div class='subscribers-row'>
                  <span
                    class='subscribers-value'
                    style='padding-top: 3px;'
                  >
                    -
                  </span>
                </div>
              )}

              {/* 暂时不需要 */}
              {/* <div
                class='subscribers-row'
                style='padding-top: 20px;'
              >
                <span class='subscribers-label'>{window.i18n.t('外部邮件')}</span>
                <span class='subscribers-value'>
                  {this.detailInfo?.channels
                    ?.find?.(item => item.channel_name === 'email')
                    ?.subscribers?.map?.(item => {
                      return <span class='email'>{item.id}</span>;
                    })}
                </span>
              </div> */}

              {/* 暂时不需要 */}
              {/* <div
                class='subscribers-row'
                style='padding-top: 20px;'
              >
                <span class='subscribers-label'>{window.i18n.t('企业微信群')}</span>
                <span class='subscribers-value'>
                  {this.detailInfo?.channels
                    ?.find?.(item => item.channel_name === 'wxbot')
                    ?.subscribers?.map?.(item => {
                      return <span class='group-id'>{item.id}</span>;
                    })}
                </span>
              </div> */}
            </span>
          </div>

          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('发送频率')}</span>
            </div>
            <span
              class='value'
              style='align-self: center;'
            >
              {this.formatFrequency(this.detailInfo)}
            </span>
          </div>

          <div class='row'>
            <div class='label'>
              <span>{window.i18n.t('有效时间范围')}</span>
            </div>
            <span
              class='value'
              style='align-self: center;'
            >
              {this.getTimeRange}
            </span>
          </div>
        </div>
      </div>
    );
  }
});
