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
import { Component } from 'vue-property-decorator';
import { ofType, Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { cancelOrResubscribeReport, getReportList, getSendRecords, sendReport } from 'monitor-api/modules/new_report';
import { deepClone, LANGUAGE_COOKIE_KEY } from 'monitor-common/utils';
import { docCookies } from 'monitor-common/utils/utils';

import ReportDetail from '../my-apply/components/report-detail';
import QueryTypeRadio from './components/query-type-radio';
import { Scenario, SendMode, SendStatus } from './mapping';
import { type Report, type ReportQueryType, type ReportSendRecord, type SendResult, FrequencyType } from './types';
import { getDefaultReportData, getDefaultSingleSendRecord, getSendFrequencyText } from './utils';

import './my-subscription.scss';

/** 发送记录 中点击 重新发送会给原先的记录额外添加其他数据。这里补上 */
type ExtraSendReportData = {
  selectedTag: string[];
  tempSendResult: (SendResult & { is_enabled: boolean })[];
};

const currentLang = docCookies.getItem(LANGUAGE_COOKIE_KEY);

@Component({
  components: {
    ReportDetail,
    QueryTypeRadio,
  },
})
class MySubscription extends tsc<object> {
  /** 我的订阅 列表只能查询自己创建的，所以该值固定不变 */
  createType = 'self';
  queryType: ReportQueryType = 'available';
  searchKey = '';
  page = 1;
  pageSize = 20;
  order = '';
  conditions = [];
  /** 订阅列表 数据 */
  reportList = [];
  /** 订阅列表 总数 */
  totalReportSize = 0;
  /** 订阅列表 loading */
  isReportListLoading = false;
  /** 订阅详情 显示抽屉栏 */
  isShowSideslider = false;
  /** 显示 发送记录 弹窗 */
  isShowSendRecord = false;
  /** 发送记录 列表 */
  sendRecordList = [];
  isSendRecordListLoading = false;
  /** 发送记录 中 popover 的实例，用作选择重新发送选择 */
  popoverInstance: unknown = null;
  /** 发送记录 单条数据 */
  currentTableRowOfSendingRecord: ExtraSendReportData & ReportSendRecord = Object.assign(getDefaultSingleSendRecord(), {
    tempSendResult: [],
    selectedTag: [],
  });
  /** 订阅详情 */
  detailInfo = getDefaultReportData();
  /** 重新发送 loading */
  isResending = false;
  tabList = [
    { type: 'available', text: '生效中', iconClass: 'available' },
    { type: 'cancelled', text: '已取消', iconClass: 'cancelled' },
    { type: 'invalid', text: '已失效', iconClass: 'invalid' },
  ];
  resetAndGetSubscriptionList() {
    this.page = 1;
    this.fetchSubscriptionList();
  }

  fetchSubscriptionList() {
    this.isReportListLoading = true;
    getReportList({
      create_type: this.createType,
      query_type: this.queryType,
      search_key: this.searchKey,
      page: this.page,
      page_size: this.pageSize,
      order: this.order,
      conditions: this.conditions,
    })
      .then(response => {
        this.reportList = response.report_list;
        this.totalReportSize = response.total;
      })
      .finally(() => {
        this.isReportListLoading = false;
      });
  }

  handleCancelSubscription(data: Report) {
    this.$bkInfo({
      extCls: 'cancel-report-dialog',
      type: 'warning',
      title: this.$t('是否取消 {0} 的订阅?', [data.name]),
      confirmLoading: true,
      confirmFn: () => {
        return cancelOrResubscribeReport({
          report_id: data.id,
          is_enabled: false,
        })
          .then(() => {
            this.$bkMessage({
              theme: 'success',
              message: this.$t('取消订阅成功'),
            });
            this.fetchSubscriptionList();
            return true;
          })
          .catch(() => false);
      },
    });
  }

  handleResubscribeReport(data: Report) {
    this.$bkInfo({
      extCls: 're-subscription-confirm',
      title: this.$t('是否重新订阅 {0} ?', [data.name]),
      confirmLoading: true,
      confirmFn: () => {
        return cancelOrResubscribeReport({
          report_id: data.id,
          is_enabled: true,
        })
          .then(() => {
            this.$bkMessage({
              theme: 'success',
              message: this.$t('重新订阅成功'),
            });
            this.fetchSubscriptionList();
            return true;
          })
          .catch(() => false);
      },
    });
  }

  getSendingRecordList() {
    this.isSendRecordListLoading = true;
    getSendRecords({
      report_id: this.detailInfo.id,
      channel_name: 'user',
    })
      .then(response => {
        this.sendRecordList = response;
      })
      .finally(() => {
        this.isSendRecordListLoading = false;
      });
  }

  formatTimeRange(s: number, e: number) {
    if (!s) return '';
    const startTime = dayjs.unix(s).format('YYYY-MM-DD HH:mm');
    const endTime = dayjs.unix(e).format('YYYY-MM-DD HH:mm');
    return `${startTime} ~ ${endTime}`;
  }

  handleResendSubscription() {
    this.isResending = true;
    const channels = [
      {
        is_enabled: true,
        channel_name: this.currentTableRowOfSendingRecord.channel_name,
        subscribers: this.currentTableRowOfSendingRecord.tempSendResult
          .filter(item => {
            return this.currentTableRowOfSendingRecord.selectedTag.includes(item.id);
          })
          .map(item => {
            delete item.result;

            item.is_enabled = true;
            return item;
          }),
      },
    ];
    sendReport({
      report_id: this.currentTableRowOfSendingRecord.report_id,
      channels,
    })
      .then(() => {
        this.$bkMessage({
          theme: 'success',
          message: this.$t('发送成功'),
        });
        // @ts-ignore
        this.popoverInstance.hide();
      })
      .finally(() => {
        this.isResending = false;
      });
  }

  /** 根据当前的 订阅场景 跳转到相应的能创建订阅的页面。
   * 比如：日志聚类 跳转到 日志平台 => 日志聚类 => 数据指纹
   * */
  goToTargetScene() {
    if (this.detailInfo.scenario === 'clustering') {
      if (!this.detailInfo.scenario_config.index_set_id) {
        this.$bkMessage({
          theme: 'warning',
          message: this.$t('请选择索引集'),
        });
        return;
      }
      // URL参数补齐再跳转即可。需要: spaceUid、bizId, activeTableTab, clusterRouteParams (一个配置对象)
      // 日志平台的 URL: window.bk_log_search_url
      const query = {
        spaceUid: window.space_list.find(item => item.bk_biz_id === window.bk_biz_id).space_uid || '',
        bizId: window.bk_biz_id,
        // 固定写
        activeTableTab: 'clustering',
        clusterRouteParams: JSON.stringify({
          // 固定写
          activeNav: 'dataFingerprint',
          requestData: {
            pattern_level: this.detailInfo.scenario_config.pattern_level,
            year_on_year_hour: this.detailInfo.scenario_config.year_on_year_hour,
            show_new_pattern: this.detailInfo.scenario_config.is_show_new_pattern,
            group_by: [],
            size: 10000,
          },
        }),
      };
      const qs = new URLSearchParams(query as any).toString();
      window.open(`${window.bk_log_search_url}#/retrieve/${this.detailInfo.scenario_config.index_set_id}?${qs}`);
    }
  }

  mounted() {
    this.fetchSubscriptionList();
  }
  render() {
    const sendingRecord = () => {
      return (
        <bk-dialog
          width='960'
          v-model={this.isShowSendRecord}
          header-position='left'
          show-footer={false}
          title={this.$t('发送记录')}
          z-index={2001}
        >
          <div>
            <div class='dialog-header-info-container'>
              <div style='display: flex;'>
                <div class='label-container'>
                  <div class='label'>{this.$t('发送频率')}:</div>
                  <div class='value'>{getSendFrequencyText(this.detailInfo)}</div>
                  {this.detailInfo.frequency.type === FrequencyType.onlyOnce && (
                    <div class='value'>{dayjs(this.detailInfo.frequency.run_time).format('YYYY-MM-DD HH:mm')}</div>
                  )}
                </div>
                {this.detailInfo.frequency.type !== FrequencyType.onlyOnce && (
                  <div class='label-container'>
                    <div
                      style='margin-left: 55px;'
                      class='label'
                    >
                      {this.$t('任务有效期')}:
                    </div>
                    <div class='value'>
                      {this.formatTimeRange(this.detailInfo.start_time, this.detailInfo.end_time)}
                    </div>
                  </div>
                )}
              </div>

              <div>
                <bk-button
                  style='font-size: 12px;'
                  disabled={this.isSendRecordListLoading}
                  theme='primary'
                  text
                  onClick={this.getSendingRecordList}
                >
                  {this.$t('刷新')}
                </bk-button>
              </div>
            </div>

            <bk-table
              style='margin-top: 16px;'
              height={400}
              v-bkloading={{
                isLoading: this.isSendRecordListLoading,
              }}
              data={this.sendRecordList}
            >
              <bk-table-column
                scopedSlots={{
                  default: ({ row }) => {
                    return <div>{row.send_time ? dayjs(row.send_time).format('YYYY-MM-DD HH:mm:ss') : '--'}</div>;
                  },
                }}
                label={this.$t('发送时间')}
                prop='send_time'
              />

              <bk-table-column
                scopedSlots={{
                  default: ({ row }) => {
                    return (
                      <div style='display: flex; align-items: center;'>
                        <i class={['dot-circle', row.send_status]} />
                        <span style='margin-left: 10px;'>{SendStatus[row.send_status]}</span>
                      </div>
                    );
                  },
                }}
                label={this.$t('发送结果')}
              />

              <bk-table-column
                scopedSlots={{
                  default: ({ row }) => {
                    return (
                      <bk-button
                        theme='primary'
                        text
                        onClick={e => {
                          this.currentTableRowOfSendingRecord = row;
                          this.sendRecordList.forEach(item => {
                            // 为了不影响原先的 send_result ,这里将使用中间变量。
                            this.$set(item, 'tempSendResult', deepClone(item.send_results));
                            this.$set(item, 'selectedTag', []);
                            // 需要根据发送结果去对 selectedTag 里的内容进行预先填充。
                            item.send_results.forEach(subItem => {
                              if (item.send_status === 'partial_failed' && !subItem.result) {
                                item.selectedTag.push(subItem.id);
                              }
                              if (item.send_status === 'failed') {
                                item.selectedTag.push(subItem.id);
                              }
                            });
                          });
                          this.$nextTick(() => {
                            if (this.popoverInstance) {
                              // @ts-ignore
                              this.popoverInstance.destroy();
                            }
                            this.popoverInstance = this.$bkPopover(e.target, {
                              content: this.$refs.popoverContent,
                              trigger: 'click',
                              arrow: true,
                              placement: 'bottom-start',
                              theme: 'light',
                              extCls: 'email-subscription-popover',
                              hideOnClick: false,
                              interactive: true,
                              zIndex: 2002,
                            });
                            // @ts-ignore
                            this.popoverInstance.show(100);
                          });
                        }}
                      >
                        {this.$t('重新发送')}
                      </bk-button>
                    );
                  },
                }}
                label={this.$t('操作')}
              />
            </bk-table>
          </div>
        </bk-dialog>
      );
    };
    const popoverTmpl = () => {
      return (
        <div style='display: none;'>
          <div
            ref='popoverContent'
            class='resend-popover-container'
          >
            <div class='success-header-text'>
              {/* 根据 data.channel_name 如果为 success 就选这些文本
                  1. 已成功发送 {0} 个内部用户
                  2. 已成功发送 {0} 个外部邮件
                  3. 已成功发送 {0} 个企业微信群

                  如果为 partial_failed, success 就选这些文本
                  1. 已成功发送 {0} 个，失败 {1} 个企业微信群
                  2. 已成功发送 {0} 个，失败 {1} 个外部邮件
                  3. 已成功发送 {0} 个，失败 {1} 个内部用户
                  */}
              <i18n path='已成功发送 {0} 个内部用户'>
                <span class='success-text'>{this.currentTableRowOfSendingRecord.send_results.length}</span>
              </i18n>
            </div>

            <div class='header-confirm-text'>
              {/* 根据 data.channel_name 如果为 success 就选这些文本
              1. 确定重新发送给以下用户
              2. 确定重新发送给以下邮件
              3. 确定重新发送给以下企微群

              如果为 partial_failed, success 就选这些文本
              1. 确定重新发送给以下失败企微群
              2. 确定重新发送给以下失败邮件
              3. 确定重新发送给以下失败用户
          */}
              {this.$t('确定重新发送给以下用户')}
            </div>

            <div style='margin-top: 10px;'>
              <bk-tag-input
                v-model={this.currentTableRowOfSendingRecord.selectedTag}
                content-width={247}
                display-key='id'
                list={this.currentTableRowOfSendingRecord.tempSendResult}
                placeholder={this.$t('请选择')}
                save-key='id'
                search-key={['id']}
                trigger='focus'
                has-delete-icon
              />
            </div>

            <div class='footer-operation'>
              <bk-button
                style='min-width: 64px;'
                disabled={!this.currentTableRowOfSendingRecord.selectedTag.length}
                loading={this.isResending}
                theme='primary'
                onClick={this.handleResendSubscription}
              >
                {this.$t('确定')}
              </bk-button>

              <bk-button
                style='min-width: 64px;margin-left: 8px;'
                onClick={() => {
                  // @ts-ignore
                  this.popoverInstance.hide();
                }}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          </div>
        </div>
      );
    };
    return (
      <div class='my-apply-container'>
        <div>
          <div class='header-container'>
            <QueryTypeRadio
              v-model={this.queryType}
              tabList={this.tabList}
              onChange={() => {
                this.resetAndGetSubscriptionList();
              }}
            />

            <bk-input
              style='width: 320px;'
              v-model={this.searchKey}
              placeholder={this.$t('请输入搜索条件')}
              right-icon='bk-icon icon-search'
              onEnter={this.resetAndGetSubscriptionList}
            />
          </div>

          <bk-table
            style='margin-top: 24px;'
            v-bkloading={{
              isLoading: this.isReportListLoading,
            }}
            data={this.reportList}
            {...{
              on: {
                'filter-change': filters => {
                  const targetKey = Object.keys(filters)[0];
                  let targetIndex = -1;
                  const result = this.conditions.filter((item, index) => {
                    if (item.key === targetKey) targetIndex = index;
                    return item.key === targetKey;
                  });
                  if (result.length) {
                    if (filters[targetKey]?.length) {
                      this.conditions[targetIndex].value = filters[targetKey];
                    } else {
                      this.conditions.splice(targetIndex, 1);
                    }
                  } else {
                    if (filters[targetKey]?.length) {
                      this.conditions.push({
                        key: targetKey,
                        value: filters[targetKey],
                      });
                    }
                  }
                  this.page = 1;
                  this.fetchSubscriptionList();
                },

                'sort-change': ({ column, prop, order }) => {
                  if (prop) {
                    this.order = `${order === 'ascending' ? '' : '-'}${prop}`;
                  } else {
                    this.order = '';
                  }
                  this.fetchSubscriptionList();
                },
                'page-change': newPage => {
                  this.page = newPage;
                  this.fetchSubscriptionList();
                },
                'page-limit-change': limit => {
                  this.page = 1;
                  this.pageSize = limit;
                  this.fetchSubscriptionList();
                },
              },
            }}
            pagination={{
              current: this.page,
              count: this.totalReportSize,
              limit: this.pageSize,
            }}
          >
            <bk-table-column
              scopedSlots={{
                default: ({ row }) => {
                  return (
                    <div
                      style='padding: 14px 0;'
                      v-bk-overflow-tips={{ content: row.name }}
                    >
                      <bk-button
                        style='height: auto;'
                        text
                        onClick={() => {
                          this.isShowSideslider = true;
                          this.detailInfo = row;
                        }}
                      >
                        {row.name}
                      </bk-button>
                    </div>
                  );
                },
              }}
              label={this.$t('订阅名称')}
            />

            <bk-table-column
              scopedSlots={{
                default: ({ row }) => {
                  return <div v-bk-overflow-tips>{Scenario[row.scenario]}</div>;
                },
              }}
              label={this.$t('订阅场景')}
            />

            <bk-table-column
              scopedSlots={{
                default: ({ row }) => {
                  return (
                    <div v-bk-overflow-tips>{row.is_self_subscribed ? this.$t('主动订阅') : this.$t('他人订阅')}</div>
                  );
                },
              }}
              label={this.$t('来源')}
            />

            <bk-table-column
              filters={[
                {
                  text: this.$t('周期发送'),
                  value: 'periodic',
                },
                {
                  text: this.$t('仅发一次'),
                  value: 'one_time',
                },
              ]}
              scopedSlots={{
                default: ({ row }) => {
                  return <div v-bk-overflow-tips>{SendMode[row.send_mode]}</div>;
                },
              }}
              columnKey='send_mode'
              label={this.$t('发送模式')}
              prop='send_mode'
            />

            <bk-table-column
              scopedSlots={{
                default: ({ row }) => {
                  return (
                    <div v-bk-overflow-tips>
                      {row?.frequency?.type === FrequencyType.onlyOnce
                        ? `${getSendFrequencyText(row)} ${dayjs(row.frequency.run_time).format('YYYY-MM-DD HH:mm')}`
                        : getSendFrequencyText(row)}
                    </div>
                  );
                },
              }}
              label={this.$t('发送时间')}
            />

            <bk-table-column
              scopedSlots={{
                default: ({ row }) => {
                  return (
                    <div v-bk-overflow-tips>
                      {row.last_send_time ? dayjs(row.last_send_time).format('YYYY-MM-DD HH:mm:ss') : '--'}
                    </div>
                  );
                },
              }}
              label={this.$t('最近一次发送时间')}
              prop='last_send_time'
              sortable='custom'
            />

            <bk-table-column
              filters={[
                {
                  text: `${this.$t('发送成功')}`,
                  value: 'success',
                },
                {
                  text: `${this.$t('未发送')}`,
                  value: 'no_status',
                },
                // {
                //   text: `${this.$t('发送部分失败')}`,
                //   value: 'partial_failed'
                // },
                {
                  text: `${this.$t('发送失败')}`,
                  value: 'failed',
                },
              ]}
              scopedSlots={{
                default: ({ row }) => {
                  return (
                    <div
                      style='display: flex; align-items: center;'
                      v-bk-overflow-tips
                    >
                      <i
                        style='margin-right: 10px;'
                        class={['dot-circle', row.send_status]}
                      />
                      {SendStatus[row.send_status]}
                    </div>
                  );
                },
              }}
              columnKey='send_status'
              label={this.$t('发送状态')}
              prop='send_status'
            />

            <bk-table-column
              scopedSlots={{
                default: ({ row }) => {
                  return (
                    <div>
                      <bk-button
                        theme='primary'
                        text
                        onClick={() => {
                          this.isShowSendRecord = true;
                          this.detailInfo = row;
                          this.getSendingRecordList();
                        }}
                      >
                        {this.$t('发送记录')}
                      </bk-button>

                      {['available', 'invalid'].includes(this.queryType) && (
                        <bk-button
                          style='margin-left: 10px;'
                          theme='primary'
                          text
                          onClick={() => this.handleCancelSubscription(row)}
                        >
                          {this.$t('取消订阅')}
                        </bk-button>
                      )}

                      {this.queryType === 'cancelled' && (
                        <bk-button
                          style='margin-left: 10px;'
                          theme='primary'
                          text
                          onClick={() => this.handleResubscribeReport(row)}
                        >
                          {this.$t('重新订阅')}
                        </bk-button>
                      )}
                    </div>
                  );
                },
              }}
              label={this.$t('操作')}
            />
          </bk-table>
        </div>

        <bk-sideslider
          width='640'
          ext-cls='my-subscription-slider'
          before-close={() => {
            this.isShowSideslider = false;
          }}
          is-show={this.isShowSideslider}
          quick-close
          transfer
        >
          <div
            style='height: 100%;'
            slot='header'
          >
            <div class='title-container'>
              <div style='display: flex;align-items: center;'>
                <span class='title'>{this.$t('订阅详情')}</span>
                <span class='sub-title'>-&nbsp;</span>
                <span
                  style={{
                    maxWidth: currentLang === 'en' ? '260px' : '350px',
                  }}
                  class='sub-title'
                  v-bk-overflow-tips
                >
                  {this.detailInfo.name}
                </span>
                <i
                  style='color: #3A84FF; font-size: 14px; margin-left: 10px; cursor: pointer;'
                  class='icon-monitor icon-copy-link link-icon'
                  onClick={this.goToTargetScene}
                />
              </div>

              <div>
                {['available', 'invalid'].includes(this.queryType) && (
                  <bk-button
                    theme='primary'
                    outline
                    onClick={() => this.handleCancelSubscription(this.detailInfo)}
                  >
                    {this.$t('取消订阅')}
                  </bk-button>
                )}

                {this.queryType === 'cancelled' && (
                  <bk-button
                    theme='primary'
                    outline
                    onClick={() => this.handleResubscribeReport(this.detailInfo)}
                  >
                    {this.$t('重新订阅')}
                  </bk-button>
                )}
              </div>
            </div>
          </div>

          <div slot='content'>
            <ReportDetail
              detailInfo={this.detailInfo}
              queryType={this.queryType}
            />
          </div>
        </bk-sideslider>

        {sendingRecord()}
        {popoverTmpl()}
      </div>
    );
  }
}
export default ofType().convert(MySubscription);
