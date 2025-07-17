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
  ref as deepRef,
  watch,
  onUnmounted,
  shallowRef,
} from 'vue';
import { useI18n } from 'vue-i18n';

import { PrimaryTable } from '@blueking/tdesign-ui';
import { Exception, Loading, Message, Popover } from 'bkui-vue';
import { $bkPopover } from 'bkui-vue/lib/popover';
import dayjs from 'dayjs';
import {
  feedbackIncidentRoot,
  incidentAlertList,
  incidentRecordOperation,
  incidentValidateQueryString,
} from 'monitor-api/modules/incident';
import { random } from 'monitor-common/utils/utils.js';

import SetMealAdd from '../../../store/modules/set-meal-add';
import StatusTag from '../components/status-tag';
import FeedbackCauseDialog from '../failure-topo/feedback-cause-dialog';
import { useIncidentInject } from '../utils';
import { replaceSpecialCondition } from '../utils';
import AlarmConfirm from './alarm-confirm';
import AlarmDispatch from './alarm-dispatch';
import ChatGroup from './chat-group/chat-group';
import Collapse from './collapse';
import ManualProcess from './manual-process';
import QuickShield from './quick-shield';

import type { IFilterSearch, IIncident } from '../types';

import './alarm-detail.scss';

type TableColumn = Record<string, any>;

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
    const scrollLoading = deepRef(false);
    const incidentId = useIncidentInject();
    const tableLoading = deepRef(false);
    const tableData = deepRef([]);
    const alertData = deepRef([]);
    const currentData = deepRef({});
    const currentIds = deepRef([]);
    const currentBizIds = deepRef([]);
    const disableKey = ['serial-number', 'project', 'category_display'];
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
    const collapseId = deepRef('');
    const moreItems = deepRef<HTMLDivElement>();
    const popoperOperateInstance = deepRef<PopoverInstance>(null);
    const opetateRow = deepRef<IOpetateRow>({});
    const popoperOperateIndex = deepRef(-1);
    const hoverRowIndex = deepRef(999999);
    const tableToolList = deepRef([]);
    const enableCreateChatGroup = deepRef((window as any).enable_create_chat_group || false);
    const alertIdsData = deepRef(props.alertIdsObject);
    const alarmDetailRef = deepRef(null);
    const alarmDetailHeight = deepRef(0);
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
    const handleEnter = ({ index }) => {
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
    const columns = shallowRef<TableColumn[]>([
      {
        title: '#',
        type: 'seq',
        colKey: 'serial-number',
        minWidth: 40,
        disabled: true,
        checked: true,
      },
      {
        title: t('告警ID'),
        colKey: 'id',
        minWidth: 134,
        ellipsis: {
          popperOptions: {
            strategy: 'fixed',
          },
        },
        fixed: 'left',
        disabled: true,
        cell: (_, { row: data }) => {
          return (
            <div
              class='name-column'
              v-bk-tooltips={{
                content: data.id,
                delay: 200,
                boundary: 'window',
                extCls: 'alarm-detail-table-tooltip',
              }}
            >
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
        title: t('告警名称'),
        colKey: 'alert_name',
        minWidth: 134,
        fixed: 'left',
        ellipsis: {
          popperOptions: {
            strategy: 'fixed',
          },
        },
        cell: (_, { row: data }) => {
          const { entity } = data;
          const isRoot = entity?.is_root || data.is_feedback_root;
          return (
            <div
              class='name-column'
              v-bk-tooltips={{
                content: data.alert_name,
                delay: 200,
                boundary: 'window',
                extCls: 'alarm-detail-table-tooltip',
              }}
            >
              <span class={`name-info ${isRoot ? 'name-info-root' : ''}`}>{data.alert_name}</span>
              {isRoot && <span class={`${entity.is_root ? 'root-cause' : 'root-feed'}`}>{t('根因')}</span>}
            </div>
          );
        },
      },
      {
        title: t('业务名称'),
        colKey: 'project',
        width: 157,
        ellipsis: {
          popperOptions: {
            strategy: 'fixed',
          },
        },
        minWidth: 60,
        cell: (_, { row: data }) => {
          return data.bk_biz_name || '--';
        },
      },
      {
        title: t('分类'),
        colKey: 'category_display',
        width: 134,
        minWidth: 60,
        ellipsis: {
          popperOptions: {
            strategy: 'fixed',
          },
        },
        cell: (_, { row: data }) => {
          return data.category_display;
        },
      },
      {
        title: t('告警指标'),
        colKey: 'index',
        minWidth: 134,
        ellipsis: {
          popperOptions: {
            strategy: 'fixed',
          },
        },
        cell: (_, { row: data }) => {
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
        title: t('告警状态'),
        colKey: 'status',
        minWidth: 134,
        ellipsis: {
          popperOptions: {
            strategy: 'fixed',
          },
        },
        cell: (_, { row: data }) => {
          const { status } = data;
          return (
            <div class='status-column'>
              <StatusTag status={status} />
            </div>
          );
        },
      },
      {
        title: t('告警阶段'),
        colKey: 'stage_display',
        minWidth: 80,
        ellipsis: {
          popperOptions: {
            strategy: 'fixed',
          },
        },
        cell: (_, { row: data }) => {
          return data?.stage_display ?? '--';
        },
      },
      {
        title: t('告警开始/结束时间'),
        colKey: 'time',
        minWidth: 145,
        ellipsis: {
          popperOptions: {
            strategy: 'fixed',
          },
        },
        cell: (_, { row: data }) => {
          return (
            <span class='time-column'>
              {formatterTime(data.begin_time)} / <br />
              {formatterTime(data.end_time)}
            </span>
          );
        },
      },
      {
        title: t('持续时间'),
        colKey: 'duration',
        width: 155,
        minWidth: 155,
        fixed: 'right',
        ellipsis: (_, { row: data }) => {
          return data.duration;
        },
        resizable: false,
        className: 'duration-class',
        cell: (_, { row: data, rowIndex: $index }) => {
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
                {!!data.entity && (
                  <span
                    class={['operate-panel-item', { 'is-disable': data.entity?.is_root }]}
                    v-bk-tooltips={{
                      content: t(data.is_feedback_root ? '取消反馈根因' : '反馈根因'),
                      trigger: 'hover',
                      delay: 200,
                      disabled: data.entity?.is_root,
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
                )}
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
          offset: 10,
          zIndex: 100,
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
    const quickShieldSuccess = (v: boolean) => {
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
    const handleGetTable = () => {
      tableLoading.value = true;
      const queryString = typeof alertIdsData.value === 'object' ? alertIdsData.value?.ids || '' : alertIdsData.value;
      const params = {
        bk_biz_ids: bkzIds.value || [],
        id: incidentId.value,
        query_string: queryString,
      };
      incidentAlertList(params)
        .then(res => {
          tableLoading.value = false;
          alertData.value = res;
        })
        .catch(() => {
          tableLoading.value = false;
          alertData.value = [];
        });
      // const data = await incidentAlertList(Object.assign(params, props.filterSearch));

      // const list = alertData.value.find(item => item.alerts.length > 0);
      // collapseId.value = list ? list.id : '';n
    };
    onMounted(() => {
      if (alarmDetailRef.value) {
        alarmDetailHeight.value = alarmDetailRef.value.offsetHeight;
      }
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
      async val => {
        alertIdsData.value = val;
        const validate = await incidentValidateQueryString(
          { query_string: replaceSpecialCondition(alertIdsData.value?.ids), search_type: 'incident' },
          { needMessage: false, needRes: true }
        )
          .then(res => res.result)
          .catch(() => false);
        validate && handleGetTable();
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
      quickShieldChange,
      getMoreOperate,
      handleChangeCollapse,
      alarmConfirmChange,
      quickShieldSuccess,
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
      disableKey,
      alarmDetailRef,
      alarmDetailHeight,
    };
  },
  render() {
    const alertData = this.alertData.filter(item => item.alerts.length > 0);
    return (
      <>
        <Loading
          class='alarm-detail-loading'
          loading={this.tableLoading}
        >
          <div
            ref='alarmDetailRef'
            class='alarm-detail bk-scroll-y'
          >
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
              onSuccess={this.quickShieldSuccess}
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
                    <PrimaryTable
                      key={item.id}
                      bkUiSettings={{
                        checked: this.columns
                          .filter(item => !this.disableKey.includes(item.colKey))
                          .map(item => item.colKey),
                      }}
                      // autoResize={true}
                      // bordered={true}
                      columns={this.columns}
                      data={item.alerts}
                      maxHeight={alertData.length > 1 ? 616 : this.alarmDetailHeight - 100}
                      tooltip-config={{ showAll: false }}
                      onRowMouseenter={this.handleEnter}
                      onRowMouseleave={() => {
                        this.hoverRowIndex = -1;
                      }}
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
