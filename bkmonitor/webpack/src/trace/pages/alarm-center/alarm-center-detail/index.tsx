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
import { defineComponent, watch } from 'vue';

import { Message, Sideslider } from 'bkui-vue';
import { copyText } from 'monitor-common/utils';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';

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
    const { t } = useI18n();
    const alarmCenterDetailStore = useAlarmCenterDetailStore();
    const { bizId, alarmId, alarmDetail } = storeToRefs(alarmCenterDetailStore);
    watch(
      () => props.alarmId,
      newVal => {
        if (newVal) {
          alarmId.value = newVal;
        }
      },
      { immediate: true }
    );

    // 复制事件详情连接
    const handleToEventDetail = (type: 'action-detail' | 'detail', isNewPage = false) => {
      let url = location.href.replace(location.hash, `#/event-center/${type}/${alarmId.value}`);
      url = url.replace(location.search, `?bizId=${bizId.value}`);
      if (isNewPage) {
        window.open(url);
        return;
      }
      let success = true;
      copyText(url, msg => {
        Message({
          message: msg,
          theme: 'error',
        });
        success = false;
      });
      if (success) {
        Message({
          message: t('复制成功'),
          theme: 'success',
        });
      }
    };

    // 作为新页面打开
    const _newPageBtn = (type: 'action-detail' | 'detail') => {
      return (
        <span
          class='new-page-btn'
          onClick={() => handleToEventDetail(type, true)}
        >
          <span class='btn-text'>{t('新开页')}</span>
          <span class='icon-monitor icon-fenxiang' />
        </span>
      );
    };

    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    return {
      handleShowChange,
      alarmDetail,
    };
  },
  render() {
    return (
      <Sideslider
        width={1280}
        v-slots={{
          header: <EventDetailHead />,
          default: <DetailCommon data={this.alarmDetail} />,
        }}
        isShow={this.show}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
