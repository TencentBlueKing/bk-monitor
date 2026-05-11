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

import { computed, defineComponent, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router/composables';

import SearchBar from './search-bar';
import UserInfoCard from './user-info-card';
import TaskListPanel from './task-list-panel';
import LogDetailPanel from './log-detail-panel';
import type { SearchParams, LogItem, UserReportStats, ProcessStatus, DataSource } from './types';
import useStore from '@/hooks/use-store';
import $http from '@/api';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import { t } from '@/hooks/use-locale';
import * as authorityMap from '@/common/authority-map';
import { isFeatureToggleOn } from '@/store/helper';

import './index.scss';

export default defineComponent({
  name: 'ClientLogSearch',
  components: {
    SearchBar,
    UserInfoCard,
    TaskListPanel,
    LogDetailPanel,
  },
  setup() {
    const store = useStore();
    const route = useRoute();
    const router = useRouter();

    /** 业务切换后检查功能开关，无权限则跳转回检索页 */
    watch(
      () => route.query.spaceUid,
      (newSpaceUid, oldSpaceUid) => {
        if (newSpaceUid && newSpaceUid !== oldSpaceUid) {
          const hasPermission = isFeatureToggleOn(
            'tgpa_task',
            [String(store.state.bkBizId), String(newSpaceUid)]
          );
          if (!hasPermission) {
            router.replace({
              name: 'retrieve',
              query: {
                spaceUid: String(newSpaceUid),
                bizId: String(store.state.bkBizId),
              },
            });
          }
        }
      }
    );

    /** 是否有下载权限 */
    const isAllowedDownload = ref(false);

    /** 获取下载权限 */
    const checkDownloadPermission = async () => {
      try {
        const params = {
          data: {
            action_ids: [authorityMap.DOWNLOAD_FILE_AUTH],
            resources: [
              {
                type: 'space',
                id: store.state.spaceUid,
              },
            ],
          },
        };
        const response = await $http.request('auth/checkAllowed', params);
        if (response.data && Array.isArray(response.data)) {
          response.data.forEach((item: any) => {
            if (item.action_id === authorityMap.DOWNLOAD_FILE_AUTH) {
              isAllowedDownload.value = item.is_allowed;
            }
          });
        } else {
          isAllowedDownload.value = false;
        }
      } catch (err) {
        console.warn('权限检查失败:', err);
        isAllowedDownload.value = false;
      }
    };

    /** 是否收起左侧任务列表面板 */
    const isTaskListCollapsed = ref(false);

    /** 当前选中的日志条目 */
    const selectedLogItem = ref<LogItem | null>(null);

    /** 当前用户累计上报统计 */
    const userReportStats = ref<UserReportStats | null>(null);

    /** 当前索引集ID */
    const indexSetId = ref<string>('');

    /** 任务列表数据 */
    const taskList = ref<LogItem[]>([]);

    /** 轮询定时器 */
    const pollingTimer = ref<number | null>(null);

    /** 组件是否已销毁 */
    const isComponentDestroyed = ref(false);

    /** 轮询间隔（毫秒） */
    const POLLING_INTERVAL = 20000;

    /** 搜索完成后是否为空数据状态 */
    const isEmptyState = computed(() => taskList.value.length === 0);

    /** 面板是否正在加载（仅手动查询） */
    const isPanelLoading = ref(false);

    /** 任务列表是否正在加载（含首次和加载更多） */
    const isTaskListLoading = ref(false);

    /** 当前搜索的时间范围 */
    const timeRange = ref<[string, string] | undefined>(undefined);

    /** 当前搜索的时区 */
    const timezone = ref<string>(window.timezone);

    /** 分页参数 */
    const page = ref(1);
    const computedPagesize = ref(10);
    const hasMore = ref(true);

    /** task-list-panel 组件实例引用，用于初始计算 pagesize */
    const taskListPanelRef = ref<any>(null);

    /**
     * 根据面板可用高度计算分页大小
     * 可用高度 = 面板高度 - 上padding(12) 上margin(16) - 下padding(12) - header(24)
     * 每个 item 占 75px
     * 分档：<10 → 10, 10~19 → 20, 20~49 → 50, ≥50 → 100
     */
    const calcPagesize = (panelHeight: number): number => {
      const availableHeight = panelHeight - 64;
      const itemCount = Math.floor(availableHeight / 75);
      if (itemCount < 10) return 10;
      if (itemCount < 20) return 20;
      if (itemCount < 50) return 50;
      return 100;
    };

    /** 上一次搜索参数，供触底加载更多使用 */
    const lastSearchParams = ref<SearchParams>({ openid: '', timeRange: ['', ''], timezone: window.timezone });

    /**
     * 请求任务列表
     * @param isLoadMore 是否为加载更多模式
     */
    const fetchTaskList = (params: SearchParams, isLoadMore = false) => {
      if (!isLoadMore) {
        page.value = 1;
        hasMore.value = true;
        isPanelLoading.value = true;
      }
      isTaskListLoading.value = true;

      const bkBizId = store.state.bkBizId;
      const [startTime, endTime] = handleTransformToTimestamp(params.timeRange);

      const query: Record<string, any> = {
        bk_biz_id: bkBizId,
        page: page.value,
        pagesize: computedPagesize.value,
      };

      // openid 是纯数字时作为 task_id，否则作为 openid
      const openidVal = params.openid.trim();
      if (openidVal) {
        if (/^\d+$/.test(openidVal)) {
          query.task_id = Number(openidVal);
        } else {
          query.openid = openidVal;
        }
      }

      if (startTime) {
        query.start_time = startTime;
      }
      if (endTime) {
        query.end_time = endTime;
      }

      $http
        .request('clientLog/getTaskList', { query })
        .then((res: any) => {
          const list = res?.data?.list ?? [];
          const total = res?.data?.total ?? 0;
          if (isLoadMore) {
            taskList.value = [...taskList.value, ...list];
          } else {
            taskList.value = list;
            // 首次加载默认选中第一项
            if (list.length > 0) {
              selectedLogItem.value = list[0];
              fetchClientInfo(list[0]);
            }
          }
          hasMore.value = taskList.value.length < total;
          // 加载完成后检查是否有 running 任务，决定是否启动轮询
          const hasRunning = taskList.value.some(item => item.process_status === 'running');
          if (hasRunning && !pollingTimer.value) {
            startPolling();
          }
        })
        .catch((_err: any) => {
          if (!isLoadMore) {
            taskList.value = [];
            selectedLogItem.value = null;
          }
        })
        .finally(() => {
          isPanelLoading.value = false;
          isTaskListLoading.value = false;
        });
    };

    /** 搜索回调 */
    const handleSearch = (params: SearchParams) => {
      stopPolling();
      timeRange.value = params.timeRange;
      timezone.value = params.timezone;
      lastSearchParams.value = params;
      fetchTaskList(params);
    };

    /** 触底加载更多 */
    const handleLoadMore = () => {
      if (isTaskListLoading.value || !hasMore.value) return;
      page.value += 1;
      fetchTaskList(lastSearchParams.value, true);
    };

    /** 切换任务列表收起状态 */
    const handleToggleTaskList = (collapsed: boolean) => {
      isTaskListCollapsed.value = collapsed;
    };

    /** 展开任务列表（从 LogDetailPanel 触发） */
    const handleExpandTaskList = () => {
      isTaskListCollapsed.value = false;
    };

    /** 点击日志条目 */
    const handleLogItemSelect = (item: LogItem) => {
      selectedLogItem.value = item;
      fetchClientInfo(item);
    };

    /**
     * 请求用户信息
     */
    const fetchClientInfo = (item: LogItem) => {
      if (!item.openid) {
        userReportStats.value = null;
        return;
      }
      const bkBizId = store.state.bkBizId;
      const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);

      const query: Record<string, any> = {
        bk_biz_id: bkBizId,
        openid: item.openid,
      };

      if (startTime) {
        query.start_time = startTime;
      }
      if (endTime) {
        query.end_time = endTime;
      }

      $http
        .request('clientLog/getClientInfo', { query })
        .then((res: any) => {
          userReportStats.value = res?.data;
        })
        .catch((_err: any) => {
          userReportStats.value = null;
        });
    };

    /** 停止轮询 */
    const stopPolling = () => {
      if (pollingTimer.value) {
        clearTimeout(pollingTimer.value);
        pollingTimer.value = null;
      }
    };

    /** 更新 taskList 中指定任务的状态 */
    const updateTaskStatus = (source: DataSource, id: number | string, status: ProcessStatus, processedAt?: string) => {
      const index = taskList.value.findIndex(item => {
        if (source === 'task') {
          return item.source === 'task' && item.task_id === id;
        }
        return item.source === 'report' && item.file_name === id;
      });
      if (index !== -1) {
        const updatedItem = { ...taskList.value[index] };
        updatedItem.process_status = status;
        if (processedAt !== undefined) {
          updatedItem.processed_at = processedAt;
        }
        taskList.value.splice(index, 1, updatedItem);
        // 同步更新 selectedLogItem
        if (selectedLogItem.value && selectedLogItem.value.source === source
          && (source === 'task' ? selectedLogItem.value.task_id === id : selectedLogItem.value.file_name === id)) {
          selectedLogItem.value = updatedItem;
        }
      }
    };

    /** 检查任务状态 */
    const checkTaskStatus = async () => {
      if (isComponentDestroyed.value) return;

      const pendingItems = taskList.value.filter(item => item.process_status === 'running' || item.process_status === 'pending');
      if (pendingItems.length === 0) {
        stopPolling();
        return;
      }

      // 按 source 分组
      const taskItems = pendingItems.filter(item => item.source === 'task');
      const reportItems = pendingItems.filter(item => item.source === 'report');

      const bkBizId = store.state.bkBizId;

      // 同时查询 task 和 report 类型任务状态
      const queries: Promise<void>[] = [];

      if (taskItems.length > 0) {
        const taskIdList = taskItems.map(item => item.task_id).filter((id): id is string => id !== null);
        queries.push(
          $http.request('clientLog/getTaskStatus', {
            data: {
              bk_biz_id: bkBizId,
              task_id_list: taskIdList,
            },
          }).then((res) => {
            if (res?.data && Array.isArray(res.data)) {
              res.data.forEach((statusItem) => {
                if (statusItem.process_status !== 'running') {
                  updateTaskStatus('task', statusItem.task_id, statusItem.process_status, statusItem.processed_at);
                }
              });
            }
          })
        );
      }

      if (reportItems.length > 0) {
        const fileNameList = reportItems.map(item => item.file_name);
        queries.push(
          $http.request('collect/getFileStatus', {
            data: {
              file_name_list: fileNameList,
            },
          }).then((res) => {
            if (res?.data && Array.isArray(res.data)) {
              res.data.forEach((statusItem: any) => {
                // report API 使用 status 字段；pending 和 running 都表示采集中
                if (statusItem.status !== 'pending' && statusItem.status !== 'running') {
                  updateTaskStatus('report', statusItem.file_name, statusItem.status as ProcessStatus);
                }
              });
            }
          })
        );
      }

      await Promise.all(queries);

      // 检查是否仍有 running 任务，决定是否继续轮询
      const stillHasRunning = taskList.value.some(item => item.process_status === 'running');
      if (stillHasRunning && !isComponentDestroyed.value) {
        startPolling();
      } else {
        stopPolling();
      }
    };

    /** 启动轮询 */
    const startPolling = () => {
      stopPolling();
      pollingTimer.value = window.setTimeout(() => {
        if (!isComponentDestroyed.value) {
          checkTaskStatus();
        }
      }, POLLING_INTERVAL);
    };

    /** 立即采集 */
    const handleCollectNow = async (item: LogItem) => {
      stopPolling();

      // 先将任务状态修改为 running
      const index = taskList.value.findIndex(t => {
        if (item.source === 'task') {
          return t.source === 'task' && t.file_name === item.file_name;
        }
        return t.source === 'report' && t.file_name === item.file_name;
      });
      if (index !== -1) {
        const updatedItem = { ...taskList.value[index], process_status: 'running' as ProcessStatus };
        taskList.value.splice(index, 1, updatedItem);
        // 如果当前选中项就是该项，同步更新选中状态
        if (selectedLogItem.value && selectedLogItem.value.source === item.source
          && (item.source === 'task' ? selectedLogItem.value.id === item.id : selectedLogItem.value.file_name === item.file_name)) {
          selectedLogItem.value = updatedItem;
        }
      }

      // 调用同步接口
      const bkBizId = store.state.bkBizId;
      try {
        if (item.source === 'task') {
          await $http.request('clientLog/syncTask', {
            data: {
              bk_biz_id: bkBizId,
              task_id_list: [item.id],
            },
          });
        } else {
          await $http.request('collect/syncUserReport', {
            data: {
              bk_biz_id: bkBizId,
              file_name_list: [item.file_name],
            },
          });
        }
      } catch (err) {
        console.error('采集失败:', err);
      }

      // 重新启动轮询
      startPolling();
    };

    // 获取索引集ID
    const getIndexSetId = async () => {
      try {
        const params = {
          query: {
            bk_biz_id: store.state.bkBizId,
          },
        };

        const response = await $http.request('collect/getTaskIndexSetId', params);
        if (response.data && response.data.index_set_id) {
          indexSetId.value = String(response.data.index_set_id);
        }
      } catch (error) {
        console.warn('获取索引集ID失败:', error);
      }
    };

    onMounted(() => {
      getIndexSetId();
      checkDownloadPermission();

      // 初始计算一次 pagesize
      const el = taskListPanelRef.value?.$el;
      if (el) {
        computedPagesize.value = calcPagesize(el.clientHeight);
      }
    });

    onUnmounted(() => {
      isComponentDestroyed.value = true;
      stopPolling();
    });

    /** 渲染空状态 */
    const renderEmptyState = () => (
      <div class='empty-state-overlay'>
        <bk-exception type='empty'>
          <div class='empty-state-content'>
            <div class='empty-state-title'>{t('检索无数据')}</div>
            <div class='empty-state-subtitle'>
              {lastSearchParams.value.openid
                ? t('未找到与 "{keyword}" 匹配的用户或任务', { keyword: lastSearchParams.value.openid })
                : t('未找到匹配的用户或任务')}
            </div>
            <div class='empty-state-tips'>
              <div>1. {t('请检查任务ID和用户ID是否输入错误')}</div>
              <div>2. {t('平台默认保存 90 天的任务记录，请检查 ID 是否过期')}</div>
              <div>
                3. {t('若检查均无问题，请联系')}
                <a
                  class='bk-helper-link'
                  href='wxwork://message/?username=BK助手'
                >
                  {t('蓝鲸助手')}
                </a>
              </div>
            </div>
          </div>
        </bk-exception>
      </div>
    );

    /** 渲染内容区域 */
    const renderContent = () => [
      <UserInfoCard userInfo={selectedLogItem.value} userReportStats={userReportStats.value} taskList={taskList.value} />,
      <div class='task-content-area'>
        {/* 左侧：任务列表 */}
        <TaskListPanel
          ref={taskListPanelRef}
          collapsed={isTaskListCollapsed.value}
          taskList={taskList.value}
          hasMore={hasMore.value}
          isLoading={isTaskListLoading.value}
          selectedLogItem={selectedLogItem.value}
          on-toggle={handleToggleTaskList}
          on-log-item-select={handleLogItemSelect}
          on-load-more={handleLoadMore}
        />
        {/* 右侧：日志详情 */}
        <LogDetailPanel
          isTaskListCollapsed={isTaskListCollapsed.value}
          selectedLogItem={selectedLogItem.value}
          indexSetId={indexSetId.value}
          timeRange={timeRange.value}
          timezone={timezone.value}
          isAllowedDownload={isAllowedDownload.value}
          on-expand={handleExpandTaskList}
          on-collect={handleCollectNow}
        />
      </div>,
    ];

    return () => (
      <div class='client-log-search-root'>
        {/* 搜索区域 */}
        <SearchBar on-search={handleSearch} />

        {/* 用户信息展示区域 + 任务内容区域 */}
        <div
          class='content-wrapper'
          v-bkloading={{ isLoading: isPanelLoading.value }}
        >
          {isEmptyState.value ? renderEmptyState() : renderContent()}
        </div>
      </div>
    );
  },
});
