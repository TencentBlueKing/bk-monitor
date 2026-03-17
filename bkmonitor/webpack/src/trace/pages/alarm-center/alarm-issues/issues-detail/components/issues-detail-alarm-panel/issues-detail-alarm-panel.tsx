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
import { defineComponent, onMounted, provide, shallowReactive, watch } from 'vue';

import * as authMap from 'monitor-pc/pages/event-center/authority-map';
import { storeToRefs } from 'pinia';
import EventDetailHead from 'trace/pages/alarm-center/alarm-detail/components/event-detail-head';

import { useAlarmCenterDetailStore } from '../../../../../../store/modules/alarm-center-detail';
import { getAuthorityMap, useAuthorityStore } from '../../../../../../store/modules/authority';
import DetailCommon from '../../../../common-detail/common-detail';

import type { IAuthority } from '@/typings/authority';

import './issues-detail-alarm-panel.scss';

export default defineComponent({
  name: 'IssuesDetailAlarmPanel',
  props: {
    /** 告警ID */
    alarmId: {
      type: String,
      required: true,
    },
  },
  setup(props) {
    const alarmCenterDetailStore = useAlarmCenterDetailStore();
    const { alarmId, alarmDetail } = storeToRefs(alarmCenterDetailStore);
    const authorityStore = useAuthorityStore();
    const authority = shallowReactive<IAuthority>({
      map: authMap,
      auth: {},
      showDetail: authorityStore.getAuthorityDetail,
    });

    provide('authority', authority);

    watch(
      () => props.alarmId,
      newVal => {
        if (newVal) {
          alarmId.value = newVal;
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

    return {
      alarmDetail,
    };
  },
  render() {
    if (!this.alarmDetail) return null;
    return (
      <div class='issues-detail-alarm-panel'>
        <EventDetailHead
          isFullscreen={true}
          showBlankBtn={false}
          showFeedbackBtn={false}
          showFullScreenBtn={false}
          showStepBtn={false}
        />
        <DetailCommon />
      </div>
    );
  },
});
