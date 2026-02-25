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
import { type PropType, defineComponent, onMounted, provide, shallowReactive, shallowRef, watch } from 'vue';

import { Sideslider } from 'bkui-vue';
import * as authMap from 'monitor-pc/pages/event-center/authority-map';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';

import DetailCommon from '../common-detail/common-detail';
import { AlarmType } from '../typings';
import ActionDetailHead from './components/action-detail-head';
import ActionDetail from './components/action-detail/action-detail';
// import DiagnosticAnalysis from './components/diagnostic-analysis/diagnostic-analysis';
import EventDetailHead from './components/event-detail-head';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';
import { getAuthorityMap, useAuthorityStore } from '@/store/modules/authority';

import type { IAuthority } from '@/typings/authority';

import './alarm-detail-sideslider.scss';

export default defineComponent({
  name: 'AlarmCenterDetail',
  props: {
    alarmId: {
      type: String,
      required: true,
    },
    alarmType: {
      type: String as PropType<AlarmType>,
      default: AlarmType.ALERT,
    },
    defaultTab: {
      type: String,
      default: '',
    },
    show: {
      type: Boolean,
      required: true,
    },
    /** 是否展示上一步和下一步按钮 */
    showStepBtn: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['update:show', 'previous', 'next'],
  setup(props, { emit }) {
    const router = useRouter();
    const isFullscreen = shallowRef(false);
    const alarmCenterDetailStore = useAlarmCenterDetailStore();
    const { alarmId, actionId, alarmType, defaultTab } = storeToRefs(alarmCenterDetailStore);
    const authorityStore = useAuthorityStore();
    const authority = shallowReactive<IAuthority>({
      map: authMap,
      auth: {},
      showDetail: authorityStore.getAuthorityDetail,
    });

    provide('authority', authority);

    watch(
      () => props.alarmType,
      newVal => {
        if (newVal !== alarmType.value) {
          alarmType.value = newVal;
        }
      },
      { immediate: true }
    );

    watch(
      () => props.defaultTab,
      newVal => {
        defaultTab.value = newVal || '';
      },
      { immediate: true }
    );

    watch(
      () => props.alarmId,
      newVal => {
        if (alarmType.value === AlarmType.ALERT && newVal && newVal !== alarmId.value) {
          alarmId.value = newVal;
          return;
        }
        if (alarmType.value === AlarmType.ACTION && newVal && newVal !== actionId.value) {
          actionId.value = newVal;
          return;
        }
      },
      { immediate: true }
    );

    const init = async () => {
      authority.auth = await getAuthorityMap(authMap);
    };

    onMounted(() => {
      init();
    });

    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    const handlePreviousDetail = () => {
      emit('previous');
    };

    const handleNextDetail = () => {
      emit('next');
    };

    const handleBlank = () => {
      router.push({
        name: 'alarm-center-detail',
        params: {
          alarmId: props.alarmId,
        },
      });
    };

    // 处理全屏切换事件
    const handleFullscreenChange = (value: boolean) => {
      isFullscreen.value = value;
    };

    const renderHeader = () => {
      switch (alarmType.value) {
        case AlarmType.ALERT:
          return (
            <EventDetailHead
              isFullscreen={isFullscreen.value}
              showStepBtn={props.showStepBtn}
              onBlank={handleBlank}
              onNext={handleNextDetail}
              onPrevious={handlePreviousDetail}
              onToggleFullscreen={handleFullscreenChange}
            />
          );
        case AlarmType.ACTION:
          return (
            <ActionDetailHead
              isFullscreen={isFullscreen.value}
              onToggleFullscreen={handleFullscreenChange}
            />
          );
      }
    };

    const renderContent = () => {
      switch (alarmType.value) {
        case AlarmType.ALERT:
          return (
            <div class='alarm-center-detail-wrapper'>
              <DetailCommon />
              {/* <DiagnosticAnalysis /> */}
            </div>
          );
        case AlarmType.ACTION:
          return <ActionDetail />;
      }
    };

    return {
      isFullscreen,
      handlePreviousDetail,
      handleNextDetail,
      handleShowChange,
      renderHeader,
      renderContent,
    };
  },
  render() {
    return (
      <Sideslider
        width={this.isFullscreen ? '100%' : '80%'}
        extCls='alarm-detail-sideslider'
        v-slots={{
          header: this.renderHeader,
          default: this.renderContent,
        }}
        isShow={this.show}
        render-directive='if'
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
