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

import EmptyCard from './components/empty-card';
import FavoriteList from './components/favorite-list';
import PageHeader from './components/page-header';
import ProfilingRetrievalView from './components/profiling-retrieval-view';
import RetrievalSearch from './components/retrieval-search';
import UploadRetrievalView from './components/upload-retrieval-view';
import { ToolsFormData } from './typings/page-header';
import { PanelType, SearchState, SearchType } from './typings';

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
      isShow: false
    });
    const searchState = reactive<SearchState>({
      isShow: true,
      autoQuery: true,
      canQuery: true,
      formData: {
        type: SearchType.Profiling,
        isComparison: false,
        server: '',
        where: [],
        comparisonWhere: []
      }
    });
    const isEmpty = ref(false);
    const dataType = ref('cpu');
    /**
     * 检索面板和收藏面板显示状态切换
     * @param type 面板类型
     * @param status 显示状态
     */
    function handleShowTypeChange(type: PanelType, status: boolean) {
      if (type === 'search') {
        searchState.isShow = status;
      } else {
        favoriteState.isShow = status;
      }
    }
    function handleToolFormDataChange(val: ToolsFormData) {
      toolsFormData.value = val;
      handleQueryDebounce();
    }

    function handleSearchFormDataChange(val: SearchState['formData']) {
      searchState.formData = val;
      handleQueryDebounce();
    }

    function handleAutoQueryChange(val: boolean) {
      searchState.autoQuery = val;
    }
    function handleQueryClear() {}
    function handleAddFavorite() {}

    const handleQueryDebounce = debounce(handleQuery, 300, false);

    function handleQuery(isBtnClick = false) {
      if (!isBtnClick && !searchState.autoQuery) return;
      isEmpty.value = false;
    }
    function handleDataTypeChange(v: string) {
      dataType.value = v;
    }
    return {
      t,
      isEmpty,
      dataType,
      favoriteState,
      searchState,
      toolsFormData,
      handleToolFormDataChange,
      handleShowTypeChange,
      handleAutoQueryChange,
      handleQuery,
      handleQueryClear,
      handleAddFavorite,
      handleSearchFormDataChange,
      handleDataTypeChange
    };
  },

  render() {
    const renderView = () => {
      if (this.isEmpty)
        return (
          <div class='empty-wrap'>
            <EmptyCard
              title={this.$t('持续 Profiling')}
              desc={this.$t('直接进行 精准查询，定位到 Trace 详情')}
            />
            <EmptyCard
              title={this.$t('上传 Profiling')}
              desc={this.$t('可以切换到 范围查询，根据条件筛选 Trace')}
            />
          </div>
        );

      if (this.searchState.formData.type === SearchType.Profiling)
        return (
          <ProfilingRetrievalView
            dataType={this.dataType}
            onUpdate:dataType={this.handleDataTypeChange}
          />
        );

      return <UploadRetrievalView formData={this.searchState.formData} />;
    };

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
                defaultWidth: 240,
                autoHidden: true,
                theme: 'simple',
                isShow: this.favoriteState.isShow,
                onHidden: () => this.handleShowTypeChange(PanelType.Favorite, false)
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
                defaultWidth: 400,
                autoHidden: true,
                theme: 'simple',
                isShow: this.searchState.isShow,
                onHidden: () => this.handleShowTypeChange(PanelType.Search, false)
              }}
            >
              <RetrievalSearch
                formData={this.searchState.formData}
                onChange={this.handleSearchFormDataChange}
              >
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
              </RetrievalSearch>
            </div>
          )}
          <div class='view-wrap'>{renderView()}</div>
        </div>
      </div>
    );
  }
});
