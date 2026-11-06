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

import { defineComponent, ref, computed, onMounted, onBeforeUnmount } from 'vue';

import EmptyStatus from '@/components/empty-status/index.vue';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useRoute from '@/hooks/use-route';
import useRouter from '@/hooks/use-router';
import useStore from '@/hooks/use-store';
import useUtils from '@/hooks/use-utils';
import { manageDraftCacheService } from '@/storage';
import TagMore from '@/views/manage-v2/log-collection/components/common-comp/tag-more';

import DownloadUrl from './download-url.tsx';
import ListBox from './list-box.tsx';
import TaskStatusDetail from './task-status-detail.tsx';
import TextFilterDetail from './text-filter-detail.tsx';
import http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'ExtractHome',
  components: {
    ListBox,
    DownloadUrl,
    TaskStatusDetail,
    TextFilterDetail,
    EmptyStatus,
    TagMore,
  },
  setup() {
    const store = useStore();
    const { t } = useLocale();
    const router = useRouter();
    const route = useRoute();

    const searchKeyword = ref(''); // 搜索关键词
    const ordering = ref('-created_at');
    const defaultSort = { prop: 'created_at', order: 'descending' };
    const isLoading = ref(false); // 加载状态
    const taskList = ref<any[]>([]); // 任务列表
    const tableContainerRef = ref<HTMLElement | null>(null);
    const tableMaxHeight = ref<number>();

    // 只限制表格最大高度，数据较少时让分页紧随末行。
    useResizeObserve(
      () => tableContainerRef.value,
      ({ contentRect }) => {
        tableMaxHeight.value = Math.floor(contentRect.height);
      },
      false,
    );

    const pagination = ref({
      // 分页配置
      count: 0,
      current: 1,
      limit: 10,
      limitList: [10, 20, 50, 100],
    });
    const timeout = ref(10); // 轮询超时时间
    const timeoutID = ref<any>(null); // 轮询定时器ID
    const sideSlider = ref({
      isLoading: false, // 侧边栏加载状态
      isShow: false, // 侧边栏显示状态
      data: {} as any, // 侧边栏数据
    });
    const notLoadingStatus = ref(['downloadable', 'redownloadable', 'expired', 'failed']); // 非加载中的状态列表
    const doneStatus = ref(['redownloadable', 'expired', 'failed']); // 已完成的状态列表
    const emptyType = ref('empty'); // 空状态类型
    const displayNameList = ref<any[]>([]); // 显示名称列表

    // 轮询列表
    const pollingList = computed(() => {
      return taskList.value.filter(item => !doneStatus.value.includes(item.download_status));
    });

    // 初始化任务列表
    const initTaskList = async () => {
      try {
        clearTimeout(timeoutID.value);
        isLoading.value = true;
        emptyType.value = searchKeyword.value ? 'search-empty' : 'empty';
        const payload: any = {
          query: {
            bk_biz_id: store.state.bkBizId,
            page: pagination.value.current,
            pagesize: pagination.value.limit,
            ...(ordering.value && { ordering: ordering.value }),
          },
        };
        if (searchKeyword.value) {
          payload.query.keyword = searchKeyword.value;
        }
        const res = await http.request('extract/getTaskList', payload);
        pagination.value.count = res.data.total;
        // 获取请求displayName的 ipList参数列表
        const allIpList = res.data.list.reduce((pre: any[], cur: any) => {
          if (!cur.enable_clone) {
            return pre;
          }
          pre.push(
            ...cur.ip_list.map((item: any) => {
              if (item?.bk_host_id) {
                return {
                  host_id: item.bk_host_id,
                };
              }
              return {
                ip: item.ip ?? '',
                cloud_id: item.bk_cloud_id ?? '',
              };
            }),
          );
          return pre;
        }, []);
        // 获取displayName
        await queryDisplayName(allIpList);
        const { formatResponseListTimeZoneString } = useUtils();
        taskList.value = formatResponseListTimeZoneString(res.data.list || [], {}, ['created_at', 'updated_at']);
        timeout.value = res.data.timeout || 10;
        pollingTaskStatus();
      } catch (e) {
        console.warn(e);
        emptyType.value = '500';
      } finally {
        isLoading.value = false;
      }
    };

    // 查询显示名称
    const queryDisplayName = async (hostList: any[]) => {
      try {
        const res = await http.request('extract/getIpListDisplayName', {
          data: {
            host_list: hostList,
          },
          params: {
            bk_biz_id: store.state.bkBizId,
          },
        });
        displayNameList.value = res.data;
      } catch {
        displayNameList.value = [];
      }
    };

    // 轮询任务状态
    const pollingTaskStatus = () => {
      if (route.name !== 'extract-home') {
        clearTimeout(timeoutID.value);
        timeoutID.value = null;
        return;
      }

      timeoutID.value = setTimeout(async () => {
        if (!pollingList.value.length) {
          return;
        }
        try {
          const res = await http.request('extract/pollingTaskStatus', {
            query: {
              task_list: pollingList.value.map(item => item.task_id).join(','),
            },
          });

          for (const newItem of res.data) {
            const taskItem = taskList.value.find(item => item.task_id === newItem.task_id);
            if (taskItem) {
              taskItem.task_process_info = newItem.task_process_info;
              taskItem.download_status = newItem.download_status;
              taskItem.download_status_display = newItem.download_status_display;
            }
          }
        } catch (err) {
          console.warn(err);
        }
        pollingTaskStatus();
      }, timeout.value * 1000);
    };

    // 处理页面可见性变化
    const handleVisibilityChange = () => {
      if (document.hidden) {
        clearTimeout(timeoutID.value);
      } else {
        initTaskList();
      }
    };

    // 处理搜索
    const handleSearch = () => {
      pagination.value.current = 1;
      initTaskList();
    };

    const handleSortChange = ({ prop, order }: { prop?: string | null; order?: string | null }) => {
      if (prop && prop !== 'created_at') {
        return;
      }
      let nextOrdering = '';
      if (prop && order) {
        nextOrdering = order === 'ascending' ? 'created_at' : '-created_at';
      }
      if (ordering.value === nextOrdering) {
        return;
      }
      ordering.value = nextOrdering;
      pagination.value.current = 1;
      initTaskList();
    };

    // 查看详情
    const viewDetail = async (row: any) => {
      try {
        sideSlider.value.isShow = true;
        sideSlider.value.isLoading = true;
        sideSlider.value.data = {};
        const res = await http.request('extract/getTaskDetail', {
          params: {
            id: row.task_id,
          },
        });
        sideSlider.value.data = res.data;
      } catch (err) {
        console.warn(err);
      } finally {
        sideSlider.value.isLoading = false;
      }
    };

    // 处理分页变化
    const handlePageChange = (page: number) => {
      if (pagination.value.current !== page) {
        pagination.value.current = page;
        initTaskList();
      }
    };

    // 处理每页数量变化
    const handlePageLimitChange = (limit: number) => {
      pagination.value.limit = limit;
      pagination.value.current = 1;
      initTaskList();
    };

    // 创建任务
    const handleCreateTask = () => {
      router.push({
        name: 'extract-create',
        query: {
          ...route.query,
        },
      });
    };

    // 克隆任务
    const cloneTask = (row: any) => {
      if (!row.enable_clone) {
        return;
      }
      sessionStorage.setItem('cloneData', JSON.stringify(row));
      manageDraftCacheService.set('cloneData', row, { source: 'extract-task' }).catch(() => {});
      router.push({
        name: 'extract-clone',
        query: {
          ...route.query,
        },
      });
    };

    // 下载文件
    const downloadFile = ({ task_id: taskId }: any) => {
      let urlPrefix = (window as any).AJAX_URL_PREFIX;
      if (!urlPrefix.endsWith('/')) {
        urlPrefix += '/';
      }
      const { bkBizId } = store.state;

      const downloadUrl = `${urlPrefix}log_extract/tasks/download/?task_id=${taskId}&bk_biz_id=${bkBizId}`;
      window.open(downloadUrl);
    };

    // 重新下载文件
    const reDownloadFile = async ({ task_id }: any) => {
      try {
        isLoading.value = true;
        await http.request('extract/reDownloadFile', {
          data: {
            task_id,
            bk_biz_id: store.state.bkBizId,
          },
        });
        await initTaskList();
      } catch (e) {
        console.warn(e);
        isLoading.value = false;
      }
    };

    // 获取下载目标列表
    const getDownloadTheTargetList = (targetItem: any) => {
      if (targetItem.enable_clone) {
        return getIPDisplayNameList(targetItem.ip_list);
      }
      return targetItem.ip_list;
    };

    // 获取IP显示名称列表
    const getIPDisplayNameList = (ipList: any[]) => {
      if (ipList?.length) {
        return ipList.map(item => {
          return (
            displayNameList.value.find(dItem => {
              const hostMatch = item.bk_host_id === dItem.bk_host_id;
              const ipMatch = `${item.ip}_${item.bk_cloud_id}` === `${dItem.bk_host_innerip}_${dItem.bk_cloud_id}`;
              if (item?.bk_host_id) {
                return hostMatch || ipMatch;
              }
              return ipMatch;
            })?.display_name || ''
          );
        });
      }
      return [];
    };

    // 处理操作
    const handleOperation = (type: string) => {
      if (type === 'clear-filter') {
        searchKeyword.value = '';
        pagination.value.current = 1;
        initTaskList();
        return;
      }

      if (type === 'refresh') {
        emptyType.value = 'empty';
        pagination.value.current = 1;
        initTaskList();
        return;
      }
    };

    // 生命周期
    onMounted(() => {
      initTaskList();
      document.addEventListener('visibilitychange', handleVisibilityChange);
    });

    onBeforeUnmount(() => {
      clearTimeout(timeoutID.value);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    });

    // 表头渲染函数
    const renderHeader = (_: any, { column }: any) => <span>{column.label}</span>;

    // 主渲染函数
    return () => (
      <div
        class='extract-task-list-container'
        v-bkloading={{ isLoading: isLoading.value }}
        data-test-id='logExtraction_div_fromBox'
      >
        {/* 新建和搜索框 */}
        <div class='option-container'>
          <bk-button
            class='create-task-button'
            data-test-id='fromBox_button_addNewExtraction'
            theme='primary'
            onClick={handleCreateTask}
          >
            {t('新建')}
          </bk-button>
          <bk-input
            class='king-input-search'
            clearable={true}
            data-test-id='fromBox_input_searchExtraction'
            right-icon='bk-icon icon-search'
            placeholder={t('搜索 文件名、创建人')}
            value={searchKeyword.value}
            on-right-icon-click={handleSearch}
            onChange={val => (searchKeyword.value = val)}
            onClear={handleSearch}
            onEnter={handleSearch}
          />
        </div>

        {/* 表格 */}
        <div
          ref={tableContainerRef}
          class='extract-task-table-container'
        >
          <bk-table
            class='king-table'
            max-height={tableMaxHeight.value}
            scopedSlots={{
              empty: () => (
                <div>
                  <EmptyStatus
                    empty-type={emptyType.value}
                    on-operation={handleOperation}
                  />
                </div>
              ),
            }}
            data={taskList.value}
            data-test-id='fromBox_table_tableBox'
            default-sort={defaultSort}
            pagination={pagination.value}
            onPage-change={handlePageChange}
            onPage-limit-change={handlePageLimitChange}
            onSort-change={handleSortChange}
          >
            {/* 授权目标列 */}
            <bk-table-column
              scopedSlots={{
                default: ({ row }: any) => (
                  <div class='authorized-target'>
                    <i18n path='{0} 个节点'>
                      <button
                        class='authorized-target-count'
                        data-test-id='extraction_button_targetDetail'
                        type='button'
                        onClick={() => viewDetail(row)}
                      >
                        {row.ip_list?.length ?? 0}
                      </button>
                    </i18n>
                  </div>
                ),
              }}
              label={t('授权目标')}
              min-width='180'
              renderHeader={renderHeader}
            />

            {/* 文件列 */}
            <bk-table-column
              scopedSlots={{
                default: ({ row }: any) =>
                  row.file_path?.length ? (
                    <TagMore
                      className='extract-file-tags'
                      gap={4}
                      keepFirstTag={false}
                      maxRows={1}
                      maxTagWidth={2400}
                      mode='index-set'
                      tags={row.file_path.map((file: string, index: number) => ({ id: index, name: file }))}
                      tooltipMode='overflow'
                      tooltipTarget='more'
                    />
                  ) : (
                    '--'
                  ),
              }}
              label={t('文件')}
              min-width='240'
              renderHeader={renderHeader}
            />

            {/* 目标类型列 */}
            <bk-table-column
              scopedSlots={{
                default: () => (
                  <bk-tag
                    class='target-type-tag'
                    radius='4px'
                    theme='warning'
                  >
                    {t('主机')}
                  </bk-tag>
                ),
              }}
              label={t('目标类型')}
              width='110'
              renderHeader={renderHeader}
            />

            {/* 创建时间列 */}
            <bk-table-column
              label={t('创建时间')}
              width='190'
              prop='created_at'
              renderHeader={renderHeader}
              sortable='custom'
            />

            {/* 创建人列 */}
            <bk-table-column
              label={t('创建人')}
              width='110'
              prop='created_by'
              renderHeader={renderHeader}
              scopedSlots={{
                default: (props: any) => <bk-user-display-name user-id={props.row.created_by}></bk-user-display-name>,
              }}
            />

            {/* 任务状态列 */}
            <bk-table-column
              scopedSlots={{
                default: ({ row }: any) => (
                  <div class='task-status'>
                    <span
                      class='task-status-icon'
                      key={row.download_status}
                    >
                      {notLoadingStatus.value.includes(row.download_status) ? (
                        <div
                          class={[
                            'status-dot',
                            ['downloadable', 'redownloadable'].includes(row.download_status)
                              ? 'status-success'
                              : 'status-failed',
                          ]}
                        />
                      ) : (
                        <bk-spin size='mini' />
                      )}
                    </span>
                    <span class='task-status-text'>{row.download_status_display}</span>
                    {row.download_status === 'failed' && (
                      <span
                        class='task-status-info bklog-icon bklog-info-fill'
                        v-bk-tooltips={{
                          disabled: !row.task_process_info,
                          content: row.task_process_info,
                        }}
                      />
                    )}
                  </div>
                ),
              }}
              label={t('任务状态')}
              width='180'
              renderHeader={renderHeader}
            />

            {/* 操作列 */}
            <bk-table-column
              width='160'
              scopedSlots={{
                default: ({ row }: any) => (
                  <div class='task-operation-container'>
                    <span
                      class='task-operation'
                      onClick={() => viewDetail(row)}
                    >
                      {t('详情')}
                    </span>
                    <span
                      class={['task-operation', !row.enable_clone && 'cannot-click']}
                      v-bk-tooltips={{
                        content: row.message,
                        disabled: row.enable_clone,
                        delay: 300,
                        placement: 'top',
                      }}
                      onClick={() => cloneTask(row)}
                    >
                      {t('克隆')}
                    </span>
                    {row.download_status === 'downloadable' && (
                      <span
                        class='task-operation'
                        onClick={() => downloadFile(row)}
                      >
                        {t('下载')}
                      </span>
                    )}
                    {row.download_status === 'redownloadable' && (
                      <span
                        class='task-operation'
                        onClick={() => reDownloadFile(row)}
                      >
                        {t('重试')}
                      </span>
                    )}
                  </div>
                ),
              }}
              label={t('操作')}
              renderHeader={renderHeader}
            />
          </bk-table>
        </div>

        {/* 右侧边栏 */}
        <bk-sideslider
          width={660}
          is-show={sideSlider.value.isShow}
          quick-close={true}
          show-mask={true}
          title={t('详情')}
          transfer
          {...{
            on: {
              'update:isShow': (val: boolean) => {
                sideSlider.value.isShow = val;
              },
            },
          }}
        >
          <template slot='content'>
            <div
              class='extract-task-detail-content'
              v-bkloading={{ isLoading: sideSlider.value.isLoading }}
            >
              <ListBox
                icon='bklog-icon bklog-info-fill'
                mark={true}
                title={sideSlider.value.data.task_process_info}
              />
              <TaskStatusDetail status-data={sideSlider.value.data.task_step_status} />
              <DownloadUrl task-id={sideSlider.value.data.task_id} />
              <ListBox
                icon='bk-icon icon-sitemap'
                list={sideSlider.value.data.preview_directory}
                title={t('文件路径')}
              />
              <ListBox
                icon='bk-icon icon-data'
                list={getDownloadTheTargetList(sideSlider.value.data)}
                title={t('文件来源主机')}
              />
              <ListBox
                icon='bk-icon icon-file'
                list={sideSlider.value.data.file_path}
                title={t('文件列表')}
              />
              <ListBox
                icon='bk-icon icon-clock'
                list={sideSlider.value.data.expiration_date}
                title={t('过期时间')}
              />
              {sideSlider.value.data.filter_type && <TextFilterDetail data={sideSlider.value.data} />}
            </div>
          </template>
        </bk-sideslider>
      </div>
    );
  },
});
