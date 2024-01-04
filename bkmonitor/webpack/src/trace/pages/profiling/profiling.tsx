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
import { Form, Sideslider } from 'bkui-vue';

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
    const isEmpty = ref(true);
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
    /**
     * 顶部左侧工具栏数据改变
     * @param val 工具栏数据
     */
    function handleToolFormDataChange(val: ToolsFormData) {
      toolsFormData.value = val;
      handleQueryDebounce();
    }

    /**
     * 查询表单数据改变
     * @param val 表单数据
     */
    function handleSearchFormDataChange(val: SearchState['formData']) {
      searchState.formData = val;
      handleQueryDebounce();
    }

    const detailShow = ref(false);
    /** 展示详情侧边栏 */
    function handleShowDetail() {
      detailShow.value = true;
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

    return {
      t,
      isEmpty,
      favoriteState,
      searchState,
      toolsFormData,
      detailShow,
      handleToolFormDataChange,
      handleShowTypeChange,
      handleAutoQueryChange,
      handleQuery,
      handleQueryClear,
      handleAddFavorite,
      handleShowDetail,
      handleSearchFormDataChange
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

      if (this.searchState.formData.type === SearchType.Profiling) return <ProfilingRetrievalView />;

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
                onShowDetail={this.handleShowDetail}
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

        <Sideslider
          isShow={this.detailShow}
          onUpdate:isShow={val => (this.detailShow = val)}
          quick-close
          width={400}
          ext-cls='profiling-detail-sideslider'
        >
          {{
            header: () => (
              <div class='profiling-detail-header'>
                <span class='title'>{this.t('基础信息')}</span>
                <span class='jump-link'>
                  {this.t('Profile 接入文档')}
                  <i class='icon-monitor icon-fenxiang'></i>
                </span>
              </div>
            ),
            default: () => (
              <div class='profiling-detail-content'>
                <Form labelWidth={144}>
                  <Form.FormItem label={`${this.t('模块名称')}:`}>rideshare-app-dotnet</Form.FormItem>
                  <Form.FormItem label={`${this.t('所属应用')}:`}>
                    rideshare-app
                    <span class='jump-link'>
                      {this.t('应用详情')}
                      <i class='icon-monitor icon-fenxiang'></i>
                    </span>
                  </Form.FormItem>
                  <Form.FormItem label={`${this.t('采样频率')}:`}>99 Hz</Form.FormItem>
                  <Form.FormItem label={`${this.t('上报数据类型')}:`}>***SDK</Form.FormItem>
                  <Form.FormItem label={`${this.t('SDK版本')}:`}>1.1.0</Form.FormItem>
                  <Form.FormItem label={`${this.t('数据语言')}:`}>java</Form.FormItem>
                  <Form.FormItem label={`${this.t('创建时间')}:`}>2023-10-31 12:49:34</Form.FormItem>
                  <Form.FormItem label={`${this.t('最近上报时间')}:`}>2023-10-31 12:49:34</Form.FormItem>
                </Form>
              </div>
            )
          }}
        </Sideslider>
      </div>
    );
  }
});
