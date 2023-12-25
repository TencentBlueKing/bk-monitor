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
import { Component, Watch } from 'vue-property-decorator';
import { Component as tsc, ofType } from 'vue-tsx-support';
import { cancelOrResubscribeReport, getReportList, getSendRecords, sendReport } from '@api/modules/new_report';
import { deepClone } from '@common/utils';
import dayjs from 'dayjs';

import SubscriptionDetail, { Scenario } from '../my-apply/components/subscription-detail';

import './my-subscription.scss';

enum SendMode {
  periodic = window.i18n.t('周期发送'),
  one_time = window.i18n.t('仅发一次')
}

enum SendStatus {
  failed = window.i18n.t('发送失败'),
  partial_failed = window.i18n.t('发送部分失败'),
  success = window.i18n.t('发送成功')
}

@Component({
  components: {
    SubscriptionDetail
  }
})
class MySubscription extends tsc<{}> {
  queryData = {
    create_type: 'self',
    query_type: 'available',
    search_key: '',
    page: 1,
    page_size: 20,
    order: '',
    conditions: []
  };
  tableData = [];
  isTableLoading = false;
  isShowSideslider = false;
  isShowSendRecord = false;
  sendRecordTable = {
    data: [],
    isLoading: false
  };
  popoverInstance: unknown = null;
  currentTableRowOfSendingRecord: unknown = {};
  isShowQuickCreateSideslider = false;
  detailInfo = {};
  isCancelingSubscription = false;
  isResending = false;
  resetAndGetSubscriptionList() {
    this.queryData.page = 1;
    this.queryData.page_size = 20;
    this.fetchSubscriptionList();
  }

  fetchSubscriptionList() {
    this.isTableLoading = true;
    getReportList(this.queryData)
      .then(response => {
        console.log(response);
        this.tableData = response;
      })
      .catch(console.log)
      .finally(() => {
        this.isTableLoading = false;
      });
  }

  handleCancelSubscription(data) {
    this.$bkInfo({
      title: this.$t('是否取消 {0} 的订阅?', [data?.name]),
      confirmLoading: true,
      confirmFn: () => {
        return cancelOrResubscribeReport({
          report_id: data?.id,
          is_enabled: false
        })
          .then(() => {
            this.$bkMessage({
              theme: 'success',
              message: this.$t('取消订阅成功')
            });
            this.fetchSubscriptionList();
            return true;
          })
          .catch(error => {
            console.log(error);
            return false;
          });
      }
    });
  }

  handleResubscribeReport(data) {
    this.$bkInfo({
      title: this.$t('是否重新订阅 {0} ?', [data?.name]),
      confirmLoading: true,
      confirmFn: () => {
        return cancelOrResubscribeReport({
          report_id: data?.id,
          is_enabled: true
        })
          .then(() => {
            this.$bkMessage({
              theme: 'success',
              message: this.$t('重新订阅成功')
            });
            this.fetchSubscriptionList();
            return true;
          })
          .catch(error => {
            console.log(error);
            return false;
          });
      }
    });
  }

  getSendingRecordList() {
    this.sendRecordTable.isLoading = true;
    getSendRecords({
      report_id: this.detailInfo.id
    })
      .then(response => {
        console.log(response);
        this.sendRecordTable.data = response;
      })
      .catch(console.log)
      .finally(() => {
        this.sendRecordTable.isLoading = false;
      });
  }

  getSendFrequencyText(data) {
    const hourTextMap = {
      0.5: window.i18n.tc('每个小时整点,半点发送'),
      1: window.i18n.tc('每个小时整点发送'),
      2: window.i18n.tc('从0点开始,每隔2小时整点发送'),
      6: window.i18n.tc('从0点开始,每隔6小时整点发送'),
      12: window.i18n.tc('每天9:00,21:00发送')
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
    if (!data?.frequency?.type) return '';
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

  formatTimeRange(s, e) {
    if (!s) return '';
    const startTime = dayjs.unix(s).format('YYYY-MM-DD HH:mm:ss');
    const endTime = dayjs.unix(e).format('YYYY-MM-DD HH:mm:ss');
    return `${startTime} ~ ${endTime}`;
  }

  handleResendSubscription() {
    this.isResending = true;
    const channels = [
      {
        is_enabled: true,
        channel_name: this.currentTableRowOfSendingRecord.channel_name,
        // subscribers: this.currentTableRowOfSendingRecord.tempSendResult
        //   .filter(item => {
        //     if (['success'].includes(this.currentTableRowOfSendingRecord.send_status) && item.result) {
        //       return item;
        //     }
        //     if (
        //       ['partial_failed', 'failed'].includes(this.currentTableRowOfSendingRecord.send_status) &&
        //       !item.result
        //     ) {
        //       return item;
        //     }
        //   })
        //   .map(item => {
        //     const o = {
        //       id: item.id,
        //       is_enabled: true
        //     };
        //     if (item.type) {
        //       o.type = item.type;
        //     }
        //     return o;
        //   })
        subscribers: this.currentTableRowOfSendingRecord.tempSendResult
          ?.filter(item => {
            return this.currentTableRowOfSendingRecord.selectedTag.includes(item.id);
          })
          .map(item => {
            // eslint-disable-next-line no-param-reassign
            delete item.result;
            // eslint-disable-next-line no-param-reassign
            item.is_enabled = true;
            return item;
          })
      }
    ];
    sendReport({
      report_id: this.currentTableRowOfSendingRecord.report_id,
      channels
    })
      .then(() => {
        this.$bkMessage({
          theme: 'success',
          message: this.$t('发送成功')
        });
        this.popoverInstance.hide();
      })
      .catch(console.log)
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
        Message({
          theme: 'warning',
          message: window.i18n.t('请选择索引集')
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
            size: 10000
          }
        })
      };
      const qs = new URLSearchParams(query as any).toString();
      window.open(`${window.bk_log_search_url}#/retrieve/${this.detailInfo.scenario_config.index_set_id}?${qs}`);
    }
  }

  @Watch('queryData.query_type')
  handleQueryTypeChange() {
    this.resetAndGetSubscriptionList();
  }

  mounted() {
    this.fetchSubscriptionList();
  }
  render() {
    const sendingRecord = () => {
      return (
        <bk-dialog
          v-model={this.isShowSendRecord}
          title={this.$t('发送记录')}
          header-position='left'
          show-footer={false}
          width='960'
          z-index={2001}
        >
          <div>
            <div class='dialog-header-info-container'>
              <div class='label-container'>
                <div class='label'>{this.$t('发送频率')}:</div>
                <div class='value'>{this.getSendFrequencyText(this.detailInfo)}</div>
              </div>
              <div class='label-container'>
                <div
                  class='label'
                  style='margin-left: 55px;'
                >
                  {this.$t('有效时间范围')}:
                </div>
                <div class='value'>{this.formatTimeRange(this.detailInfo?.start_time, this.detailInfo?.end_time)}</div>
              </div>
            </div>

            <bk-table
              data={this.sendRecordTable.data}
              v-bkloading={{
                isLoading: this.sendRecordTable.isLoading
              }}
              style='margin-top: 16px;'
            >
              <bk-table-column
                label={this.$t('发送时间')}
                prop='send_time'
              ></bk-table-column>

              <bk-table-column
                label={this.$t('发送结果')}
                scopedSlots={{
                  default: ({ row }) => {
                    return (
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <i class={['dot-circle', row.send_status]} />
                        <span style='margin-left: 10px;'>{SendStatus[row.send_status]}</span>
                      </div>
                    );
                  }
                }}
              ></bk-table-column>

              <bk-table-column
                label={this.$t('操作')}
                scopedSlots={{
                  default: ({ row }) => {
                    return (
                      <bk-button
                        text
                        theme='primary'
                        onClick={e => {
                          this.currentTableRowOfSendingRecord = row;
                          this.sendRecordTable.data.forEach(item => {
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
                              zIndex: 2002
                            });
                            this.popoverInstance.show(100);
                          });
                        }}
                      >
                        {this.$t('重新发送')}
                      </bk-button>
                    );
                  }
                }}
              ></bk-table-column>
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
                <span class='success-text'>{this.currentTableRowOfSendingRecord?.send_results?.length}</span>
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

            {/* <div class='tag-content'>
              {this.currentTableRowOfSendingRecord?.tempSendResult?.map((item, index) => {
                if (['success'].includes(this.currentTableRowOfSendingRecord.send_status) && item.result) {
                  return (
                    <bk-tag
                      closable={
                        this.currentTableRowOfSendingRecord?.tempSendResult?.filter(target => target.result).length > 1
                      }
                      onClose={() => {
                        this.currentTableRowOfSendingRecord?.tempSendResult?.splice(index, 1);
                      }}
                    >
                      {item.id}
                    </bk-tag>
                  );
                }
                if (
                  ['partial_failed', 'failed'].includes(this.currentTableRowOfSendingRecord.send_status) &&
                  !item.result
                ) {
                  return (
                    <bk-tag
                      closable={
                        this.currentTableRowOfSendingRecord?.tempSendResult.filter(target => !target.result).length > 1
                      }
                      onClose={() => {
                        this.currentTableRowOfSendingRecord?.tempSendResult?.splice(index, 1);
                      }}
                    >
                      {item.id}
                    </bk-tag>
                  );
                }
              })}
            </div> */}

            <div style='margin-top: 10px;'>
              <bk-tag-input
                v-model={this.currentTableRowOfSendingRecord.selectedTag}
                list={this.currentTableRowOfSendingRecord.tempSendResult}
                placeholder={window.i18n.t('请选择')}
                has-delete-icon
                trigger='focus'
                display-key='id'
                save-key='id'
                search-key={['id']}
                // popoverOptions={{
                //   extCls: 'resend-tag-input'
                // }}
                // ext-cls='resend-tag-input'
              ></bk-tag-input>
            </div>

            <div class='footer-operation'>
              <bk-button
                theme='primary'
                style='min-width: 64px;'
                disabled={!this.currentTableRowOfSendingRecord?.selectedTag?.length}
                loading={this.isResending}
                onClick={this.handleResendSubscription}
              >
                {this.$t('确定')}
              </bk-button>

              <bk-button
                style='min-width: 64px;margin-left: 8px;'
                onClick={() => {
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
        <div class='header-container'>
          <div class='radio-container'>
            <div
              class={['radio', this.queryData.query_type === 'available' && 'selected']}
              onClick={() => (this.queryData.query_type = 'available')}
            >
              <i class='circle effecting'></i>
              {this.$t('生效中')}
            </div>
            <div
              class={['radio', this.queryData.query_type === 'cancelled' && 'selected']}
              onClick={() => (this.queryData.query_type = 'cancelled')}
            >
              <i class='circle canceled'></i>
              {this.$t('已取消')}
            </div>
            <div
              class={['radio', this.queryData.query_type === 'invalid' && 'selected']}
              onClick={() => (this.queryData.query_type = 'invalid')}
            >
              <i class='circle effected'></i>
              {this.$t('已失效')}
            </div>
          </div>

          <bk-input
            v-model={this.queryData.search_key}
            placeholder={this.$t('请输入搜索条件')}
            right-icon='bk-icon icon-search'
            style={{ width: '320px' }}
            onEnter={this.resetAndGetSubscriptionList}
          ></bk-input>
        </div>

        <bk-table
          data={this.tableData}
          v-bkloading={{
            isLoading: this.isTableLoading
          }}
          style={{ marginTop: '24px' }}
          {...{
            on: {
              'filter-change': filters => {
                const targetKey = Object.keys(filters)[0];
                let targetIndex = -1;
                const result = this.queryData.conditions.filter((item, index) => {
                  if (item.key === targetKey) targetIndex = index;
                  return item.key === targetKey;
                });
                if (result.length) {
                  if (filters[targetKey]?.length) {
                    this.queryData.conditions[targetIndex].value = filters[targetKey];
                  } else {
                    this.queryData.conditions.splice(targetIndex, 1);
                  }
                } else {
                  if (filters[targetKey]?.length) {
                    this.queryData.conditions.push({
                      key: targetKey,
                      value: filters[targetKey]
                    });
                  }
                }
                this.resetAndGetSubscriptionList();
              },
              // eslint-disable-next-line @typescript-eslint/no-unused-vars
              'sort-change': ({ column, prop, order }) => {
                if (prop) {
                  this.queryData.order = `${order === 'ascending' ? '' : '-'}${prop}`;
                } else {
                  this.queryData.order = '';
                }
                this.resetAndGetSubscriptionList();
              },
              'page-change': newPage => {
                this.queryData.page = newPage;
                this.fetchSubscriptionList();
              },
              'page-limit-change': limit => {
                this.queryData.page_size = limit;
                this.fetchSubscriptionList();
              }
            }
          }}
          pagination={{
            current: this.queryData.page,
            count: this.tableData.length,
            limit: this.queryData.page_size
          }}
        >
          <bk-table-column
            label={this.$t('邮件标题')}
            scopedSlots={{
              default: ({ row }) => {
                return (
                  <bk-button
                    text
                    title='primary'
                    onClick={() => {
                      this.isShowSideslider = true;
                      this.detailInfo = row;
                    }}
                  >
                    {row?.content_config?.title}
                  </bk-button>
                );
              }
            }}
          ></bk-table-column>

          <bk-table-column
            label={this.$t('订阅场景')}
            scopedSlots={{
              default: ({ row }) => {
                return <div>{Scenario[row.scenario]}</div>;
              }
            }}
          ></bk-table-column>

          {/* 没找到 */}
          <bk-table-column
            label={this.$t('来源')}
            scopedSlots={{
              default: ({ row }) => {
                return <div>{row.is_self_subscribed ? this.$t('主动订阅') : this.$t('他人订阅')}</div>;
              }
            }}
          ></bk-table-column>

          <bk-table-column
            label={this.$t('发送模式')}
            prop='send_mode'
            columnKey='send_mode'
            filters={[
              {
                text: window.i18n.t('周期发送'),
                value: 'periodic'
              },
              {
                text: window.i18n.t('仅发一次'),
                value: 'one_time'
              }
            ]}
            scopedSlots={{
              default: ({ row }) => {
                return <div>{SendMode[row.send_mode]}</div>;
              }
            }}
          ></bk-table-column>

          {/* 没找到 */}
          <bk-table-column
            label={this.$t('发送时间')}
            scopedSlots={{
              default: ({ row }) => {
                return <div>{this.getSendFrequencyText(row)}</div>;
              }
            }}
          ></bk-table-column>

          <bk-table-column
            label={this.$t('最近一次发送时间')}
            sortable='custom'
            prop='last_send_time'
            scopedSlots={{
              default: ({ row }) => {
                return <div>{row.last_send_time || this.$t('未发送')}</div>;
              }
            }}
          ></bk-table-column>

          <bk-table-column
            label={this.$t('发送状态')}
            prop='send_status'
            columnKey='send_status'
            filters={[
              {
                text: `${window.i18n.t('发送成功')}`,
                value: 'success'
              },
              {
                text: `${window.i18n.t('发送部分失败')}`,
                value: 'partial_failed'
              },
              {
                text: `${window.i18n.t('发送失败')}`,
                value: 'failed'
              }
            ]}
            scopedSlots={{
              default: ({ row }) => {
                return row.send_status !== 'no_status' ? (
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <i
                      class={['dot-circle', row.send_status]}
                      style={{ marginRight: '10px' }}
                    ></i>
                    {SendStatus[row.send_status]}
                  </div>
                ) : (
                  <div>{this.$t('未发送')}</div>
                );
              }
            }}
          ></bk-table-column>

          <bk-table-column
            label={this.$t('操作')}
            scopedSlots={{
              default: ({ row }) => {
                return (
                  <div>
                    <bk-button
                      text
                      theme='primary'
                      onClick={() => {
                        this.isShowSendRecord = true;
                        this.detailInfo = row;
                        this.getSendingRecordList();
                      }}
                    >
                      {this.$t('发送记录')}
                    </bk-button>

                    {['available', 'invalid'].includes(this.queryData.query_type) && (
                      <bk-button
                        text
                        theme='primary'
                        style={{ marginLeft: '10px' }}
                        onClick={() => this.handleCancelSubscription(row)}
                      >
                        {this.$t('取消订阅')}
                      </bk-button>
                    )}

                    {this.queryData.query_type === 'cancelled' && (
                      <bk-button
                        text
                        theme='primary'
                        style={{ marginLeft: '10px' }}
                        onClick={() => this.handleResubscribeReport(row)}
                      >
                        {this.$t('重新订阅')}
                      </bk-button>
                    )}
                  </div>
                );
              }
            }}
          ></bk-table-column>
        </bk-table>

        <bk-sideslider
          is-show={this.isShowSideslider}
          width='640'
          ext-cls='my-subscription-slider'
          transfer
          before-close={() => {
            this.isShowSideslider = false;
          }}
        >
          <div
            slot='header'
            style={{ height: '100%' }}
          >
            <div class='title-container'>
              <div>
                <span class='title'>{this.$t('订阅详情')}</span>
                <span class='sub-title'>-&nbsp;{this.detailInfo?.name}</span>
                <i
                  class='icon-monitor icon-copy-link'
                  style={{
                    color: '#3A84FF',
                    fontSize: '14px',
                    marginLeft: '10px',
                    cursor: 'pointer'
                  }}
                  onClick={this.goToTargetScene}
                />
              </div>

              <div>
                {['available', 'invalid'].includes(this.queryData.query_type) && (
                  <bk-button
                    theme='primary'
                    outline
                    onClick={() => this.handleCancelSubscription(this.detailInfo)}
                  >
                    {this.$t('取消订阅')}
                  </bk-button>
                )}

                {this.queryData.query_type === 'cancelled' && (
                  <bk-button
                    theme='primary'
                    outline
                    onClick={() => this.handleResubscribeReport(this.detailInfo)}
                  >
                    {this.$t('重新订阅')}
                  </bk-button>
                )}

                {/* 暂不需要 */}
                {/* <bk-button style={{ marginLeft: '8px' }}>{this.$t('编辑')}</bk-button> */}
              </div>
            </div>
          </div>

          <div slot='content'>
            <SubscriptionDetail
              detailInfo={this.detailInfo}
              queryType={this.queryData.query_type}
            ></SubscriptionDetail>
          </div>
        </bk-sideslider>

        {sendingRecord()}
        {popoverTmpl()}
      </div>
    );
  }
}
export default ofType().convert(MySubscription);
