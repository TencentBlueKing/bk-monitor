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

import { defineComponent, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { debounce } from '../../../monitor-common/utils/utils';
import { getDefautTimezone } from '../../../monitor-pc/i18n/dayjs';
import { DEFAULT_TIME_RANGE } from '../../components/time-range/utils';

import PageHeader, { ToolsFormData } from './components/page-header';

import './profiling.scss';

export default defineComponent({
  name: 'ProfilingPage',
  setup() {
    const { t } = useI18n();
    const searchFormData = reactive({
      autoQuery: true
    });
    const isShowFavorite = ref(false);
    const isShowSearch = ref(true);
    const toolsFormData = ref<ToolsFormData>({
      timeRange: DEFAULT_TIME_RANGE,
      timezone: getDefautTimezone(),
      refreshInterval: -1
    });
    function handleToolFormDataChange(val: ToolsFormData) {
      toolsFormData.value = val;
      handleQueryScopeDebounce();
    }
    function handleShowTypeChange(type: 'search' | 'favorite') {
      if (type === 'search') isShowSearch.value = !isShowSearch.value;
      else isShowFavorite.value = !isShowFavorite.value;
    }

    const handleQueryScopeDebounce = debounce(handleQuery, 300, false);

    function handleQuery(isBtnClick = false) {
      if (!isBtnClick && !searchFormData.autoQuery) return;
    }

    return {
      t,
      isShowFavorite,
      isShowSearch,
      toolsFormData,
      handleToolFormDataChange,
      handleShowTypeChange
    };
  },

  render() {
    return (
      <div class='profiling-page'>
        <PageHeader
          v-model={this.toolsFormData}
          isShowFavorite={this.isShowFavorite}
          isShowSearch={this.isShowSearch}
          onShowTypeChange={this.handleShowTypeChange}
          onChange={this.handleToolFormDataChange}
        ></PageHeader>
        <div class='page-content'>
          <div class='favorite-list-wrap'></div>
          <div class='search-form-wrap'></div>
          <div class='view-wrap'></div>
        </div>
      </div>
    );
  }
});
