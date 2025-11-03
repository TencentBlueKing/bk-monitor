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
import { formatFileSize, clearTableFilter } from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { InfoBox, Message } from 'bk-magic-vue';

import RestoreSlider from '../archive-restore/restore-slider.tsx';
import ListSlider from './list-slider.tsx';
import StateTable from './state-table.tsx';
import http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'ArchiveList',
  components: {
    StateTable,
    ListSlider,
    RestoreSlider,
    EmptyStatus,
  },
  setup() {
    const store = useStore();
    const { t } = useLocale(); // 获取国际化函数
    const archiveTable = ref<any>(null); // 表格引用

    const isTableLoading = ref(false); // 表格加载状态
    // const isRenderSlider = ref(true); // 是否渲染侧滑组件
    const showRestoreSlider = ref(false); // 是否显示回溯侧滑
    const showSlider = ref(false); // 是否显示归档侧滑
    const keyword = ref(''); // 搜索关键词
    const editArchiveId = ref<null | number>(null); // 编辑的归档ID
    const editArchive = ref<any>(null); // 编辑的归档数据
    const dataList = ref<any[]>([]); // 表格数据列表
    const emptyType = ref('empty'); // 空状态类型
    const pagination = reactive({
      // 分页配置
      current: 1,
      count: 0,
      limit: 10,
      limitList: [10, 20, 50, 100],
    });

    const bkBizId = computed(() => store.getters.bkBizId); // 业务ID
    const authorityMapComputed = computed(() => authorityMap); // 权限映射计算属性

    // 获取文件大小
    const getFileSize = (size: number) => {
      return formatFileSize(size);
    };

    // 获取过期天数
    const getExpiredDays = (props: any) => {
      return props.row.snapshot_days ? `${props.row.snapshot_days} ${t('天')}` : t('永久');
    };

    // 请求数据
    const requestData = () => {
      isTableLoading.value = true;
      emptyType.value = keyword.value ? 'search-empty' : 'empty';

      http
        .request('archive/getArchiveList', {
          query: {
            keyword: keyword.value,
            bk_biz_id: bkBizId.value,
            page: pagination.current,
            pagesize: pagination.limit,
          },
        })
        .then((res: any) => {
          const { data } = res;
          pagination.count = data.total;
          dataList.value = data.list;
        })
        .catch((err: any) => {
          console.warn(err);
        })
        .finally(() => {
          isTableLoading.value = false;
        });
    };

    // 搜索
    const search = () => {
      pagination.current = 1;
      requestData();
    };

    // 新建归档
    const handleCreate = () => {
      editArchive.value = null;
      showSlider.value = true;
    };

    // 分页变换
    const handlePageChange = (page: number) => {
      if (pagination.current !== page) {
        pagination.current = page;
        requestData();
      }
    };

    // 分页限制
    const handleLimitChange = (limit: number) => {
      if (pagination.limit !== limit) {
        pagination.current = 1;
        pagination.limit = limit;
        requestData();
      }
    };

    // 更新归档后回调
    const handleUpdatedTable = () => {
      showSlider.value = false;
      search();
    };

    // 关闭归档侧滑弹窗
    const handleCancelSlider = () => {
      showSlider.value = false;
    };

    // 关闭回溯侧滑弹窗
    const handleCancelRestoreSlider = () => {
      showRestoreSlider.value = false;
    };

    // 更新回溯后回调
    const handleUpdatedRestore = () => {
      showRestoreSlider.value = false;
      editArchiveId.value = null;
    };

    // 操作处理
    const operateHandler = (row: any, operateType: string) => {
      if (!row.permission?.[authorityMapComputed.value.MANAGE_COLLECTION_AUTH]) {
        return getOptionApplyData({
          action_ids: [authorityMapComputed.value.MANAGE_COLLECTION_AUTH],
          resources: [
            {
              type: 'collection',
              id: row.instance_id,
            },
          ],
        });
      }

      if (operateType === 'restore') {
        editArchiveId.value = row.archive_config_id;
        showRestoreSlider.value = true;
        return;
      }

      if (operateType === 'edit') {
        editArchive.value = row;
        showSlider.value = true;
        return;
      }

      if (operateType === 'delete') {
        InfoBox({
          type: 'warning',
          subTitle: t('当前归档ID为{n}，确认要删除？', { n: row.archive_config_id }),
          confirmFn: () => {
            requestDelete(row);
          },
        });
        return;
      }
    };

    // 删除请求
    const requestDelete = (row: any) => {
      http
        .request('archive/deleteArchive', {
          params: {
            archive_config_id: row.archive_config_id,
          },
        })
        // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
        .then((res: any) => {
          if (res.result) {
            const page =
              dataList.value.length <= 1 ? (pagination.current > 1 ? pagination.current - 1 : 1) : pagination.current;
            Message({
              theme: 'success',
              message: t('删除成功'),
            });
            if (page !== pagination.current) {
              handlePageChange(page);
            } else {
              requestData();
            }
          }
        })
        .catch(() => {});
    };

    // 权限申请
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

    // 操作处理
    const handleOperation = (type: string) => {
      if (type === 'clear-filter') {
        keyword.value = '';
        clearTableFilter(archiveTable.value);
        search();
        return;
      }

      if (type === 'refresh') {
        emptyType.value = 'empty';
        search();
        return;
      }
    };

    // 组件挂载时获取数据
    onMounted(() => {
      search();
    });

    // 表头渲染函数
    const renderHeader = (_: any, { column }: any) => <span>{column.label}</span>;

    return () => (
      <section
        class='log-archive-list'
        data-test-id='archive_section_archiveList'
      >
        {/* 顶部操作栏 */}
        <section class='top-operation'>
          <bk-button
            class='fl'
            data-test-id='archiveList_button_newArchive'
            theme='primary'
            onClick={handleCreate}
          >
            {t('新建')}
          </bk-button>
          <div class='fr list-search'>
            <bk-input
              data-test-id='archiveList_input_searchListItem'
              placeholder={t('请输入名称')}
              right-icon='bk-icon icon-search'
              value={keyword.value}
              clearable
              on-right-icon-click={search}
              onChange={val => (keyword.value = val)}
              onEnter={search}
            />
          </div>
        </section>

        {/* 表格区域 */}
        <section class='log-archive-table'>
          <bk-table
            ref={archiveTable}
            class='archive-table'
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
            data={dataList.value}
            data-test-id='archiveList_section_tableList'
            limit-list={pagination.limitList}
            pagination={pagination}
            onPage-change={handlePageChange}
            onPage-limit-change={handleLimitChange}
          >
            <bk-table-column
              width='30'
              scopedSlots={{
                default: (props: any) => (
                  <div class='state-table-wrapper'>
                    <StateTable archiveConfigId={props.row.archive_config_id} />
                  </div>
                ),
              }}
              align='center'
              type='expand'
            />
            <bk-table-column
              width='100'
              label='ID'
              scopedSlots={{ default: (props: any) => props.row.archive_config_id }}
            />
            <bk-table-column
              label={t('名称')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.instance_name }}
            />
            <bk-table-column
              label={t('过期设置')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => getExpiredDays(props) }}
            />
            <bk-table-column
              label={t('总大小')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => getFileSize(props.row.store_size) }}
            />
            <bk-table-column
              label={t('索引数量')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.index_count }}
            />
            <bk-table-column
              label={t('归档仓库')}
              prop='target_snapshot_repository_name'
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.target_snapshot_repository_name }}
            />
            <bk-table-column
              width='200'
              scopedSlots={{
                default: (props: any) => (
                  <div class='collect-table-operate'>
                    {/* 回溯 */}
                    <bk-button
                      class='mr10 king-button'
                      disabled={!props.row.permission?.[authorityMapComputed.value.MANAGE_COLLECTION_AUTH]}
                      theme='primary'
                      text
                      onClick={() => operateHandler(props.row, 'restore')}
                    >
                      {t('回溯')}
                    </bk-button>
                    {/* 编辑 */}
                    <bk-button
                      class='mr10 king-button'
                      disabled={!props.row.permission?.[authorityMapComputed.value.MANAGE_COLLECTION_AUTH]}
                      theme='primary'
                      text
                      onClick={() => operateHandler(props.row, 'edit')}
                    >
                      {t('编辑')}
                    </bk-button>
                    {/* 删除 */}
                    <bk-button
                      class='mr10 king-button'
                      disabled={!props.row.permission?.[authorityMapComputed.value.MANAGE_COLLECTION_AUTH]}
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

        {/* 新增/编辑归档 */}
        <ListSlider
          editArchive={editArchive.value}
          showSlider={showSlider.value}
          onHandleCancelSlider={handleCancelSlider}
          onHandleUpdatedTable={handleUpdatedTable}
        />

        {/* 新建回溯 */}
        <RestoreSlider
          archiveId={editArchiveId.value}
          showSlider={showRestoreSlider.value}
          onHandleCancelSlider={handleCancelRestoreSlider}
          onHandleUpdatedTable={handleUpdatedRestore}
        />
      </section>
    );
  },
});
