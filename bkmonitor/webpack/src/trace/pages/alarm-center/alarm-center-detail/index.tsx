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
import { computed, defineComponent, PropType } from 'vue';

import DetailCommon from '../detail-common';
import { Message, Sideslider } from 'bkui-vue';
import type { IAlert } from '../detail-common/typeing';
import EventDetailHead from './components/event-detail-head';
import { AlarmType } from '../typings';
import { useI18n } from 'vue-i18n';
import { copyText } from 'monitor-common/utils';
import { useAppStore } from '@/store/modules/app';

export default defineComponent({
  name: 'AlarmCenterDetail',
  props: {
    data: {
      type: Object as PropType<IAlert>,
    },
    detailType: {
      type: String as PropType<AlarmType>,
      default: AlarmType.ALERT,
    },
    loading: {
      type: Boolean,
      default: false,
    },
    show: {
      type: Boolean,
      default: false,
    },
    isFeedback: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['update:show'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useAppStore();
    const bizId = computed(() => store.bizId);

    // 复制事件详情连接
    const handleToEventDetail = (type: 'action-detail' | 'detail', isNewPage = false) => {
      let url = location.href.replace(location.hash, `#/event-center/${type}/${props.data?.id}`);
      url = url.replace(location.search, `?bizId=${props.data?.bk_biz_id || bizId}`);
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
    const newPageBtn = (type: 'action-detail' | 'detail') => {
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

    const renderDetailHeader = () => {
      switch (props.detailType) {
        case AlarmType.ALERT:
          return (
            <EventDetailHead
              basicInfo={props.data}
              bizId={props.data?.bk_biz_id}
              eventId={props.data?.id}
              isFeedback={props.isFeedback}
            />
          );
        case AlarmType.ACTION:
          return (
            <div class='title-wrap'>
              <span>{t('处理记录详情')}</span>
              <i
                class='icon-monitor icon-copy-link'
                onClick={() => handleToEventDetail('action-detail')}
              />
              {newPageBtn('action-detail')}
            </div>
          );
        default:
          return null;
      }
    };

    const renderDetailContent = () => {
      switch (props.detailType) {
        case AlarmType.ALERT:
          return <DetailCommon data={props.data} />;
        case AlarmType.ACTION:
          return null;
        default:
          return null;
      }
    };

    return {
      handleShowChange,
      renderDetailHeader,
      renderDetailContent,
    };
  },
  render() {
    return (
      <Sideslider
        width={1280}
        isShow={this.show}
        onUpdate:isShow={this.handleShowChange}
        v-slots={{
          header: this.renderDetailHeader,
          default: this.renderDetailContent,
        }}
      />
    );
  },
});
