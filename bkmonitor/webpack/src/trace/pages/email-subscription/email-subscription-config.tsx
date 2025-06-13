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
import { computed, defineComponent, nextTick, onMounted, reactive, watch } from 'vue';
import { shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { PrimaryTable, type SortInfo, type TableProps, type FilterValue } from '@blueking/tdesign-ui';
import {
  Button,
  Dialog,
  Dropdown,
  InfoBox,
  Input,
  Loading,
  Message,
  overflowTitle,
  Popover,
  Radio,
  Sideslider,
  Switcher,
  TagInput,
} from 'bkui-vue';
import dayjs from 'dayjs';
import {
  createOrUpdateReport,
  deleteReport,
  getApplyRecords,
  getReport,
  getReportList,
  getSendRecords,
  sendReport,
} from 'monitor-api/modules/new_report';
import { LANGUAGE_COOKIE_KEY, deepClone } from 'monitor-common/utils';
import { docCookies } from 'monitor-common/utils/utils';

import EmptyStatus from '../../components/empty-status/empty-status';
import NavBar from '../../components/nav-bar/nav-bar';
import CreateSubscriptionForm from './components/create-subscription-form';
import SubscriptionDetail from './components/subscription-detail';
import TestSendSuccessDialog from './components/test-send-success-dialog';
import CreateSubscription from './create-subscription';
import { ChannelName, Scenario, SendMode, SendStatus } from './mapping';
import { FrequencyType, type ITable, type TestSendingTarget } from './types';
import { getDefaultReportData, getSendFrequencyText } from './utils';

import './email-subscription-config.scss';

type TooltipsToggleMapping = {
  [key: number]: boolean;
};

// 表格字段 显隐设置的配置需要持久化到本地。
const keyOfTableSettingInLocalStorage = 'report_list_table_settings';
const keyOfTableForSelfSettingInLocalStorage = 'report_list_table_for_self_settings';

const currentLang = docCookies.getItem(LANGUAGE_COOKIE_KEY);

/** 判断当场是否为克隆场景。若是则把表单 id 的 key 去掉，让后端生成新数据。 */
let isOnCloneMode = false;

export default defineComponent({
  name: 'EmailSubscriptionConfig',
  directives: {
    overflowTitle,
  },
  setup() {
    const { t } = useI18n();
    const router = useRouter();
    const route = useRoute();
    // 查询订阅列表 相关参数 开始
    const createType = shallowRef<'manager' | 'self' | 'user'>('manager');
    const queryType = shallowRef<'all' | 'available' | 'invalid'>('all');
    const queryTypeForSelf = shallowRef<'all' | 'FAILED' | 'RUNNING' | 'SUCCESS'>('all');
    const searchKey = shallowRef('');
    const page = shallowRef(1);
    const pageSize = shallowRef(20);
    const order = shallowRef('');
    const conditions = shallowRef([]);
    // 查询订阅列表 相关参数 结束
    const totalReportSize = shallowRef(0);
    // 控制 订阅列表 中多个 tooltips 的显隐
    const toggleMap = reactive<TooltipsToggleMapping>({});
    // 显示 发送记录 的 dialog
    const isShowSendRecord = shallowRef(false);
    const isShowCreateSubscription = shallowRef(false);
    const navList = shallowRef([
      {
        id: 'report',
        name: t('订阅配置'),
      },
    ]);
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const ApplyStatus = {
      RUNNING: t('未审批'),
      FAILED: t('未通过'),
      SUCCESS: t('已通过'),
    };
    const isSelfMode = shallowRef(false);
    const isTableLoading = shallowRef(false);
    const table = reactive<ITable>({
      data: [],
      columns: [
        {
          label: `${t('订阅名称')}`,
          field: 'name',
        },
        {
          label: `${t('通知渠道')}`,
          field: 'channels',
        },
        {
          label: `${t('订阅场景')}`,
          field: 'scenario',
        },
        {
          label: `${t('发送模式')}`,
          field: 'send_mode',
          filter: [
            {
              label: t('周期发送'),
              value: 'periodic',
            },
            {
              label: t('仅发一次'),
              value: 'one_time',
            },
          ],
        },
        {
          label: `${t('发送时间')}`,
          field: 'send_time',
        },
        {
          label: `${t('最近一次发送时间')}`,
          field: 'last_send_time',
          sortable: true,
        },
        {
          label: `${t('发送状态')}`,
          field: 'send_status',
          filter: [
            {
              label: `${t('发送成功')}`,
              value: 'success',
            },
            {
              label: `${t('未发送')}`,
              value: 'no_status',
            },
            // {
            //   label: `${t('发送部分失败')}`,
            //   value: 'partial_failed'
            // },
            {
              label: `${t('发送失败')}`,
              value: 'failed',
            },
          ],
        },
        {
          label: `${t('创建人')}`,
          field: 'create_user',
        },
        {
          label: `${t('启/停')}`,
          field: 'is_enabled',
        },
        {
          label: `${t('创建时间')}`,
          field: 'create_time',
          sortable: true,
        },
        {
          label: `${t('操作')}`,
          field: 'action',
          width: `${(window.i18n.locale as unknown as string) === 'zhCN' ? '150px' : '170px'}`,
        },
      ],
      settings: {
        fields: [],
        checked: [],
        size: 'small',
      },
    });
    const emptyType = shallowRef('empty');
    // 根据 table 字段生成对应的字段显隐 setting
    table.settings.fields = table.columns.map(item => {
      return {
        label: item.label,
        field: item.field,
      };
    });
    table.settings.checked = table.columns
      // 这里先不展示 创建时间 ，让用户自己手动开。
      .filter(item => !['create_time'].includes(item.field))
      .map(item => item.field);
    // 订阅审批
    const tableForSelf = reactive<ITable>({
      data: [],
      columns: [
        {
          width: '20%',
          label: `${t('订阅名称')}`,
          field: 'content_title',
        },
        {
          label: `${t('通知渠道')}`,
          field: 'channels',
        },
        {
          label: `${t('订阅场景')}`,
          field: 'scenario',
        },
        {
          label: `${t('发送模式')}`,
          field: 'send_mode',
          filter: [
            {
              label: t('周期发送'),
              value: 'periodic',
            },
            {
              label: t('仅发一次'),
              value: 'one_time',
            },
          ],
        },
        {
          label: `${t('发送时间')}`,
          field: 'send_time',
        },
        {
          label: `${t('审批状态')}`,
          field: 'status',
        },
        {
          label: `${t('创建人')}`,
          field: 'create_user',
        },
        {
          label: `${t('操作')}`,
          field: 'self_action',
          width: `${(window.i18n.locale as unknown as string) === 'zhCN' ? '150px' : '170px'}`,
        },
      ],
      settings: {
        fields: [],
        checked: [],
        size: 'small',
      },
    });
    // 根据 tableForSelf 字段生成对应的字段显隐 setting
    tableForSelf.settings.fields = tableForSelf.columns.map(item => {
      return {
        label: item.label,
        field: item.field,
      };
    });
    tableForSelf.settings.checked = tableForSelf.columns.map(item => item.field);
    setTableSetting();

    // 发送记录 里控制多个 tooltips 的显隐
    const toggleMapForSendRecord = reactive<TooltipsToggleMapping>({});
    const sendRecordTable = reactive<{
      data: any[];
      columns: TableProps['columns'];
      isLoading: boolean;
    }>({
      data: [],
      columns: [
        {
          title: `${t('发送时间')}`,
          colKey: 'send_time',
          cell: (_, { row: data }) => {
            return <span>{dayjs(data.send_time).format('YYYY-MM-DD HH:mm:ss')}</span>;
          },
        },
        {
          title: `${t('类型')}`,
          cell: (_, { row: data }) => <span>{t(ChannelName[data.channel_name])}</span>,
        },
        {
          title: `${t('接收人')}`,
          cell: (_, { row: data }) => {
            const content = data.send_results.map(item => item.id).toString();
            return (
              <bk-user-display-name
                style='overflow: hidden;text-overflow: ellipsis;white-space: nowrap;'
                v-overflow-tips
                user-id={content}
              />
            );
          },
        },
        {
          title: `${t('发送结果')}`,
          cell: (_, { row: data }) => {
            return (
              <span>
                <i class={['icon-circle', data.send_status]} />
                {data.send_results.filter(item => item.result).length ? (
                  <span style='margin-left: 10px;'>{t(SendStatus[data.send_status])}</span>
                ) : (
                  <span
                    style='margin-left: 10px;'
                    v-bk-tooltips={{
                      content: data.send_results.find(item => !item.result)?.message,
                      placement: 'top',
                    }}
                  >
                    {t(SendStatus[data.send_status])}
                  </span>
                )}
              </span>
            );
          },
          colKey: 'send_status',
        },
        {
          title: `${t('操作')}`,
          cell: (_, { row: data, rowIndex: index }) => {
            return (
              <Popover
                extCls='email-subscription-popover'
                // zIndex={99999 + index}
                v-slots={{
                  content: () => {
                    let headerText = '';
                    let headerConfirmText = '';
                    if (['success'].includes(data.send_status)) {
                      const headerTextMap = {
                        user: '已成功发送 {0} 个内部用户',
                        email: '已成功发送 {0} 个外部邮件',
                        wxbot: '已成功发送 {0} 个企业微信群',
                      };
                      headerText = headerTextMap[data.channel_name];
                      const headerConfirmTextMap = {
                        user: '确定重新发送给以下用户',
                        email: '确定重新发送给以下邮件',
                        wxbot: '确定重新发送给以下企业微信群',
                      };
                      headerConfirmText = headerConfirmTextMap[data.channel_name];
                    } else if (['partial_failed', 'failed'].includes(data.send_status)) {
                      const headerTextMap = {
                        user: '已成功发送 {0} 个，失败 {1} 个内部用户',
                        email: '已成功发送 {0} 个，失败 {1} 个外部邮件',
                        wxbot: '已成功发送 {0} 个，失败 {1} 个企业微信群',
                      };
                      headerText = headerTextMap[data.channel_name];
                      const headerConfirmTextMap = {
                        user: '确定重新发送给以下失败用户',
                        email: '确定重新发送给以下失败邮件',
                        wxbot: '确定重新发送给以下失败企业微信群',
                      };
                      headerConfirmText = headerConfirmTextMap[data.channel_name];
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
                            <span class='success-text'>{data.send_results.filter(item => item.result).length}</span>
                            {['partial_failed', 'failed'].includes(data.send_status) && (
                              <span class='fail-text'>{data.send_results.filter(item => !item.result).length}</span>
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
                          {t(headerConfirmText)}
                        </div>

                        <div style='margin-top: 10px;'>
                          <TagInput
                            v-model={data.selectedTag}
                            content-width={238}
                            display-key='id'
                            list={data.tempSendResult}
                            placeholder={t('请选择')}
                            save-key='id'
                            search-key={['id']}
                            trigger='focus'
                            has-delete-icon
                          />
                        </div>

                        <div class='footer-operation'>
                          <Button
                            style='min-width: 64px;'
                            disabled={!data.selectedTag.length}
                            loading={isResending.value}
                            theme='primary'
                            onClick={() => {
                              handleResendSubscription(data, index);
                            }}
                          >
                            {t('确定')}
                          </Button>

                          <Button
                            style='min-width: 64px;margin-left: 8px;'
                            onClick={() => {
                              toggleMapForSendRecord[index] = false;
                            }}
                          >
                            {t('取消')}
                          </Button>
                        </div>
                      </div>
                    );
                  },
                }}
                isShow={toggleMapForSendRecord[index] || false}
                placement='bottom-start'
                theme='light'
                trigger='click'
                disableOutsideClick
              >
                <Button
                  theme='primary'
                  text
                  onClick={() => {
                    toggleMapForSendRecord[index] = true;
                    // 每次重新发送都会重置一次 tag 列表。不知道是否实用。
                    sendRecordTable.data.forEach(item => {
                      item.tempSendResult = deepClone(item.send_results);
                      // 这里将展示 TagInput 用的保存变量。

                      item.selectedTag = [];
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
                  }}
                >
                  {t('重新发送')}
                </Button>
              </Popover>
            );
          },
          colKey: 'action',
        },
      ],
      isLoading: false,
    });

    // 显隐 订阅详情 抽屉组件
    const isShowSubscriptionDetailSideslider = shallowRef(false);
    // 显隐 编辑订阅 抽屉组件
    const isShowEditSideslider = shallowRef(false);

    // 显隐 测试发送 的 dropdownMenu 组件
    const isShowDropdownMenu = shallowRef(false);
    // 测试发送 是否loading
    const isSending = shallowRef(false);
    // 子组件 里面是大表单
    const refOfCreateSubscriptionForm = shallowRef();
    // 是否显示 测试发送 完成后的弹窗
    const isShowTestSendResult = shallowRef(false);
    // 订阅详情 数据，这个数据是来源于 订阅列表 里，该列表是带有详情的，不需要再请求即可获得。
    const subscriptionDetail = shallowRef(getDefaultReportData());

    // 发送记录 里 重新发送 的 loading
    const isResending = shallowRef(false);
    // 点击相同索引集警告中的 订阅名称 ，加载其它订阅详情的 loading
    const isFetchReport = shallowRef(false);
    // checkNeedShowEditSlider() 对应的变量。 以免太早显示编辑态触发了表单内部的api请求（要根据该方法获取 scenario 变量才能去调用。）
    const isShowCreateReportFormComponent = shallowRef(true);
    const isShowHeaderNav = shallowRef(true);

    function handleGoToCreateConfigPage() {
      router.push({
        name: 'create-report',
      });
    }

    function handleInputKeydown() {
      if (isManagerOrUser.value) resetAndGetSubscriptionList();
      emptyType.value = searchKey.value ? 'search-empty' : 'empty';
    }

    async function handleDeleteRow(report_id) {
      await deleteReport({
        report_id,
      }).then(() => {
        fetchSubscriptionList();
      });
    }

    async function testSending(to: TestSendingTarget) {
      // 先校验一次子组件的表单
      const tempFormData = await refOfCreateSubscriptionForm.value.validateAllForms();
      if (!tempFormData) return;
      const clonedFormData = deepClone(tempFormData);
      if (to === 'self') {
        const selfChannels = [
          {
            is_enabled: true,
            subscribers: [
              {
                id: window.user_name || window.username,
                type: 'user',
                is_enabled: true,
              },
            ],
            channel_name: 'user',
          },
        ];
        clonedFormData.channels = selfChannels;
      }
      // 删除无用 key
      /* eslint-disable */
      const {
        create_time,
        create_user,
        is_deleted,
        is_manager_created,
        last_send_time,
        send_mode,
        send_round,
        send_status,
        update_time,
        update_user,
        id,
        is_invalid,
        ...formData
      } = clonedFormData;
      /* eslint-enable */
      isSending.value = true;
      await sendReport(formData)
        .then(() => {
          isShowTestSendResult.value = true;
        })
        .finally(() => {
          isSending.value = false;
          isShowDropdownMenu.value = false;
        });
    }

    function resetAndGetSubscriptionList() {
      page.value = 1;
      fetchSubscriptionList();
    }

    function fetchSubscriptionList() {
      isTableLoading.value = true;
      getReportList({
        create_type: createType.value,
        query_type: queryType.value,
        search_key: searchKey.value,
        page: page.value,
        page_size: pageSize.value,
        order: order.value,
        conditions: conditions.value,
      })
        .then(response => {
          table.data = response.report_list;
          totalReportSize.value = response.total;
        })
        .finally(() => {
          isTableLoading.value = false;
        });
    }

    function handleSetEnable(index) {
      console.log(index);
      const data = table.data[index];
      createOrUpdateReport(data)
        .then(() => {})
        .catch(() => {
          data.is_enabled = !data.is_enabled;
        });
    }

    function getSendingRecordList() {
      sendRecordTable.isLoading = true;
      getSendRecords({
        report_id: subscriptionDetail.value.id,
      })
        .then(response => {
          sendRecordTable.data = response;
        })
        .finally(() => {
          sendRecordTable.isLoading = false;
        });
    }

    function formatTimeRange(s, e) {
      if (!s) return '';
      const startTime = dayjs.unix(s).format('YYYY-MM-DD HH:mm');
      const endTime = dayjs.unix(e).format('YYYY-MM-DD HH:mm');
      return `${startTime} ~ ${endTime}`;
    }

    function handleResendSubscription(data, index) {
      isResending.value = true;
      const channels = [
        {
          is_enabled: true,
          channel_name: data.channel_name,
          subscribers: data.tempSendResult
            .filter(item => {
              return data.selectedTag.includes(item.id);
            })
            .map(item => {
              // biome-ignore lint/performance/noDelete: <explanation>
              delete item.result;
              item.is_enabled = true;
              return item;
            }),
        },
      ];
      sendReport({
        report_id: data.report_id,
        channels,
      })
        .then(() => {
          Message({
            theme: 'success',
            message: t('发送成功'),
          });
        })
        .finally(() => {
          isResending.value = false;
          toggleMapForSendRecord[index] = false;
        });
    }

    function handleEmptyOperation(type) {
      if (type === 'refresh') {
        emptyType.value = 'empty';
      } else if (type === 'clear-filter') {
        searchKey.value = '';
        emptyType.value = searchKey.value ? 'search-empty' : 'empty';
      }

      if (isManagerOrUser.value) {
        resetAndGetSubscriptionList();
      } else {
        fetchApplyList();
      }
    }

    async function handleSendMyself() {
      isSending.value = true;
      const selfChannels = [
        {
          is_enabled: true,
          subscribers: [
            {
              id: window.user_name || window.username,
              type: 'user',
              is_enabled: true,
            },
          ],
          channel_name: 'user',
        },
      ];
      const clonedFormData = deepClone(subscriptionDetail.value);
      clonedFormData.channels = selfChannels;
      // 去掉无用 key ，这些都来自于 后端返回 ，前端用不着，但后端不让上传的
      /* eslint-disable */
      const {
        create_time,
        create_user,
        is_deleted,
        is_manager_created,
        last_send_time,
        send_mode,
        send_round,
        send_status,
        update_time,
        update_user,
        id,
        is_invalid,
        ...formData
      } = clonedFormData;
      /* eslint-enable */
      formData.report_id = id;
      await sendReport(formData)
        .then(() => {
          setTimeout(() => {
            isShowTestSendResult.value = true;
          }, 500);
        })
        .finally(() => {
          isSending.value = false;
        });
    }

    /** 点击已存在的相同索引集对应的 订阅名称 时，切换 编辑抽屉的 订阅详情 内容 */
    function handleReportDetailChange(reportId) {
      isFetchReport.value = true;
      getReport({
        report_id: reportId,
      })
        .then(response => {
          subscriptionDetail.value = response;
          nextTick(() => {
            refOfCreateSubscriptionForm.value.setFormData();
          });
        })
        .finally(() => {
          isFetchReport.value = false;
        });
    }

    /**
     * 新增订阅 页面选择了重复的索引集时，点击相应的 订阅名称 就会跳回来这个页面。
     * 其中 url 会带一些参数去打开编辑抽屉。
     */
    function checkNeedShowEditSlider() {
      const { reportId, isShowEditSlider } = route.query;
      if (isShowEditSlider !== 'true') return;

      isShowCreateReportFormComponent.value = false;
      isShowEditSideslider.value = true;
      isFetchReport.value = true;
      getReport({
        report_id: reportId,
      })
        .then(response => {
          subscriptionDetail.value = response;
          nextTick(() => {
            refOfCreateSubscriptionForm.value.setFormData();
          });
        })
        .catch(() => {
          isShowEditSideslider.value = false;
        })
        .finally(() => {
          isFetchReport.value = false;
          isShowCreateReportFormComponent.value = true;
          // 只需要打开一次 slider 即可。把 url 参数清空，避免刷新页面时还会出现 slider 。
          router.replace({
            name: 'report',
          });
        });
    }

    function setTableSetting() {
      const tableSetting = window.localStorage.getItem(keyOfTableSettingInLocalStorage);
      const tableForSelfSetting = window.localStorage.getItem(keyOfTableForSelfSettingInLocalStorage);
      if (tableSetting) {
        table.settings.checked = JSON.parse(tableSetting);
      }
      if (tableForSelfSetting) {
        tableForSelf.settings.checked = JSON.parse(tableForSelfSetting);
      }
    }

    function fetchApplyList() {
      tableForSelf.data.length = 0;
      isTableLoading.value = true;
      getApplyRecords({
        query_type: 'biz',
        // 选择 全部 时则不传
        status: queryTypeForSelf.value === 'all' ? undefined : queryTypeForSelf.value,
      })
        .then(res => {
          tableForSelf.data = res;
        })
        .finally(() => {
          isTableLoading.value = false;
        });
    }

    function fetchReportDetail(report_id) {
      isFetchReport.value = true;
      getReport({
        report_id,
      })
        .then(response => {
          subscriptionDetail.value = response;
        })
        .finally(() => {
          isFetchReport.value = false;
        });
    }

    function getUrlSearchParams() {
      const url = new URLSearchParams(window.location.search);
      isShowHeaderNav.value = Boolean(url.get('needMenu') !== 'false');
    }

    const isManagerOrUser = computed(() => {
      return ['manager', 'user'].includes(createType.value);
    });

    const filterConfig = shallowRef<FilterValue>({});

    const computedTableDataForSelf = computed(() => {
      return tableForSelf.data
        .filter(item => {
          const entries = Object.entries(filterConfig.value || {});
          if (!entries.length) return true;
          return entries.every(([key, valList]) => {
            return valList.includes(item[key]);
          });
        })
        .filter(item => {
          return item.content_title.includes(searchKey.value) || item.create_user.includes(searchKey.value);
        });
    });

    function handleSetFormat({ row, rowIndex }, filed) {
      const isGrayText = queryType.value === 'invalid' || !isManagerOrUser.value ? false : row.is_invalid;
      switch (filed) {
        case 'name': {
          return (
            <span
              class='subscription-name'
              onClick={() => {
                subscriptionDetail.value = row;
                isShowSubscriptionDetailSideslider.value = true;
              }}
            >
              {t(`${row.name}`)}
            </span>
          );
        }
        case 'channels': {
          const content = row.channels
            .filter(item => item.is_enabled)
            .map(item => t(ChannelName[item.channel_name]))
            .toString();
          return (
            <span
              class={{
                'gray-text': isGrayText,
              }}
            >
              {content}
            </span>
          );
        }
        case 'scenario': {
          return (
            <span
              class={{
                'gray-text': isGrayText,
              }}
            >
              {t(Scenario[row.scenario])}
            </span>
          );
        }
        case 'send_mode': {
          return (
            <span
              class={{
                'gray-text': isGrayText,
              }}
            >
              {t(SendMode[row.send_mode])}
            </span>
          );
        }
        case 'send_time': {
          const content =
            row?.frequency?.type === FrequencyType.onlyOnce
              ? `${getSendFrequencyText(row)} ${dayjs(row.frequency.run_time).format('YYYY-MM-DD HH:mm')}`
              : getSendFrequencyText(row);
          return (
            <span
              class={{
                'gray-text': isGrayText,
              }}
            >
              {content}
            </span>
          );
        }
        case 'last_send_time': {
          return (
            <span
              class={{
                'gray-text': isGrayText,
              }}
            >
              {row.last_send_time ? dayjs(row.last_send_time).format('YYYY-MM-DD HH:mm:ss') : t('未发送')}
            </span>
          );
        }
        case 'send_status': {
          return (
            <span
              class={{
                'gray-text': isGrayText,
              }}
            >
              <i
                style='margin-right: 10px;'
                class={['icon-circle', row.send_status]}
              />
              {t(SendStatus[row.send_status])}
            </span>
          );
        }
        case 'create_user': {
          return row.create_user ? (
            <bk-user-display-name
              class={{
                'gray-text': isGrayText,
              }}
              user-id={row.create_user}
            />
          ) : (
            '--'
          );
        }
        case 'is_enabled': {
          return (
            <Switcher
              v-model={row.is_enabled}
              size='small'
              theme='primary'
              onChange={() => handleSetEnable(rowIndex)}
            />
          );
        }
        case 'create_time': {
          return <span>{dayjs(row.create_time).format('YYYY-MM-DD HH:mm:ss')}</span>;
        }
        case 'action': {
          return (
            <div style='display: flex;align-items: center;'>
              <Button
                theme='primary'
                text
                onClick={() => {
                  isShowSendRecord.value = true;
                  subscriptionDetail.value = row;
                  getSendingRecordList();
                }}
              >
                {t('发送记录')}
              </Button>

              <Button
                style='margin-left: 10px;'
                theme='primary'
                text
                onClick={() => {
                  subscriptionDetail.value = row;
                  isShowEditSideslider.value = true;
                }}
              >
                {t('编辑')}
              </Button>

              {/* 实现方式有问题，看看有没有其它的实现方式 */}
              <div>
                <Popover
                  extCls='email-subscription-popover'
                  v-slots={{
                    content: () => (
                      <div>
                        <div
                          class='popover-item'
                          onClick={() => {
                            toggleMap[rowIndex] = false;
                            // 将当前数据深拷贝一次，将 name 增加 _clone 后缀，再把 id 的 key 删掉（让接口直接创建新数据）
                            // 最后赋值到 subscriptionDetail 中，打开编辑抽屉组件让用户进行修改。
                            const clonedSubscriptionDetail = deepClone(row);
                            clonedSubscriptionDetail.name = `${clonedSubscriptionDetail.name}_clone`;
                            subscriptionDetail.value = clonedSubscriptionDetail;
                            isShowEditSideslider.value = true;
                            isOnCloneMode = true;
                          }}
                        >
                          {t('克隆')}
                        </div>
                        <div
                          class='popover-item'
                          onClick={() => {
                            toggleMap[rowIndex] = false;
                            InfoBox({
                              extCls: 'report-tips-dialog',
                              infoType: 'warning',
                              title: t('是否删除 {0} ?', [row.name]),
                              showMask: true,
                              onConfirm: () => {
                                return handleDeleteRow(row.id)
                                  .then(() => {
                                    return true;
                                  })
                                  .catch(() => {
                                    return false;
                                  });
                              },
                            });
                          }}
                        >
                          {t('删除')}
                        </div>
                      </div>
                    ),
                  }}
                  isShow={toggleMap[rowIndex] || false}
                  placement='bottom-start'
                  theme='light'
                  trigger='click'
                >
                  <i
                    style='margin-left: 10px;'
                    class='more-btn icon-monitor icon-mc-more'
                    onClick={() => (toggleMap[rowIndex] = true)}
                  />
                </Popover>
              </div>
            </div>
          );
        }
        case 'content_title': {
          return (
            <span
              class='subscription-name'
              onClick={() => {
                fetchReportDetail(row.report_id);
                isSelfMode.value = true;
                isShowSubscriptionDetailSideslider.value = true;
              }}
            >
              {t(`${row.content_title}`)}
            </span>
          );
        }
        case 'status': {
          return (
            <span>
              <i
                style='margin-right: 10px;'
                class={['icon-circle', row.status]}
              />
              {ApplyStatus[row.status]}
            </span>
          );
        }
        case 'self_action': {
          return (
            <div>
              <Button
                theme='primary'
                text
                onClick={() => {
                  window.open(row.approval_url, '_blank');
                }}
              >
                {['SUCCESS', 'FAILED'].includes(row.status) ? t('查看') : t('操作')}
              </Button>
            </div>
          );
        }
        default: {
          return <span>--</span>;
        }
      }
    }

    watch(route, () => {
      checkNeedShowEditSlider();
    });

    onMounted(() => {
      checkNeedShowEditSlider();
      fetchSubscriptionList();
      getUrlSearchParams();
    });
    return {
      t,
      createType,
      queryType,
      searchKey,
      page,
      pageSize,
      order,
      conditions,
      totalReportSize,
      handleInputKeydown,
      handleGoToCreateConfigPage,
      table,
      emptyType,
      handleEmptyOperation,
      isShowSendRecord,
      sendRecordTable,
      isShowSubscriptionDetailSideslider,
      isShowEditSideslider,
      testSending,
      refOfCreateSubscriptionForm,
      resetAndGetSubscriptionList,
      fetchSubscriptionList,
      subscriptionDetail,
      handleDeleteRow,
      isSending,
      getSendingRecordList,
      getSendFrequencyText,
      formatTimeRange,
      handleSendMyself,
      toggleMapForSendRecord,
      isShowTestSendResult,
      isShowDropdownMenu,
      handleReportDetailChange,
      isFetchReport,
      isShowCreateReportFormComponent,
      isOnCloneMode,
      navList,
      isShowCreateSubscription,
      isTableLoading,
      tableForSelf,
      isManagerOrUser,
      fetchApplyList,
      queryTypeForSelf,
      fetchReportDetail,
      isSelfMode,
      computedTableDataForSelf,
      filterConfig,
      isShowHeaderNav,
      handleSetFormat,
    };
  },
  render() {
    const headerTmpl = () => {
      return (
        <div class='header-container'>
          <div class='left-container'>
            <Button
              theme='primary'
              // onClick={this.handleGoToCreateConfigPage}
              onClick={() => {
                this.isShowCreateSubscription = true;
              }}
            >
              <i class='icon-monitor icon-mc-add' />
              <span>{this.t('新建')}</span>
            </Button>
            <Radio.Group
              style='margin-left: 16px;background-color: white;'
              v-model={this.createType}
              onChange={() => {
                if (this.isManagerOrUser) {
                  this.resetAndGetSubscriptionList();
                } else {
                  this.fetchApplyList();
                }
              }}
            >
              <Radio.Button label='manager'>{this.t('管理员创建的')}</Radio.Button>
              <Radio.Button label='user'>{this.t('用户订阅的')}</Radio.Button>
              <Radio.Button label='self'>{this.t('订阅审批')}</Radio.Button>
            </Radio.Group>
          </div>
          <div class='right-container'>
            {this.isManagerOrUser && (
              <Radio.Group
                v-model={this.queryType}
                type='capsule'
                onChange={() => {
                  this.resetAndGetSubscriptionList();
                }}
              >
                <Radio.Button label='all'>{this.t('全部')}</Radio.Button>
                <Radio.Button label='available'>
                  <i
                    style='margin-right: 4px;'
                    class='icon-circle success'
                  />
                  <span>{this.t('生效中')}</span>
                </Radio.Button>
                <Radio.Button label='invalid'>
                  <i
                    style='margin-right: 4px;'
                    class='icon-circle gray'
                  />
                  <span>{this.t('已失效')}</span>
                </Radio.Button>
                {/* 暂时不需要 */}
                {/* <Radio.Button label='cancelled'>
                <i
                  class='icon-circle cancelled'
                  style='margin-right: 4px;'
                />
                <span>{this.t('已取消')}</span>
              </Radio.Button> */}
              </Radio.Group>
            )}
            {!this.isManagerOrUser && (
              <Radio.Group
                v-model={this.queryTypeForSelf}
                type='capsule'
                onChange={() => {
                  this.fetchApplyList();
                }}
              >
                <Radio.Button label='all'>{this.t('全部')}</Radio.Button>
                <Radio.Button label='RUNNING'>{this.t('未审批')}</Radio.Button>
                <Radio.Button label='FAILED'>{this.t('未通过')}</Radio.Button>
                <Radio.Button label='SUCCESS'>{this.t('已通过')}</Radio.Button>
              </Radio.Group>
            )}
            <Input
              class='search-input'
              v-model={this.searchKey}
              v-slots={{
                suffix: () => (
                  <div class='suffix-icon'>
                    <i class='icon-monitor icon-mc-search' />
                  </div>
                ),
              }}
              placeholder={this.t('请输入搜索条件')}
              clearable
              onBlur={this.handleInputKeydown}
              onClear={this.handleInputKeydown}
              onEnter={this.handleInputKeydown}
            />
          </div>
        </div>
      );
    };
    return (
      <div>
        {this.isShowHeaderNav && (
          <NavBar
            class='report-nav'
            routeList={this.navList}
          />
        )}
        <div class={['email-subscription-config-container', { 'as-iframe': !this.isShowHeaderNav }]}>
          {/* 头部搜索 部分 */}
          {headerTmpl()}
          <Loading loading={this.isTableLoading}>
            <PrimaryTable
              style='margin-top: 16px;background-color: white;'
              v-show={this.isManagerOrUser}
              v-slots={{
                empty: () => (
                  <EmptyStatus
                    type={this.emptyType}
                    onOperation={this.handleEmptyOperation}
                  />
                ),
              }}
              columns={this.table.columns.map(item => {
                return {
                  colKey: item.field,
                  width: item.width,
                  filter: item.filter?.length
                    ? {
                        list: item.filter,
                        type: 'multiple',
                        showConfirmAndReset: true,
                      }
                    : undefined,
                  minWidth: item?.minWidth,
                  sorter: item.sortable,
                  ellipsis: {
                    popperOptions: {
                      strategy: 'fixed',
                    },
                  },
                  title: item.label,
                  cell: (_, ctx) => this.handleSetFormat(ctx, item.field),
                };
              })}
              pagination={{
                current: this.page,
                pageSize: this.pageSize,
                total: this.totalReportSize,
              }}
              sort={{
                sortBy: this.order?.replace(/^-/, '') || '',
                descending: this.order?.startsWith('-') || false,
              }}
              bkUiSettings={this.table.settings}
              data={this.table.data}
              showSortColumnBgColor={true}
              onFilterChange={(filters: TableProps['filterValue']) => {
                const conditions = [];
                for (const [key, selected] of Object.entries(filters)) {
                  selected?.length &&
                    conditions.push({
                      key,
                      value: selected,
                    });
                }
                this.conditions = conditions;
                this.page = 1;
                this.fetchSubscriptionList();
              }}
              onPageChange={(pageInfo: TableProps['pagination']) => {
                this.page = pageInfo.current;
                this.pageSize = pageInfo.pageSize;
                this.fetchSubscriptionList();
              }}
              // onSettingChange={({ checked, size }) => {
              //   this.table.settings.size = size;
              //   window.localStorage.setItem(keyOfTableSettingInLocalStorage, JSON.stringify(checked));
              // }}
              onSortChange={(sort: SortInfo) => {
                if (sort) {
                  this.order = `${!sort.descending ? '' : '-'}${sort.sortBy}`;
                } else {
                  this.order = '';
                }
                this.fetchSubscriptionList();
              }}
            />
            <PrimaryTable
              style='margin-top: 16px;background-color: white;'
              v-show={this.createType === 'self'}
              v-slots={{
                empty: () => (
                  <EmptyStatus
                    type={this.emptyType}
                    onOperation={this.handleEmptyOperation}
                  />
                ),
              }}
              columns={this.tableForSelf.columns.map(item => ({
                colKey: item.field,
                cell: (_, ctx) => this.handleSetFormat(ctx, item.field),
                ellipsis: {
                  popperOptions: {
                    strategy: 'fixed',
                  },
                },
                title: item.label,
                filter: item.filter?.length
                  ? {
                      list: item.filter,
                      type: 'multiple',
                      showConfirmAndReset: true,
                    }
                  : undefined,
                sorter: item.sortable,
              }))}
              bkUiSettings={this.tableForSelf.settings}
              data={this.computedTableDataForSelf}
              filterValue={this.filterConfig}
              onFilterChange={(filters: TableProps['filterValue']) => {
                this.filterConfig = filters;
              }}
              // onSettingChange={({ checked, size }) => {
              //   this.tableForSelf.settings.size = size;
              //   window.localStorage.setItem(keyOfTableForSelfSettingInLocalStorage, JSON.stringify(checked));
              // }}
            />
          </Loading>
          <Dialog
            width='960'
            dialog-type='show'
            is-show={this.isShowSendRecord}
            title={this.t('发送记录')}
            onClosed={() => {
              this.isShowSendRecord = false;
              for (const key of Object.keys(this.toggleMapForSendRecord)) {
                this.toggleMapForSendRecord[key] = false;
              }
            }}
          >
            <div>
              <div class='dialog-header-info-container'>
                <div style='display: flex;'>
                  <div class='label-container'>
                    <div class='label'>{this.t('发送频率')}:</div>
                    <div
                      style='max-width: 200px;white-space: normal;word-break: break-all;'
                      class='value'
                    >
                      {this.getSendFrequencyText(this.subscriptionDetail)}
                    </div>
                    {this.subscriptionDetail.frequency.type === FrequencyType.onlyOnce && (
                      <div class='value'>
                        {dayjs(this.subscriptionDetail.frequency.run_time).format('YYYY-MM-DD HH:mm')}
                      </div>
                    )}
                  </div>
                  {this.subscriptionDetail.frequency.type !== FrequencyType.onlyOnce && (
                    <div class='label-container'>
                      <div
                        style='margin-left: 55px;'
                        class='label'
                      >
                        {this.t('任务有效期')}:
                      </div>
                      <div class='value'>
                        {this.formatTimeRange(this.subscriptionDetail.start_time, this.subscriptionDetail.end_time)}
                      </div>
                    </div>
                  )}
                </div>
                <div>
                  <Button
                    style='font-size: 12px;'
                    disabled={this.sendRecordTable.isLoading}
                    theme='primary'
                    text
                    onClick={this.getSendingRecordList}
                  >
                    {this.t('刷新')}
                  </Button>
                </div>
              </div>

              <Loading loading={this.sendRecordTable.isLoading}>
                <PrimaryTable
                  style='margin-top: 16px;'
                  height={400}
                  columns={this.sendRecordTable.columns}
                  data={this.sendRecordTable.data}
                  rowKey='id'
                />
              </Loading>
            </div>
          </Dialog>

          <Sideslider
            width={960}
            ext-cls='edit-subscription-sideslider-container'
            v-model={[this.isShowCreateSubscription, 'isShow']}
            render-directive='if'
            title={this.t('新建订阅')}
            transfer
          >
            <CreateSubscription
              onCloseCreateSubscriptionSlider={() => {
                this.isShowCreateSubscription = false;
              }}
              onSaveSuccess={() => {
                this.fetchSubscriptionList();
                this.isShowCreateSubscription = false;
              }}
            />
          </Sideslider>

          <Sideslider
            // 根据显示内容要动态调整。
            width={640}
            ext-cls='detail-subscription-sideslider-container'
            v-model={[this.isShowSubscriptionDetailSideslider, 'isShow']}
            v-slots={{
              header: () => {
                return (
                  <div class='slider-header-container'>
                    <div class='title-container'>
                      <span class='title'>{this.t('订阅详情')}</span>
                      <span
                        style={{
                          maxWidth: currentLang === 'en' ? '180px' : '250px',
                        }}
                        class='sub-title'
                        v-overflow-tips
                      >
                        -&nbsp;{this.subscriptionDetail.name}
                      </span>
                    </div>

                    {!this.isSelfMode && (
                      <div class='operation-container'>
                        <Button
                          style='margin-right: 8px;'
                          onClick={() => {
                            InfoBox({
                              extCls: 'report-tips-dialog',
                              infoType: 'warning',
                              title: this.t('是否发送给自己?'),
                              showMask: true,
                              onConfirm: () => {
                                return this.handleSendMyself()
                                  .then(() => {
                                    return true;
                                  })
                                  .catch(() => {
                                    return false;
                                  });
                              },
                            });
                          }}
                        >
                          {this.t('发送给自己')}
                        </Button>
                        <Button
                          style='margin-right: 8px;'
                          theme='primary'
                          outline
                          onClick={() => {
                            this.isShowEditSideslider = true;
                          }}
                        >
                          {this.t('编辑')}
                        </Button>

                        <Popover
                          v-slots={{
                            content: () => {
                              return (
                                <div>
                                  <div>
                                    <span>{`${this.t('更新人')}: `}</span>
                                    <bk-user-display-name user-id={this.subscriptionDetail.update_user} />
                                  </div>
                                  <div>{`${this.t('更新时间')}: ${dayjs(this.subscriptionDetail.update_time).format(
                                    'YYYY-MM-DD HH:mm:ss'
                                  )}`}</div>
                                  <div>
                                    <span>{`${this.t('创建人')}: `}</span>
                                    <bk-user-display-name user-id={this.subscriptionDetail.create_user} />
                                  </div>
                                  <div>{`${this.t('创建时间')}: ${dayjs(this.subscriptionDetail.create_time).format(
                                    'YYYY-MM-DD HH:mm:ss'
                                  )}`}</div>
                                </div>
                              );
                            },
                          }}
                          placement='bottom-end'
                        >
                          <Button style='margin-right: 24px;'>
                            <i class='icon-monitor icon-lishi' />
                          </Button>
                        </Popover>
                      </div>
                    )}
                  </div>
                );
              },
              default: () => {
                return (
                  <div>
                    <SubscriptionDetail
                      style='padding: 20px 40px;'
                      detailInfo={this.subscriptionDetail}
                    />
                  </div>
                );
              },
            }}
            render-directive='if'
            transfer
            onHidden={() => {
              this.isSelfMode = false;
            }}
          />

          <Sideslider
            width={960}
            ext-cls='edit-subscription-sideslider-container'
            v-model={[this.isShowEditSideslider, 'isShow']}
            render-directive='if'
            title={this.t('编辑')}
            transfer
            onHidden={() => {
              this.isShowDropdownMenu = false;
              isOnCloneMode = false;
            }}
            onShown={() => {
              this.isShowSubscriptionDetailSideslider = false;
              this.isShowCreateSubscription = false;
            }}
          >
            <Loading
              class='loading-edit-slider'
              loading={this.isFetchReport}
            >
              <div>
                <div class='create-subscription-container'>
                  {this.isShowCreateReportFormComponent && (
                    <CreateSubscriptionForm
                      ref='refOfCreateSubscriptionForm'
                      detailInfo={this.subscriptionDetail}
                      mode='edit'
                      onSelectExistedReport={this.handleReportDetailChange}
                    />
                  )}
                </div>

                <div class='footer-bar'>
                  <Button
                    style='width: 88px;margin-right: 8px;'
                    theme='primary'
                    onClick={() => {
                      this.refOfCreateSubscriptionForm.validateAllForms().then(response => {
                        if (isOnCloneMode) {
                          // 由于表单会返回 id 的默认值，这里特殊处理删掉。
                          // biome-ignore lint/performance/noDelete: <explanation>
                          delete response.id;
                        }
                        createOrUpdateReport(response).then(() => {
                          Message({
                            theme: 'success',
                            message: this.t('保存成功'),
                          });
                          this.fetchSubscriptionList();
                          this.isShowEditSideslider = false;
                        });
                      });
                    }}
                  >
                    {this.t('保存')}
                  </Button>
                  <Dropdown
                    v-slots={{
                      content: () => {
                        return (
                          <Dropdown.DropdownMenu>
                            <Dropdown.DropdownItem onClick={() => this.testSending('self')}>
                              {this.t('给自己')}
                            </Dropdown.DropdownItem>
                            <Dropdown.DropdownItem onClick={() => this.testSending('all')}>
                              {this.t('给全员')}
                            </Dropdown.DropdownItem>
                          </Dropdown.DropdownMenu>
                        );
                      },
                    }}
                    isShow={this.isShowDropdownMenu}
                    placement='top-start'
                    trigger='manual'
                  >
                    <Button
                      style='width: 88px;margin-right: 8px;'
                      loading={this.isSending}
                      theme='primary'
                      outline
                      onClick={() => {
                        this.isShowDropdownMenu = !this.isShowDropdownMenu;
                      }}
                    >
                      {this.t('测试发送')}
                    </Button>
                  </Dropdown>
                  <Button
                    style='width: 88px;'
                    onClick={() => {
                      this.isShowEditSideslider = false;
                    }}
                  >
                    {this.t('取消')}
                  </Button>
                </div>
              </div>
            </Loading>
          </Sideslider>

          <TestSendSuccessDialog v-model={this.isShowTestSendResult} />
        </div>
      </div>
    );
  },
});
