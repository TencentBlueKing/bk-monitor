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

import { PropType, computed, defineComponent, onBeforeUnmount, ref, watch } from 'vue';

import useStore from '@/hooks/use-store';
// 版本日志对话框（Composition API + TSX）
import { Dialog as BkDialog } from 'bk-magic-vue';

import { axiosInstance } from '@/api';

import './log-version.scss';

interface VersionItem {
  title: string;
  date: string;
  detail?: string;
}

export default defineComponent({
  name: 'LogVersion',
  props: {
    dialogShow: {
      type: Boolean as PropType<boolean>,
      default: false,
    },
  },
  setup(props, { emit }) {
    const store = useStore();
    const t = (msg: string) => ((window as any).$t ? (window as any).$t(msg) : msg);

    // state
    const show = ref<boolean>(false);
    const current = ref<number>(0);
    const active = ref<number>(0);
    const logList = ref<VersionItem[]>([]);
    const loading = ref<boolean>(false);

    const isExternal = computed<boolean>(() => store.state.isExternal);
    const spaceUid = computed<string>(() => store.state.spaceUid);

    // computed
    const currentLog = computed<VersionItem>(() => {
      const empty: VersionItem = { title: '', date: '', detail: '' };
      return logList.value[active.value] || empty;
    });

    // watch dialogShow -> open & preload list
    watch(
      () => props.dialogShow,
      async v => {
        show.value = !!v;
        if (v) {
          loading.value = true;
          logList.value = await getVersionLogsList();
          if (logList.value.length) {
            await handleItemClick();
          }
          loading.value = false;
        }
      },
      { immediate: true },
    );

    onBeforeUnmount(() => {
      show.value = false;
      emit('update:dialog-show', false);
    });

    function handleValueChange(v: boolean) {
      emit('update:dialog-show', v);
    }

    async function handleItemClick(v = 0) {
      active.value = v;
      if (!currentLog.value.detail) {
        loading.value = true;
        const detail = await getVersionLogsDetail();
        currentLog.value.detail = detail as string;
        loading.value = false;
      }
    }

    async function getVersionLogsList(): Promise<VersionItem[]> {
      const params: any = {
        method: 'get',
        url: `${(window as any).SITE_URL}version_log/version_logs_list/`,
      };
      if (isExternal.value) {
        params.headers = { 'X-Bk-Space-Uid': spaceUid.value };
      }
      const { data } = await axiosInstance(params).catch(_ => {
        console.warn(_);
        return { data: { data: [] } } as any;
      });
      return (data?.data || []).map((item: any) => ({ title: item[0], date: item[1], detail: '' }));
    }

    async function getVersionLogsDetail(): Promise<string> {
      const params: any = {
        method: 'get',
        url: `${(window as any).SITE_URL}version_log/version_log_detail/`,
        params: { log_version: currentLog.value.title },
      };
      if (isExternal.value) {
        params.headers = { 'X-Bk-Space-Uid': spaceUid.value };
      }
      const { data } = await axiosInstance(params).catch(_ => {
        console.warn(_);
        return { data: '' } as any;
      });
      return data?.data || '';
    }

    return () => (
      <BkDialog
        width='1105'
        show-footer={false}
        value={show.value}
        {...{ on: { 'value-change': handleValueChange } }}
      >
        <div
          class='bklog-v3-version'
          v-bkloading={{ isLoading: loading.value }}
        >
          <div class='bklog-v3-version-left'>
            <ul class='left-list'>
              {logList.value.map((item, index) => (
                <li
                  key={index}
                  class={['left-list-item', { 'item-active': index === active.value }]}
                  onClick={() => {
                    void handleItemClick(index);
                  }}
                >
                  <span class='item-title'>{item.title}</span>
                  <span class='item-date'>{item.date}</span>
                  {index === current.value ? <span class='item-current'>{t('当前版本')}</span> : null}
                </li>
              ))}
            </ul>
          </div>
          <div class='bklog-v3-version-right'>
            <div
              class='detail-container'
              innerHTML={
                (window as any).$xss
                  ? (window as any).$xss(currentLog.value.detail)
                  : (currentLog.value.detail as string)
              }
            />
          </div>
        </div>
      </BkDialog>
    );
  },
});
