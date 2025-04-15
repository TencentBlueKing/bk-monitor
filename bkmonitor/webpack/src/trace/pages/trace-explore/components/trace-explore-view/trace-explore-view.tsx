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
import { defineComponent, ref as deepRef, type PropType, computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { Checkbox } from 'bkui-vue';

import { useTraceExploreStore } from '../../../../store/modules/explore';
import TraceExploreTable from '../trace-explore-table/trace-explore-table';

import type { ICommonParams } from '../../typing';

import './trace-explore-view.scss';

/** 快速过滤项(包含) */
enum TableCheckBoxFiltersEnum {
  EntrySpan = 'entry',
  Error = 'error',
  RootSpan = 'root_span',
}

export default defineComponent({
  name: 'TraceExploreView',
  props: {
    commonParams: {
      type: Object as PropType<ICommonParams>,
      default: () => ({}),
    },
  },
  setup() {
    const { t } = useI18n();
    const store = useTraceExploreStore();

    /** table上方快捷筛选操作区域（ “包含” 区域中的 复选框组）选中的值 */
    const checkboxFilters = deepRef([]);

    /** 当前激活的视角(trace/span) */
    const mode = computed<'span' | 'trace'>(() => store.mode);
    /** 当前选中的应用 Name */
    const appName = computed<string>(() => store.appName);

    /**
     * @description table上方快捷筛选操作区域（ “包含” 区域中的 复选框组）值改变后触发的回调
     * @param checkedGroup
     */
    function handleCheckboxGroupChange(checkedGroup: string[]) {
      checkboxFilters.value = checkedGroup;
      console.log('================ handleCheckboxGroupChange逻辑待补充 ================');
    }

    /**
     * @description table上方快捷筛选操作区域（ “包含” 区域中的 复选框组） 渲染方法
     *
     */
    function filtersCheckBoxGroupRender() {
      return (
        <Checkbox.Group
          modelValue={checkboxFilters.value}
          onChange={handleCheckboxGroupChange}
        >
          <Checkbox
            v-bk-tooltips={{
              content: t('整个Trace的第一个Span'),
              placement: 'top',
              theme: 'light',
            }}
            label={TableCheckBoxFiltersEnum.RootSpan}
          >
            {t('根Span')}
          </Checkbox>
          <Checkbox
            v-bk-tooltips={{
              content: t('每个Service的第一个Span'),
              placement: 'top',
              theme: 'light',
            }}
            label={TableCheckBoxFiltersEnum.EntrySpan}
          >
            {t('入口Span')}
          </Checkbox>
          <Checkbox label={TableCheckBoxFiltersEnum.Error}>{t('错误')}</Checkbox>
        </Checkbox.Group>
      );
    }

    return {
      mode,
      appName,
      filtersCheckBoxGroupRender,
    };
  },
  render() {
    const { mode, appName, filtersCheckBoxGroupRender } = this;
    return (
      <div class='trace-explore-view'>
        <div class='trace-explore-view-chart'>chart</div>
        <div class='trace-explore-view-filter'>
          <span class='filter-label'>{this.$t('包含')}：</span>
          {filtersCheckBoxGroupRender()}
        </div>
        <div class='trace-explore-view-table'>
          <TraceExploreTable
            appName={appName}
            mode={mode}
          />
        </div>
      </div>
    );
  },
});
