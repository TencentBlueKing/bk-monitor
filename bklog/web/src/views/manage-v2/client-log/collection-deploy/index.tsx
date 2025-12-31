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

import { defineComponent, onBeforeUnmount, onMounted, ref } from 'vue';

import useStore from '@/hooks/use-store';
import useUtils from '@/hooks/use-utils';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { t } from '@/hooks/use-locale';
import * as authorityMap from '../../../../common/authority-map';
import { tenantManager, UserInfoLoadedEventData } from '@/views/retrieve-core/tenant-manager';
import { TaskStatus } from './types';

import CollectionTable from './collection-table';
import CollectionSlider from '../collection-slider';

import http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'CollectionDeploy',
  components: {
    CollectionTable,
    CollectionSlider,
  },
  props: {
    indexSetId: {
      type: String,
      default: '',
    },
    isAllowedCreate: {
      type: Boolean,
      default: false,
    },
    isAllowedDownload: {
      type: Boolean,
      default: false,
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

    const userDisplayMap = new Map(); // 用于创建人 到租户信息的映射

    const tableData = ref({
      total: 0,
      list: [],
    });
    const isLoading = ref(false); // 加载状态
    const searchKeyword = ref(''); // 搜索关键词

    // 侧边栏相关状态
    const showSlider = ref(false); // 新建采集侧边栏打开状态
    const logData = ref(null); // 日志数据
    const operateType = ref('create'); // 操作类型： create、clone、view

    // 轮询相关状态
    const timer = ref(null); // 轮询定时器
    const isShouldPollTask = ref(false); // 是否需要轮询任务
    const isComponentDestroyed = ref(false); // 组件是否已销毁

    // 启动轮询
    const startPolling = () => {
      stopPolling();
      timer.value = setTimeout(() => {
        if (isShouldPollTask.value) {
          pollTaskStatus();
        }
      }, 30000); // 30秒轮询一次
    };

    // 停止轮询
    const stopPolling = () => {
      if (timer.value) {
        clearTimeout(timer.value);
        timer.value = null;
      }
    };

    // 判断是否需要轮询
    const checkShouldPoll = (taskList: any[]) => {
      // 如果组件已销毁，不进行轮询判断
      if (isComponentDestroyed.value) {
        return;
      }

      isShouldPollTask.value = false;

      // 遍历新任务列表，检查轮询需求并更新现有任务状态
      taskList.forEach((newTask) => {
        // 检查是否有未完成的任务
        if (newTask.status !== TaskStatus.COMPLETED) {
          isShouldPollTask.value = true;
        }

        // 更新现有任务列表中对应任务的状态
        tableData.value.list.forEach((existingTask) => {
          if (existingTask.id === newTask.id) {
            existingTask.status = newTask.status;
            existingTask.status_name = newTask.status_name;
          }
        });
      });

      // 如果需要轮询，启动轮询
      if (isShouldPollTask.value) {
        startPolling();
      } else {
        stopPolling();
      }
    };

    // 处理搜索事件
    const handleSearch = (keyword: string) => {
      searchKeyword.value = keyword;
    };

    // 处理输入框内容改变事件
    const handleInputChange = (value: string) => {
      if (value === '') {
        searchKeyword.value = '';
      }
    };

    // 轮询获取任务状态
    const pollTaskStatus = async () => {
      try {
        const params = {
          query: {
            bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
          },
        };

        const response = await http.request('collect/getTaskLogList', params);
        if (response.data.list.length > 0) {
          checkShouldPoll(response.data.list);
        }
      } catch (error) {
        console.warn('轮询获取任务状态失败:', error);
        // 轮询失败时停止轮询
        stopPolling();
      }
    };

    // 获取列表数据
    const requestData = async () => {
      try {
        const params = {
          query: {
            bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
          },
        };

        isLoading.value = true;

        const response = await http.request('collect/getTaskLogList', params);
        const listWithTenantInfo = await processListWithTenantInfo(response.data.list);
        tableData.value = response.data;
        tableData.value.list = listWithTenantInfo;

        // 通知父组件更新总数
        emit('update-total', response.data.total);

        // 检查是否需要轮询
        checkShouldPoll(listWithTenantInfo);
      } catch (error) {
        console.warn('获取采集下发列表失败:', error);
      } finally {
        isLoading.value = false;
      }
    };

    const { formatResponseListTimeZoneString } = useUtils();

    // 处理列表数据，添加租户信息
    const processListWithTenantInfo = async (list: any[]) => {
      if (list.length === 0) {
        return list;
      }
      // 为每项添加 tenant_info 字段，并收集所有的 created_by
      const tenantUserIds = [];

      const listWithTenantInfo = formatResponseListTimeZoneString(list, (item) => {
        let tenantInfo = {
          login_name: '',
          full_name: '',
          display_name: '',
        };
        if (userDisplayMap.get(item.created_by)) {
          tenantInfo = userDisplayMap.get(item.created_by);
        } else {
          userDisplayMap.set(item.created_by, tenantInfo);
        }
        const newItem = {
          tenant_info: tenantInfo,
        };

        // 收集 created_by 用于批量查询用户信息
        tenantUserIds.push(item.created_by);

        return newItem;
      });

      // 批量获取用户信息
      tenantManager.batchGetUserDisplayInfo(tenantUserIds);
      return listWithTenantInfo;
    };

    // 处理用户信息更新事件
    const handleUserInfoUpdate = (data: UserInfoLoadedEventData) => {
      const userInfo = data.userInfo;

      // 直接根据映射关系更新对应的列表项对象
      userInfo.forEach((userInfo, userId) => {
        const targetItem = userDisplayMap.get(userId);
        if (targetItem && userInfo) {
          // 修改映射中的对象
          Object.assign(targetItem, {
            login_name: userInfo.login_name || '',
            full_name: userInfo.full_name || '',
            display_name: userInfo.display_name || '',
          });
        }
      });
    };

    // 清除搜索关键词
    const handleClearKeyword = () => {
      searchKeyword.value = '';
    };

    // 新建采集
    const handleCreateTask = async () => {
      if (props.isAllowedCreate) {
        handleOperateTask(null, 'create');
      } else {
        const paramData = {
          action_ids: [authorityMap.CREATE_CLIENT_COLLECTION_AUTH],
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

    // 任务操作
    const handleOperateTask = (task: any, type: string) => {
      logData.value = task;
      operateType.value = type;
      showSlider.value = true;
    };

    // 新建采集成功后回调
    const handleUpdatedTable = () => {
      handleCancelSlider();
      requestData(); // 刷新数据
    };

    // 关闭侧边栏
    const handleCancelSlider = () => {
      showSlider.value = false;
      logData.value = null;
      operateType.value = 'create';
    };

    onMounted(async () => {
      // 获取数据
      requestData();

      // 监听事件
      tenantManager.on('userInfoUpdated', handleUserInfoUpdate);
    });

    onBeforeUnmount(() => {
      // 标记组件已销毁
      isComponentDestroyed.value = true;

      // 清理事件监听
      tenantManager.off('userInfoUpdated', handleUserInfoUpdate);

      // 清理轮询定时器
      stopPolling();
    });

    return () => {
      return (
        <div class='collection-deploy'>
          {/* 按钮、搜索区域 */}
          <div class='deploy-header'>
            <div>
              <bk-button
                theme='primary'
                v-cursor={{ active: !props.isAllowedCreate }}
                onClick={handleCreateTask}
                disabled={isLoading.value}
              >
                {t('新建采集')}
              </bk-button>
            </div>
            <div>
              <bk-input
                placeholder={t('搜索 任务 ID、任务名称、openID、创建方式、任务状态、任务阶段、创建人')}
                value={searchKeyword.value}
                clearable
                right-icon={'bk-icon icon-search'}
                onEnter={handleSearch}
                on-right-icon-click={handleSearch}
                onClear={handleClearKeyword}
                onChange={handleInputChange}
              ></bk-input>
            </div>
          </div>
          {/* 表格内容区域 */}
          <section>
            <CollectionTable
              total={tableData.value.total}
              isAllowedDownload={props.isAllowedDownload}
              data={tableData.value.list}
              indexSetId={props.indexSetId}
              paginationConfig={props.paginationConfig}
              v-bkloading={{ isLoading: isLoading.value }}
              keyword={searchKeyword.value}
              on-clear-keyword={handleClearKeyword}
              on-clone-task={task => handleOperateTask(task, 'clone')}
              on-view-task={task => handleOperateTask(task, 'view')}
            />
          </section>
          {/* 新建采集侧边栏 */}
          <CollectionSlider
            showSlider={showSlider.value}
            logData={logData.value}
            operateType={operateType.value}
            on-cancel-slider={handleCancelSlider}
            on-updated-table={handleUpdatedTable}
          />
        </div>
      );
    };
  },
});
