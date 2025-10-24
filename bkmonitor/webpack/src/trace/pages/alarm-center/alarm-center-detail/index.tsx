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
import { defineComponent, shallowRef, watch } from 'vue';

import { Sideslider } from 'bkui-vue';
import { storeToRefs } from 'pinia';

import DetailCommon from '../detail-common';
import EventDetailHead from './components/event-detail-head';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

export default defineComponent({
  name: 'AlarmCenterDetail',
  props: {
    alarmId: {
      type: String,
      required: true,
    },
    show: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['update:show'],
  setup(props, { emit }) {
    const isFullscreen = shallowRef(false);
    const alarmCenterDetailStore = useAlarmCenterDetailStore();
    const { alarmId } = storeToRefs(alarmCenterDetailStore);

    watch(
      () => props.alarmId,
      newVal => {
        if (newVal) {
          alarmId.value = newVal;
        }
      },
      { immediate: true }
    );

    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    return {
      isFullscreen,
      handleShowChange,
    };
  },
  render() {
    return (
      <Sideslider
        width={this.isFullscreen ? '100%' : 1280}
        v-slots={{
          header: () => (
            <EventDetailHead
              isFullscreen={this.isFullscreen}
              onToggleFullscreen={val => {
                this.isFullscreen = val;
              }}
            />
          ),
          default: () => <DetailCommon />,
        }}
        isShow={this.show}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
