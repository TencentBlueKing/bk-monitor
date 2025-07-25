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

import { type Ref, computed, defineComponent, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue';

import { Dialog, Form, Input, Loading, Message, Popover, Progress, Tag } from 'bkui-vue';
import { editIncident, incidentAlertAggregate } from 'monitor-api/modules/incident';
import { useI18n } from 'vue-i18n';

import ChatGroup from '../alarm-detail/chat-group/chat-group';
import { LEVEL_LIST } from '../constant';
import { useIncidentInject } from '../utils';
import FailureEditDialog from './failure-edit-dialog';

import type { IIncident } from '../types';
import type { IAggregationRoot } from '../types';

import './failure-header.scss';

export default defineComponent({
  name: 'FailureHeader',
  emits: ['editSuccess'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const isShow = ref<boolean>(false);
    const isShowResolve = ref<boolean>(false);
    const listLoading = ref(false);
    const alertAggregateData = ref<IAggregationRoot[]>([]);
    const alertAggregateTotal = ref(0);
    const showTime = ref('00:00:00');
    const timer = ref(null);
    const btnLoading = ref(false);
    const incidentReason = ref('');
    const playLoading = inject<Ref<boolean>>('playLoading');
    const currentData = ref({});
    const levelList = LEVEL_LIST;
    const statusList = {
      /** 已恢复  */
      recovered: {
        icon: 'mc-check-fill',
        color: '#1CAB88',
      },
      /** 观察中  */
      recovering: {
        icon: 'guanchazhong',
        color: '#FF9C01',
      },
      /** 已解决  */
      closed: {
        icon: 'mc-solved',
        color: '#979BA5',
      },
    };
    const incidentId = useIncidentInject();
    /** 一键拉群弹窗 */
    const chatGroupDialog = reactive({
      show: false,
      alertName: '',
      bizId: [],
      assignee: [],
      alertIds: [],
    });
    const editIncidentDialogRef = ref(null);
    const incidentDetail = inject<Ref<IIncident>>('incidentDetail');
    const incidentDetailData: Ref<IIncident> = computed(() => {
      return incidentDetail.value;
    });
    const getIncidentAlertAggregate = () => {
      listLoading.value = true;
      incidentAlertAggregate({
        id: incidentId.value,
        aggregate_bys: [],
        bk_biz_ids: [-1],
      })
        .then(res => {
          alertAggregateData.value = res;
          const list: IAggregationRoot[] = Object.values(res || {});
          const total: any = list.reduce((prev, cur) => {
            return prev + cur?.count;
          }, 0);
          alertAggregateTotal.value = total;
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          listLoading.value = false;
        });
    };
    const handleBack = () => {
      const { bk_biz_id } = incidentDetail.value;
      const { origin, pathname } = location;
      const url = `${origin}${pathname}?bizId=${bk_biz_id}#/event-center?searchType=incident&activeFilterId=incident`;
      window.location.href = url;
    };
    /** 一期先不展示 */
    // const tipsItem = (val: number) => (
    //   <span class='tips-more'>
    //     ，其中 <b>{val}</b> 个未分派
    //     <span class='tips-btn'>
    //       <i class='icon-monitor icon-fenpai tips-btn-icon'></i>
    //       {t('告警分派')}
    //     </span>
    //   </span>
    // );
    const statusTips = () => {
      const list = Object.values(alertAggregateData.value);
      const total = alertAggregateTotal.value;
      return (
        <div class='header-status-tips'>
          <div class='tips-head'>
            {t('故障内的告警：共')}
            <b> {total} </b>
            {t('个')}
          </div>
          {list.map((item: any, ind: number) => (
            <span
              key={item.name}
              class={['tips-item', { marked: ind === 0 }]}
            >
              {item.name}：<b>{item.count}</b> (<b>{Math.round((item.count / total) * 100) || 0}%</b>)
              {/* {ind === 0 && tipsItem(10)} */}
            </span>
          ))}
        </div>
      );
    };
    const renderStatusIcon = (status = 'closed') => {
      // 未恢复
      if (status === 'abnormal') {
        const data: IAggregationRoot = alertAggregateData.value.filter(item => item.id === 'ABNORMAL')[0];
        return (
          <Progress
            width={38}
            bg-color='#EBECF0'
            color='#EB3333'
            percent={Math.round((data?.count / alertAggregateTotal.value) * 100)}
            stroke-width={12}
            type='circle'
            text-inside
          >
            <label class='status-num'>{data?.count || 0}</label>
          </Progress>
        );
      }
      const info = statusList[status];
      return (
        <i
          style={{ color: info?.color }}
          class={`icon-monitor icon-${info?.icon} status-icon`}
        />
      );
    };
    const editIncidentHandle = (type = 'edit') => {
      editIncidentDialogRef.value?.validate().then(() => {
        btnLoading.value = true;
        const { id, incident_id } = incidentDetailData.value;
        editIncident({ incident_reason: incidentReason.value, incident_id, id, status: 'closed' })
          .then(() => {
            Message({
              theme: 'success',
              message: t('标记成功'),
            });
            if (type === 'resolve') {
              isShowResolve.value = false;
            } else {
              isShow.value = false;
            }
            onEditSuccess();
          })
          .catch(() => {
            if (type === 'resolve') {
              isShowResolve.value = true;
            } else {
              isShow.value = true;
            }
          })
          .finally(() => {
            btnLoading.value = false;
          });
      });
    };
    /** 标记已解决弹框  */
    const DialogFn = () => (
      <Dialog
        ext-cls='failure-edit-dialog'
        dialog-type='operation'
        is-show={isShowResolve.value}
        title={t('标记已解决')}
        onClosed={() => {
          isShowResolve.value = false;
        }}
        onConfirm={() => {
          editIncidentHandle('resolve');
        }}
      >
        <Form
          ref='editIncidentDialogRef'
          form-type={'vertical'}
          model={{ incidentReason: incidentReason.value }}
        >
          <Form.FormItem
            label={t('故障原因')}
            property='incidentReason'
            required
          >
            <Input
              v-model={incidentReason.value}
              maxlength={300}
              type='textarea'
            />
          </Form.FormItem>
        </Form>
      </Dialog>
    );
    const convertTimestamp = (timestamp1, timestamp2) => {
      // 计算两个时间戳之间的差值（以毫秒为单位）
      const diff = Math.abs(timestamp1 - timestamp2);
      const totalSeconds = Math.floor(diff / 1000);
      const days = Math.floor(totalSeconds / (24 * 3600));
      const remainingSeconds = totalSeconds % (24 * 3600);
      const hours = Math.floor(remainingSeconds / 3600);
      const remainingSeconds1 = remainingSeconds % 3600;
      const minutes = Math.floor(remainingSeconds1 / 60);
      const seconds = remainingSeconds1 % 60;
      if (days > 0) {
        return `${days}d ${hours}h ${minutes}m`;
      }
      const padZeros = (str: number) => `${str > 10 ? str : `0${str}`}`;
      return `${padZeros(hours)}:${padZeros(minutes)}:${padZeros(seconds)}`;
    };
    onMounted(() => {
      getIncidentAlertAggregate();
    });
    onBeforeUnmount(() => {
      clearInterval(timer.value);
    });
    const onEditSuccess = () => {
      setTimeout(() => {
        getIncidentAlertAggregate();
        emit('editSuccess');
      }, 1000);
    };
    /**
     * @description: 一键拉群弹窗关闭/显示
     * @param {boolean} show
     * @return {*}
     */
    const chatGroupShowChange = (show: boolean) => {
      chatGroupDialog.show = show;
    };
    const handleChatGroup = () => {
      const { id, assignees, incident_name, bk_biz_id } = incidentDetailData.value;
      chatGroupDialog.assignee = assignees || [];
      chatGroupDialog.alertName = incident_name;
      chatGroupDialog.bizId = [bk_biz_id];
      chatGroupDialog.alertIds.splice(0, chatGroupDialog.alertIds.length, id);
      chatGroupDialog.show = true;
    };
    return {
      DialogFn,
      incidentDetailData,
      isShow,
      levelList,
      t,
      statusTips,
      isShowResolve,
      renderStatusIcon,
      handleBack,
      listLoading,
      showTime,
      timer,
      getIncidentAlertAggregate,
      onEditSuccess,
      convertTimestamp,
      playLoading,
      chatGroupDialog,
      chatGroupShowChange,
      currentData,
      handleChatGroup,
      editIncidentDialogRef,
    };
  },
  render() {
    const { id, incident_name, labels, status_alias, level, level_alias, status, begin_time, end_time } =
      this.incidentDetailData;
    const isRecovered = status !== 'recovered';
    /** 持续时间 */
    const handleShowTime = () => {
      if (!begin_time) {
        return '00:00:00';
      }
      if (!end_time) {
        this.showTime = this.convertTimestamp(begin_time * 1000, new Date().getTime());
        /** 只有故障未恢复状态下才计时 */
        if (status === 'abnormal') {
          this.timer = setInterval(() => {
            if (begin_time) {
              this.showTime = this.convertTimestamp(begin_time * 1000, new Date().getTime());
            }
          }, 1000);
        }
        return this.showTime;
      }
      return this.convertTimestamp(begin_time * 1000, end_time * 1000);
    };
    return (
      <Loading loading={this.listLoading}>
        <div class='failure-header'>
          {this.playLoading && <div class='failure-header-loading' />}
          <i
            class='icon-monitor icon-back-left head-icon'
            onClick={this.handleBack}
          />
          <span class={`header-sign ${this.levelList[level]?.key}`}>
            <i class={`icon-monitor icon-${this.levelList[level]?.key} sign-icon`} />
            {level_alias}
          </span>
          <div class='header-info'>
            <span class='info-id'>{id}</span>
            <div class='info-name'>
              <label
                class='info-name-title mr8'
                title={incident_name}
              >
                {incident_name}
              </label>
              {(labels || []).map((item: any) => (
                <Tag key={item}>{item.replace(/\//g, '')}</Tag>
              ))}
              <span
                class='info-edit'
                onClick={() => {
                  this.isShow = true;
                }}
              >
                <i class='icon-monitor icon-bianji info-edit-icon' />
                {this.t('编辑')}
              </span>
            </div>
          </div>
          <Popover
            width='220'
            extCls='header-status-popover'
            v-slots={{
              content: () => {
                return this.statusTips();
              },
            }}
            disabled={status !== 'abnormal'}
            offset={{ mainAxis: 1, alignmentAxis: 16 }}
            placement='bottom-start'
            theme='light'
          >
            <div class='header-status'>
              <div class='header-status-icon'>{this.renderStatusIcon(status)}</div>
              <span class='status-info'>
                <span class='txt'>{status_alias ? this.t(`${status_alias}`) : '--'}</span>
                <span class='txt'>
                  {this.t('故障持续时间：')}
                  <b>{handleShowTime()}</b>
                </span>
              </span>
            </div>
          </Popover>
          <div class='header-btn-group'>
            <div
              class={['header-btn', { disabled: isRecovered }]}
              v-bk-tooltips={{
                content: status === 'abnormal' ? this.t('故障已恢复，才可以标记已解决') : this.t('故障已解决'),
                disabled: !isRecovered,
                placement: 'bottom',
              }}
              onClick={() => {
                if (!isRecovered) {
                  this.isShowResolve = !this.isShowResolve;
                }
              }}
            >
              <i class='icon-monitor icon-mc-solved btn-icon' />
              {this.t('标记已解决')}
            </div>
            <div
              class='header-btn header-group-btn'
              onClick={() => this.handleChatGroup()}
            >
              <i class='icon-monitor icon-qiye-weixin btn-icon' />
              {this.t('故障群')}
            </div>
          </div>
          <FailureEditDialog
            levelList={this.levelList}
            visible={this.isShow}
            onEditSuccess={this.onEditSuccess}
            onUpdate:isShow={(val: boolean) => {
              this.isShow = val;
            }}
          />
          {this.DialogFn()}
        </div>
        <ChatGroup
          alarmEventName={this.chatGroupDialog.alertName}
          alertIds={this.chatGroupDialog.alertIds}
          assignee={this.chatGroupDialog.assignee}
          data={this.incidentDetailData}
          show={this.chatGroupDialog.show}
          type={'incident'}
          onShowChange={this.chatGroupShowChange}
        />
      </Loading>
    );
  },
});
