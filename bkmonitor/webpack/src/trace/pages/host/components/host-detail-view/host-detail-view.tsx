/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions
 * of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { computed, defineComponent, inject } from 'vue';
import type { PropType } from 'vue';

import { useI18n } from 'vue-i18n';

import HostDetailView from '../../../../components/common-detail/host-detail-view';
import EmptyStatus from '../../../../components/empty-status/empty-status';
import HostLoading, { HostRefreshStatus } from '../host-loading/host-loading';
import { HOST_DETAIL_STATE_KEY } from '../../composables/use-host-detail';

import type { IDetailItem } from '../../../../components/common-detail/typing';

import './host-detail-view.scss';

export default defineComponent({
  name: 'HostDetailViewWrapper',
  components: {
    HostDetailView,
    EmptyStatus,
  },
  props: {
    /** 组件宽度 */
    width: { type: [Number, String] },
    /** 详情数据 */
    data: { type: Array as PropType<IDetailItem[]>, default: () => [] },
    /** 是否只读 */
    readonly: { type: Boolean, default: false },
    /** 加载状态 */
    loading: { type: Boolean, default: false },
  },
  setup() {
    const { t } = useI18n();
    const detailState = inject(HOST_DETAIL_STATE_KEY, null);
    const detailError = computed(() => detailState?.error.value ?? false);
    const handleRetry = () => detailState?.retry();
    return { detailError, handleRetry, t };
  },
  render() {
    return (
      <div class='host-detail-view-wrapper'>
        <div class='host-detail-view-title'>{this.t('详情')}</div>
        <HostRefreshStatus loading={this.loading && this.data.length > 0} error={this.detailError && this.data.length > 0} onRetry={this.handleRetry} />
        {this.loading && !this.data.length ? (
          <HostLoading variant='detail' />
        ) : this.detailError && !this.data.length ? (
          <EmptyStatus
            scene='part'
            type='500'
            onOperation={this.handleRetry}
          />
        ) : this.data.length > 0 ? (
          <HostDetailView
            width={this.width}
            data={this.data}
            readonly={this.readonly}
          />
        ) : (
          <EmptyStatus
            scene='part'
            showOperation={false}
            type='empty'
          />
        )}
      </div>
    );
  },
});
