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

import { defineComponent, ref, reactive, computed, onMounted } from 'vue';

import * as authorityMap from '@/common/authority-map';
import { clearTableFilter } from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { InfoBox, Message } from 'bk-magic-vue';

import RepositorySlider from './repository-slider.tsx';
import http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'ArchiveRepository',
  components: {
    RepositorySlider,
    EmptyStatus,
  },
  setup() {
    const store = useStore();
    const { t } = useLocale();
    const repositoryTable = ref<any>(null);

    const isTableLoading = ref(false); // 表格加载状态
    const showSlider = ref(false); // 侧滑弹窗显示状态
    const editClusterId = ref<null | number>(null); // 当前编辑的集群ID
    const tableDataOrigin = ref<any[]>([]); // 原始表格数据
    const tableDataSearched = ref<any[]>([]); // 搜索/过滤后的表格数据
    const tableDataPaged = ref<any[]>([]); // 当前分页展示的数据
    const emptyType = ref('empty'); // 空状态类型
    const filterSearchObj = reactive<Record<string, number>>({}); // 过滤条件统计对象
    const isFilterSearch = ref(false); // 是否处于过滤搜索状态
    const params = reactive({ keyword: '' }); // 搜索参数
    const filterConditions = reactive({ type: '', cluster_source_type: '' }); // 过滤条件
    const pagination = reactive({
      // 分页参数
      current: 1,
      count: 0,
      limit: 10,
      limitList: [10, 20, 50, 100],
    });

    // 仓库类型映射
    const repoTypeMap = computed(() => ({
      hdfs: 'HDFS',
      fs: t('共享目录'),
      cos: 'COS',
    }));

    const bkBizId = computed(() => store.getters.bkBizId); // 业务ID
    const authorityMapComputed = computed(() => authorityMap); // 权限映射计算属性
    const globalsData = computed(() => store.getters['globals/globalsData']); // 全局数据

    // 仓库类型过滤项
    const repositoryFilters = computed(() =>
      Object.keys(repoTypeMap.value).map(item => ({ text: repoTypeMap.value[item], value: item })),
    );

    // 来源过滤项
    const sourceFilters = computed(() => {
      const esSourceType = globalsData.value?.es_source_type || [];
      return esSourceType.map((data: any) => ({ text: data.name, value: data.id }));
    });

    // 加载表格数据
    const getTableData = () => {
      isTableLoading.value = true;
      http
        .request('archive/getRepositoryList', {
          query: { bk_biz_id: bkBizId.value },
        })
        .then((res: any) => {
          const data: any[] = Array.isArray(res.data) ? res.data : [];
          tableDataOrigin.value = data;
          tableDataSearched.value = data;
          pagination.count = data.length;
          computePageData();
        })
        .catch((err: any) => {
          console.warn(err);
          emptyType.value = '500';
        })
        .finally(() => {
          isTableLoading.value = false;
        });
    };

    // 计算当前分页数据
    const computePageData = () => {
      emptyType.value = params.keyword || isFilterSearch.value ? 'search-empty' : 'empty';
      const { current, limit } = pagination;
      const start = (current - 1) * limit;
      const end = current * limit;
      tableDataPaged.value = tableDataSearched.value.slice(start, end);
    };

    // 搜索处理
    const handleSearch = () => {
      isTableLoading.value = true;
      if (params.keyword) {
        tableDataSearched.value = tableDataOrigin.value.filter(item =>
          (item.repository_name + item.cluster_name).includes(params.keyword),
        );
      } else {
        tableDataSearched.value = tableDataOrigin.value;
      }
      pagination.current = 1;
      pagination.count = tableDataSearched.value.length;
      computePageData();
      setTimeout(() => {
        isTableLoading.value = false;
      }, 300);
    };

    // 过滤条件变更处理
    const handleFilterChange = (data: Record<string, string[]>) => {
      for (const item of Object.keys(data)) {
        tableDataSearched.value = tableDataOrigin.value.filter(repo => {
          filterConditions[item] = Object.values(data)[0][0];
          const { type, cluster_source_type: clusterType } = filterConditions;
          if (!(type || clusterType)) {
            return true;
          }
          if (type && clusterType) {
            return repo.type === type && repo.cluster_source_type === clusterType;
          }
          return repo.type === type || repo.cluster_source_type === clusterType;
        });
      }
      for (const [key, value] of Object.entries(data)) {
        filterSearchObj[key] = value.length;
      }
      isFilterSearch.value = Object.values(filterSearchObj).reduce((pre, cur) => pre || !!cur, false);
      pagination.current = 1;
      pagination.count = tableDataSearched.value.length;
      computePageData();
    };

    // 新建仓库按钮点击
    const handleCreate = () => {
      editClusterId.value = null;
      showSlider.value = true;
    };

    // 关闭侧滑弹窗
    const handleCancelSlider = () => {
      showSlider.value = false;
    };

    // 分页页码变更
    const handlePageChange = (page: number) => {
      if (pagination.current !== page) {
        pagination.current = page;
        computePageData();
      }
    };

    // 分页条数变更
    const handleLimitChange = (limit: number) => {
      if (pagination.limit !== limit) {
        pagination.current = 1;
        pagination.limit = limit;
        computePageData();
      }
    };

    // 表格操作按钮处理（如删除）
    const operateHandler = (row: any, operateType: string) => {
      if (!row.permission?.[authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH]) {
        return getOptionApplyData({
          action_ids: [authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH],
          resources: [{ type: 'es_source', id: row.cluster_id }],
        });
      }
      if (operateType === 'delete') {
        InfoBox({
          type: 'warning',
          subTitle: t('当前仓库名称为{n}，确认要删除？', { n: row.repository_name }),
          confirmFn: () => requestDeleteRepo(row),
        });
      }
    };

    // 删除仓库请求
    const requestDeleteRepo = (row: any) => {
      http
        .request('archive/deleteRepository', {
          data: {
            cluster_id: row.cluster_id,
            snapshot_repository_name: row.repository_name,
          },
        })
        .then((res: any) => {
          if (res.result) {
            Message({
              theme: 'success',
              message: t('删除成功'),
            });
            if (tableDataPaged.value.length <= 1) {
              pagination.current = pagination.current > 1 ? pagination.current - 1 : 1;
            }
            const deleteIndex = tableDataSearched.value.findIndex(item => item.repository_name === row.repository_name);
            tableDataSearched.value.splice(deleteIndex, 1);
            computePageData();
          }
        });
    };

    // 权限申请弹窗
    const getOptionApplyData = async (paramData: any) => {
      try {
        isTableLoading.value = true;
        const res = await store.dispatch('getApplyData', paramData);
        store.commit('updateState', { authDialogData: res.data });
      } catch (err) {
        console.warn(err);
      } finally {
        isTableLoading.value = false;
      }
    };

    // 仓库信息更新后回调
    const handleUpdatedTable = () => {
      showSlider.value = false;
      pagination.current = 1;
      getTableData();
    };

    // 清空筛选条件
    const handleOperation = (type: string) => {
      if (type === 'clear-filter') {
        params.keyword = '';
        pagination.current = 1;
        clearTableFilter(repositoryTable.value);
        handleSearch();
        return;
      }
      if (type === 'refresh') {
        emptyType.value = 'empty';
        pagination.current = 1;
        handleSearch();
        return;
      }
    };

    onMounted(() => {
      // 组件挂载时获取表格数据
      getTableData();
    });

    // 表头渲染函数
    const renderHeader = (_: any, { column }: any) => <span>{column.label}</span>;

    return () => (
      <section
        class='log-archive-repository'
        data-test-id='archive_section_storehouseContainer'
      >
        {/* 顶部操作栏 */}
        <section class='top-operation'>
          <bk-button
            class='fl'
            data-test-id='storehouseContainer_button_addNewStoreHouse'
            theme='primary'
            onClick={handleCreate}
          >
            {t('新建')}
          </bk-button>
          <div class='repository-search fr'>
            <bk-input
              data-test-id='storehouseContainer_input_searchTableItem'
              placeholder={t('请输入仓库名称')}
              right-icon='bk-icon icon-search'
              value={params.keyword}
              clearable
              on-right-icon-click={handleSearch}
              onChange={val => (params.keyword = val)}
              onEnter={handleSearch}
            />
          </div>
        </section>

        {/* 表格区域 */}
        <section
          class='log-repository-table'
          data-test-id='storehouseContainer_section_tableList'
        >
          <bk-table
            ref={repositoryTable}
            class='repository-table'
            v-bkloading={{ isLoading: isTableLoading.value }}
            scopedSlots={{
              empty: () => (
                <div>
                  <EmptyStatus
                    emptyType={emptyType.value}
                    on-operation={handleOperation}
                  />
                </div>
              ),
            }}
            data={tableDataPaged.value}
            limit-list={pagination.limitList}
            pagination={pagination}
            onFilter-change={handleFilterChange}
            onPage-change={handlePageChange}
            onPage-limit-change={handleLimitChange}
          >
            <bk-table-column
              width='120'
              label={t('集群ID')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.cluster_id }}
            />
            <bk-table-column
              label={t('仓库名称')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.repository_name }}
            />
            <bk-table-column
              label={t('ES集群')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.cluster_name }}
            />
            <bk-table-column
              class-name='filter-column'
              column-key='type'
              filter-multiple={false}
              filters={repositoryFilters.value}
              label={t('类型')}
              prop='type'
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => repoTypeMap.value[props.row.type] }}
            />
            <bk-table-column
              class-name='filter-column'
              column-key='cluster_source_type'
              filter-multiple={false}
              filters={sourceFilters.value}
              label={t('来源')}
              prop='cluster_source_type'
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.cluster_source_name }}
            />
            <bk-table-column
              label={t('创建人')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.creator }}
            />
            <bk-table-column
              label={t('创建时间')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.create_time }}
            />
            <bk-table-column
              width='160'
              scopedSlots={{
                default: (props: any) => (
                  <div class='repository-table-operate'>
                    <bk-button
                      class='mr10 king-button'
                      disabled={!props.row.permission?.[authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH]}
                      theme='primary'
                      text
                      onClick={() => operateHandler(props.row, 'delete')}
                    >
                      {t('删除')}
                    </bk-button>
                  </div>
                ),
              }}
              label={t('操作')}
              renderHeader={renderHeader}
            />
          </bk-table>
        </section>

        {/* 新建/编辑归档仓库侧滑 */}
        <RepositorySlider
          editClusterId={editClusterId.value}
          showSlider={showSlider.value}
          onHandleCancelSlider={handleCancelSlider}
          onHandleUpdatedTable={handleUpdatedTable}
        />
      </section>
    );
  },
});
