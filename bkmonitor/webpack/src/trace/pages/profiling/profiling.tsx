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
import { monitorDrag } from '../../utils/drag-directive';
import HandleBtn from '../main/handle-btn/handle-btn';

import FavoriteList from './components/favorite-list';
import PageHeader from './components/page-header';
import ProfilingRetrieval from './components/profiling-retrieval';
import { ToolsFormData } from './typings/page-header';

import './profiling.scss';

export default defineComponent({
  name: 'ProfilingPage',
  directives: { monitorDrag },
  setup() {
    const { t } = useI18n();
    const toolsFormData = ref<ToolsFormData>({
      timeRange: DEFAULT_TIME_RANGE,
      timezone: getDefautTimezone(),
      refreshInterval: -1
    });
    const favoriteState = reactive({
      defaultWidth: 240,
      width: 240,
      isShow: false
    });
    const searchState = reactive({
      isShow: true,
      defaultWidth: 400,
      width: 400,
      autoQuery: true,
      canQuery: true,
      formData: {}
    });
    function handleToolFormDataChange(val: ToolsFormData) {
      toolsFormData.value = val;
      handleQueryScopeDebounce();
    }
    function handleShowTypeChange(type: 'search' | 'favorite', status: boolean) {
      if (type === 'search') {
        searchState.isShow = status;
      } else {
        favoriteState.isShow = status;
      }
    }
    function handleWidthChange(type: 'search' | 'favorite', width: number) {
      if (type === 'search') {
        searchState.width = width;
      } else {
        favoriteState.width = width;
      }
    }

    function handleAutoQueryChange(val: boolean) {
      searchState.autoQuery = val;
    }
    function handleQueryClear() {}
    function handleAddFavorite() {}

    const handleQueryScopeDebounce = debounce(handleQuery, 300, false);

    function handleQuery(isBtnClick = false) {
      if (!isBtnClick && !searchState.autoQuery) return;
    }

    return {
      t,
      favoriteState,
      searchState,
      toolsFormData,
      handleToolFormDataChange,
      handleShowTypeChange,
      handleAutoQueryChange,
      handleQuery,
      handleQueryClear,
      handleAddFavorite,
      handleWidthChange
    };
  },

  render() {
    return (
      <div class='profiling-page'>
        <div class='page-header'>
          <PageHeader
            v-model={this.toolsFormData}
            isShowFavorite={this.favoriteState.isShow}
            isShowSearch={this.searchState.isShow}
            onShowTypeChange={this.handleShowTypeChange}
            onChange={this.handleToolFormDataChange}
          ></PageHeader>
        </div>
        <div class='page-content'>
          {this.favoriteState.isShow && (
            <div
              class='favorite-list-wrap'
              v-monitor-drag={{
                minWidth: 200,
                maxWidth: 500,
                defaultWidth: this.favoriteState.defaultWidth,
                autoHidden: true,
                theme: 'simple',
                isShow: this.favoriteState.isShow,
                onHidden: () => this.handleShowTypeChange('favorite', false),
                onWidthChange: width => this.handleWidthChange('favorite', width)
              }}
            >
              <FavoriteList></FavoriteList>
            </div>
          )}
          {this.searchState.isShow && (
            <div
              class='search-form-wrap'
              v-monitor-drag={{
                minWidth: 200,
                maxWidth: 800,
                defaultWidth: this.searchState.defaultWidth,
                autoHidden: true,
                theme: 'simple',
                isShow: this.searchState.isShow,
                onHidden: () => this.handleShowTypeChange('search', false),
                onWidthChange: width => this.handleWidthChange('search', width)
              }}
            >
              <ProfilingRetrieval>
                {{
                  query: () => (
                    <HandleBtn
                      autoQuery={this.searchState.autoQuery}
                      canQuery={this.searchState.canQuery}
                      onChangeAutoQuery={this.handleAutoQueryChange}
                      onQuery={() => this.handleQuery(true)}
                      onClear={this.handleQueryClear}
                      onAdd={this.handleAddFavorite}
                    ></HandleBtn>
                  )
                }}
              </ProfilingRetrieval>
            </div>
          )}
          <div class='view-wrap'></div>
        </div>
      </div>
    );
  }
});
