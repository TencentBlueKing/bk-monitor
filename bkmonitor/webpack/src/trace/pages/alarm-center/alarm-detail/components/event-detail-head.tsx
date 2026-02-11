/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { computed, defineComponent, reactive, shallowRef, watch } from 'vue';

import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { deepClone } from 'monitor-common/utils/utils';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import TemporaryShareNew from '../../../../components/temporary-share/temporary-share-new';
import { useAlarmCenterDetailStore } from '../../../../store/modules/alarm-center-detail';
import { fetchListAlertFeedback } from '../../services/alarm-detail';
import Feedback from './feedback';
import ChatGroup from '@/pages/failure/alarm-detail/chat-group/chat-group';

import type { IChatGroupDialogOptions } from '../../typings';

import './event-detail-head.scss';

export default defineComponent({
  name: 'EventDetailHead',
  props: {
    isFullscreen: {
      type: Boolean,
      default: false,
    },
    showStepBtn: {
      type: Boolean,
      default: true,
    },
    showFullScreenBtn: {
      type: Boolean,
      default: true,
    },
    showFeedbackBtn: {
      type: Boolean,
      default: true,
    },
    showWxChartBtn: {
      type: Boolean,
      default: true,
    },
    showBlankBtn: {
      type: Boolean,
      default: true,
    },
  },
  emits: {
    toggleFullscreen: val => typeof val === 'boolean',
    previous: () => true,
    next: () => true,
    blank: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const route = useRoute();
    const alarmCenterDetailStore = useAlarmCenterDetailStore();
    /** 是否反馈 */
    const isFeedback = shallowRef(false);

    const { alarmId, alarmDetail, loading } = storeToRefs(alarmCenterDetailStore);

    /** 一键拉群弹窗 */
    const chatGroupDialog = reactive<IChatGroupDialogOptions>({
      show: false,
      alertName: '',
      alertIds: [],
      assignee: [],
    });
    const feedbackDialog = shallowRef(false);
    /** 是否支持一键拉群 todo */
    const enableCreateChatGroup = computed(() => props.showWxChartBtn && Boolean(window.enable_create_chat_group));
    /** 右侧操作按钮 */
    const btnGroupObject = computed(() => {
      return [
        {
          id: 'previous',
          title: t('上一个'),
          icon: 'icon-back-left',
          isShow: props.showStepBtn,
        },
        {
          id: 'next',
          title: t('下一个'),
          icon: 'icon-back-right',
          isShow: props.showStepBtn,
        },
        {
          id: 'wx-chart',
          title: t('拉群'),
          icon: 'icon-we-com',
          isShow: enableCreateChatGroup.value,
        },
        {
          id: 'feedback',
          title: isFeedback.value ? t('已反馈') : t('反馈'),
          icon: 'icon-a-FeedBackfankui',
          isShow: props.showFeedbackBtn,
        },
        {
          id: 'blank',
          title: t('新开页'),
          icon: 'icon-a-NewPagexinkaiye',
          isShow: props.showBlankBtn,
        },
        {
          id: 'fullscreen',
          title: props.isFullscreen ? t('退出全屏') : t('全屏'),
          icon: props.isFullscreen ? 'icon-mc-unfull-screen' : 'icon-fullscreen',
          isShow: props.showFullScreenBtn,
        },
      ];
    });

    const formatShareTokenParams = params => {
      params.data.name = 'alarm-center-detail';
      params.data.path = '/trace/alarm-center/detail/:alarmId';
      params.data.params = {
        alarmId: alarmId.value,
      };
      params.data.query = {};
      return params;
    };

    /** 获取告警反馈 */
    const getAlertFeedback = async () => {
      const data = await fetchListAlertFeedback(
        alarmCenterDetailStore.alarmDetail.id,
        alarmCenterDetailStore.alarmDetail.bk_biz_id
      ).catch(() => []);
      isFeedback.value = data.length > 0;
    };

    watch(
      () => alarmDetail.value,
      newVal => {
        if (newVal && !loading.value) {
          getAlertFeedback();
        }
      },
      { immediate: true }
    );

    /** 策略详情跳转 */
    const toStrategyDetail = () => {
      // 如果 告警来源 是监控策略就要跳转到 策略详情 。
      if (alarmDetail.value.plugin_id === 'bkmonitor') {
        window.open(
          `${location.origin}${location.pathname}?bizId=${alarmDetail.value.bk_biz_id}/#/strategy-config/detail/${alarmId.value}?fromEvent=true`
        );
      } else if (alarmDetail.value.plugin_id) {
        // 否则都新开一个页面并添加 告警源 查询，其它查询项保留。
        const query = deepClone(route.query);
        query.queryString = `告警源 : "${alarmDetail.value.plugin_id}"`;
        const queryString = new URLSearchParams(query).toString();
        window.open(`${location.origin}${location.pathname}${location.search}/#/event-center?${queryString}`);
      }
    };
    // 告警级别标签
    const getTagComponent = (severity: number) => {
      const level = {
        1: { label: t('致命'), className: 'level-tag-fatal', icon: 'icon-danger' },
        2: { label: t('预警'), className: 'level-tag-warning', icon: 'icon-mind-fill' },
        3: { label: t('提醒'), className: 'level-tag-info', icon: 'icon-tips' },
      };
      const className = severity ? level[severity].className : '';
      const label = severity ? level[severity].label : '';
      return (
        <div class={['level-tag', className]}>
          <i class={`icon-monitor ${level[severity]?.icon} sign-icon`} />
          {label}
        </div>
      );
    };

    const handleBtnClick = (id: string) => {
      switch (id) {
        case 'wx-chart':
          handleChatGroup();
          break;
        case 'feedback':
          handleFeedback(true);
          break;
        case 'fullscreen':
          emit('toggleFullscreen', !props.isFullscreen);
          break;
        case 'previous':
          emit('previous');
          break;
        case 'next':
          emit('next');
          break;
        case 'blank':
          emit('blank');
          break;
      }
    };
    /**
     * @description: 一键拉群
     * @return {*}
     */
    const handleChatGroup = () => {
      chatGroupDialog.assignee = alarmDetail.value.assignee || [];
      chatGroupDialog.alertName = alarmDetail.value.alert_name;
      chatGroupDialog.alertIds.splice(0, chatGroupDialog.alertIds.length, alarmDetail.value.id);
      chatGroupShowChange(true);
    };
    /**
     * @description: 一键拉群弹窗关闭/显示
     * @param {boolean} show
     * @return {*}
     */
    const chatGroupShowChange = (show: boolean) => {
      chatGroupDialog.show = show;
    };
    /* 反馈 */
    const handleFeedback = (v: boolean) => {
      feedbackDialog.value = v;
    };
    const handleFeedBackConfirm = () => {
      isFeedback.value = true;
    };

    return {
      t,
      chatGroupDialog,
      feedbackDialog,
      btnGroupObject,
      alarmDetail,
      alarmId,
      loading,
      getTagComponent,
      toStrategyDetail,
      chatGroupShowChange,
      handleFeedback,
      handleFeedBackConfirm,
      handleBtnClick,
      formatShareTokenParams,
    };
  },
  render() {
    if (this.loading)
      return (
        <div class='event-detail-head-main'>
          <div class='level-tag skeleton-element' />
          <div class='event-detail-title skeleton-element' />
          <div class='event-detail-head-btn-group'>
            <div class='btn-item skeleton-element' />
            <div class='btn-item skeleton-element' />
          </div>
        </div>
      );
    return (
      <div class='event-detail-head-main'>
        {this.getTagComponent(this.alarmDetail?.severity)}
        <div class='event-detail-head-content'>
          <span class='event-id'>
            ID: {this.alarmId}
            <TemporaryShareNew
              formatTokenParams={this.formatShareTokenParams}
              type='event'
            />
          </span>
          {this.alarmDetail?.alert_name && (
            <span
              class='basic-title-name'
              v-bk-tooltips={{ content: this.alarmDetail?.alert_name, allowHTML: false, placements: ['bottom'] }}
            >
              {this.alarmDetail?.alert_name}
            </span>
          )}

          {this.alarmDetail?.plugin_id ? (
            <span
              class='btn-strategy-detail'
              onClick={this.toStrategyDetail}
            >
              <span>{this.t('来源：{0}', [this.alarmDetail?.plugin_display_name])}</span>
              <i class='icon-monitor icon-fenxiang icon-float' />
            </span>
          ) : undefined}
        </div>
        <div class='event-detail-head-btn-group'>
          {this.btnGroupObject
            .filter(item => item.isShow)
            .map(item => (
              <div
                key={item.id}
                class='btn-group-item'
                onClick={() => this.handleBtnClick(item.id)}
              >
                <span class={`icon-monitor btn-item-icon ${item.icon}`} />
                <span class='btn-text'>{item.title}</span>
              </div>
            ))}
        </div>
        <ChatGroup
          alarmEventName={this.chatGroupDialog.alertName}
          alertIds={this.chatGroupDialog.alertIds}
          assignee={this.chatGroupDialog.assignee}
          show={this.chatGroupDialog.show}
          onShowChange={this.chatGroupShowChange}
        />
        <Feedback
          key='feedback'
          ids={[this.alarmDetail?.id]}
          show={this.feedbackDialog}
          onConfirm={this.handleFeedBackConfirm}
          onUpdate:isShow={this.handleFeedback}
        />
      </div>
    );
  },
});
