/* eslint-disable @typescript-eslint/naming-convention */
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

import { type Ref, computed, defineComponent, onMounted, provide, reactive, ref } from 'vue';

import { Dialog } from 'bkui-vue';
import { queryServicesDetail } from 'monitor-api/modules/apm_profile';
import { getDefaultTimezone } from 'monitor-pc/i18n/dayjs';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { handleTransformToTimestamp } from '../../components/time-range/utils';
import ProfilingQueryImage from '../../static/img/profiling-query.png';
import ProfilingUploadQueryImage from '../../static/img/profiling-upload-query.png';
import { monitorDrag } from '../../utils/drag-directive';
import EmptyCard from './components/empty-card';
import HandleBtn from './components/handle-btn';
// import FavoriteList from './components/favorite-list';
import PageHeader from './components/page-header';
import ProfilingDetail from './components/profiling-detail';
import ProfilingRetrievalView from './components/profiling-retrieval-view';
import RetrievalSearch from './components/retrieval-search';
import UploadRetrievalView from './components/upload-retrieval-view';
import {
  type DataTypeItem,
  type FileDetail,
  type SearchState,
  type ServicesDetail,
  DetailType,
  PanelType,
  SearchType,
} from './typings';
import { type ToolsFormData, MenuEnum } from './typings/page-header';

import type { ISelectMenuOption } from '../../components/select-menu/select-menu';

import './profiling.scss';

export default defineComponent({
  name: 'ProfilingPage',
  directives: { monitorDrag },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const { t } = useI18n();
    /** 顶部工具栏数据 */
    const toolsFormData = ref<ToolsFormData>({
      timeRange: ['now-15m', 'now'],
      timezone: getDefaultTimezone(),
      refreshInterval: -1,
    });
    provide<Ref<ToolsFormData>>('toolsFormData', toolsFormData);

    // 是否展示复位
    const showRestore = ref<boolean>(false);
    // 时间范围缓存用于复位功能
    const cacheTimeRange = ref('');
    provide<Ref<boolean>>('showRestore', showRestore);
    // 是否开启（框选/复位）全部操作
    const enableSelectionRestoreAll = computed(() => searchState.formData.type === SearchType.Profiling);
    provide<Ref<boolean>>('enableSelectionRestoreAll', enableSelectionRestoreAll);
    // 框选图表事件范围触发（触发后缓存之前的时间，且展示复位按钮）
    provide('handleChartDataZoom', handleChartDataZoom);
    provide('handleRestoreEvent', handleRestoreEvent);

    /** 当前选择服务的详情数据 */
    const selectServiceData = ref<ServicesDetail>();

    /** 查询数据状态 */
    const searchState = reactive<SearchState>({
      isShow: true,
      autoQueryTimer: null,
      autoQuery: true,
      loading: false,
      formData: {
        type: SearchType.Profiling,
        isComparison: false,
        server: {
          app_name: '',
          service_name: '',
        },
        dateComparisonEnable: false,
        where: [],
        comparisonWhere: [],
      },
    });

    const searchType = computed(() => searchState.formData.type);
    provide<Ref<SearchType>>('profilingSearchType', searchType);

    const canQuery = computed(() => {
      if (searchState.loading || !dataType.value) return false;
      if (searchState.formData.type === SearchType.Profiling) {
        // 持续检索必须选择应用/服务后才能查询
        return !!(searchState.formData.server.app_name && searchState.formData.server.service_name);
      }
      return true;
    });
    const isEmpty = ref(true);
    const dataType = ref('');
    const dataTypeList = ref<DataTypeItem[]>([]);
    const aggMethod = ref('');
    const aggMethodList = ref<DataTypeItem[]>([
      {
        key: 'AVG',
        name: 'AVG',
      },
      {
        key: 'SUM',
        name: 'SUM',
      },
      {
        key: 'LAST',
        name: 'LAST',
      },
    ]);
    /* 当前选择的文件 */
    const curFileInfo = ref(null);
    /** 查询参数 */
    const queryParams = ref(getParams());
    /**
     * 检索面板和收藏面板显示状态切换
     * @param type 面板类型
     * @param status 显示状态
     */
    function handleShowTypeChange(type: PanelType, status: boolean) {
      if (type === 'search') {
        searchState.isShow = status;
      }
    }
    /**
     * 顶部左侧工具栏数据改变
     * @param val 工具栏数据
     */
    function handleToolFormDataChange(val: ToolsFormData) {
      toolsFormData.value = val;
      setUrlParams();
    }

    /** 是否全屏 */
    const isFull = ref(false);
    function handleMenuSelect(menu: ISelectMenuOption) {
      if (menu.id === MenuEnum.FullScreen) {
        isFull.value = true;
      }
    }

    function handleDataTypeChange(v: string, type?: string) {
      (type === 'agg' ? aggMethod : dataType).value = v;
      if (type === 'agg') {
        aggMethod.value = v;
      } else {
        dataType.value = v;
        // 切换数据类型时，汇聚方法需要切换成后端给的值
        aggMethod.value = dataTypeList.value.find(item => item.key === v).default_agg_method || 'AVG';
      }
      // dataType.value = v;
      handleQuery();
    }

    /**
     * 查询表单数据改变
     * @param val 表单数据
     */
    function handleSearchFormDataChange(updateItem: Partial<SearchState['formData']>, hasQuery: boolean) {
      for (const [key, val] of Object.entries(updateItem)) {
        searchState.formData[key] = val;
      }

      hasQuery && handleQuery();
    }

    function handleTypeChange(val: SearchType) {
      searchState.formData.type = val;
      if (val === SearchType.Profiling) {
        selectServiceData.value && getDataTypeList(selectServiceData.value);
        handleQuery();
      } else {
        // Upload暂不支持对比模式
        searchState.formData.isComparison = false;
        searchState.formData.dateComparisonEnable = false;
      }
    }

    /** 应用/服务改变后获取具体数据 */
    async function handleAppServiceChange(app_name: string, service_name: string) {
      searchState.formData.server.app_name = app_name;
      searchState.formData.server.service_name = service_name;
      const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
      searchState.loading = true;
      selectServiceData.value = await queryServicesDetail({
        start_time: start,
        end_time: end,
        app_name,
        service_name,
      }).catch(() => ({}));
      searchState.loading = false;
      detailData.value = selectServiceData.value;
      getDataTypeList(selectServiceData.value);
      handleQuery();
    }

    /** 切换自动查询 */
    function handleAutoQueryChange(val: boolean) {
      searchState.autoQuery = val;
      startAutoQueryTimer();
    }
    /** 启动自动查询定时器 */
    function startAutoQueryTimer() {
      window.clearInterval(searchState.autoQueryTimer);
      /**
       * 以下情况不能自动查询
       * 1. 没有开启自动查询
       * 2. 没有设置自动查询间隔
       */
      if (toolsFormData.value.refreshInterval === -1 || !searchState.autoQuery) return;
      searchState.autoQueryTimer = window.setInterval(() => {
        handleQuery();
      }, toolsFormData.value.refreshInterval);
    }

    /** 清除查询条件 */
    function handleQueryClear() {
      searchState.formData = {
        type: searchState.formData.type,
        isComparison: false,
        dateComparisonEnable: false,
        where: [],
        comparisonWhere: [],
        server: {
          app_name: '',
          service_name: '',
        },
      };
      isEmpty.value = true;
    }

    function setUrlParams() {
      if (searchState.formData.type === SearchType.Upload) {
        router.replace({
          query: {},
        });
      } else {
        const { global_query, ...params } = getParams();
        router.replace({
          query: {
            target: encodeURIComponent(
              JSON.stringify({
                ...params,
                start: toolsFormData.value.timeRange[0],
                end: toolsFormData.value.timeRange[1],
              })
            ),
          },
        });
      }
    }
    function getUrlParams() {
      const { target } = route.query;
      if (target) {
        const {
          app_name = '',
          service_name = '',
          start = 'now-15m',
          end = 'now',
          agg_method,
          data_type,
          filter_labels = {},
          diff_filter_labels = {},
          is_compared = false,
        } = JSON.parse(decodeURIComponent(target as string));
        searchState.formData = {
          type: SearchType.Profiling,
          isComparison: is_compared,
          dateComparisonEnable: false,
          server: {
            app_name,
            service_name,
          },
          where: Object.entries<string | string[]>(filter_labels).map(([key, value]) => ({
            key,
            method: 'eq',
            value,
          })),
          comparisonWhere: Object.entries<string | string[]>(diff_filter_labels).map(([key, value]) => ({
            key,
            method: 'eq',
            value,
          })),
        };
        toolsFormData.value = {
          ...toolsFormData.value,
          timeRange: [start, end],
        };
        dataType.value = data_type;
        aggMethod.value = agg_method;
        handleAppServiceChange(app_name, service_name);
      }
    }
    getUrlParams();

    /** 获取接口请求参数 */
    function getParams() {
      const { server, isComparison, where, comparisonWhere, type, startTime, endTime } = searchState.formData;
      const profilingParams = { ...server, global_query: false };
      const uploadParams = {
        profile_id: curFileInfo.value?.profile_id,
        global_query: true,
        start: startTime,
        end: endTime,
      };

      return {
        is_compared: isComparison,
        filter_labels: where.reduce((pre, cur) => {
          if (cur.key && cur.value) pre[cur.key] = cur.value;
          return pre;
        }, {}),
        diff_filter_labels: comparisonWhere.reduce((pre, cur) => {
          if (cur.key && cur.value && isComparison) pre[cur.key] = cur.value;
          return pre;
        }, {}),
        data_type: dataType.value,
        agg_method: aggMethod.value,
        ...(type === SearchType.Upload ? uploadParams : profilingParams),
      };
    }

    /** 查询功能 */
    function handleQuery(autoQuery = true) {
      isEmpty.value = !canQuery.value;
      if (!canQuery.value) return;
      if (!searchState.autoQuery && autoQuery) return;
      queryParams.value = getParams();
      setUrlParams();
    }

    // ----------------------详情-------------------------
    const detailShow = ref(false);
    const detailType = ref<DetailType>(DetailType.Application);
    const detailData = ref<FileDetail | ServicesDetail>(null);
    /** 展示服务详情 */
    function handleShowDetail(type: DetailType, detail: FileDetail | ServicesDetail) {
      detailShow.value = true;
      detailType.value = type;
      detailData.value = detail;
    }

    onMounted(() => {
      searchState.autoQuery && startAutoQueryTimer();
    });

    /**
     * @description 当前选择profiling文件
     * @param fileInfo
     */
    function handleSelectFile(fileInfo: FileDetail) {
      const { query_start_time: startTime, query_end_time: endTime } = fileInfo;
      searchState.formData.startTime = startTime;
      searchState.formData.endTime = endTime;
      curFileInfo.value = fileInfo;
      getDataTypeList(fileInfo);
      handleQuery();
    }

    function getDataTypeList(val: FileDetail | ServicesDetail) {
      dataTypeList.value = val?.data_types || [];
      const target = dataTypeList.value.some(item => item.key === dataType.value);
      if (!target) {
        dataType.value = dataTypeList.value[0]?.key || '';
        // url参数没带aggMethod时取后端给的default_agg_method,
        aggMethod.value = dataTypeList.value[0]?.default_agg_method || 'AVG';
      }
    }

    // 框选图表事件范围触发（触发后缓存之前的时间，且展示复位按钮）
    function handleChartDataZoom(value) {
      if (JSON.stringify(toolsFormData.value.timeRange) !== JSON.stringify(value)) {
        cacheTimeRange.value = JSON.parse(JSON.stringify(toolsFormData.value.timeRange));
        toolsFormData.value.timeRange = value;
        showRestore.value = true;
      }
    }

    function handleRestoreEvent() {
      toolsFormData.value.timeRange = JSON.parse(JSON.stringify(cacheTimeRange.value));
      showRestore.value = false;
    }

    return {
      t,
      isEmpty,
      dataType,
      aggMethod,
      searchState,
      canQuery,
      toolsFormData,
      detailShow,
      detailType,
      detailData,
      queryParams,
      isFull,
      dataTypeList,
      aggMethodList,
      selectServiceData,
      startAutoQueryTimer,
      handleToolFormDataChange,
      handleShowTypeChange,
      handleTypeChange,
      handleAutoQueryChange,
      handleQuery,
      handleQueryClear,
      handleSearchFormDataChange,
      handleAppServiceChange,
      handleDataTypeChange,
      handleShowDetail,
      handleSelectFile,
      handleMenuSelect,
    };
  },

  render() {
    const renderView = () => {
      const handleGuideClick = (type: SearchType) => {
        this.searchState.formData = { ...this.searchState.formData, type };
      };

      if (this.searchState.formData.type === SearchType.Upload) {
        return (
          <UploadRetrievalView
            aggMethod={this.aggMethod}
            aggMethodList={this.aggMethodList}
            dataType={this.dataType}
            dataTypeList={this.dataTypeList}
            formData={this.searchState.formData}
            queryParams={this.queryParams}
            onDataTypeChange={this.handleDataTypeChange}
            onSelectFile={fileInfo => this.handleSelectFile(fileInfo)}
            onShowFileDetail={detail => this.handleShowDetail(DetailType.UploadFile, detail)}
          />
        );
      }

      if (this.isEmpty)
        return (
          <div class='empty-wrap'>
            <div onClick={() => handleGuideClick(SearchType.Profiling)}>
              <EmptyCard
                desc={this.t('直接进行 精准查询，定位到 Trace 详情')}
                title={this.t('持续 Profiling')}
              >
                {{
                  img: () => (
                    <img
                      class='empty-image'
                      alt='empty'
                      src={ProfilingQueryImage}
                    />
                  ),
                }}
              </EmptyCard>
            </div>
            <div onClick={() => handleGuideClick(SearchType.Upload)}>
              <EmptyCard
                desc={this.t('可以切换到 范围查询，根据条件筛选 Trace')}
                title={this.t('上传 Profiling')}
              >
                {{
                  img: () => (
                    <img
                      class='empty-image'
                      alt='empty'
                      src={ProfilingUploadQueryImage}
                    />
                  ),
                }}
              </EmptyCard>
            </div>
          </div>
        );

      return (
        <ProfilingRetrievalView
          aggMethod={this.aggMethod}
          aggMethodList={this.aggMethodList}
          dataType={this.dataType}
          dataTypeList={this.dataTypeList}
          formData={this.searchState.formData}
          queryParams={this.queryParams}
          onUpdate:aggMethod={event => this.handleDataTypeChange(event, 'agg')}
          onUpdate:dataType={this.handleDataTypeChange}
        />
      );
    };

    return (
      <div class='profiling-page'>
        <div class='page-header'>
          <PageHeader
            data={this.toolsFormData}
            isShowSearch={this.searchState.isShow}
            onChange={this.handleToolFormDataChange}
            onImmediateRefresh={this.handleQuery}
            onMenuSelect={this.handleMenuSelect}
            onRefreshIntervalChange={this.startAutoQueryTimer}
            onShowTypeChange={this.handleShowTypeChange}
          />
        </div>
        <div class='page-content'>
          {/* {this.favoriteState.isShow && (
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
          )} */}
          <div
            class='search-form-wrap'
            v-monitor-drag={{
              minWidth: 200,
              maxWidth: 800,
              defaultWidth: 400,
              autoHidden: true,
              theme: 'simple',
              isShow: this.searchState.isShow,
              onWidthChange: () => {},
              onHidden: () => this.handleShowTypeChange(PanelType.Search, false),
            }}
          >
            <RetrievalSearch
              formData={this.searchState.formData}
              onAppServiceChange={this.handleAppServiceChange}
              onChange={this.handleSearchFormDataChange}
              onShowDetail={() => this.handleShowDetail(DetailType.Application, this.selectServiceData)}
              onTypeChange={this.handleTypeChange}
            >
              {{
                query: () => (
                  <HandleBtn
                    autoQuery={this.searchState.autoQuery}
                    canQuery={this.canQuery}
                    loading={this.searchState.loading}
                    onChangeAutoQuery={this.handleAutoQueryChange}
                    onClear={this.handleQueryClear}
                    onQuery={() => {
                      this.handleQuery(false);
                    }}
                  />
                ),
              }}
            </RetrievalSearch>
          </div>
          <div class='view-wrap'>{renderView()}</div>
        </div>

        <ProfilingDetail
          detailData={this.detailData}
          detailType={this.detailType}
          show={this.detailShow}
          onShowChange={val => {
            this.detailShow = val;
          }}
        />

        {this.isFull && (
          <Dialog
            ext-cls='full-dialog'
            dialog-type='show'
            draggable={false}
            header-align='center'
            is-show={this.isFull}
            title={this.t('查看大图')}
            zIndex={8004}
            fullscreen
            onClosed={() => {
              this.isFull = false;
            }}
          >
            <div class='view-wrap'>{renderView()}</div>
          </Dialog>
        )}
      </div>
    );
  },
});
