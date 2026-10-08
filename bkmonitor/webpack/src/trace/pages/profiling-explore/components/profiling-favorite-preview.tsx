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

import { DateRange } from '@blueking/date-picker';
import { useI18n } from 'vue-i18n';

import type { QueryState, TimeRange } from '../types';
import type { IWhereItem } from '@/components/retrieval-filter/typing';

import './profiling-favorite-preview.scss';

export default defineComponent({
  name: 'ProfilingFavoritePreview',
  props: {
    value: { type: Object as PropType<QueryState>, required: true },
  },
  setup(props) {
    const { t } = useI18n();
    function formatRange(value: TimeRange) {
      const range = new DateRange(value, 'YYYY-MM-DD HH:mm:ss', props.value.timezone);
      return range.isValidate ? range.toDisplayString() : value.join(' ~ ');
    }
    function renderFilters(filters: IWhereItem[]) {
      if (!filters.length) return <span class='profiling-favorite-muted'>{t('未设置筛选条件')}</span>;
      return (
        <div class='profiling-favorite-filters'>
          {filters.map((filter, index) => (
            <div
              key={index}
              class='profiling-favorite-filter'
            >
              {index > 0 && (
                <span class='profiling-favorite-relation'>{(filter.condition || 'and').toUpperCase()}</span>
              )}
              <div class='profiling-favorite-expression'>
                <span class='profiling-favorite-field'>{filter.key}</span>
                <span class='profiling-favorite-operator'>
                  {!filter.method || ['eq', 'equal'].includes(filter.method) ? '=' : filter.method}
                </span>
                <span class='profiling-favorite-values'>
                  {filter.value.map((value, valueIndex) => (
                    <span key={valueIndex}>
                      {valueIndex > 0 && (
                        <span class='profiling-favorite-relation'>{filter.options?.group_relation || 'OR'}</span>
                      )}
                      <span class='profiling-favorite-value'>{JSON.stringify(value)}</span>
                    </span>
                  ))}
                </span>
              </div>
            </div>
          ))}
        </div>
      );
    }
    return { t, formatRange, renderFilters };
  },
  render() {
    const value = this.value;
    const file = value.view?.tab === 'file' ? value.file : null;
    const comparing = !file && value.mode !== 'none';
    return (
      <div class='profiling-favorite-preview'>
        <div class='profiling-favorite-heading'>
          <strong>{this.t(file ? '文件分析' : '应用服务')}</strong>
          {comparing && (
            <span class='profiling-favorite-mode'>{this.t(value.mode === 'time' ? '时间对比' : '条件对比')}</span>
          )}
        </div>
        <dl class='profiling-favorite-summary'>
          {file ? (
            <>
              <dt>{this.t('文件')}</dt>
              <dd>{file.fileName || file.profileId}</dd>
            </>
          ) : (
            <>
              <dt>{this.t('应用')}</dt>
              <dd>{value.appName || '--'}</dd>
              <dt>{this.t('服务')}</dt>
              <dd>{value.serviceName || '--'}</dd>
            </>
          )}
          <dt>{this.t('数据类型')}</dt>
          <dd>{(file ? file.dataType : value.dataType) || '--'}</dd>
          <dt>{this.t('汇聚方法')}</dt>
          <dd>{file ? file.aggregation : value.aggregation}</dd>
          <dt>{this.t('时间范围')}</dt>
          <dd>{this.formatRange(value.timeRange)}</dd>
          <dt>{this.t('时区')}</dt>
          <dd>{value.timezone || '--'}</dd>
        </dl>
        <section class='profiling-favorite-query'>
          <h4>{this.t(comparing ? '查询项' : '筛选条件')}</h4>
          {!file && value.mode === 'time' && value.baselineRange && (
            <p class='profiling-favorite-range'>{this.formatRange(value.baselineRange)}</p>
          )}
          {this.renderFilters(
            file ? [...file.where, ...(file.commonWhere || [])] : [...value.where, ...(value.commonWhere || [])]
          )}
        </section>
        {comparing && (
          <section class='profiling-favorite-query'>
            <h4>{this.t('对比项')}</h4>
            {value.mode === 'time' && value.comparisonRange && (
              <p class='profiling-favorite-range'>{this.formatRange(value.comparisonRange)}</p>
            )}
            {this.renderFilters([...value.comparisonWhere, ...(value.comparisonCommonWhere || [])])}
          </section>
        )}
      </div>
    );
  },
});
