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
import { type PropType, defineComponent, shallowReactive, watch } from 'vue';
import { shallowRef } from 'vue';

import { Button } from 'bkui-vue';
import { EMode } from 'trace/components/retrieval-filter/typing';
import TableSkeleton from 'trace/components/skeleton/table-skeleton';
import { useI18n } from 'vue-i18n';

import RetrievalFilter from '../../../../../components/retrieval-filter/retrieval-filter';
import { useAlarmLog } from '../../../composables/use-alarm-log';
import IndexSetSelector from './index-set-selector/index-set-selector';
import LogTable from './log-table/log-table';

import type { AlarmDetail } from '../../../typings/detail';

import './index.scss';

export default defineComponent({
  name: 'PanelLog',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => null,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const { getIndexSetList, updateTableData, resetTableData } = useAlarmLog(props.detail);
    const selectLoading = shallowRef(false);
    /** 索引集列表 */
    const indexSetList = shallowRef([]);
    const relatedBkBizId = shallowRef(-1);
    /** 选中的索引集ID */
    const selectIndexSet = shallowRef<number | string>('');
    /** 表格数据 */
    const tableData = shallowReactive({
      data: [],
      total: 0,
      columns: [],
      limit: 30,
      offset: 0,
    });
    const keyword = shallowRef('');
    const filterMode = shallowRef<EMode>(EMode.ui);
    /** 表格加载状态 */
    const tableLoading = shallowRef(false);
    /** 滚动加载状态 */
    const scrollLoading = shallowRef(false);

    watch(
      () => props.detail,
      val => {
        if (val) {
          init();
        }
      },
      { immediate: true }
    );

    async function init() {
      selectLoading.value = true;
      tableLoading.value = true;
      const data = await getIndexSetList();
      relatedBkBizId.value = data?.relatedBkBizId || -1;
      indexSetList.value = data?.relatedIndexSetList || [];
      selectIndexSet.value = indexSetList.value[0]?.index_set_id || '';
      selectLoading.value = false;
      getTableData();
    }

    /**
     * 获取日志列表
     * @param params
     */
    async function getTableData(
      params = {
        limit: tableData.limit,
        offset: tableData.offset,
      }
    ) {
      tableData.limit = params.limit;
      tableData.offset = params.offset;
      if (tableData.offset) {
        scrollLoading.value = true;
      } else {
        tableLoading.value = true;
      }

      const data = await updateTableData({
        index_set_id: selectIndexSet.value,
        keyword: keyword.value,
        limit: tableData.limit,
        offset: tableData.offset,
      });
      tableData.data = data?.data || [];
      tableData.total = data?.total || 0;
      tableData.columns = data?.columns || [];
      if (tableData.offset) {
        scrollLoading.value = false;
      } else {
        tableLoading.value = false;
      }
    }

    /**
     * 切换索引集
     * @param indexSetId 索引集ID
     */
    function handleChangeIndexSet(indexSetId: number | string) {
      selectIndexSet.value = indexSetId;
      resetTableData();
      getTableData({
        limit: tableData.limit,
        offset: 0,
      });
    }

    /**
     * 日志列表滚动加载
     * @param params
     */
    function handleTableScroll(params: { limit: number; offset: number }) {
      getTableData(params);
    }

    /**
     * 跳转日志搜索页
     */
    function handleGoLog() {
      const url = `${window.bk_log_search_url}#/retrieve/${selectIndexSet.value}?bizId=${props.detail?.bk_biz_id || (relatedBkBizId.value === -1 ? window.cc_biz_id : relatedBkBizId.value)}`;
      window.open(url, '_blank');
    }

    /**
     * 日志搜索
     */
    function handleSearch() {
      resetTableData();
      getTableData({
        limit: tableData.limit,
        offset: 0,
      });
    }

    /**
     * 日志搜索关键词改变
     * @param queryString 关键词
     */
    function handleQueryStringChange(queryString: string) {
      keyword.value = queryString;
    }

    /**
     * 日志搜索模式改变
     * @param mode 模式
     */
    function handleModeChange(mode: EMode) {
      filterMode.value = mode;
      if (mode === EMode.ui) {
        keyword.value = '';
      }
      handleSearch();
    }

    return {
      indexSetList,
      tableData,
      selectIndexSet,
      tableLoading,
      selectLoading,
      scrollLoading,
      keyword,
      filterMode,
      handleChangeIndexSet,
      t,
      handleTableScroll,
      handleGoLog,
      handleSearch,
      handleQueryStringChange,
      handleModeChange,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-alarm-log'>
        <div class='panel-log-header'>
          {this.selectLoading ? (
            <div class='skeleton-element select-loading' />
          ) : (
            <IndexSetSelector
              indexSetList={this.indexSetList}
              value={this.selectIndexSet}
              onChange={this.handleChangeIndexSet}
            />
          )}
          <Button
            class='ml-16'
            theme='primary'
            text
            onClick={this.handleGoLog}
          >
            <span>{this.t('更多日志')}</span>
            <span class='icon-monitor icon-fenxiang ml-5' />
          </Button>
        </div>
        <div class='panel-log-filter'>
          <RetrievalFilter
            filterMode={this.filterMode}
            queryString={this.keyword}
            zIndex={4000}
            onModeChange={this.handleModeChange}
            onQueryStringChange={this.handleQueryStringChange}
            onSearch={this.handleSearch}
          />
        </div>
        {this.tableLoading ? (
          <TableSkeleton type={4} />
        ) : (
          <LogTable
            scrollLoading={this.scrollLoading}
            tableData={this.tableData}
            onScroll={this.handleTableScroll}
          />
        )}
      </div>
    );
  },
});
