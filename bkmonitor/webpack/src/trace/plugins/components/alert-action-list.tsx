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
import { type Ref, computed, ref as deepRef, defineComponent, inject, reactive } from 'vue';

import { Message } from 'bkui-vue';
import BkDropdown, { BkDropdownItem, BkDropdownMenu } from 'bkui-vue/lib/dropdown';
import BkLink from 'bkui-vue/lib/link';
import { random } from 'lodash';
import { feedbackIncidentRoot, incidentRecordOperation } from 'monitor-api/modules/incident';
import { useI18n } from 'vue-i18n';

import AlarmConfirm from '../../pages/failure/alarm-detail/alarm-confirm';
import AlarmDispatch from '../../pages/failure/alarm-detail/alarm-dispatch';
import ManualProcess from '../../pages/failure/alarm-detail/manual-process';
import QuickShield from '../../pages/failure/alarm-detail/quick-shield';
import FeedbackCauseDialog from '../../pages/failure/failure-topo/feedback-cause-dialog';
import { useIncidentInject } from '../../pages/failure/utils';
import { useChartInfoInject } from '../hooks/chart';

import type { IIncident } from '../../pages/failure/types';
export default defineComponent({
  name: 'AlertActionList',
  emits: ['listHidden', 'listShown', 'successLoad'],
  setup(props, { emit, slots }) {
    const chartInfo = useChartInfoInject();
    const isActionFocus = deepRef(false);
    const { t } = useI18n();
    const isShowList = deepRef(false);
    const textStyle = 'font-size: 12px;line-height: 20px;font-weight: 400; cursor: pointer;';
    const widthStyle = 'width:110px;display:inline-block;text-align:right;';
    const incidentDetail = inject<Ref<IIncident>>('incidentDetail');
    const incidentId = useIncidentInject();
    const iconFontSize = '16px';
    const isRootCause = computed(() => {
      return chartInfo?.is_feedback_root;
    });
    const currentData = computed(() => {
      const { is_root } = chartInfo?.entity || { is_root: false };
      return { ...chartInfo, ...{ is_root, incident_id: incidentDetail?.value?.incident_id } };
    });
    const actionClickFn = (e: MouseEvent, fn) => {
      e.stopImmediatePropagation();
      e.stopPropagation();
      e.preventDefault();
      isActionFocus.value = true;
      emit('listShown');
      fn?.(chartInfo?.value ? chartInfo.value : chartInfo);
    };

    const afterCloseFn = () => {
      setTimeout(() => {
        emit('listHidden');
      });
    };

    const actionList = reactive([
      {
        id: 'alert_detail',
        name: t('告警详情'),
        icon: 'icon-mc-list',
        onClick: e => actionClickFn(e, handleAlertDetail),
      },
      {
        id: 'alert_confirm',
        name: t('告警确认'),
        icon: 'icon-duihao',
        onClick: e => actionClickFn(e, handleAlertConfirm),
      },
      {
        id: 'manual_handling',
        name: t('手动处理'),
        icon: 'icon-chuli',
        onClick: e => actionClickFn(e, handleManualProcess),
      },
      {
        id: 'quick_block',
        name: t('快捷屏蔽'),
        icon: 'icon-mc-notice-shield',
        onClick: e => actionClickFn(e, handleQuickShield),
      },
      {
        id: 'alarm_dispatch',
        name: t('告警分派'),
        icon: 'icon-fenpai',
        onClick: e => actionClickFn(e, handleAlarmDispatch),
      },
      {
        id: 'feedback_new_root_cause',
        // name: t('反馈新根因'),
        // icon: ' icon-fankuixingenyin',
        name: !isRootCause.value ? t('反馈根因') : t('取消反馈根因'),
        icon: !isRootCause.value ? 'icon-fankuixingenyin' : 'icon-mc-cancel-feedback',
        onClick: e => actionClickFn(e, handleRootCauseConfirm),
      },
    ]);

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
    const currentIds = deepRef([]);
    const currentBizIds = deepRef([]);

    const incidentDetailData = computed(() => {
      return incidentDetail?.value;
    });
    const showActionList = computed(() => {
      const { entity } = currentData.value;
      return !entity ? actionList.filter(item => item.id !== 'feedback_new_root_cause') : actionList;
    });

    /** 设置各种操作弹框需要的数据 */
    const setDialogData = data => {
      currentIds.value = [data.id];
      currentBizIds.value = [data.bk_biz_id];
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
    };
    const handleManualProcess = v => {
      setDialogData(v);
      manualProcessShowChange(true);
    };
    /**
     * @description: 手动处理
     * @param {*} v
     * @return {*}
     */
    const manualProcessShowChange = (v: boolean) => {
      dialog.manualProcess.show = v;
      if (!v) {
        afterCloseFn();
      }
    };

    const feedbackIncidentRootApi = (isCancel, data) => {
      const { bk_biz_id, id } = data;
      const params = {
        id: incidentId.value,
        is_cancel: false,
        incident_id: incidentDetailData.value?.incident_id,
        bk_biz_id,
        feedback: {
          incident_root: data.entity.entity_id,
          content: '',
        },
      };
      if (isCancel) {
        params.is_cancel = true;
      }
      feedbackIncidentRoot(params).then(() => {
        Message({
          theme: 'success',
          message: t('取消反馈成功'),
        });
        handleGetTable();
        incidentRecordOperation({
          id,
          incident_id: incidentId.value,
          bk_biz_id,
          operation_type: 'feedback',
          extra_info: {
            feedback_incident_root: '',
            is_cancel: isCancel,
          },
        });
      });
    };
    const handleRootCauseConfirm = v => {
      if (v.is_feedback_root) {
        feedbackIncidentRootApi(true, v);
        return;
      }
      setDialogData(v);
      dialog.rootCauseConfirm.data = v;
      dialog.rootCauseConfirm.show = true;
    };
    const handleAlertDetail = v => {
      window.__BK_WEWEB_DATA__?.showDetailSlider?.(JSON.parse(JSON.stringify({ ...v })));
    };
    const handleAlertConfirm = v => {
      setDialogData(v);
      dialog.alarmConfirm.show = true;
    };
    const handleAlarmDispatch = v => {
      setDialogData(v);
      handleAlarmDispatchShowChange(true);
    };

    const handleAlarmDispatchShowChange = v => {
      dialog.alarmDispatch.show = v;
      if (!v) {
        afterCloseFn();
      }
    };

    /* 手动处理轮询状态 */
    const handleDebugStatus = (actionIds: number[]) => {
      dialog.manualProcess.actionIds = actionIds;
      dialog.manualProcess.debugKey = random(8);
    };

    const handleMouseEnter = () => {
      isActionFocus.value = false;
      isShowList.value = !isShowList.value;
      if (isShowList.value || isActionFocus.value) {
        emit('listShown');
        return;
      }

      emit('listHidden');
    };

    const handleClick = (e: MouseEvent) => {
      e.stopImmediatePropagation();
      e.stopPropagation();
      e.preventDefault();
    };

    const handleFeedbackChange = (val: boolean) => {
      dialog.rootCauseConfirm.show = val;
      if (!val) {
        afterCloseFn();
      }
    };

    const handleGetTable = () => {
      emit('successLoad');
    };
    /* 搜索条件包含action_id 且 打开批量搜索则更新url状态 */
    const batchUrlUpdate = () => {
      return;
    };
    /**
     * @description: 快捷屏蔽
     * @param {boolean} v
     * @return {*}
     */
    const quickShieldChange = (v: boolean) => {
      dialog.quickShield.show = v;
      if (!v) {
        batchUrlUpdate();
        afterCloseFn();
      }
    };

    const handleMealInfo = (mealInfo: { name: string }) => {
      dialog.manualProcess.mealInfo = mealInfo;
    };

    const handleAlarmDispatchSuccess = () => {};
    const handleConfirmAfter = () => {};
    const alarmConfirmChange = v => {
      dialog.alarmConfirm.show = v;
      if (!v) {
        afterCloseFn();
      }
    };
    const isConfirmDisabled = computed(() => {
      const { is_ack, status } = currentData.value;
      return is_ack || ['RECOVERED', 'CLOSED'].includes(status);
    });
    const style = 'color: #c4c6cc;cursor: not-allowed;';
    const getDisabled = (item: any) => {
      const { is_root } = currentData.value;
      const isFeedDisabled = item.id === 'feedback_new_root_cause' && is_root;
      const isConfirmDis = item.id === 'alert_confirm' && isConfirmDisabled.value;
      return isFeedDisabled || isConfirmDis;
    };
    return () => (
      <div>
        <BkDropdown
          v-slots={{
            content: () =>
              !isActionFocus.value && (
                <BkDropdownMenu>
                  {showActionList.value.map(item => (
                    <BkDropdownItem
                      key={item.id}
                      style={`font-size: 12px;color: #63656E; ${getDisabled(item) ? style : ''}`}
                      onClick={e => {
                        if (getDisabled(item)) {
                          return;
                        }
                        item.onClick(e, currentData.value);
                      }}
                    >
                      <i
                        style='margin-right: 4px;font-size: 12px;'
                        class={['icon-monitor', item.icon]}
                      />
                      {item.name}
                    </BkDropdownItem>
                  ))}
                </BkDropdownMenu>
              ),
          }}
          onHide={handleMouseEnter}
          onShow={handleMouseEnter}
        >
          {slots.content ? (
            slots.content()
          ) : (
            <BkLink
              style={[textStyle, widthStyle]}
              theme='primary'
              onClick={handleClick}
            >
              {t('告警操作')}{' '}
              {isShowList.value ? (
                <i
                  style={[textStyle, `font-size: ${iconFontSize};`]}
                  class={['icon-monitor', 'icon-arrow-up']}
                />
              ) : (
                <i
                  style={[textStyle, `font-size: ${iconFontSize};`]}
                  class={['icon-monitor', 'icon-arrow-down']}
                />
              )}
            </BkLink>
          )}
        </BkDropdown>
        <FeedbackCauseDialog
          data={currentData.value}
          visible={dialog.rootCauseConfirm.show}
          onEditSuccess={handleGetTable}
          onRefresh={handleGetTable}
          onUpdate:isShow={handleFeedbackChange}
        />
        <QuickShield
          bizIds={currentBizIds.value}
          data={currentData.value}
          details={dialog.quickShield.details}
          ids={currentIds.value}
          show={dialog.quickShield.show}
          onChange={quickShieldChange}
          onRefresh={handleGetTable}
        />
        <ManualProcess
          alertIds={currentIds.value}
          bizIds={currentBizIds.value}
          data={currentData.value}
          show={dialog.manualProcess.show}
          onDebugStatus={handleDebugStatus}
          onMealInfo={handleMealInfo}
          onRefresh={handleGetTable}
          onShowChange={manualProcessShowChange}
        />
        <AlarmDispatch
          alertIds={currentIds.value}
          bizIds={currentBizIds.value}
          data={currentData.value}
          show={dialog.alarmDispatch.show}
          onRefresh={handleGetTable}
          onShow={handleAlarmDispatchShowChange}
          onSuccess={handleAlarmDispatchSuccess}
        />
        <AlarmConfirm
          bizIds={currentBizIds.value}
          data={currentData.value}
          ids={currentIds.value}
          show={dialog.alarmConfirm.show}
          onChange={alarmConfirmChange}
          onConfirm={handleConfirmAfter}
          onRefresh={handleGetTable}
        />
      </div>
    );
  },
});
