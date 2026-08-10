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

import { defineComponent } from 'vue';
import type { PropType } from 'vue';

import { useI18n } from 'vue-i18n';

import HostDetailView from '../../../../components/common-detail/host-detail-view';
import EmptyStatus from '../../../../components/empty-status/empty-status';

import type { IDetailItem } from '../../../../components/common-detail/typing';

import './host-detail-view.scss';

/** 骨架屏行配置 */
const SKELETON_ROWS = [
  { labelWidth: 80, valueWidth: 100 },
  { labelWidth: 80, valueWidth: 140 },
  { labelWidth: 80, valueWidth: 120 },
  { labelWidth: 80, valueWidth: 160 },
  { labelWidth: 80, valueWidth: 100 },
  { labelWidth: 80, valueWidth: 80 },
  { labelWidth: 80, valueWidth: 90 },
  { labelWidth: 80, valueWidth: 110 },
];

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
    return { t };
  },
  render() {
    return (
      <div class='host-detail-view-wrapper'>
        <div class='host-detail-view-title'>{this.t('详情')}</div>
        {this.loading ? (
          <div class='host-detail-view-skeleton'>
            {SKELETON_ROWS.map((row, index) => (
              <div
                key={index}
                class='host-detail-view-skeleton-row'
              >
                <div
                  style={{ width: `${row.labelWidth}px`, height: '20px' }}
                  class='skeleton-element'
                />
                <div
                  style={{ width: `${row.valueWidth}px`, height: '20px' }}
                  class='skeleton-element'
                />
              </div>
            ))}
          </div>
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
