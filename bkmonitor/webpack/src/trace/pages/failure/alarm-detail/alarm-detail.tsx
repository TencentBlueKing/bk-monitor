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
import {
  type Ref,
  computed,
  defineComponent,
  inject,
  onBeforeMount,
  onMounted,
  reactive,
  ref,
  watch,
  onUnmounted,
} from 'vue';
import { useI18n } from 'vue-i18n';

import { Exception, Loading, Message, Popover, Table } from 'bkui-vue';
import { $bkPopover } from 'bkui-vue/lib/popover';
import dayjs from 'dayjs';
import { feedbackIncidentRoot, incidentAlertList, incidentRecordOperation } from 'monitor-api/modules/incident';
import { random } from 'monitor-common/utils/utils.js';

import SetMealAdd from '../../../store/modules/set-meal-add';
import StatusTag from '../components/status-tag';
import FeedbackCauseDialog from '../failure-topo/feedback-cause-dialog';
import { useIncidentInject } from '../utils';
import AlarmConfirm from './alarm-confirm';
import AlarmDispatch from './alarm-dispatch';
import ChatGroup from './chat-group/chat-group';
import Collapse from './collapse';
import ManualProcess from './manual-process';
import QuickShield from './quick-shield';

import type { IFilterSearch, IIncident } from '../types';
import type { TableIColumn, TableSettings } from 'bkui-vue/lib/table';

import './alarm-detail.scss';

type PopoverInstance = {
  show: () => void;
  hide: () => void;
  close: () => void;
  [key: string]: any;
};

interface IOpetateRow {
  status?: string;
  is_ack?: boolean;
  ack_operator?: string;
  is_shielded?: boolean;
  shield_operator?: string[];
}
export enum EBatchAction {
  alarmConfirm = 'ack',
  alarmDispatch = 'dispatch',
  quickShield = 'shield',
}
export default defineComponent({
  props: {
    filterSearch: {
      type: Object as () => IFilterSearch,
      default: () => ({}),
    },
    alertIdsObject: {
      type: [Object, String],
      default: () => ({}),
    },
    searchValidate: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['refresh'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    const setMealAddModule = SetMealAdd();
    onBeforeMount(async () => await setMealAddModule.getVariableDataList());
    const scrollLoading = ref(false);
    const incidentId = useIncidentInject();
    const tableLoading = ref(false);
    const tableData = ref([]);
    const alertData = ref([]);
    const currentData = ref({});
    const currentIds = ref([]);
    const currentBizIds = ref([]);
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
              name: '',
            },
          },
        ],
        ids: [],
        bizIds: [],
      },
      alarmConfirm: {
        show: false,
        ids: [],
        bizIds: [],
      },
      rootCauseConfirm: {
        show: false,
        ids: [],
        data: {},
        bizIds: [],
      },
      alarmDispatch: {
        show: false,
        bizIds: [],
        alertIds: [],
        data: {},
      },
      manualProcess: {
        show: false,
        alertIds: [],
        bizIds: [],
        debugKey: random(8),
        actionIds: [],
        mealInfo: null,
      },
    });
    const incidentDetail = inject<Ref<IIncident>>('incidentDetail');
    const incidentDetailData = computed(() => {
      return incidentDetail.value;
    });
    /** 一键拉群弹窗  */
    const chatGroupDialog = reactive({
      show: false,
      alertName: '',
      bizId: [],
      assignee: [],
      alertIds: [],
    });
    const collapseId = ref('');
    const moreItems = ref<HTMLDivElement>();
    const popoperOperateInstance = ref<PopoverInstance>(null);
    const opetateRow = ref<IOpetateRow>({});
    const popoperOperateIndex = ref(-1);
    const hoverRowIndex = ref(999999);
    const tableToolList = ref([]);
    const enableCreateChatGroup = ref((window as any).enable_create_chat_group || false);
    const alertIdsData = ref(props.alertIdsObject);
    if (enableCreateChatGroup.value) {
      tableToolList.value.push({
        id: 'chat',
        name: t('一键拉群'),
      });
    }
    const formatterTime = (time: number | string): string => {
      if (!time) return '--';
      if (typeof time !== 'number') return time;
      if (time.toString().length < 13) return dayjs(time * 1000).format('YYYY-MM-DD HH:mm:ss');
      return dayjs(time).format('YYYY-MM-DD HH:mm:ss');
    };
    const handleQuickShield = v => {
      setDialogData(v);
      dialog.quickShield.show = true;
      dialog.quickShield.details = [
        {
          severity: v.severity,
          dimension: v.dimension_message,
          trigger: v.description,
          strategy: {
            id: v?.strategy_id as unknown as string,
            name: v?.strategy_name,
          },
        },
      ];
      handleHideMoreOperate();
    };
    const handleManualProcess = v => {
      setDialogData(v);
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
      window.__BK_WEWEB_DATA__?.showDetailSlider?.(JSON.parse(JSON.stringify({ ...data })));
    };

    /**
     * @description: 一键拉群
     * @param {*} v
     * @return {*}
     */
    const handleChatGroup = v => {
      const { id, assignee, alert_name, bk_biz_id } = v;
      setDialogData(v);
      chatGroupDialog.assignee = assignee || [];
      chatGroupDialog.alertName = alert_name;
      chatGroupDialog.bizId = [bk_biz_id];
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
    const feedbackIncidentRootApi = (isCancel, data) => {
      const { bk_biz_id } = data;
      const params = {
        id: incidentId.value,
        incident_id: incidentDetailData.value?.incident_id,
        bk_biz_id,
        feedback: {
          incident_root: data.entity.entity_id,
          content: '',
        },
        is_cancel: false,
      };
      if (isCancel) {
        params.is_cancel = true;
      }
      feedbackIncidentRoot(params).then(() => {
        Message({
          theme: 'success',
          message: t('取消反馈成功'),
        });
        incidentRecordOperation({
          incident_id: incidentDetailData.value?.incident_id,
          bk_biz_id,
          operation_type: 'feedback',
          extra_info: {
            feedback_incident_root: '',
            is_cancel: isCancel,
          },
        }).then(res => {
          res && setTimeout(() => emit('refresh'), 2000);
        });
        handleGetTable();
      });
    };
    /** 设置各种操作弹框需要的数据 */
    const setDialogData = data => {
      currentData.value = { ...data, ...{ incident_id: incidentDetailData.value?.incident_id } };
      currentIds.value = [data.id];
      currentBizIds.value = [data.bk_biz_id];
    };
    const handleRootCauseConfirm = v => {
      if (v.entity.is_root) {
        return;
      }
      if (v.is_feedback_root) {
        feedbackIncidentRootApi(true, v);
        return;
      }
      setDialogData(v);
      dialog.rootCauseConfirm.show = true;
    };
    const handleAlertConfirm = v => {
      setDialogData(v);
      dialog.alarmConfirm.show = true;
      handleHideMoreOperate();
    };
    const handleAlarmDispatch = v => {
      setDialogData(v);
      handleAlarmDispatchShowChange(true);
    };
    const handleEnter = (e, row, index) => {
      hoverRowIndex.value = index;
    };
    /* 告警确认文案 */
    const askTipMsg = (isAak, status, ackOperator) => {
      const statusNames = {
        RECOVERED: t('告警已恢复'),
        CLOSED: t('告警已失效'),
      };
      if (!isAak) {
        return statusNames[status];
      }
      return `${ackOperator || ''}${t('已确认')}`;
    };
    const columns = reactive<TableIColumn[]>([
      {
        label: '#',
        type: 'index',
        prop: 'index',
        width: 40,
        minWidth: 40,
        render: ({ index }) => {
          return index + 1;
        },
      },
      {
        label: t('告警ID'),
        prop: 'id',
        width: 'auto',
        render: ({ data }) => {
          return (
            <div class='name-column'>
              <span
                class={`event-status status-${data.severity} id-column`}
                onClick={() => handleShowDetail(data)}
              >
                {data.id}
              </span>
            </div>
          );
        },
      },
      {
        width: 'auto',
        label: t('告警名称'),
        prop: 'alert_name',
        render: ({ data }) => {
          const { entity } = data;
          const isRoot = entity.is_root || data.is_feedback_root;
          return (
            <div class='name-column'>
              <span class={`name-info ${isRoot ? 'name-info-root' : ''}`}>{data.alert_name}</span>
              {isRoot && <span class={`${entity.is_root ? 'root-cause' : 'root-feed'}`}>{t('根因')}</span>}
            </div>
          );
        },
      },
      {
        width: 'auto',
        label: t('业务名称'),
        prop: 'project',
        render: ({ data }) => {
          return `[${data.bk_biz_id}] ${data.bk_biz_name || '--'}`;
        },
      },
      {
        width: 'auto',
        label: t('分类'),
        prop: 'category_display',
        render: ({ data }) => {
          return data.category_display;
        },
      },
      {
        label: t('告警指标'),
        prop: 'index',
        width: 'auto',
        render: ({ data }) => {
          const isEmpty = !data?.metric_display?.length;
          if (isEmpty) return '--';
          const key = random(10);
          const content = (
            <div
              id={key}
              class='tag-column'
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
          );
          return (
            <div class='tag-column-wrap'>
              {/* {content} */}
              <Popover
                extCls='tag-column-popover'
                v-slots={{
                  default: () => content,
                  content: () => content,
                }}
                arrow={true}
                maxWidth={400}
                placement='top'
                theme='light common-table'
              />
            </div>
          );
        },
      },
      {
        label: t('告警状态'),
        prop: 'status',
        minWidth: 134,
        width: '134',
        render: ({ data }) => {
          const { status } = data;
          return (
            <div class='status-column'>
              <StatusTag status={status} />
            </div>
          );
        },
      },
      {
        label: t('告警阶段'),
        width: 'auto',
        prop: 'stage_display',
        render: ({ data }) => {
          return data?.stage_display ?? '--';
        },
      },
      {
        label: t('告警开始/结束时间'),
        prop: 'time',
        minWidth: 145,
        width: '145',
        render: ({ data }) => {
          return (
            <span class='time-column'>
              {formatterTime(data.begin_time)} / <br />
              {formatterTime(data.end_time)}
            </span>
          );
        },
      },
      {
        label: t('持续时间'),
        prop: 'duration',
        width: 136,
        render: ({ data, index: $index }) => {
          return (
            <div class='status-column'>
              <span>{data.duration}</span>
              <div
                style={{
                  display: hoverRowIndex.value === $index || popoperOperateIndex.value === $index ? 'flex' : 'none',
                }}
                class='operate-panel-border'
              />
              <div
                style={{
                  display: hoverRowIndex.value === $index || popoperOperateIndex.value === $index ? 'flex' : 'none',
                }}
                class='operate-panel'
              >
                <span
                  class={['operate-panel-item', { 'is-disable': data.entity.is_root }]}
                  v-bk-tooltips={{
                    content: t(data.is_feedback_root ? '取消反馈根因' : '反馈根因'),
                    trigger: 'hover',
                    delay: 200,
                    disabled: data.entity.is_root,
                  }}
                  onClick={() => handleRootCauseConfirm(data)}
                >
                  <i
                    class={[
                      'icon-monitor',
                      !data.is_feedback_root ? 'icon-fankuixingenyin' : 'icon-mc-cancel-feedback',
                    ]}
                  />
                </span>
                <span
                  class='operate-panel-item'
                  v-bk-tooltips={{ content: t('告警分派'), delay: 200, appendTo: 'parent' }}
                  onClick={() => handleAlarmDispatch(data)}
                >
                  <i class='icon-monitor icon-fenpai' />
                </span>
                <span
                  class={['operate-more', { active: popoperOperateIndex.value === $index }]}
                  onClick={e => handleShowMoreOperate(e, $index, data)}
                >
                  <span class='icon-monitor icon-mc-more' />
                </span>
              </div>
            </div>
          );
        },
      },
    ]);

    const settings = ref<TableSettings>({
      fields: columns.slice(1, columns.length - 1).map(data => {
        const { label, prop } = data as { label: string; prop: string };
        return {
          label,
          disabled: prop === 'id',
          field: prop,
        };
      }),
      checked: columns.slice(1, columns.length - 1).map(({ prop }) => prop as string),
      trigger: 'manual' as const,
    });
    const getMoreOperate = () => {
      const { status, is_ack: isAck, ack_operator: ackOperator } = opetateRow.value;
      return (
        <div style={{ display: 'none' }}>
          <div
            ref='moreItems'
            class='alarm-detail-table-options-more-items'
          >
            <div
              class={['more-item', { 'is-disable': false }]}
              onClick={() => handleChatGroup(opetateRow.value)}
            >
              <span class='icon-monitor icon-we-com' />
              <span>{window.i18n.t('一键拉群')}</span>
            </div>
            <div
              class={['more-item', { 'is-disable': isAck || ['RECOVERED', 'CLOSED'].includes(status) }]}
              v-bk-tooltips={{
                disabled: !(isAck || ['RECOVERED', 'CLOSED'].includes(status)),
                content: askTipMsg(isAck, status, ackOperator),
                delay: 200,
                appendTo: 'parent',
                zIndex: 9999999,
              }}
              onClick={() =>
                !isAck && !['RECOVERED', 'CLOSED'].includes(status) && handleAlertConfirm(opetateRow.value)
              }
            >
              <span class='icon-monitor icon-duihao' />
              <span>{window.i18n.t('告警确认')}</span>
            </div>
            <div
              class={['more-item', { 'is-disable': false }]}
              onClick={() => handleManualProcess(opetateRow.value)}
            >
              <span class='icon-monitor icon-chuli' />
              <span>{window.i18n.t('手动处理')}</span>
            </div>
            <div
              class={['more-item', { 'is-disable': opetateRow.value?.is_shielded }]}
              v-bk-tooltips={{
                disabled: !opetateRow.value?.is_shielded,
                content: opetateRow?.value?.is_shielded
                  ? `${opetateRow?.value.shield_operator?.[0] || ''}${t('已屏蔽')}`
                  : '',
                delay: 200,
                appendTo: () => document.body,
              }}
              onClick={() => !opetateRow.value?.is_shielded && handleQuickShield(opetateRow.value)}
            >
              <span class='icon-monitor icon-mc-notice-shield' />
              <span>{window.i18n.t('快捷屏蔽')}</span>
            </div>
          </div>
        </div>
      );
    };
    const handleHideMoreOperate = (e?: Event) => {
      if (!popoperOperateInstance.value) {
        return;
      }
      if (e) {
        const { classList } = e.target as HTMLElement;
        if (classList.contains('icon-mc-more') || classList.contains('operate-more')) {
          return;
        }
      }
      popoperOperateInstance.value.hide();
      popoperOperateInstance.value.close();
      popoperOperateInstance.value = null;
      popoperOperateIndex.value = -1;
    };
    const handleShowMoreOperate = (e, index, data) => {
      popoperOperateIndex.value = index;
      opetateRow.value = data;
      if (!popoperOperateInstance.value) {
        popoperOperateInstance.value = $bkPopover({
          target: e.target,
          content: moreItems.value,
          arrow: false,
          trigger: 'manual',
          placement: 'bottom',
          theme: 'light common-monitor',
          width: 120,
          extCls: 'alarm-detail-table-more-popover',
          disabled: false,
          isShow: true,
          always: false,
          height: 'auto',
          maxWidth: '120',
          maxHeight: 'auto',
          allowHtml: false,
          renderType: 'auto',
          padding: 0,
          offset: 0,
          zIndex: 10,
          disableTeleport: false,
          autoPlacement: false,
          autoVisibility: false,
          disableOutsideClick: false,
          disableTransform: false,
          modifiers: [],
          popoverDelay: 20,
          componentEventDelay: 0,
          forceClickoutside: false,
          immediate: false,
        });
        popoperOperateInstance.value.install();
        setTimeout(() => {
          popoperOperateInstance.value?.vm?.show();
        }, 100);
      } else {
        popoperOperateInstance.value.update(e.target, {
          target: e.target,
          content: moreItems.value,
        });
      }
    };
    const handleLoadData = () => {
      // scrollLoading.value = true;
      //   scrollLoading.value = false;
    };
    const handleConfirmAfter = () => {};
    const alarmConfirmChange = v => {
      dialog.alarmConfirm.show = v;
      handleGetTable();
    };
    const handleAlarmDispatchShowChange = v => {
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
        // tableData.value.value.forEach(item => {
        //   if (dialog.quickShield.ids.includes(item.id)) {
        //     item.is_shielded = true;
        //     item.shield_operator = [window.username || window.user_name];
        //   }
        //     key
        //   }
        // };
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
    };
    const handleGetTable = async () => {
      tableLoading.value = true;
      const queryString = typeof alertIdsData.value === 'object' ? alertIdsData.value?.ids || '' : alertIdsData.value;
      const params = {
        bk_biz_ids: bkzIds.value || [],
        id: incidentId.value,
        query_string: queryString,
      };
      const data = await incidentAlertList(params);
      // const data = await incidentAlertList(Object.assign(params, props.filterSearch));
      tableLoading.value = false;
      alertData.value = data;
      // const list = alertData.value.find(item => item.alerts.length > 0);
      // collapseId.value = list ? list.id : '';n
    };
    onMounted(() => {
      props.searchValidate && handleGetTable();
      document.body.addEventListener('click', handleHideMoreOperate);
    });
    onUnmounted(() => {
      handleHideMoreOperate();
      document.body.removeEventListener('click', handleHideMoreOperate);
    });
    const handleAlarmDispatchSuccess = () => {};
    const handleChangeCollapse = ({ id, isCollapse }) => {
      if (isCollapse) {
        collapseId.value = null;
        return;
      }
      collapseId.value = id;
    };

    const handleSettingChange = ({ checked }) => {
      console.log(checked, settings.value);
    };
    const handleFeedbackChange = (val: boolean) => {
      dialog.rootCauseConfirm.show = val;
    };
    // const closeTag = () => {
    //   alertIdsData.value = {};
    //   handleGetTable();
    // };
    const refresh = () => {
      emit('refresh');
    };
    watch(
      () => props.alertIdsObject,
      val => {
        alertIdsData.value = val;
        props.searchValidate && handleGetTable();
      },
      { deep: true }
    );
    return {
      t,
      alertData,
      moreItems,
      collapseId,
      dialog,
      opetateRow,
      tableLoading,
      hoverRowIndex,
      columns,
      tableData,
      scrollLoading,
      chatGroupDialog,
      settings,
      handleSettingChange,
      quickShieldChange,
      getMoreOperate,
      handleChangeCollapse,
      alarmConfirmChange,
      quickShieldSucces,
      handleConfirmAfter,
      handleFeedbackChange,
      handleRootCauseConfirm,
      handleAlarmDispatchShowChange,
      manualProcessShowChange,
      chatGroupShowChange,
      handleMealInfo,
      handleLoadData,
      handleAlarmDispatchSuccess,
      handleDebugStatus,
      handleEnter,
      handleGetTable,
      alertIdsData,
      // closeTag,
      incidentDetailData,
      currentData,
      currentIds,
      currentBizIds,
      refresh,
    };
  },
  render() {
    const alertData = this.alertData.filter(item => item.alerts.length > 0);
    return (
      <>
        <Loading loading={this.tableLoading}>
          <div class='alarm-detail bk-scroll-y'>
            {/* {this.alertIdsData?.label && (
              <Tag
                style={{ marginBottom: '10px' }}
                theme='info'
                closable
                onClose={this.closeTag}
              >
                {this.alertIdsData.label}
              </Tag>
            )} */}
            <FeedbackCauseDialog
              data={this.currentData}
              visible={this.dialog.rootCauseConfirm.show}
              onEditSuccess={this.handleGetTable}
              onRefresh={this.refresh}
              onUpdate:isShow={this.handleFeedbackChange}
            />
            <ChatGroup
              alarmEventName={this.chatGroupDialog.alertName}
              alertIds={this.chatGroupDialog.alertIds}
              assignee={this.chatGroupDialog.assignee}
              data={this.currentData}
              show={this.chatGroupDialog.show}
              onRefresh={this.refresh}
              onShowChange={this.chatGroupShowChange}
            />
            <QuickShield
              bizIds={this.currentBizIds}
              data={this.currentData}
              details={this.dialog.quickShield.details}
              ids={this.currentIds}
              show={this.dialog.quickShield.show}
              onChange={this.quickShieldChange}
              onRefresh={this.refresh}
              onSuccess={this.quickShieldSucces}
            />
            <ManualProcess
              alertIds={this.currentIds}
              bizIds={this.currentBizIds}
              data={this.currentData}
              show={this.dialog.manualProcess.show}
              onDebugStatus={this.handleDebugStatus}
              onMealInfo={this.handleMealInfo}
              onRefresh={this.refresh}
              onShowChange={this.manualProcessShowChange}
            />
            <AlarmDispatch
              alertIds={this.currentIds}
              bizIds={this.currentBizIds}
              data={this.currentData}
              show={this.dialog.alarmDispatch.show}
              onRefresh={this.refresh}
              onShow={this.handleAlarmDispatchShowChange}
              onSuccess={this.handleAlarmDispatchSuccess}
            />
            <AlarmConfirm
              bizIds={this.currentBizIds}
              data={this.currentData}
              ids={this.currentIds}
              show={this.dialog.alarmConfirm.show}
              onChange={this.alarmConfirmChange}
              onConfirm={this.handleConfirmAfter}
              onRefresh={this.refresh}
            />
            {this.getMoreOperate()}
            {this.alertData.map(item => {
              return item.alerts.length > 0 ? (
                <Collapse
                  id={item.id}
                  key={item.id}
                  collapse={this.collapseId !== item.id}
                  num={item.alerts.length}
                  title={item.name}
                  onChangeCollapse={this.handleChangeCollapse}
                >
                  <div class='alarm-detail-table'>
                    <Table
                      columns={this.columns}
                      data={item.alerts}
                      max-height={616}
                      scroll-loading={this.scrollLoading}
                      settings={this.settings}
                      show-overflow-tooltip={true}
                      onRowMouseEnter={this.handleEnter}
                      onRowMouseLeave={() => {
                        this.hoverRowIndex = -1;
                      }}
                      onSettingChange={this.handleSettingChange}
                      // onScrollBottom={this.handleLoadData}
                    />
                  </div>
                </Collapse>
              ) : (
                ''
              );
            })}
            {alertData.length === 0 && (
              <Exception
                description={this.t('搜索数据为空')}
                scene='part'
                type='empty'
              />
            )}
          </div>
        </Loading>
      </>
    );
  },
});
