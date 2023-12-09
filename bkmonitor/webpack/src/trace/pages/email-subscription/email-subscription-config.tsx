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
import { defineComponent, onMounted, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import {
  cloneSubscription,
  createOrUpdateSubscription,
  deleteSubscription,
  getSendRecords,
  getSubscription,
  getSubscriptionList,
  sendSubscription
} from '@api/modules/email_subscription';
import { deepClone } from '@common/utils';
import { Button, Dialog, Dropdown, Input, Message, Popover, Radio, Sideslider, Switcher, Table, Tag } from 'bkui-vue';
import dayjs from 'dayjs';

import CreateSubscriptionForm from './components/create-subscription-form';
import SubscriptionDetail from './components/subscription-detail';

import './email-subscription-config.scss';

enum SendMode {
  periodic = window.i18n.t('周期发送'),
  'only-time' = window.i18n.t('仅发一次')
}

enum SendStatus {
  failed = window.i18n.t('发送失败'),
  partial_failed = window.i18n.t('发送部分失败'),
  success = window.i18n.t('发送成功')
}

enum ChannelName {
  email = window.i18n.t('外部邮件'),
  wxbot = window.i18n.t('企业微信群'),
  user = window.i18n.t('内部用户')
}

export enum Scenario {
  clustering = window.i18n.t('日志聚类'),
  dashboard = window.i18n.t('仪表盘'),
  scene = window.i18n.t('观测场景')
}

export enum YearOnYearHour {
  0 = window.i18n.t('不比对'),
  1 = window.i18n.t('1小时前'),
  2 = window.i18n.t('2小时前'),
  3 = window.i18n.t('3小时前'),
  6 = window.i18n.t('6小时前'),
  12 = window.i18n.t('12小时前'),
  24 = window.i18n.t('24小时前')
}
export default defineComponent({
  name: 'EmailSubscriptionConfig',
  setup() {
    const { t } = useI18n();
    const router = useRouter();
    const queryData = reactive({
      create_type: 'manager',
      query_type: 'all',
      search_key: '',
      page: 1,
      page_size: 20,
      order: '',
      conditions: []
    });
    function handleGoToCreateConfigPage() {
      router.push({
        name: 'create-subscription'
      });
      console.log('handleGoToCreateConfigPage');
    }
    function handleInputKeydown() {
      resetAndGetSubscriptionList();
    }
    function handleClone() {
      cloneDialog.loading = true;
      cloneSubscription({
        subscription_id: cloneDialog.subscription_id
      })
        .then(() => {
          fetchSubscriptionList();
        })
        .catch(console.log)
        .finally(() => {
          cloneDialog.loading = false;
          cloneDialog.isShow = false;
        });
    }
    function handleDeleteRow() {
      deleteDialog.loading = true;
      deleteSubscription({
        subscription_id: deleteDialog.subscription_id
      })
        .then(() => {
          fetchSubscriptionList();
        })
        .catch(console.log)
        .finally(() => {
          deleteDialog.loading = false;
          deleteDialog.isShow = false;
        });
    }
    const toggleMap = reactive({});
    const isShowSendRecord = ref(false);
    const table = reactive({
      data: [],
      columns: {
        fields: [
          {
            label: `${window.i18n.t('订阅名称')}`,
            render: ({ data }) => {
              return (
                <Button
                  theme='primary'
                  text
                  onClick={() => {
                    subscriptionDetail.value = data;
                    isShowSubscriptionDetailSideslider.value = true;
                    // getSubscriptionDetail(data.id);
                  }}
                >
                  {window.i18n.t(`${data.name}`)}
                </Button>
              );
            }
          },
          {
            label: `${window.i18n.t('通知渠道')}`,
            field: 'channels',
            render: ({ data }) => {
              return <div>{data.channels.map(item => ChannelName[item.channel_name]).toString()}</div>;
            }
          },
          {
            label: `${window.i18n.t('订阅场景')}`,
            field: 'scenario',
            render: ({ data }) => {
              return <div>{Scenario[data.scenario]}</div>;
            }
          },
          {
            label: `${window.i18n.t('发送模式')}`,
            field: 'send_mode',
            render: ({ data }) => {
              return <div>{SendMode[data.send_mode]}</div>;
            },
            filter: {
              list: [
                {
                  text: window.i18n.t('周期发送'),
                  value: 'periodic'
                },
                {
                  text: window.i18n.t('仅发一次'),
                  value: 'only-time'
                }
              ],
              filterFn: () => true
            }
          },
          {
            label: `${window.i18n.t('发送时间')}`,
            render: ({ data }) => {
              // const hourTextMap = {
              //   0.5: window.i18n.tc('每个小时整点,半点发送'),
              //   1: window.i18n.tc('每个小时整点发送'),
              //   2: window.i18n.tc('从0点开始,每隔2小时整点发送'),
              //   6: window.i18n.tc('从0点开始,每隔6小时整点发送'),
              //   12: window.i18n.tc('每天9:00,21:00发送')
              // };
              // const weekMap = [
              //   window.i18n.t('周一'),
              //   window.i18n.t('周二'),
              //   window.i18n.t('周三'),
              //   window.i18n.t('周四'),
              //   window.i18n.t('周五'),
              //   window.i18n.t('周六'),
              //   window.i18n.t('周日')
              // ];
              // let str = '';
              // switch (data.frequency.type) {
              //   case 3: {
              //     const weekStrArr = data.frequency.week_list.map(item => weekMap[item - 1]);
              //     const weekStr = weekStrArr.join(', ');
              //     str = `${weekStr} ${data.frequency.run_time}`;
              //     break;
              //   }
              //   case 4: {
              //     const dayArr = data.frequency.day_list.map(item => `${item}号`);
              //     const dayStr = dayArr.join(', ');
              //     str = `${dayStr} ${data.frequency.run_time}`;
              //     break;
              //   }
              //   case 5: {
              //     str = hourTextMap[data.frequency.hour];
              //     break;
              //   }
              //   default:
              //     str = data.frequency.runTime;
              //     break;
              // }
              return <div>{getSendFrequencyText(data)}</div>;
            }
          },
          {
            label: `${window.i18n.t('最近一次发送时间')}`,
            field: 'last_send_time',
            sort: {
              value: 'asc'
            },
            render: ({ data }) => {
              return <div>{data.last_send_time || window.i18n.t('未发送')}</div>;
            }
          },
          {
            label: `${window.i18n.t('发送状态')}`,
            field: 'send_status',
            render: ({ data }) => {
              return data.send_status !== 'no_status' ? (
                <div>
                  <i
                    class={['icon-circle', data.send_status]}
                    style={{ marginRight: '10px' }}
                  ></i>
                  {SendStatus[data.send_status]}
                </div>
              ) : (
                <div>{window.i18n.t('未发送')}</div>
              );
            },
            filter: {
              list: [
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
              ],
              filterFn: () => true
            }
          },
          {
            label: `${window.i18n.t('创建人')}`,
            field: 'create_user'
          },
          {
            label: `${window.i18n.t('启/停')}`,
            render: ({ data, index }) => {
              return (
                <div>
                  <Switcher
                    v-model={data.is_enabled}
                    theme='primary'
                    onChange={() => handleSetEnable(index)}
                  ></Switcher>
                </div>
              );
            }
          },
          {
            label: `${window.i18n.t('操作')}`,
            render: row => {
              return (
                <div>
                  <Button
                    theme='primary'
                    text
                    onClick={() => {
                      isShowSendRecord.value = true;
                      subscriptionDetail.value = row.data;
                      getSendingRecordList();
                    }}
                  >
                    {window.i18n.t('发送记录')}
                  </Button>

                  <Button
                    theme='primary'
                    text
                    style='margin-left: 10px;'
                    onClick={() => {
                      subscriptionDetail.value = row.data;
                      isShowEditSideslider.value = true;
                    }}
                  >
                    {window.i18n.t('编辑')}
                  </Button>

                  {/* 实现方式有问题，看看有没有其它的实现方式 */}
                  <Popover
                    trigger='click'
                    theme='light'
                    isShow={toggleMap[row.index] || false}
                    placement='bottom-start'
                    extCls='email-subscription-popover'
                    v-slots={{
                      content: () => (
                        <div>
                          <div
                            class='popover-item'
                            onClick={() => {
                              toggleMap[row.index] = false;
                              cloneDialog.subscription_id = row.data.id;
                              cloneDialog.isShow = true;
                            }}
                          >
                            {window.i18n.t('克隆')}
                          </div>
                          <div
                            class='popover-item'
                            onClick={() => {
                              toggleMap[row.index] = false;
                              deleteDialog.subscription_id = row.data.id;
                              deleteDialog.isShow = true;
                            }}
                          >
                            {window.i18n.t('删除')}
                          </div>
                        </div>
                      )
                    }}
                  >
                    <i
                      class='more-btn icon-monitor icon-mc-more'
                      style='margin-left: 10px;'
                      onClick={() => (toggleMap[row.index] = true)}
                    />
                  </Popover>
                </div>
              );
            }
          }
        ],
        limit: 0
      }
    });

    const toggleMapForSendRecord = reactive({});
    const sendRecordTable = reactive({
      data: [],
      columns: {
        fields: [
          {
            label: `${window.i18n.t('发送时间')}`,
            field: 'send_time'
          },
          {
            label: `${window.i18n.t('类型')}`,
            render: ({ data }) => {
              return ChannelName[data.channel];
            }
          },
          {
            label: `${window.i18n.t('接收人')}`,
            render: ({ data }) => {
              return (
                // 显示的内容量会很多，这里样式调整一下。
                <div style='white-space: normal;line-height: 16px;padding: 14px 0;'>
                  {data.send_result.map(item => item.id).toString()}
                </div>
              );
            }
          },
          {
            label: `${window.i18n.t('发送结果')}`,
            render: ({ data }) => {
              return (
                <div>
                  <i class={['icon-circle', data.send_status]} />
                  <span style='margin-left: 10px;'>{SendStatus[data.send_status]}</span>
                </div>
              );
            }
          },
          {
            label: `${window.i18n.t('操作')}`,
            render: ({ data, index }) => {
              return (
                <Popover
                  trigger='click'
                  isShow={toggleMapForSendRecord[index] || false}
                  theme='light'
                  placement='bottom-start'
                  extCls='email-subscription-popover'
                  v-slots={{
                    content: () => {
                      let headerText = '';
                      let headerConfirmText = '';
                      if (['success'].includes(data.send_status)) {
                        const headerTextMap = {
                          user: '已成功发送 {0} 个内部用户',
                          email: '已成功发送 {0} 个外部邮件',
                          wxbot: '已成功发送 {0} 个企业微信机器人'
                        };
                        headerText = headerTextMap[data.channel];
                        const headerConfirmTextMap = {
                          user: '确定重新发送给以下用户',
                          email: '确定重新发送给以下邮件',
                          wxbot: '确定重新发送给以下企业微信机器人'
                        };
                        headerConfirmText = headerConfirmTextMap[data.channel];
                      } else if (['partial_failed', 'failed'].includes(data.send_status)) {
                        const headerTextMap = {
                          user: '已成功发送 {0} 个，失败 {1} 个内部用户',
                          email: '已成功发送 {0} 个，失败 {1} 个外部邮件',
                          wxbot: '已成功发送 {0} 个，失败 {1} 个企业微信机器人'
                        };
                        headerText = headerTextMap[data.channel];
                        const headerConfirmTextMap = {
                          user: '确定重新发送给以下失败用户',
                          email: '确定重新发送给以下失败邮件',
                          wxbot: '确定重新发送给以下失败企业微信机器人'
                        };
                        headerConfirmText = headerConfirmTextMap[data.channel];
                      }

                      return (
                        <div class='resend-popover-container'>
                          <div class='success-header-text'>
                            {/* 根据 data.channel 如果为 success 就选这些文本
                            1. 已成功发送 {0} 个内部用户
                            2. 已成功发送 {0} 个外部邮件
                            3. 已成功发送 {0} 个企业微信群

                            如果为 partial_failed, failed 就选这些文本
                            1. 已成功发送 {0} 个，失败 {1} 个企业微信群
                            2. 已成功发送 {0} 个，失败 {1} 个外部邮件
                            3. 已成功发送 {0} 个，失败 {1} 个内部用户
                          */}
                            <i18n-t keypath={headerText}>
                              <span class='success-text'>{data.send_result.filter(item => item.result).length}</span>
                              {['partial_failed', 'failed'].includes(data.send_status) && (
                                <span class='fail-text'>{data.send_result.filter(item => !item.result).length}</span>
                              )}
                            </i18n-t>
                          </div>

                          <div class='header-confirm-text'>
                            {/* 根据 data.channel 如果为 success 就选这些文本
                              1. 确定重新发送给以下用户
                              2. 确定重新发送给以下邮件
                              3. 确定重新发送给以下企微群

                              如果为 partial_failed, success 就选这些文本
                              1. 确定重新发送给以下失败企微群
                              2. 确定重新发送给以下失败邮件
                              3. 确定重新发送给以下失败用户
                            */}
                            {window.i18n.t(headerConfirmText)}
                          </div>

                          <div class='tag-content'>
                            {/* <Tag closable onClose={() => {}}></Tag> */}
                            {data.tempSendResult.map((item, index) => {
                              if (['success'].includes(data.send_status) && item.result) {
                                return (
                                  <Tag
                                    closable
                                    onClose={() => {
                                      data.tempSendResult.splice(index, 1);
                                    }}
                                  >
                                    {item.id}
                                  </Tag>
                                );
                              }
                              if (['partial_failed', 'failed'].includes(data.send_status) && !item.result) {
                                return (
                                  <Tag
                                    closable
                                    onClose={() => {
                                      data.tempSendResult.splice(index, 1);
                                    }}
                                  >
                                    {item.id}
                                  </Tag>
                                );
                              }
                              return null;
                            })}
                          </div>

                          <div class='footer-operation'>
                            <Button
                              theme='primary'
                              style='min-width: 64px;'
                              loading={isResending.value}
                              onClick={() => {
                                console.log(data);
                                handleResendSubscription(data);
                              }}
                            >
                              {window.i18n.t('确定')}
                            </Button>

                            <Button
                              style='min-width: 64px;margin-left: 8px;'
                              onClick={() => {
                                toggleMapForSendRecord[index] = false;
                              }}
                            >
                              {window.i18n.t('取消')}
                            </Button>
                          </div>
                        </div>
                      );
                    }
                  }}
                >
                  <Button
                    text
                    theme='primary'
                    onClick={() => {
                      toggleMapForSendRecord[index] = true;
                      // 每次重新发送都会重置一次 tag 列表。不知道是否实用。
                      sendRecordTable.data.forEach(item => {
                        // eslint-disable-next-line no-param-reassign
                        item.tempSendResult = deepClone(item.send_result);
                      });
                    }}
                  >
                    {window.i18n.t('重新发送')}
                  </Button>
                </Popover>
              );
            }
          }
        ]
      }
    });

    const isShowSubscriptionDetailSideslider = ref(false);
    const isShowEditSideslider = ref(false);

    const isSending = ref(false);
    function testSending(to) {
      if (to === 'self') {
        isSending.value = true;
        sendSubscription({
          subscription_id: subscriptionDetail.value?.id,
          channels: [
            {
              is_enabled: true,
              subscribers: [
                {
                  id: window.username,
                  type: 'user',
                  is_enabled: true
                }
              ],
              channel_name: 'user'
            }
          ]
        })
          .then(() => {
            Message({
              theme: 'success',
              message: window.i18n.t('发送成功')
            });
          })
          .catch(console.log)
          .finally(() => {
            isSending.value = false;
          });
      }
      if (to === 'all') {
        console.log(refOfCreateSubscriptionForm.value);
        sendSubscription({
          subscription_id: subscriptionDetail.value?.id,
          channels: refOfCreateSubscriptionForm.value?.formData?.channels || []
        })
          .then(() => {
            Message({
              theme: 'success',
              message: window.i18n.t('发送成功')
            });
          })
          .catch(console.log)
          .finally(() => {
            isSending.value = false;
          });
      }
    }

    const refOfCreateSubscriptionForm = ref();

    function resetAndGetSubscriptionList() {
      queryData.page = 1;
      queryData.page_size = 20;
      fetchSubscriptionList();
    }
    function fetchSubscriptionList() {
      getSubscriptionList(queryData)
        .then(response => {
          console.log(response);
          table.data = response;
        })
        .catch(console.log);
    }

    const subscriptionDetail = ref({});
    function getSubscriptionDetail(subscription_id) {
      getSubscription({
        subscription_id
      })
        .then(response => {
          console.log(response);
          subscriptionDetail.value = response;
        })
        .catch(console.log);
    }

    function handleSetEnable(index) {
      const data = table.data[index];
      createOrUpdateSubscription(data)
        .then(() => {})
        .catch(() => {
          // eslint-disable-next-line no-param-reassign
          data.is_enabled = !data.is_enabled;
        });
    }

    const cloneDialog = reactive({
      isShow: false,
      loading: false,
      subscription_id: 0
    });

    const deleteDialog = reactive({
      isShow: false,
      loading: false,
      subscription_id: 0
    });

    function getSendingRecordList() {
      getSendRecords({
        subscription_id: subscriptionDetail.value.id
      })
        .then(response => {
          console.log(response);
          sendRecordTable.data = response;
        })
        .catch(console.log);
    }

    function getSendFrequencyText(data) {
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
          str = data.frequency.runTime;
          break;
      }
      return str;
    }

    function formatTimeRange(s, e) {
      if (!s) return '';
      const startTime = dayjs.unix(s).format('YYYY-MM-DD HH:mm:ss');
      const endTime = dayjs.unix(e).format('YYYY-MM-DD HH:mm:ss');
      return `${startTime} ~ ${endTime}`;
    }

    const isResending = ref(false);
    function handleResendSubscription(data) {
      isResending.value = true;
      const channels = [
        {
          is_enabled: true,
          channel_name: data.channel,
          subscribers: data.tempSendResult
            .filter(item => {
              if (['success'].includes(data.send_status) && item.result) {
                return item;
              }
              if (['partial_failed', 'failed'].includes(data.send_status) && !item.result) {
                return item;
              }
            })
            .map(item => {
              const o = {
                id: item.id,
                is_enabled: true
              };
              if (item.type) {
                o.type = item.type;
              }
              return o;
            })
        }
      ];
      sendSubscription({
        subscription_id: data.subscription_id,
        channels
      })
        .then(() => {
          Message({
            theme: 'success',
            message: window.i18n.t('发送成功')
          });
        })
        .catch(console.log)
        .finally(() => {
          isResending.value = false;
        });
    }

    onMounted(() => {
      fetchSubscriptionList();
    });
    return {
      t,
      queryData,
      handleInputKeydown,
      handleGoToCreateConfigPage,
      table,
      isShowSendRecord,
      sendRecordTable,
      isShowSubscriptionDetailSideslider,
      isShowEditSideslider,
      testSending,
      refOfCreateSubscriptionForm,
      resetAndGetSubscriptionList,
      fetchSubscriptionList,
      subscriptionDetail,
      cloneDialog,
      handleClone,
      deleteDialog,
      handleDeleteRow,
      isSending,
      getSendingRecordList,
      getSendFrequencyText,
      formatTimeRange
    };
  },
  render() {
    const headerTmpl = () => {
      return (
        <div class='header-container'>
          <div class='left-container'>
            <Button
              theme='primary'
              onClick={this.handleGoToCreateConfigPage}
            >
              <i class='icon-monitor icon-mc-add'></i>
              <span>{this.t('新建')}</span>
            </Button>
            <Radio.Group
              v-model={this.queryData.create_type}
              style='margin-left: 16px;'
              onChange={() => {
                this.resetAndGetSubscriptionList();
              }}
            >
              <Radio.Button label='manager'>{this.t('管理员创建的')}</Radio.Button>
              <Radio.Button label='user'>{this.t('用户订阅的')}</Radio.Button>
            </Radio.Group>
          </div>
          <div class='right-container'>
            <Radio.Group
              v-model={this.queryData.query_type}
              type='capsule'
              onChange={() => {
                this.resetAndGetSubscriptionList();
              }}
            >
              <Radio.Button label='all'>{this.t('全部')}</Radio.Button>
              <Radio.Button label='available'>
                <i
                  class='icon-circle success'
                  style='margin-right: 4px;'
                />
                <span>{this.t('生效中')}</span>
              </Radio.Button>
              <Radio.Button label='invalid'>
                <i
                  class='icon-circle gray'
                  style='margin-right: 4px;'
                />
                <span>{this.t('已失效')}</span>
              </Radio.Button>
            </Radio.Group>
            <Input
              v-model={this.queryData.search_key}
              clearable
              class='search-input'
              onEnter={this.handleInputKeydown}
              placeholder={window.i18n.t('请输入搜索条件')}
              v-slots={{
                suffix: () => (
                  <div class='suffix-icon'>
                    <i class='icon-monitor icon-mc-search'></i>
                  </div>
                )
              }}
            />
          </div>
        </div>
      );
    };
    return (
      <div class='email-subscription-config-container'>
        {/* 头部搜索 部分 */}
        {headerTmpl()}
        <Table
          data={this.table.data}
          columns={this.table.columns.fields}
          border={['outer']}
          style='margin-top: 16px;background-color: white;'
          pagination={{
            current: this.queryData.page,
            limit: this.queryData.page_size,
            count: this.table.data.length,
            onChange: pageNum => {
              console.log(pageNum);
              this.queryData.page = pageNum;
            },
            onLimitChange: limit => {
              console.log(limit);
              this.queryData.page_size = limit;
            }
          }}
          onColumnFilter={({ checked, column, index }) => {
            console.log({ checked, column, index });
            let currentIndex = -1;
            const result = this.queryData.conditions.filter((item, index) => {
              currentIndex = index;
              return item.key === column.field;
            });
            if (result.length) {
              this.queryData.conditions[currentIndex].value = checked;
            } else {
              this.queryData.conditions.push({
                key: column.field,
                value: checked
              });
            }
            this.fetchSubscriptionList();
          }}
          onColumnSort={({ column, index, type }) => {
            console.log({ column, index, type });
            if (type !== 'null') {
              this.queryData.order = `${type === 'asc' ? '' : '-'}${column.field}`;
            } else {
              this.queryData.order = '';
            }
            this.fetchSubscriptionList();
          }}
        ></Table>
        <Dialog
          is-show={this.isShowSendRecord}
          title={this.t('发送记录')}
          dialog-type='show'
          width='960'
          onClosed={() => (this.isShowSendRecord = false)}
        >
          <div>
            <div class='dialog-header-info-container'>
              <div class='label-container'>
                <div class='label'>{this.t('发送频率')}:</div>
                <div class='value'>{this.getSendFrequencyText(this.subscriptionDetail)}</div>
              </div>
              <div class='label-container'>
                <div
                  class='label'
                  style='margin-left: 55px;'
                >
                  {this.t('有效时间范围')}:
                </div>
                <div class='value'>
                  {this.formatTimeRange(this.subscriptionDetail?.start_time, this.subscriptionDetail?.end_time)}
                </div>
              </div>
            </div>

            <Table
              data={this.sendRecordTable.data}
              columns={this.sendRecordTable.columns.fields}
              style='margin-top: 16px;'
            />
          </div>
        </Dialog>

        <Sideslider
          v-model={[this.isShowSubscriptionDetailSideslider, 'isShow']}
          // 根据显示内容要动态调整。
          width={640}
          quick-close={false}
          transfer
          v-slots={{
            header: () => {
              return (
                <div class='slider-header-container'>
                  <div class='title-container'>
                    <span class='title'>{window.i18n.t('订阅详情')}</span>
                    <span class='sub-title'>-&nbsp;{this.subscriptionDetail?.name}</span>
                  </div>

                  <div class='operation-container'>
                    <Button style='margin-right: 8px;'>{window.i18n.t('发送给自己')}</Button>
                    <Button
                      outline
                      theme='primary'
                      style='margin-right: 8px;'
                      onClick={() => {
                        this.isShowSubscriptionDetailSideslider = false;
                        this.isShowEditSideslider = true;
                      }}
                    >
                      {window.i18n.t('编辑')}
                    </Button>

                    <Popover
                      placement='bottom-end'
                      v-slots={{
                        content: () => {
                          return (
                            <div>
                              <div>{`${window.i18n.t('更新人')}: ${this.subscriptionDetail?.update_user}`}</div>
                              <div>{`${window.i18n.t('更新时间')}: ${this.subscriptionDetail?.update_time}`}</div>
                              <div>{`${window.i18n.t('创建人')}: ${this.subscriptionDetail?.create_user}`}</div>
                              <div>{`${window.i18n.t('创建时间')}: ${this.subscriptionDetail?.create_time}`}</div>
                            </div>
                          );
                        }
                      }}
                    >
                      <Button style='margin-right: 24px;'>
                        <i class='icon-monitor icon-lishi'></i>
                      </Button>
                    </Popover>
                  </div>
                </div>
              );
            },
            default: () => {
              return (
                <div>
                  <SubscriptionDetail
                    detailInfo={this.subscriptionDetail}
                    style='padding: 20px 40px;'
                  ></SubscriptionDetail>
                </div>
              );
            }
          }}
        ></Sideslider>

        <Sideslider
          v-model={[this.isShowEditSideslider, 'isShow']}
          title={'编辑'}
          width={960}
          quick-close={false}
          ext-cls='edit-subscription-sideslider-container'
          transfer
        >
          <div>
            <div class='create-subscription-container'>
              <CreateSubscriptionForm
                ref='refOfCreateSubscriptionForm'
                mode='quick'
                detailInfo={this.subscriptionDetail}
              ></CreateSubscriptionForm>
            </div>

            <div class='footer-bar'>
              <Button
                theme='primary'
                style={{ width: '88px', marginRight: '8px' }}
                onClick={() => {
                  this.refOfCreateSubscriptionForm
                    .validateAllForms()
                    .then(response => {
                      console.log(response);
                      createOrUpdateSubscription(response)
                        .then(() => {
                          console.log('success');
                        })
                        .catch(console.log);
                    })
                    .catch(console.log());
                }}
              >
                {window.i18n.t('保存')}
              </Button>
              <Dropdown
                trigger='click'
                placement='top-start'
                v-slots={{
                  content: () => {
                    return (
                      <Dropdown.DropdownMenu>
                        <Dropdown.DropdownItem onClick={() => this.testSending('self')}>
                          {window.i18n.t('给自己')}
                        </Dropdown.DropdownItem>
                        <Dropdown.DropdownItem onClick={() => this.testSending('all')}>
                          {window.i18n.t('给全员')}
                        </Dropdown.DropdownItem>
                      </Dropdown.DropdownMenu>
                    );
                  }
                }}
              >
                <Button
                  theme='primary'
                  outline
                  loading={this.isSending}
                  style={{ width: '88px', marginRight: '8px' }}
                >
                  {window.i18n.t('测试发送')}
                </Button>
              </Dropdown>
              <Button
                style={{ width: '88px' }}
                onClick={() => {
                  this.isShowEditSideslider = false;
                }}
              >
                {window.i18n.t('取消')}
              </Button>
            </div>
          </div>
        </Sideslider>

        {/* 克隆确认 */}
        <Dialog
          isShow={this.cloneDialog.isShow}
          isLoading={this.cloneDialog.loading}
          title={window.i18n.t('提示')}
          confirmText={window.i18n.t('确认')}
          cancelText={window.i18n.t('取消')}
          onClosed={() => {
            this.cloneDialog.isShow = false;
          }}
          onConfirm={this.handleClone}
        >
          <div>{window.i18n.t('是否克隆?')}</div>
        </Dialog>

        {/* 删除确认 */}
        <Dialog
          isShow={this.deleteDialog.isShow}
          isLoading={this.deleteDialog.loading}
          title={window.i18n.t('提示')}
          confirmText={window.i18n.t('确认')}
          cancelText={window.i18n.t('取消')}
          onClosed={() => {
            this.deleteDialog.isShow = false;
          }}
          onConfirm={this.handleDeleteRow}
        >
          <div>{window.i18n.t('是否删除?')}</div>
        </Dialog>
      </div>
    );
  }
});
