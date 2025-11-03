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

import { defineComponent, ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue';

import * as authorityMap from '@/common/authority-map';
import { formatFileSize } from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { InfoBox, Message } from 'bk-magic-vue';

import RestoreSlider from './restore-slider.tsx';
import http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'ArchiveRestore',
  components: {
    RestoreSlider,
    EmptyStatus,
  },
  setup() {
    const store = useStore();
    const { t } = useLocale();

    const isTableLoading = ref(false); // 表格加载状态
    const showSlider = ref(false); // 是否显示侧滑
    const editRestore = ref<any>(null); // 编辑的回溯数据
    const timer = ref<any>(null); // 定时器引用
    const timerNum = ref(0); // 定时器编号
    const keyword = ref(''); // 搜索关键词
    const dataList = ref<any[]>([]); // 表格数据列表
    const restoreIds = ref<number[]>([]); // 异步获取状态参数
    const emptyType = ref('empty'); // 空状态类型
    const pagination = reactive({
      // 分页配置
      current: 1,
      count: 0,
      limit: 10,
      limitList: [10, 20, 50, 100],
    });

    const bkBizId = computed(() => store.getters.bkBizId); // 业务ID
    const authorityMapComputed = computed(() => authorityMap); // 权限映射

    // 搜索处理
    const search = () => {
      pagination.current = 1;
      stopStatusPolling();
      requestData();
    };

    // 新建回溯
    const handleCreate = () => {
      showSlider.value = true;
      editRestore.value = null;
    };

    // 分页页码变更
    const handlePageChange = (page: number) => {
      if (pagination.current !== page) {
        pagination.current = page;
        stopStatusPolling();
        requestData();
      }
    };

    // 分页条数变更
    const handleLimitChange = (limit: number) => {
      if (pagination.limit !== limit) {
        pagination.current = 1;
        pagination.limit = limit;
        stopStatusPolling();
        requestData();
      }
    };

    // 更新回溯后回调
    const handleUpdatedTable = () => {
      showSlider.value = false;
      search();
    };

    // 关闭新增回溯/编辑归回溯滑弹窗
    const handleCancelSlider = () => {
      showSlider.value = false;
    };

    // 开始状态轮询
    const startStatusPolling = () => {
      timerNum.value += 1;
      const currentTimerNum = timerNum.value;
      stopStatusPolling();
      timer.value = setTimeout(() => {
        if (currentTimerNum === timerNum.value && restoreIds.value.length) {
          requestRestoreStatus(true);
        }
      }, 10_000);
    };

    // 停止状态轮询
    const stopStatusPolling = () => {
      if (timer.value) {
        clearTimeout(timer.value);
        timer.value = null;
      }
    };

    // 获取回溯列表
    const requestRestoreList = async () => {
      try {
        const res = await http.request('archive/restoreList', {
          query: {
            keyword: keyword.value,
            bk_biz_id: bkBizId.value,
            page: pagination.current,
            pagesize: pagination.limit,
          },
        });
        const { data } = res;
        restoreIds.value = [];
        pagination.count = data.total;
        for (const row of data.list) {
          row.status = '';
          row.status_name = '';
          restoreIds.value.push(row.restore_config_id);
        }
        dataList.value.splice(0, dataList.value.length, ...data.list);
        return res;
      } catch (error) {
        console.warn('获取回溯列表失败:', error);
        throw error;
      } finally {
        isTableLoading.value = false;
      }
    };

    // 请求数据
    const requestData = async () => {
      isTableLoading.value = true;
      emptyType.value = keyword.value ? 'search-empty' : 'empty';

      try {
        await requestRestoreList();
        if (restoreIds.value.length) {
          requestRestoreStatus();
        }
      } catch {
        emptyType.value = '500';
      } finally {
        isTableLoading.value = false;
      }
    };

    // 获取回溯状态
    const requestRestoreStatus = async (isPrivate = false) => {
      const currentTimerNum = timerNum.value;

      try {
        const res = await http.request('archive/getRestoreStatus', {
          data: {
            restore_config_ids: restoreIds.value,
          },
        });

        if (currentTimerNum === timerNum.value) {
          statusHandler(res.data || []);
          startStatusPolling();
        }
      } catch (error) {
        if (isPrivate) {
          stopStatusPolling();
        }
        console.warn('获取回溯状态失败:', error);
      }
    };

    // 状态处理
    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
    const statusHandler = (data: any[]) => {
      for (const item of data) {
        for (const row of dataList.value) {
          if (row.restore_config_id === item.restore_config_id) {
            const completeCount = item.complete_doc_count;
            const totalCount = item.total_doc_count;

            if (completeCount >= totalCount) {
              row.status = 'finish';
              row.status_name = t('完成');
            }
            if (completeCount === 0) {
              row.status = 'unStart';
              row.status_name = t('未开始');
            }
            if (completeCount > 0 && completeCount < totalCount) {
              const percent = `${Math.round((completeCount / totalCount) * 100)}%`;
              row.status = 'restoring';
              row.status_name = `${t('回溯中')}(${percent})`;
            }
          }
        }
      }
    };

    // 操作处理
    const operateHandler = (row: any, operateType: string) => {
      if (operateType === 'search' && !row.permission?.[authorityMapComputed.value.SEARCH_LOG_AUTH]) {
        return getOptionApplyData({
          action_ids: [authorityMapComputed.value.SEARCH_LOG_AUTH],
          resources: [
            {
              type: 'indices',
              id: row.index_set_id,
            },
          ],
        });
      }

      if (
        (operateType === 'edit' || operateType === 'delete') &&
        !row.permission?.[authorityMapComputed.value.MANAGE_COLLECTION_AUTH]
      ) {
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

      if (operateType === 'search') {
        // 跳转到检索页面
        window.location.href = `#/retrieve/${row.index_set_id}`;
        return;
      }

      if (operateType === 'edit') {
        editRestore.value = row;
        showSlider.value = true;
        return;
      }

      if (operateType === 'delete') {
        InfoBox({
          type: 'warning',
          title: t('确认删除该回溯？'),
          confirmFn: () => requestDelete(row),
        });
      }
    };

    // 删除请求
    const requestDelete = async (row: any) => {
      try {
        const res = await http.request('archive/deleteRestore', {
          params: {
            restore_config_id: row.restore_config_id,
          },
        });

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
      } catch (error) {
        console.warn('删除失败:', error);
      }
    };

    // 获取文件大小
    const getFileSize = (size: number) => formatFileSize(size);

    // 权限申请
    const getOptionApplyData = async (paramData: any) => {
      try {
        isTableLoading.value = true;
        const res = await store.dispatch('getApplyData', paramData);
        store.commit('updateState', { authDialogData: res.data });
      } catch (err) {
        console.warn('权限申请失败:', err);
      } finally {
        isTableLoading.value = false;
      }
    };

    // 操作处理
    const handleOperation = (type: string) => {
      if (type === 'clear-filter') {
        keyword.value = '';
        search();
        return;
      }

      if (type === 'refresh') {
        emptyType.value = 'empty';
        search();
        return;
      }
    };

    // 表头渲染函数
    const renderHeader = (_: any, { column }: any) => <span>{column.label}</span>;

    // 组件挂载时初始化
    onMounted(() => {
      search();
    });

    // 组件卸载前清理定时器
    onBeforeUnmount(() => {
      timerNum.value = -1;
      stopStatusPolling();
    });

    return () => (
      <section
        class='log-archive-restore'
        data-test-id='archive_section_restoreContainer'
      >
        {/* 顶部操作栏 */}
        <section class='top-operation'>
          <bk-button
            class='fl'
            data-test-id='restoreContainer_button_addNewRestore'
            theme='primary'
            onClick={handleCreate}
          >
            {t('新建')}
          </bk-button>
          <div class='restore-search fr'>
            <bk-input
              data-test-id='restoreContainer_input_searchRestoreItem'
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
        <section class='log-restore-table'>
          <bk-table
            class='restore-table'
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
            limit-list={pagination.limitList}
            pagination={pagination}
            onPage-change={handlePageChange}
            onPage-limit-change={handleLimitChange}
          >
            <bk-table-column
              label={t('索引集名称')}
              min-width='200'
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.index_set_name }}
            />
            <bk-table-column
              label={t('归档项')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.instance_name }}
            />
            <bk-table-column
              label={t('时间范围')}
              min-width='240'
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => `${props.row.start_time} - ${props.row.end_time}` }}
            />
            <bk-table-column
              class-name='filter-column'
              label={t('资源占用')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => getFileSize(props.row.total_store_size) }}
            />
            <bk-table-column
              label={t('过期时间')}
              min-width='120'
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => props.row.expired_time }}
            />
            <bk-table-column
              scopedSlots={{
                default: (props: any) => (
                  <div class='restore-status'>
                    <span class={`status-icon is-${props.row.status}`} />
                    <span class='status-text'>{props.row.status_name}</span>
                  </div>
                ),
              }}
              label={t('回溯状态')}
              renderHeader={renderHeader}
            />
            <bk-table-column
              label={t('是否过期')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (props: any) => (props.row.is_expired ? t('是') : t('否')) }}
            />
            <bk-table-column
              width='180'
              scopedSlots={{
                default: (props: any) => (
                  <div class='restore-table-operate'>
                    {/* 检索 */}
                    <bk-button
                      class='mr10 king-button'
                      vCursor={{
                        active: !props.row.permission?.[authorityMapComputed.value.MANAGE_COLLECTION_AUTH],
                      }}
                      disabled={props.row.is_expired}
                      theme='primary'
                      text
                      onClick={() => operateHandler(props.row, 'search')}
                    >
                      {t('检索')}
                    </bk-button>
                    {/* 编辑 */}
                    <bk-button
                      class='mr10 king-button'
                      vCursor={{
                        active: !props.row.permission?.[authorityMapComputed.value.MANAGE_COLLECTION_AUTH],
                      }}
                      disabled={props.row.is_expired}
                      theme='primary'
                      text
                      onClick={() => operateHandler(props.row, 'edit')}
                    >
                      {t('编辑')}
                    </bk-button>
                    {/* 删除 */}
                    <bk-button
                      class='mr10 king-button'
                      vCursor={{
                        active: !props.row.permission?.[authorityMapComputed.value.MANAGE_COLLECTION_AUTH],
                      }}
                      disabled={props.row.is_expired}
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

        {/* 新增/编辑回溯侧滑 */}
        <RestoreSlider
          editRestore={editRestore.value}
          showSlider={showSlider.value}
          onHandleCancelSlider={handleCancelSlider}
          onHandleUpdatedTable={handleUpdatedTable}
        />
      </section>
    );
  },
});
