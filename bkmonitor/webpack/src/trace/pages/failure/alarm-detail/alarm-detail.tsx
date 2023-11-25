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
import { defineComponent, onBeforeMount, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Table } from 'bkui-vue';
import { $bkPopover } from 'bkui-vue/lib/popover';

import { random } from '../../../../monitor-common/utils/utils.js';
import SetMealAdd from '../../../store/modules/set-meal-add';

import ChatGroup from './chat-group/chat-group';
import AlarmConfirm from './alarm-confirm';
import AlarmDispatch from './alarm-dispatch';
import Collapse from './collapse';
import ManualProcess from './manual-process';
import QuickShield from './quick-shield';

import './alarm-detail.scss';

export enum EBatchAction {
  quickShield = 'shield',
  alarmConfirm = 'ack',
  alarmDispatch = 'dispatch'
}
export default defineComponent({
  setup() {
    const { t } = useI18n();
    const setMealAddModule = SetMealAdd();
    onBeforeMount(async () => await setMealAddModule.getVariableDataList());
    const eventStatusMap = {
      ABNORMAL: {
        color: '#EA3536',
        bgColor: '#FEEBEA',
        name: t('未恢复'),
        icon: 'icon-mind-fill'
      },
      RECOVERED: {
        color: '#14A568',
        bgColor: '#E4FAF0',
        name: t('已恢复')
      },
      CLOSED: {
        color: '#63656E',
        bgColor: '#F0F1F5',
        name: t('已关闭')
      }
    };
    const scrollLoading = ref(false);
    const queryString = ref('');
    const dialog = reactive({
      quickShield: {
        show: false,
        details: [
          {
            severity: 1,
            dimension: '',
            trigger: '',
            strategy: {
              id: '',
              name: ''
            }
          }
        ],
        ids: [],
        bizIds: []
      },
      alarmConfirm: {
        show: false,
        ids: [],
        bizIds: []
      },
      rootCauseConfirm: {
        show: false,
        ids: [],
        bizIds: []
      },
      alarmDispatch: {
        show: false,
        bizIds: [],
        alertIds: []
      },
      manualProcess: {
        show: false,
        alertIds: [],
        bizIds: [],
        debugKey: random(8),
        actionIds: [],
        mealInfo: null
      }
    });
    /** 一键拉群弹窗 */
    const chatGroupDialog = reactive({
      show: false,
      alertName: '',
      assignee: [],
      alertIds: []
    });
    const moreItems = ref(null);
    const popoperOperateInstance = ref(null);
    const opetateRow = ref({});
    const popoperOperateIndex = ref(-1);
    const hoverRowIndex = ref(0);
    const tableToolList = ref([]);
    const enableCreateChatGroup = ref((window as any).enable_create_chat_group || false);
    if (enableCreateChatGroup.value) {
      tableToolList.value.push({
        id: 'chat',
        name: t('一键拉群')
      });
    }
    const handleQuickShield = v => {
      dialog.quickShield.bizIds = [v.bk_biz_id];
      dialog.quickShield.show = true;
      dialog.quickShield.ids = [v.id];
      dialog.quickShield.details = [
        {
          severity: v.severity,
          dimension: v.dimension_message,
          trigger: v.description,
          strategy: {
            id: v?.strategy_id as unknown as string,
            name: v?.strategy_name
          }
        }
      ];
      handleHideMoreOperate();
    };
    const handleManualProcess = v => {
      console.log(v);
      dialog.manualProcess.alertIds = [v.id] as any;
      dialog.manualProcess.bizIds = [2]; // [v.bk_biz_id];
      manualProcessShowChange(true);
      handleHideMoreOperate();
    };
    /**
     * @description: 手动处理
     * @param {*} v
     * @return {*}
     */
    const manualProcessShowChange = (v: boolean) => {
      dialog.manualProcess.show = v;
    };
    const handleShowDetail = data => {
      console.log(data);
    };

    /**
     * @description: 一键拉群
     * @param {*} v
     * @return {*}
     */
    const handleChatGroup = v => {
      const { id, assignee, alert_name } = v;
      chatGroupDialog.assignee = assignee || [];
      chatGroupDialog.alertName = alert_name;
      chatGroupDialog.alertIds.splice(0, chatGroupDialog.alertIds.length, id);
      chatGroupShowChange(true);
      handleHideMoreOperate();
    };
    /**
     * @description: 一键拉群弹窗关闭/显示
     * @param {boolean} show
     * @return {*}
     */
    const chatGroupShowChange = (show: boolean) => {
      chatGroupDialog.show = show;
    };
    const handleRootCauseConfirm = v => {
      dialog.rootCauseConfirm.ids = [v.id];
      dialog.rootCauseConfirm.bizIds = [v.bk_biz_id];
      dialog.rootCauseConfirm.show = true;
    };
    const handleAlertConfirm = v => {
      dialog.alarmConfirm.ids = [v.id];
      dialog.alarmConfirm.bizIds = [v.bk_biz_id];
      dialog.alarmConfirm.show = true;
      handleHideMoreOperate();
    };
    const handleAlarmDispatch = v => {
      dialog.alarmDispatch.alertIds = [v.id] as any;
      dialog.alarmDispatch.bizIds = [v.bk_biz_id];
      handleAlarmDispatchShowChange(true);
    };
    const handleEnter = (e, row, index) => {
      hoverRowIndex.value = index;
    };
    /* 告警确认文案 */
    const askTipMsg = (isAak, status, ackOperator) => {
      const statusNames = {
        RECOVERED: t('告警已恢复'),
        CLOSED: t('告警已关闭')
      };
      if (!isAak) {
        return statusNames[status];
      }
      return `${ackOperator || ''}${t('已确认')}`;
    };
    const columns = reactive([
      {
        label: '#',
        type: 'index'
      },
      {
        label: t('告警ID'),
        field: 'id',
        render: ({ data }) => {
          return (
            <span
              class={`event-status status-${data.severity} id-column`}
              onClick={() => handleShowDetail(data)}
            >
              {data.id}
            </span>
          );
        }
      },
      {
        label: t('告警名称'),
        field: 'name',
        render: ({ data }) => {
          return (
            <span class='name-column'>
              {data.name}
              {/* <span class='root-cause'>{t('根因')}</span> */}
            </span>
          );
        }
      },
      {
        label: t('业务名称'),
        filed: 'project'
      },
      {
        label: t('分类'),
        filed: 'type'
      },
      {
        label: t('告警指标'),
        filed: 'index',
        render: ({ data }) => {
          const isEmpt = !data?.metric_display?.length;
          if (isEmpt) return '--';
          const key = random(10);
          return (
            <div class='tag-column-wrap'>
              <div
                class='tag-column'
                id={key}
                v-bk-tooltip={{
                  allowHTML: true,
                  theme: 'light common-table',
                  interactive: true
                }}
              >
                {data.metric_display.map(item => (
                  <div
                    key={item.id}
                    class='tag-item set-item'
                  >
                    {item.name || item.id}
                  </div>
                ))}
              </div>
            </div>
          );
        }
      },
      {
        label: t('告警状态'),
        filed: 'status',
        minWidth: 134,
        render: ({ data }) => {
          // is_ack: isAck, ack_operator: ackOperator
          const { status } = data;
          return (
            <div class='status-column'>
              <span
                class='status-label'
                style={{
                  color: eventStatusMap?.[status]?.color,
                  backgroundColor: eventStatusMap?.[status]?.bgColor
                }}
              >
                {eventStatusMap?.[status]?.icon ? (
                  <i
                    style={{ color: eventStatusMap?.[status]?.color }}
                    class={['icon-monitor item-icon', eventStatusMap?.[status]?.icon ?? '']}
                  ></i>
                ) : (
                  ''
                )}
                {eventStatusMap?.[status]?.name || '--'}
              </span>
            </div>
          );
        }
      },
      {
        label: t('告警阶段'),
        filed: 'stage_display',
        render: ({ data }) => {
          return data?.stage_display ?? '--';
        }
      },
      {
        label: t('告警开始/结束时间'),
        filed: 'time',
        render: ({ data }) => {
          console.log(data, '...');
          return (
            <span class='time-column'>
              {data.start_time}/ <br></br>
              {data.start_time}
            </span>
          );
        }
      },
      {
        label: t('持续时间'),
        filed: 'project',
        width: 136,
        render: ({ data, index: $index }) => {
          const { status, is_ack: isAck, ack_operator: ackOperator } = data;
          return (
            <div class='status-column'>
              <span>{data.chixu}</span>
              <div
                class='operate-panel'
                style={{
                  display:
                    'flex' || hoverRowIndex.value === $index || popoperOperateIndex.value === $index ? 'flex' : 'none'
                }}
              >
                <span
                  class={['operate-panel-item']}
                  onClick={() => handleRootCauseConfirm(data)}
                  v-bk-tooltips={{
                    content: t(data.fankui ? '反馈根因' : '取消反馈根因'),
                    trigger: 'hover',
                    delay: 200
                  }}
                >
                  <i class={['icon-monitor', data.fankui ? 'icon-fankuixingenyin' : 'icon-mc-cancel-feedback']}></i>
                </span>
                <span
                  class='operate-panel-item'
                  onClick={() => handleAlarmDispatch(data)}
                  v-bk-tooltips={{ content: t('告警分派'), delay: 200, appendTo: 'parent' }}
                >
                  <i class='icon-monitor icon-fenpai'></i>
                </span>
                <span
                  class={['operate-more', { active: popoperOperateIndex.value === $index }]}
                  onClick={e => handleShowMoreOperate(e, $index)}
                >
                  <span class='icon-monitor icon-mc-more'></span>
                </span>
              </div>
            </div>
          );
        }
      }
    ]);
    const tableData = reactive([{ xx: 1 }]);
    const getMoreOperate = () => {
      return (
        <div style={{ display: 'none' }}>
          <div
            class='alarm-detail-table-options-more-items'
            ref='moreItems'
          >
            <div
              class={['more-item', { 'is-disable': false }]}
              onClick={() => handleChatGroup(opetateRow.value)}
            >
              <span class='icon-monitor icon-we-com'></span>
              <span>{window.i18n.t('一键拉群')}</span>
            </div>
            <div
              class={['more-item', { 'is-disable': false }]}
              onClick={() => handleAlertConfirm(opetateRow.value)}
            >
              <span class='icon-monitor icon-duihao'></span>
              <span>{window.i18n.t('告警确认')}</span>
            </div>
            <div
              class={['more-item', { 'is-disable': false }]}
              onClick={() => handleManualProcess(opetateRow.value)}
            >
              <span class='icon-monitor icon-chuli'></span>
              <span>{window.i18n.t('手动处理')}</span>
            </div>
            <div
              class={['more-item', { 'is-disable': false }]}
              // v-bk-tooltips={{
              //   content: opetateRow?.value?.is_shielded
              //     ? `${opetateRow?.value.shield_operator?.[0] || ''}${this.$t('已屏蔽')}`
              //     : '',
              //   delay: 200,
              //   appendTo: () => document.body
              // }}
              onClick={() => handleQuickShield(opetateRow.value)}
            >
              <span class='icon-monitor icon-mc-notice-shield'></span>
              <span>{window.i18n.t('快捷屏蔽')}</span>
            </div>
          </div>
        </div>
      );
    };
    const handleHideMoreOperate = () => {
      popoperOperateInstance.value.hide();
      popoperOperateInstance.value.close();
      popoperOperateInstance.value = null;
      popoperOperateIndex.value = -1;
    };
    const handleShowMoreOperate = (e, index) => {
      console.log(moreItems, moreItems.value);
      popoperOperateIndex.value = index;
      opetateRow.value = tableData[index];
      if (!popoperOperateInstance.value) {
        popoperOperateInstance.value = $bkPopover({
          target: e.target,
          content: moreItems.value,
          arrow: false,
          trigger: 'click',
          placement: 'bottom',
          theme: 'light common-monitor',
          width: 120,
          extCls: 'alarm-detail-table-more-popover',
          onAfterHidden: () => {
            popoperOperateInstance.value.destroy();
            popoperOperateInstance.value = null;
            popoperOperateIndex.value = -1;
          }
        });
      }
      setTimeout(popoperOperateInstance.value.show, 100);
    };
    const handleLoadData = () => {
      // scrollLoading.value = true;
      //   scrollLoading.value = false;
    };
    const handleConfirmAfter = v => {};
    const alarmConfirmChange = v => {
      dialog.alarmConfirm.show = v;
    };
    const handleAlarmDispatchShowChange = v => {
      console.log('handleAlarmDispatchShowChange', v);
      dialog.alarmDispatch.show = v;
    };
    /* 手动处理轮询状态 */
    const handleDebugStatus = (actionIds: number[]) => {
      dialog.manualProcess.actionIds = actionIds;
      dialog.manualProcess.debugKey = random(8);
    };
    const handleMealInfo = (mealInfo: { name: string }) => {
      dialog.manualProcess.mealInfo = mealInfo;
    };
    /**
     * @description: 屏蔽成功
     * @param {boolean} v
     * @return {*}
     */
    const quickShieldSucces = (v: boolean) => {
      if (v) {
        // tableData.value.forEach(item => {
        //   if (dialog.quickShield.ids.includes(item.id)) {
        //     item.is_shielded = true;
        //     item.shield_operator = [window.username || window.user_name];
        //   }
        // });
      }
    };
    /* 搜索条件包含action_id 且 打开批量搜索则更新url状态 */
    const batchUrlUpdate = (type: EBatchAction | '') => {
      return;
      if (/(^action_id).+/g.test(queryString.value) || !type) {
        const key = random(10);
        const params = {
          name: this.$route.name,
          query: {
            ...handleParam2Url(),
            batchAction: type || undefined,
            key
          }
        };
        // this.$router.replace(params);
        // this.routeStateKeyList.push(key);
      }
    };
    /**
     * @description: 快捷屏蔽
     * @param {boolean} v
     * @return {*}
     */
    const quickShieldChange = (v: boolean) => {
      dialog.quickShield.show = v;
      if (!v) {
        batchUrlUpdate('');
      }
    };
    const handleAlarmDispatchSuccess = data => {
      // tableData.forEach(item => {
      //   if (data.ids.includes(item.id)) {
      //     if (item.appointee) {
      //       const usersSet = new Set();
      //       item.appointee.concat(data.users).forEach(u => {
      //         usersSet.add(u);
      //       });
      //       item.appointee = Array.from(usersSet) as string[];
      //     } else {
      //       item.appointee = data.users;
      //     }
      //   }
      // });
    };
    return {
      moreItems,
      dialog,
      hoverRowIndex,
      columns,
      tableData,
      scrollLoading,
      chatGroupDialog,
      quickShieldChange,
      getMoreOperate,
      alarmConfirmChange,
      quickShieldSucces,
      handleConfirmAfter,
      handleRootCauseConfirm,
      handleAlarmDispatchShowChange,
      manualProcessShowChange,
      chatGroupShowChange,
      handleMealInfo,
      handleLoadData,
      handleAlarmDispatchSuccess,
      handleDebugStatus,
      handleEnter
    };
  },
  render() {
    return (
      <div class='alarm-detail'>
        <ChatGroup
          show={this.chatGroupDialog.show}
          assignee={this.chatGroupDialog.assignee}
          alarmEventName={this.chatGroupDialog.alertName}
          alertIds={this.chatGroupDialog.alertIds}
          onShowChange={this.chatGroupShowChange}
        />
        <QuickShield
          details={this.dialog.quickShield.details}
          ids={this.dialog.quickShield.ids}
          bizIds={this.dialog.quickShield.bizIds}
          show={this.dialog.quickShield.show}
          onChange={this.quickShieldChange}
          onSucces={this.quickShieldSucces}
        ></QuickShield>
        <ManualProcess
          show={this.dialog.manualProcess.show}
          bizIds={this.dialog.manualProcess.bizIds}
          alertIds={this.dialog.manualProcess.alertIds}
          onShowChange={this.manualProcessShowChange}
          onDebugStatus={this.handleDebugStatus}
          onMealInfo={this.handleMealInfo}
        ></ManualProcess>
        <AlarmDispatch
          show={this.dialog.alarmDispatch.show}
          alertIds={this.dialog.alarmDispatch.alertIds}
          bizIds={this.dialog.alarmDispatch.bizIds}
          onShow={this.handleAlarmDispatchShowChange}
          onSuccess={this.handleAlarmDispatchSuccess}
        ></AlarmDispatch>
        <AlarmConfirm
          show={this.dialog.alarmConfirm.show}
          ids={this.dialog.alarmConfirm.ids}
          bizIds={this.dialog.alarmConfirm.bizIds}
          onConfirm={this.handleConfirmAfter}
          onChange={this.alarmConfirmChange}
        ></AlarmConfirm>
        {this.getMoreOperate()}
        <Collapse title='用户体验'>
          <div class='alarm-detail-table'>
            <Table
              columns={this.columns}
              data={this.tableData}
              max-height={616}
              scroll-loading={this.scrollLoading}
              onRowMouseEnter={this.handleEnter}
              onRowMouseLeave={() => (this.hoverRowIndex = -1)}
              onScrollBottom={this.handleLoadData}
            ></Table>
          </div>
        </Collapse>
      </div>
    );
  }
});
