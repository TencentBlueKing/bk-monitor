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
import { computed, defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { activated, deactivated, loadApp } from '@blueking/bk-weweb';
import { Loading, Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './event-detail.scss';

export default defineComponent({
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    eventDetail: {
      type: Object,
      required: true,
    },
  },
  emits: ['update:show'],
  setup(props, { emit }) {
    const loading = ref(false);
    // variables
    const detailRef = ref<HTMLDivElement>();
    let instance = null;
    const eventUrl = computed(() => {
      const url = new URL(window.location.href);
      url.pathname = url.pathname.replace('/trace', '');
      url.hash = `#/event-detail/detail/${props.eventDetail?.id}`;
      url.searchParams.set('bizId', props.eventDetail?.bk_biz_id);
      return url.toString();
    });

    const { t } = useI18n();

    watch(
      () => props.show,
      () => {
        loadDetail();
      }
    );

    // hooks
    onBeforeUnmount(() => {
      handleBeforeClose();
    });
    onMounted(() => {
      loadDetail();
    });

    // methods
    async function loadDetail() {
      instance = await loadApp({
        id: 'alarmDetail',
        scopeCss: true,
        scopeJs: true,
        showSourceCode: false,
        scopeLocation: true,
        url: eventUrl.value,
      });
    }
    function handleBeforeClose() {
      deactivated('alarmDetail');
      return true;
    }
    function handleShown() {
      loading.value = true;
      nextTick(async () => {
        if (!instance) {
          await loadDetail();
        }
        activated('alarmDetail', detailRef.value);
        setTimeout(() => {
          loading.value = false;
        }, 1500);
      });
    }
    return {
      detailRef,
      handleBeforeClose,
      handleShown,
      loading,
      t,
    };
  },
  render() {
    return (
      <div>
        <Sideslider
          width={1280}
          beforeClose={this.handleBeforeClose}
          isShow={this.show}
          title={this.t('告警详情')}
          onShown={this.handleShown}
          onUpdate:isShow={v => this.$emit('update:show', v)}
        >
          <Loading
            class='yey'
            loading={this.loading}
          >
            <div
              ref='detailRef'
              class='event-detail'
            />
          </Loading>
        </Sideslider>
      </div>
    );
  },
});
