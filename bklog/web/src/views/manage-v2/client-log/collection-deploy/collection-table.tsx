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

import { computed, defineComponent, ref } from 'vue';

import { clearTableFilter, downFile } from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';

import { t } from '@/hooks/use-locale';
import * as authorityMap from '../../../../common/authority-map';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { TRIGGER_FREQUENCY_OPTIONS, CLIENT_TYPE_OPTIONS } from '../constant';
import { TaskStatus, TaskScene } from './types';
import { useTableSetting } from '../hooks/use-table-setting';
import { useSearchTask } from '../hooks/use-search-task';
import http from '@/api';

import './collection-table.scss';

export default defineComponent({
  name: 'CollectionTable',
  components: {
    EmptyStatus,
  },
  props: {
    keyword: {
      type: String,
      default: '',
    },
    pagination: {
      type: Object,
      default: () => ({
        current: 1,
        count: 0,
        limit: 10,
        limitList: [10, 20, 50, 100],
      }),
    },
    isAllowedDownload: {
      type: Boolean,
      default: false,
    },
    data: {
      type: Array,
      default: () => [],
    },
    indexSetId: {
      type: String,
      default: '',
    },
    hasFilter: {
      type: Boolean,
      default: false,
    },
    createdBys: {
      type: Array,
      default: () => [],
    },
  },
  emits: [
    'clear-keyword',
    'clone-task',
    'view-task',
    'page-change',
    'page-limit-change',
    'filter-change',
    'sort-change',
  ],
  setup(props, { emit }) {
    const store = useStore();

    const logTableRef = ref(null); // 表格引用

    // 表格字段配置
    const tableFields = [
      { id: 'task_id', label: t('任务 ID') },
      { id: 'task_name', label: t('任务名称'), disabled: true },
      { id: 'openid', label: 'openid', disabled: true },
      { id: 'status_name', label: t('任务状态') },
      { id: 'scene_name', label: t('任务阶段') },
      { id: 'created_by', label: t('创建人') },
      { id: 'created_at', label: t('创建时间') },
      { id: 'log_path', label: t('日志路径') },
      { id: 'frequency', label: t('触发频率') },
      { id: 'platform', label: t('客户端类型') },
      { id: 'max_file_num', label: t('最大文件个数') },
    ];

    // 默认显示的字段ID
    const defaultSelectedIds = [
      'task_id',
      'task_name',
      'openid',
      'status_name',
      'scene_name',
      'created_by',
      'created_at',
      'log_path',
    ];

    // 使用表格设置 hook
    const { columnSetting, checkFields, handleSettingChange } = useTableSetting({
      cacheKey: 'clientLog',
      fields: tableFields,
      defaultSelectedIds,
    });

    // 使用检索任务 Hook
    const { searchTask } = useSearchTask({
      indexSetId: props.indexSetId,
    });

    // 任务状态选项
    const taskStatuses = [
      { text: t('待审批'), value: TaskStatus.PENDING_APPROVAL },
      { text: t('审批通过'), value: TaskStatus.APPROVED },
      { text: t('审批拒绝'), value: TaskStatus.REJECTED },
      { text: t('已创建'), value: TaskStatus.CREATED },
      { text: t('执行中'), value: TaskStatus.RUNNING },
      { text: t('停止'), value: TaskStatus.STOPPED },
      { text: t('执行失败'), value: TaskStatus.FAILED },
      { text: t('执行完成'), value: TaskStatus.COMPLETED },
      { text: t('创建失败'), value: TaskStatus.CREATE_FAILED },
      { text: t('认领超时'), value: TaskStatus.CLAIM_TIMEOUT },
      { text: t('执行超时'), value: TaskStatus.EXECUTION_TIMEOUT },
      { text: t('认领中'), value: TaskStatus.CLAIMING },
      { text: t('已删除'), value: TaskStatus.DELETED },
      { text: t('创建中'), value: TaskStatus.CREATING },
      { text: t('启动中'), value: TaskStatus.STARTING },
    ];

    // 任务阶段选项
    const taskScenes = [
      { text: t('登录后'), value: TaskScene.AFTER_LOGIN },
      { text: t('登录前'), value: TaskScene.BEFORE_LOGIN },
    ];

    // 添加分页变化事件处理函数
    const handlePageChange = (current: number) => {
      emit('page-change', current);
    };

    // 添加分页限制变化事件处理函数
    const handlePageLimitChange = (limit: number) => {
      emit('page-limit-change', limit);
    };

    // 过滤器变化事件处理函数
    const handleFilterChange = (filters: any) => {
      emit('filter-change', filters);
    };

    // 排序变化事件处理函数
    const handleSortChange = (sort: any) => {
      emit('sort-change', sort);
    };

    // 空状态类型计算属性
    const emptyType = computed(() => {
      return props.hasFilter ? 'search-empty' : 'empty';
    });

    // 清空过滤条件
    const clearFilters = () => {
      clearTableFilter(logTableRef.value);
      emit('clear-keyword');
    };

    // 克隆任务
    const cloneTask = (task: any) => {
      emit('clone-task', task);
    };

    // 查看任务
    const viewTask = (task: any) => {
      emit('view-task', task);
    };

    // 下载文件
    const downloadFile = async (id: number, status: number) => {
      if (status !== TaskStatus.COMPLETED) {
        return;
      }
      if (props.isAllowedDownload) {
        try {
          const params = {
            query: {
              bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
              id,
            },
          };
          const response = await http.request('collect/getDownloadLink', params);
          const downloadUrl = response.data.url;
          if (downloadUrl) {
            downFile(downloadUrl);
          }
        } catch (error) {
          console.warn('获取下载链接失败:', error);
        }
      } else {
        const paramData = {
          action_ids: [authorityMap.DOWNLOAD_FILE_AUTH],
          resources: [
            {
              type: 'space',
              id: store.state.spaceUid,
            },
          ],
        };
        const res = await store.dispatch('getApplyData', paramData);
        store.commit('updateState', { authDialogData: res.data });
      }
    };

    // 检索任务 - 直接传入查询条件
    const handleSearchTask = (row: any) => {
      const conditions = [
        {
          field: 'task_id',
          operator: '=',
          value: row.task_id,
        },
      ];
      searchTask(conditions, [row.processed_at, 'now']);
    };

    // 任务名称插槽
    const nameSlot = {
      default: ({ row }) => (
        <bk-button
          class='king-button name-button'
          text
          theme='primary'
          on-click={() => viewTask(row)}
        >
          {row.task_name}
        </bk-button>
      ),
    };

    // openid插槽
    const openidSlot = {
      default: ({ row }) => <span class=''>{row.openid.split('\n').join(';')}</span>,
    };

    // 任务状态插槽
    const statusSlot = {
      default: ({ row }) => {
        // 加载中状态：执行中、创建中、启动中、认领中
        const loadingStatuses = [TaskStatus.RUNNING, TaskStatus.CREATING, TaskStatus.STARTING, TaskStatus.CLAIMING];

        // 失败状态：创建失败、认领超时、审批拒绝、执行失败、执行超时
        const failedStatuses = [
          TaskStatus.CREATE_FAILED,
          TaskStatus.CLAIM_TIMEOUT,
          TaskStatus.REJECTED,
          TaskStatus.FAILED,
          TaskStatus.EXECUTION_TIMEOUT,
        ];

        // 成功状态：审批通过、执行完成、已创建
        const successStatuses = [TaskStatus.APPROVED, TaskStatus.COMPLETED, TaskStatus.CREATED];

        // 停止状态：停止、已删除
        const stoppedStatuses = [TaskStatus.STOPPED, TaskStatus.DELETED];

        // 待审批状态
        const pendingStatuses = [TaskStatus.PENDING_APPROVAL];

        const renderStatusIcon = () => {
          if (loadingStatuses.includes(row.status)) {
            return <bk-spin size='mini'></bk-spin>;
          }
          if (failedStatuses.includes(row.status)) {
            return <div class='status-dot status-failed'></div>;
          }
          if (successStatuses.includes(row.status)) {
            return <div class='status-dot status-success'></div>;
          }
          if (stoppedStatuses.includes(row.status)) {
            return <div class='status-dot status-stopped'></div>;
          }
          if (pendingStatuses.includes(row.status)) {
            return <div class='status-dot status-pending'></div>;
          }
          return null;
        };

        return (
          <div class='status-row'>
            <div
              class='status-icon'
              key={row.status}
            >
              {renderStatusIcon()}
            </div>
            {row.status_name}
          </div>
        );
      },
    };

    // 创建人插槽
    const creatorSlot = {
      default: ({ row }) => <bk-user-display-name user-id={row.created_by}></bk-user-display-name>,
    };

    // 客户端类型插槽
    const platformSlot = {
      default: ({ row }) => (
        <div class='platform-row'>
          {CLIENT_TYPE_OPTIONS.find(option => option.value === row.platform)?.label || row.platform}
        </div>
      ),
    };

    // 触发频率插槽
    const frequencySlot = {
      default: ({ row }) => (
        <div class='frequency-row'>
          {TRIGGER_FREQUENCY_OPTIONS.find(option => option.value === row.frequency)?.label || row.frequency}
        </div>
      ),
    };

    // 操作项插槽
    const operateSlot = {
      default: ({ row }: any) => (
        <div class='log-table-operate'>
          <span
            class='king-button'
            v-bk-tooltips={{
              content: t('任务未处理完成'),
              disabled: row.process_status === 'success',
            }}
          >
            <bk-button
              text
              theme='primary'
              disabled={row.process_status !== 'success'}
              on-click={() => handleSearchTask(row)}
            >
              {t('检索')}
            </bk-button>
          </span>
          <bk-button
            class='king-button'
            text
            theme='primary'
            on-click={() => cloneTask(row)}
          >
            {t('克隆')}
          </bk-button>
          <span
            class='king-button'
            v-bk-tooltips={{
              content: t('暂无下载链接，请在任务完成后点击下载'),
              disabled: row.status === TaskStatus.COMPLETED,
            }}
          >
            <bk-button
              disabled={row.status !== TaskStatus.COMPLETED}
              text
              class={[
                {
                  'disabled-download': !props.isAllowedDownload,
                },
              ]}
              theme='primary'
              v-cursor={{
                active: row.status === TaskStatus.COMPLETED && !props.isAllowedDownload,
              }}
              on-click={() => downloadFile(row.id, row.status)}
            >
              {t('下载文件')}
            </bk-button>
          </span>
        </div>
      ),
    };

    return () => (
      <div class='log-table'>
        <bk-table
          data={props.data}
          pagination={props.pagination}
          outer-border={false}
          ref={logTableRef}
          onPage-change={handlePageChange}
          onPage-limit-change={handlePageLimitChange}
          onFilter-change={handleFilterChange}
          onSort-change={handleSortChange}
          scopedSlots={{
            empty: () => (
              <div>
                <EmptyStatus
                  emptyType={emptyType.value}
                  on-operation={clearFilters}
                />
              </div>
            ),
          }}
        >
          {checkFields('task_id') && (
            <bk-table-column
              key='task_id'
              class-name='filter-column overflow-hidden-text'
              width='100'
              label={t('任务 ID')}
              prop='task_id'
            />
          )}
          <bk-table-column
            key='task_name'
            class-name='filter-column'
            min-width='140'
            label={t('任务名称')}
            prop='task_name'
            scopedSlots={nameSlot}
          />
          <bk-table-column
            key='openid'
            class-name='filter-column overflow-hidden-text'
            min-width='140'
            label='openid'
            prop='openid'
            scopedSlots={openidSlot}
          />
          {checkFields('status_name') && (
            <bk-table-column
              key='status_name'
              class-name='filter-column overflow-hidden-text'
              width='120'
              label={t('任务状态')}
              prop='status_name'
              column-key='status'
              filters={taskStatuses}
              filter-multiple={false}
              scopedSlots={statusSlot}
            />
          )}
          {checkFields('scene_name') && (
            <bk-table-column
              key='scene_name'
              class-name='filter-column overflow-hidden-text'
              width='100'
              label={t('任务阶段')}
              prop='scene_name'
              column-key='scene'
              filters={taskScenes}
              filter-multiple={false}
            />
          )}
          {checkFields('created_by') && (
            <bk-table-column
              key='created_by'
              class-name='filter-column overflow-hidden-text'
              min-width='100'
              label={t('创建人')}
              prop='created_by'
              column-key='created_by'
              filters={props.createdBys}
              filter-multiple={false}
              filter-searchable
              scopedSlots={creatorSlot}
            />
          )}
          {checkFields('created_at') && (
            <bk-table-column
              key='created_at'
              class-name='filter-column overflow-hidden-text'
              width='190'
              label={t('创建时间')}
              prop='created_at'
              sortable
            />
          )}
          {checkFields('log_path') && (
            <bk-table-column
              key='log_path'
              class-name='filter-column overflow-hidden-text'
              min-width='160'
              label={t('日志路径')}
              prop='log_path'
            />
          )}
          {checkFields('frequency') && (
            <bk-table-column
              key='frequency'
              class-name='filter-column overflow-hidden-text'
              width='100'
              label={t('触发频率')}
              prop='frequency'
              scopedSlots={frequencySlot}
            />
          )}
          {checkFields('platform') && (
            <bk-table-column
              key='platform'
              class-name='filter-column overflow-hidden-text'
              width='100'
              label={t('客户端类型')}
              prop='platform'
              scopedSlots={platformSlot}
            />
          )}
          {checkFields('max_file_num') && (
            <bk-table-column
              key='max_file_num'
              class-name='filter-column overflow-hidden-text'
              width='120'
              label={t('最大文件个数')}
              prop='max_file_num'
            />
          )}
          <bk-table-column
            label={t('操作')}
            width='150'
            fixed='right'
            scopedSlots={operateSlot}
          />
          <bk-table-column
            type='setting'
            key='setting'
            tippy-options={{ zIndex: 3000 }}
          >
            <bk-table-setting-content
              v-en-style='width: 530px'
              fields={columnSetting.value.fields}
              selected={columnSetting.value.selectedFields}
              on-setting-change={handleSettingChange}
            />
          </bk-table-column>
        </bk-table>
      </div>
    );
  },
});
