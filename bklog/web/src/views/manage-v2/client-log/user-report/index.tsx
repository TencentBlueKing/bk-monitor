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

import { defineComponent, ref, onMounted, onBeforeUnmount, watch } from 'vue';

import { t } from '@/hooks/use-locale';
import http from '@/api';
import { BK_LOG_STORAGE } from '@/store/store.type';
import useStore from '@/hooks/use-store';
import useRouter from '@/hooks/use-router';
import useUtils from '@/hooks/use-utils';
import ReportTable from './report-table';
import BatchUpload from './batch-upload';
import UploadResult from './upload-result';
import { FileUploadStatus, UploadStatus, UserReportItem, FileStatusItem } from './types';

import './index.scss';

export default defineComponent({
  name: 'UserReport',
  components: {
    ReportTable,
    BatchUpload,
    UploadResult,
  },
  props: {
    isAllowedDownload: {
      type: Boolean,
      default: false,
    },
    indexSetId: {
      type: String,
      default: '',
    },
    paginationConfig: {
      type: Object,
      default: () => ({
        limit: 10,
        limitList: [10, 20, 50, 100],
      }),
    },
  },
  emits: ['update-total'],
  setup(props, { emit }) {
    const store = useStore();
    const router = useRouter();

    const searchKeyword = ref('');
    const isLoading = ref(false);
    const showBatchUpload = ref(false);
    const showUploadResult = ref(false);
    const uploadStatus = ref<UploadStatus>(UploadStatus.RUNNING);
    const uploadData = ref<{ file_name_list: string[]; openid_list: string[] } | null>(null);
    const tableData = ref<{
      list: UserReportItem[];
      total: number;
    }>({
      list: [],
      total: 0,
    });

    // 分页状态
    const pagination = ref({
      current: 1,
      limit: props.paginationConfig.limit,
    });

    // 排序状态
    const sortParams = ref({
      order_field: '',
      order_type: '',
    });

    // 文件状态轮询相关状态（30秒轮询）
    const fileStatusTimer = ref(null);
    const shouldPollFileStatus = ref(false);
    const isComponentDestroyed = ref(false);

    // 同步任务轮询相关状态（10秒轮询）
    const syncTaskTimer = ref(null);
    const currentRecordId = ref<string>('');

    // 上传请求版本号，用于忽略过期请求的响应
    let uploadRequestId = 0;

    // 获取同步记录状态的方法
    const getSyncRecord = async (recordId: string): Promise<{ status: string } | null> => {
      try {
        const params = {
          query: {
            record_id: recordId,
          },
        };

        const response = await http.request('collect/getSyncRecord', params);
        return response.data;
      } catch (error) {
        console.error('获取同步记录状态失败:', error);
        return null;
      }
    };

    // 获取文件状态的方法
    const getFileStatus = async (fileNameList: string[]): Promise<FileStatusItem[]> => {
      try {
        const params = {
          data: {
            file_name_list: fileNameList,
          },
        };

        const response = await http.request('collect/getFileStatus', params);
        return response.data;
      } catch (error) {
        console.error('获取文件状态失败:', error);
        return [];
      }
    };

    // 启动文件状态轮询（30秒）
    const startFileStatusPolling = (immediate = false) => {
      stopFileStatusPolling();

      // 如果需要立即执行一次
      if (immediate) {
        pollFileStatus();
      } else {
        // 否则按正常间隔轮询
        fileStatusTimer.value = setTimeout(() => {
          if (shouldPollFileStatus.value && !isComponentDestroyed.value) {
            pollFileStatus();
          }
        }, 30000); // 30秒轮询一次
      }
    };

    // 停止文件状态轮询
    const stopFileStatusPolling = () => {
      if (fileStatusTimer.value) {
        clearTimeout(fileStatusTimer.value);
        fileStatusTimer.value = null;
      }
    };

    // 停止同步任务轮询
    const stopSyncTaskPolling = () => {
      if (syncTaskTimer.value) {
        clearTimeout(syncTaskTimer.value);
        syncTaskTimer.value = null;
      }
      currentRecordId.value = '';
    };

    // 启动同步任务轮询（10秒）
    const startSyncTaskPolling = (recordId: string) => {
      stopSyncTaskPolling();
      currentRecordId.value = recordId;

      const pollSyncTask = async () => {
        if (isComponentDestroyed.value || !currentRecordId.value) {
          return;
        }

        try {
          const syncRecord = await getSyncRecord(currentRecordId.value);

          if (syncRecord) {
            let { status } = syncRecord;

            if (status === FileUploadStatus.PENDING) {
              status = UploadStatus.RUNNING; // PENDING 状态表示任务在排队等待处理 也算正在处理中
            }

            if (status === UploadStatus.RUNNING) {
              // 继续轮询
              syncTaskTimer.value = setTimeout(pollSyncTask, 10000);
              return;
            }

            // 成功或失败，更新状态
            uploadStatus.value = status as UploadStatus;
          } else {
            // 获取同步记录失败，标记为失败
            uploadStatus.value = UploadStatus.FAILED;
          }
        } catch (error) {
          console.error('轮询同步状态失败:', error);
          uploadStatus.value = UploadStatus.FAILED;
        }

        // 更新表格中匹配项的状态
        updateItemsStatus(
          uploadData.value.file_name_list,
          uploadData.value.openid_list,
          uploadStatus.value as unknown as FileUploadStatus,
        );

        // 统一处理轮询结束后的逻辑
        stopSyncTaskPolling();
        startFileStatusPolling(true);
      };

      // 立即执行第一次轮询
      pollSyncTask();
    };

    // 判断是否需要轮询文件状态
    const checkShouldPollFileStatus = (dataList: UserReportItem[] | FileStatusItem[]) => {
      if (isComponentDestroyed.value) {
        return;
      }

      shouldPollFileStatus.value = false;

      // 检查是否有未完成的任务
      if (Array.isArray(dataList)) {
        dataList.forEach((item) => {
          if (item.status && item.status !== FileUploadStatus.SUCCESS) {
            shouldPollFileStatus.value = true;
          }
        });
      }

      // 如果需要轮询，启动轮询
      if (shouldPollFileStatus.value) {
        startFileStatusPolling();
      } else {
        stopFileStatusPolling();
      }
    };

    // 轮询获取文件状态
    const pollFileStatus = async () => {
      if (isComponentDestroyed.value) return;

      const list = tableData.value.list;
      if (!list || list.length === 0) return;

      // 提取所有文件名
      const fileNames = list.map((item: UserReportItem) => item.file_name).filter((fileName: string) => fileName);

      if (fileNames.length === 0) return;

      try {
        const statusData = await getFileStatus(fileNames);

        if (Array.isArray(statusData) && statusData.length > 0) {
          // 创建状态映射并更新列表
          const statusMap = new Map<string, FileUploadStatus>();
          statusData.forEach((item: FileStatusItem) => {
            statusMap.set(item.file_name, item.status);
          });

          // 更新列表中的状态
          tableData.value.list = list.map((item: UserReportItem) => {
            const newStatus = statusMap.get(item.file_name);
            return newStatus !== undefined ? { ...item, status: newStatus } : item;
          });

          // 检查是否需要继续轮询
          checkShouldPollFileStatus(statusData);
        }
      } catch (error) {
        console.warn('轮询获取文件状态失败:', error);
        // 轮询失败时停止轮询
        stopFileStatusPolling();
      }
    };

    const { formatResponseListTimeZoneString } = useUtils();

    // 获取用户上报数据
    const fetchUserReportData = async () => {
      isLoading.value = true;
      try {
        const params = {
          query: {
            bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
            page: pagination.value.current,
            pagesize: pagination.value.limit,
            ...(searchKeyword.value && { keyword: searchKeyword.value }),
            ...(sortParams.value.order_field && {
              order_field: sortParams.value.order_field,
              order_type: sortParams.value.order_type,
            }),
          },
        };

        const response = await http.request('collect/getUserReportList', params);
        const originalList: UserReportItem[] = response.data.list || [];

        // 格式化响应数据中的时间字段
        const formattedList = formatResponseListTimeZoneString(originalList, {}, ['report_time']);

        tableData.value = {
          list: formattedList,
          total: response.data.total || 0,
        };

        // 通知父组件更新 tab 中的 count
        emit('update-total', tableData.value.total);

        // 获取列表数据后，检查是否需要轮询
        checkShouldPollFileStatus(formattedList);
      } catch (error) {
        console.error('获取用户上报数据失败:', error);
      } finally {
        isLoading.value = false;
      }
    };

    // 搜索处理
    const handleSearch = (keyword: string) => {
      searchKeyword.value = keyword;
      pagination.value.current = 1;
      fetchUserReportData();
    };

    // 分页变化处理
    const handlePageChange = (current: number) => {
      pagination.value.current = current;
      fetchUserReportData();
    };

    // 分页大小变化处理
    const handlePageLimitChange = (limit: number) => {
      pagination.value.limit = limit;
      pagination.value.current = 1;
      fetchUserReportData();
    };

    // 排序变化处理
    const handleSortChange = (sortData: { order_field: string; order_type: string }) => {
      sortParams.value = sortData;
      fetchUserReportData();
    };

    // 清洗配置
    // const handleCleanConfig = () => {};

    // 搜索框回车事件
    // const handleSearchEnter = (keyword: string) => {
    //   handleSearch(keyword);
    // };

    // 搜索图标点击事件
    // const handleSearchIconClick = (keyword: string) => {
    //   handleSearch(keyword);
    // };

    // 清空搜索
    // const handleClearSearch = () => {
    //   searchKeyword.value = '';
    //   handleSearch('');
    // };

    const handleViewSDKDoc = () => {
      const sdkDocUrl = 'https://iwiki.woa.com/p/4013039938';
      window.open(sdkDocUrl, '_blank');
    };

    // 批量上传按钮点击事件
    const handleBatchUpload = () => {
      showBatchUpload.value = true;
    };

    // 批量上传确认事件
    const handleBatchUploadConfirm = (data: { file_name_list: string[]; openid_list: string[] }) => {
      handleUpload({
        ...data,
      });
    };

    // 更新表格中匹配项的状态
    const updateItemsStatus = (fileNameList: string[], openidList: string[], status: FileUploadStatus) => {
      const fileNameSet = new Set(fileNameList);
      const openidSet = new Set(openidList);

      tableData.value.list = tableData.value.list.map((item: UserReportItem) => {
        if (fileNameSet.has(item.file_name) || openidSet.has(item.openid)) {
          return { ...item, status };
        }
        return item;
      });
    };

    // 上传事件
    const handleUpload = async (data: { file_name_list: string[]; openid_list: string[] }) => {
      // 生成新的请求ID
      uploadRequestId += 1;
      const currentRequestId = uploadRequestId;

      // 保存上传数据，用于重试
      uploadData.value = data;
      // 显示上传结果弹窗
      showUploadResult.value = true;
      uploadStatus.value = UploadStatus.RUNNING;
      stopFileStatusPolling();

      // 更新表格中匹配项的状态为RUNNING
      updateItemsStatus(data.file_name_list, data.openid_list, FileUploadStatus.RUNNING);

      try {
        const requestData: any = {
          bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
        };

        if (data.file_name_list && data.file_name_list.length > 0) {
          requestData.file_name_list = data.file_name_list;
        }
        if (data.openid_list && data.openid_list.length > 0) {
          requestData.openid_list = data.openid_list;
        }

        const params = {
          data: requestData,
        };

        const response = await http.request('collect/syncUserReport', params);

        // 检查是否是最新的请求，如果不是则忽略响应
        if (currentRequestId !== uploadRequestId) {
          return;
        }

        // 获取record_id并开始轮询同步状态
        if (response.data && response.data.record_id) {
          startSyncTaskPolling(response.data.record_id);
        } else {
          // 没有返回record_id，标记为失败
          uploadStatus.value = UploadStatus.FAILED;
          stopSyncTaskPolling();
        }
      } catch (error) {
        // 检查是否是最新的请求，如果不是则忽略
        if (currentRequestId !== uploadRequestId) {
          return;
        }

        console.error('上传失败:', error);
        // 上传失败
        uploadStatus.value = UploadStatus.FAILED;
        stopSyncTaskPolling();
      }
    };

    // 关闭上传结果弹窗
    const handleUploadResultClose = () => {
      showUploadResult.value = false;

      uploadRequestId += 1;

      stopSyncTaskPolling();
      startFileStatusPolling();
    };

    // 重试上传
    const handleUploadRetry = () => {
      if (uploadData.value) {
        handleUpload(uploadData.value);
      }
    };

    // 去首页查询
    const handleGoSearch = () => {
      // 跳转到检索页面
      router.push({
        name: 'retrieve',
        params: {
          indexId: props.indexSetId,
        },
      });
    };

    // 返回列表
    const handleBackList = () => {
      showUploadResult.value = false;
    };

    // 监听搜索关键词变化，如果为空则自动搜索
    watch(
      () => searchKeyword.value,
      (newVal) => {
        if (!newVal) {
          handleSearch('');
        }
      },
    );

    // 监听 total 变化，通知父组件更新 tab 中的 count
    watch(
      () => tableData.value.total,
      (newTotal) => {
        emit('update-total', newTotal);
      },
    );

    onMounted(() => {
      fetchUserReportData();
    });

    onBeforeUnmount(() => {
      // 标记组件已销毁
      isComponentDestroyed.value = true;
      // 清理文件状态轮询定时器
      stopFileStatusPolling();
      // 清理同步任务轮询定时器
      stopSyncTaskPolling();
    });

    return () => (
      <div class='user-report'>
        {/* Alert 提示 */}
        <span onClick={handleViewSDKDoc}>
          <bk-alert
            class='alert-info'
            type='info'
            title={t('使用本功能，需要在您的项目中集成并初始化相应的软件开发工具包（SDK），点击查看。')}
          ></bk-alert>
        </span>

        {/* 操作区域 */}
        <div class='operating-area'>
          <div>
            <bk-button
              theme='primary'
              on-click={handleBatchUpload}
              disabled={isLoading.value}
            >
              {t('批量上传')}
            </bk-button>
            {/* <bk-button onClick={handleCleanConfig}>{t('清洗配置')}</bk-button> */}
          </div>
          {/* <div>
            <bk-input
              value={searchKeyword.value}
              placeholder={t('搜索 任务 ID、任务名称、openID、创建方式、任务状态、任务阶段、创建人')}
              clearable
              right-icon='bk-icon icon-search'
              onEnter={handleSearchEnter}
              onRight-icon-click={handleSearchIconClick}
              onClear={handleClearSearch}
            ></bk-input>
          </div> */}
        </div>

        {/* 表格区域 */}
        <ReportTable
          data={tableData.value.list}
          total={tableData.value.total}
          keyword={searchKeyword.value}
          loading={isLoading.value}
          isAllowedDownload={props.isAllowedDownload}
          indexSetId={props.indexSetId}
          paginationConfig={props.paginationConfig}
          on-page-change={handlePageChange}
          on-page-limit-change={handlePageLimitChange}
          on-search={handleSearch}
          on-sort-change={handleSortChange}
          on-upload={handleUpload}
        />

        {/* 批量上传弹窗 */}
        <BatchUpload
          show={showBatchUpload.value}
          on-cancel={(val: boolean) => (showBatchUpload.value = val)}
          on-confirm={handleBatchUploadConfirm}
        />

        {/* 上传结果弹窗 */}
        <UploadResult
          show={showUploadResult.value}
          status={uploadStatus.value}
          on-close={handleUploadResultClose}
          on-retry={handleUploadRetry}
          on-go-search={handleGoSearch}
          on-back-list={handleBackList}
        />
      </div>
    );
  },
});
