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
import { defineComponent } from 'vue';

import { storeToRefs } from 'pinia';

import TemporaryShareNew from '@/components/temporary-share/temporary-share-new';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import './action-detail-head.scss';

export default defineComponent({
  name: 'ActionDetailHead',
  props: {
    isFullscreen: {
      type: Boolean,
      default: false,
    },
    showFullScreenBtn: {
      type: Boolean,
      default: true,
    },
  },
  emits: {
    toggleFullscreen: val => typeof val === 'boolean',
  },
  setup(props, { emit }) {
    const alarmCenterDetailStore = useAlarmCenterDetailStore();

    const { actionId } = storeToRefs(alarmCenterDetailStore);

    const handleFullscreenChange = () => {
      emit('toggleFullscreen', !props.isFullscreen);
    };

    return {
      actionId,
      handleFullscreenChange,
    };
  },
  render() {
    return (
      <div class='action-detail-head'>
        <div class='detail-head-title'>{this.$t('处理记录详情')}</div>
        <span class='detail-id'>ID: {this.actionId}</span>
        <TemporaryShareNew type='event' />
        {this.showFullScreenBtn && (
          <div
            class='fullscreen-btn'
            onClick={this.handleFullscreenChange}
          >
            <span
              class={`icon-monitor btn-item-icon ${this.isFullscreen ? 'icon-mc-unfull-screen' : 'icon-fullscreen'}`}
            />
            <span class='btn-text'>{this.isFullscreen ? this.$t('退出全屏') : this.$t('全屏')}</span>
          </div>
        )}
      </div>
    );
  },
});
