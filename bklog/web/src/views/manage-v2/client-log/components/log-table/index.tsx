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

import { computed, defineComponent, onMounted, ref, watch } from 'vue';

import { clearTableFilter, getDefaultSettingSelectFiled, setDefaultSettingSelectFiled } from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';

import { t } from '@/hooks/use-locale';
import { TRIGGER_FREQUENCY_OPTIONS, CLIENT_TYPE_OPTIONS } from '../../constant';

import './index.scss';

export default defineComponent({
  name: 'LogTable',
  components: {
    EmptyStatus,
  },
  props: {
    keyword: {
      type: String,
      default: '',
    },
    total: {
      type: Number,
      default: 0,
    },
    data: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['clear-keyword', 'clone-task', 'view-task'],
  setup(props, { emit }) {
    const pagination = ref({
      current: 1,
      count: props.total,
      limit: 10,
      limitList: [10, 20, 50, 100],
    });

    const createTypes = ref([]); // 创建方式
    const createdBys = ref([]); // 创建人
    const logTableRef = ref(null); // 表格引用
    const settingCacheKey = 'clientLog'; // 设置缓存键
    const tableDataSort = ref({
      id: '',
      order: '',
    });

    const settingFields = ref([
      { id: 'id', label: t('任务 ID') },
      { id: 'task_name', label: t('任务名称'), disabled: true },
      { id: 'openid', label: 'openid', disabled: true },
      { id: 'create_type', label: t('创建方式') },
      { id: 'status_name', label: t('任务状态') },
      { id: 'scene_name', label: t('任务阶段') },
      { id: 'created_by', label: t('创建人') },
      { id: 'created_at', label: t('创建时间') },
      { id: 'log_path', label: t('日志路径') },
      { id: 'frequency', label: t('触发频率') },
      { id: 'platform', label: t('客户端类型') },
      { id: 'max_file_num', label: t('最大文件个数') },
    ]);

    const columnSetting = ref({
      fields: settingFields.value,
      selectedFields: settingFields.value.slice(0, 8),
    });

    // 任务状态选项
    const taskStatuses = [
      { text: t('待审批'), value: -3 },
      { text: t('审批通过'), value: -2 },
      { text: t('审批拒绝'), value: -1 },
      { text: t('已创建'), value: 0 },
      { text: t('执行中'), value: 1 },
      { text: t('停止'), value: 2 },
      { text: t('执行失败'), value: 3 },
      { text: t('执行完成'), value: 4 },
      { text: t('创建失败'), value: 5 },
      { text: t('认领超时'), value: 6 },
      { text: t('执行超时'), value: 7 },
      { text: t('认领中'), value: 8 },
      { text: t('已删除'), value: 9 },
      { text: t('创建中'), value: 10 },
      { text: t('启动中'), value: 11 },
    ];

    // 任务阶段选项
    const taskScenes = [
      { text: t('登录后'), value: 4 },
      { text: t('登录前'), value: 1 },
    ];

    // 当前筛选条件
    const filterParams = ref({
      create_type: [],
      status: [],
      scene: [],
      created_by: [],
    });

    // 从日志数据中提取去重数据
    const extractUniqueData = () => {
      if (!props.data || props.data.length === 0) {
        return;
      }

      // 提取创建方式
      const types = [...new Set(props.data.map(item => item.create_type))].filter(Boolean);
      createTypes.value = types.map(type => ({ text: type, value: type }));

      // 提取创建人
      const creators = [...new Set(props.data.map(item => item.created_by))].filter(Boolean);
      createdBys.value = creators.map(creator => ({ text: creator, value: creator }));
    };

    // 监听data变化，更新提取的数据
    watch(
      () => props.data,
      () => {
        pagination.value.current = 1;
        extractUniqueData();
      },
    );

    watch(
      () => props.total,
      (newTotal) => {
        pagination.value.count = newTotal;
      },
    );

    // 关键词搜索后重置分页
    watch(
      () => props.keyword,
      () => {
        pagination.value.current = 1;
      },
    );

    // 添加分页变化事件处理函数
    const handlePageChange = (current: number) => {
      pagination.value.current = current;
    };

    // 添加分页限制变化事件处理函数
    const handlePageLimitChange = (limit: number) => {
      pagination.value.limit = limit;
      pagination.value.current = 1;
    };

    // 根据过滤参数过滤日志列表
    const filterByParams = (list, params) => {
      return list.filter((item) => {
        return Object.keys(params).every((key) => {
          const paramValue = params[key];
          if (filterIsNotCompared(paramValue)) {
            return true;
          }
          return item[key].toString() === paramValue;
        });
      });
    };

    // 根据排序参数排序日志列表
    const sortLogList = (list) => {
      const { id, order } = tableDataSort.value;

      // 检查是否有有效的排序条件
      if (!id || !order) {
        return list;
      }

      // 只允许特定字段进行排序
      const allowedSortFields = ['id', 'task_name', 'openid', 'created_at'];
      if (!allowedSortFields.includes(id)) {
        return list;
      }

      const isAsc = order === 'ascending';

      return [...list].sort((a, b) => {
        let compareResult = 0;

        // 根据不同字段使用不同的排序逻辑
        switch (id) {
          case 'id':
            compareResult = a[id] - b[id];
            break;

          case 'task_name':
          case 'openid':
            compareResult = (a[id] || '').localeCompare(b[id] || '');
            break;

          case 'created_at':
            compareResult = (a[id] || '').localeCompare(b[id] || '');
            break;

          default:
            return 0;
        }

        // 根据排序方向返回结果
        return isAsc ? compareResult : -compareResult;
      });
    };

    // 过滤后的日志列表
    const filteredLogList = computed(() => {
      let logList = props.data;

      if (isFilterSearch.value) {
        logList = filterByParams(logList, filterParams.value);
      }

      // 关键词搜索
      if (props.keyword) {
        const keywordLower = props.keyword.trim().toLowerCase();
        logList = logList.filter((item: Record<string, any>) => {
          const searchFields = [
            item.id?.toString() || '',
            item.task_name || '',
            item.openid || '',
            item.create_type || '',
            item.status_name || '',
            item.scene_name || '',
            item.created_by || '',
          ];

          return searchFields.some(field => field.toLowerCase().includes(keywordLower));
        });
      }

      changePagination({ count: logList.length });

      return logList;
    });

    // 显示的日志列表
    const logShowList = computed(() => {
      const logList = sortLogList(filteredLogList.value);

      const { current, limit } = pagination.value;
      const startIndex = (current - 1) * limit;
      const endIndex = current * limit;
      return logList.slice(startIndex, endIndex);
    });

    // 空状态类型计算属性
    const emptyType = computed(() => {
      return props.keyword || isFilterSearch.value ? 'search-empty' : 'empty';
    });

    // 是否筛选搜索
    const isFilterSearch = computed(() => {
      return !!Object.values(filterParams.value).some(item => !filterIsNotCompared(item));
    });

    // 过滤器变化事件处理函数
    const handleFilterChange = (filters: any) => {
      // 更新当前过滤条件
      Object.keys(filters).forEach((key) => {
        filterParams.value[key] = filters[key].join('');
      });
      handlePageChange(1);
    };

    // 排序变化事件处理函数
    const handleSortChange = (sort: any) => {
      const { prop, order } = sort;
      tableDataSort.value = {
        id: prop,
        order,
      };
    };

    // 过滤条件是否为空
    const filterIsNotCompared = (val: string | any[]) => {
      if (typeof val === 'string' && val === '') return true;
      if (Array.isArray(val) && !val.length) return true;
      return false;
    };

    // 更新分页信息
    const changePagination = (paginationValue = {}) => {
      Object.assign(pagination.value, paginationValue);
    };

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
    const downloadFile = (downloadUrl: string) => {
      window.open(downloadUrl);
    };

    // 检查字段显示
    const checkFields = (field: string) => {
      return columnSetting.value.selectedFields.some(item => item.id === field);
    };

    // 设置变化处理
    const handleSettingChange = ({ fields }) => {
      columnSetting.value.selectedFields.splice(0, columnSetting.value.selectedFields.length, ...fields);
      setDefaultSettingSelectFiled(settingCacheKey, fields);
    };

    // 计算limit
    const calculateLimitList = () => {
      const fixedHeight = 368; // 需要减去的固定高度
      const rowHeight = 43; // 行固定高度

      // 获取浏览器高度
      const clientHeight = document.documentElement.offsetHeight;

      // 计算可以显示的行数
      const rows = Math.ceil((clientHeight - fixedHeight) / rowHeight);
      // 根据可显示行数设置合适的limit
      if (rows < 10) {
        pagination.value.limit = 10;
      } else if (rows < 20) {
        pagination.value.limit = 20;
      } else if (rows < 50) {
        pagination.value.limit = 50;
      } else {
        pagination.value.limit = 100;
      }
    };

    calculateLimitList();

    onMounted(() => {
      const { selectedFields } = columnSetting.value;
      columnSetting.value.selectedFields = getDefaultSettingSelectFiled(settingCacheKey, selectedFields);
    });

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
      default: ({ row }) => (
        <div class='status-row'>
          <div
            class='status-icon'
            key={row.status}
          >
            {row.status === 8 && <bk-spin size='mini'></bk-spin>}
            {row.status === 6 && <div class='claimed-expired'></div>}
          </div>
          {row.status_name}
        </div>
      ),
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
          <bk-button
            class='king-button'
            text
            theme='primary'
            on-click={() => cloneTask(row)}
          >
            {t('克隆')}
          </bk-button>
          <bk-button
            class='king-button'
            text
            theme='primary'
            disabled={!row.permission?.search_client_log || row.download_url === ''}
            on-click={() => downloadFile(row.download_url)}
          >
            {t('下载文件')}
          </bk-button>
        </div>
      ),
    };

    return () => (
      <div class='log-table'>
        <bk-table
          data={logShowList.value}
          pagination={pagination.value}
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
          {checkFields('id') && (
            <bk-table-column
              key='id'
              class-name='filter-column overflow-hidden-text'
              width='100'
              label={t('任务 ID')}
              prop='id'
              sortable
            />
          )}
          <bk-table-column
            key='task_name'
            class-name='filter-column'
            min-width='140'
            label={t('任务名称')}
            prop='task_name'
            scopedSlots={nameSlot}
            sortable
          />
          <bk-table-column
            key='openid'
            class-name='filter-column overflow-hidden-text'
            min-width='140'
            label='openid'
            prop='openid'
            scopedSlots={openidSlot}
            sortable
          />
          {checkFields('create_type') && (
            <bk-table-column
              key='create_type'
              class-name='filter-column overflow-hidden-text'
              min-width='100'
              label={t('创建方式')}
              prop='create_type'
              column-key='create_type'
              filters={createTypes}
              filter-multiple={false}
            />
          )}
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
              filters={createdBys}
              filter-multiple={false}
              filter-searchable
              scopedSlots={creatorSlot}
            />
          )}
          {checkFields('created_at') && (
            <bk-table-column
              key='created_at'
              class-name='filter-column overflow-hidden-text'
              width='160'
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
