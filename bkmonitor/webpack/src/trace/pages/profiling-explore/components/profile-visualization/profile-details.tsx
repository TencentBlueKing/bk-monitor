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
import { type PropType, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import { diffTextColor, formatDiff, formatProfileValue, formatProportion } from '../../utils/flame-layout';

import type { DiffInfo } from '../../types';

export default defineComponent({
  name: 'ProfileDetails',
  props: {
    name: { type: String, required: true },
    unit: { type: String, default: '' },
    dataType: { type: String, default: '' },
    total: { type: Number, default: 0 },
    self: { type: Number, default: 0 },
    rootTotal: { type: Number, default: 0 },
    diff: { type: Object as PropType<Partial<DiffInfo>>, default: null },
    table: Boolean,
  },
  setup() {
    return { t: useI18n().t, formatProfileValue, formatProportion, formatDiff, diffTextColor };
  },
  render() {
    const format = (value: number) => this.formatProfileValue(value, this.unit);
    const label = this.table
      ? this.dataType.toUpperCase()
      : this.t(this.unit === 'bytes' ? '大小' : this.unit === 'count' ? '数量' : '耗时');
    return (
      <>
        <div class='profile-tip-name'>{this.name}</div>
        <table class='profile-tip-values'>
          {this.diff ? (
            <>
              <thead>
                <tr>
                  <th />
                  <th>{this.t('当前')}</th>
                  <th>{this.t('参照')}</th>
                  <th>{this.t('差异')}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{label}</td>
                  <td>{format(this.diff.baseline)}</td>
                  <td>{format(this.diff.comparison)}</td>
                  <td style={{ color: this.diffTextColor(this.diff) }}>{this.formatDiff(this.diff)}</td>
                </tr>
              </tbody>
            </>
          ) : this.table ? (
            <>
              <thead>
                <tr>
                  <th />
                  <th>Self (% of total)</th>
                  <th>Total (% of total)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{label}</td>
                  <td>
                    {format(this.self)} ({this.formatProportion(this.self, this.rootTotal)})
                  </td>
                  <td>
                    {format(this.total)} ({this.formatProportion(this.total, this.rootTotal)})
                  </td>
                </tr>
              </tbody>
            </>
          ) : (
            <tbody>
              <tr>
                <td>{this.t('占比')}</td>
                <td>{this.formatProportion(this.total, this.rootTotal)}</td>
              </tr>
              <tr>
                <td>{label}</td>
                <td>{format(this.total)}</td>
              </tr>
            </tbody>
          )}
        </table>
        {!this.table && (
          <div class='profile-tip-hint'>
            <i class='icon-monitor icon-mc-mouse' />
            {this.t('鼠标右键有更多菜单')}
          </div>
        )}
      </>
    );
  },
});
