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

import { defineComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import useStore from '@/hooks/use-store';
// import { useRouter } from 'vue-router/composables';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { t } from '@/hooks/use-locale';
import * as authorityMap from '../../../common/authority-map';
import { tenantManager, UserInfoLoadedEventData } from '@/views/retrieve-core/tenant-manager';
import { TaskStatus } from './components/log-table/types';

import LogTable from './components/log-table';
import CollectionSlider from './collection-slider';

import http from '@/api';

import './index.scss';
import useUtils from '@/hooks/use-utils';

// tab类型常量定义
const TAB_TYPES = {
  COLLECT: t('采集下发'),
  REPORT: t('用户上报'),
} as const;

type TabType = (typeof TAB_TYPES)[keyof typeof TAB_TYPES];

export default defineComponent({
  name: 'ClientLog',
  components: {
    LogTable,
    CollectionSlider,
  },
  setup() {
    const store = useStore();
    // const router = useRouter();

    const userDisplayMap = new Map(); // 用于创建人 到租户信息的映射

    const tabs = ref([
      // tab配置
      {
        title: TAB_TYPES.COLLECT,
        count: 0,
      },
      // 暂时隐藏 用户上报
      // {
      //   title: TAB_TYPES.REPORT,
      //   count: 0,
      // },
    ]);
    const activeTab = ref<TabType>(TAB_TYPES.COLLECT); // 激活的tab
    const showSlider = ref(false); // 新建采集侧边栏打开状态
    const tableData = ref({
      total: 0,
      list: [],
    });
    const isLoading = ref(false); // 加载状态
    const logData = ref(null); // 日志数据
    const searchKeyword = ref(''); // 搜索关键词
    const operateType = ref('create'); // 操作类型： create、clone、view
    const isAllowedCreate = ref(false); // 是否允许创建
    const isAllowedDownload = ref(false); // 是否允许下载
    const isGrayRelease = ref(false); // 是否为灰度业务
    const indexSetId = ref<string>(''); // 索引集ID

    // 轮询相关状态
    const timer = ref(null); // 轮询定时器
    const isShouldPollTask = ref(false); // 是否需要轮询任务
    const isComponentDestroyed = ref(false); // 组件是否已销毁

    // 获取索引集ID
    const getIndexSetId = async () => {
      try {
        const params = {
          query: {
            bk_biz_id: store.state.bkBizId,
          },
        };

        const response = await http.request('collect/getTaskIndexSetId', params);
        if (response.data && response.data.index_set_id) {
          indexSetId.value = String(response.data.index_set_id);
        }
      } catch (error) {
        console.warn('获取索引集ID失败:', error);
      }
    };

    // 检查是否为灰度业务
    const checkGrayReleaseAccess = () => {
      const bizId = store.state.bkBizId;
      const spaceUid = store.state.spaceUid;

      // 获取总开关状态
      const { tgpa_task: tgpaTaskToggle } = window.FEATURE_TOGGLE;
      const whiteList = window.FEATURE_TOGGLE_WHITE_LIST?.tgpa_task ?? [];

      let hasAccess = false;

      switch (tgpaTaskToggle) {
        case 'on':
          hasAccess = true;
          break;
        case 'off':
          hasAccess = false;
          break;
        case 'debug': {
          // 检查白名单
          const normalizedWhiteList = whiteList.map((id: any) => String(id));
          hasAccess = normalizedWhiteList.includes(String(bizId)) || normalizedWhiteList.includes(String(spaceUid));
          break;
        }
        default:
          // 没有配置，默认为全开
          hasAccess = true;
          break;
      }

      isGrayRelease.value = !hasAccess;
    };

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

    // tab点击事件
    const handleTabClick = (title: TabType) => {
      activeTab.value = title;
    };

    // 设置侧边栏打开状态
    const setSidebarOpen = (open: boolean) => {
      showSlider.value = open;
    };

    // 新建采集成功后回调
    const handleUpdatedTable = () => {
      showSlider.value = false;
      requestData();
    };

    // 关闭侧边栏
    const handleCancelSlider = () => {
      showSlider.value = false;
      logData.value = null;
      operateType.value = 'create';
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
        if (activeTab.value === TAB_TYPES.COLLECT) {
          if (response.data.list.length > 0) {
            checkShouldPoll(response.data.list);
          }
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
        if (activeTab.value === TAB_TYPES.COLLECT) {
          const listWithTenantInfo = await processListWithTenantInfo(response.data.list);
          tableData.value = response.data;
          tableData.value.list = listWithTenantInfo;
          tabs.value[0].count = response.data.total;

          // 检查是否需要轮询
          checkShouldPoll(listWithTenantInfo);
        }
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

    onMounted(async () => {
      // 如果是灰度业务，则不做任何处理
      if (isGrayRelease.value) {
        return;
      }

      // 获取索引集ID
      getIndexSetId();

      // 检查创建权限
      checkCreateAuth();

      // 获取数据
      fetchDataByTabType(activeTab.value);

      // 监听事件
      tenantManager.on('userInfoUpdated', handleUserInfoUpdate);
    });

    watch(
      () => store.state.spaceUid,
      (newSpaceUid, oldSpaceUid) => {
        if (newSpaceUid && newSpaceUid !== oldSpaceUid) {
          // 检查灰度业务权限
          checkGrayReleaseAccess();
        }
      },
      { immediate: true },
    );

    onBeforeUnmount(() => {
      // 标记组件已销毁
      isComponentDestroyed.value = true;

      // 清理事件监听
      tenantManager.off('userInfoUpdated', handleUserInfoUpdate);

      // 清理轮询定时器
      stopPolling();
    });

    // 清除搜索关键词
    const handleClearKeyword = () => {
      searchKeyword.value = '';
    };

    // 任务操作
    const handleOperateTask = (task: any, type: string) => {
      logData.value = task;
      operateType.value = type;
      setSidebarOpen(true);
    };

    // 清洗配置
    // const handleCleanConfig = () => {
    //   router.push({
    //     name: 'clean-config',
    //     query: {
    //       spaceUid: store.state.spaceUid,
    //       backRoute: 'tgpa-task',
    //     },
    //   });
    // };

    // 检查创建权限
    const checkCreateAuth = async () => {
      try {
        const params = {
          data: {
            action_ids: [authorityMap.CREATE_CLIENT_COLLECTION_AUTH, authorityMap.DOWNLOAD_FILE_AUTH],
            resources: [
              {
                type: 'space',
                id: store.state.spaceUid,
              },
            ],
          },
        };

        const response = await http.request('auth/checkAllowed', params);

        // 处理返回的权限数据
        if (response.data && Array.isArray(response.data)) {
          response.data.forEach((item) => {
            if (item.action_id === authorityMap.CREATE_CLIENT_COLLECTION_AUTH) {
              isAllowedCreate.value = item.is_allowed;
            }
            if (item.action_id === authorityMap.DOWNLOAD_FILE_AUTH) {
              isAllowedDownload.value = item.is_allowed;
            }
          });
        } else {
          // 如果数据格式不正确，默认为无权限
          isAllowedCreate.value = false;
          isAllowedDownload.value = false;
        }
      } catch (err) {
        console.warn('权限检查失败:', err);
        isAllowedCreate.value = false;
        isAllowedDownload.value = false;
      }
    };

    // 新建采集
    const handleCreateTask = async () => {
      if (isAllowedCreate.value) {
        setSidebarOpen(true);
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

    // 根据tab类型获取数据
    const fetchDataByTabType = (tabType: TabType) => {
      if (tabType === TAB_TYPES.COLLECT) {
        requestData();
      }
      if (tabType === TAB_TYPES.REPORT) {
        // 暂无用户上报接口
        isLoading.value = true;
        tableData.value = {
          total: 0,
          list: [],
        };
        isLoading.value = false;
      }
    };

    // 监听activeTab变化
    watch(activeTab, fetchDataByTabType);

    return () => {
      // 如果是灰度业务，显示提醒
      if (isGrayRelease.value) {
        return (
          <div class='client-log-main gray-release-content'>
            <bk-exception
              class='exception-wrap-item'
              type='403'
              scene='part'
            >
              <span>{t('灰度业务')}</span>
              <div class='text-subtitle'>{t('本功能为灰度业务，请联系管理员开通')}</div>
            </bk-exception>
          </div>
        );
      }
      return (
        <div class='client-log-main'>
          {/* tab部分 */}
          <div class='tabs'>
            {tabs.value.map(tab => (
              <div
                class={['tab-item', activeTab.value === tab.title && 'active']}
                onClick={() => {
                  handleTabClick(tab.title as TabType);
                }}
              >
                <span class='tab-item-title'>{tab.title}</span>
                <span class='tab-item-num'>{tab.count}</span>
              </div>
            ))}
          </div>
          <div class='client-log-container'>
            {/* 按钮、搜索、alter提示区域 */}
            {activeTab.value === TAB_TYPES.COLLECT ? (
              <div class='deploy-header'>
                {/* 采集下发 */}
                <div>
                  <bk-button
                    theme='primary'
                    v-cursor={{ active: !isAllowedCreate.value }}
                    onClick={handleCreateTask}
                    disabled={isLoading.value}
                  >
                    {t('新建采集')}
                  </bk-button>
                  {/* <bk-button
                  disabled={isLoading.value}
                  onClick={handleCleanConfig}
                >
                  {t('清洗配置')}
                </bk-button> */}
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
            ) : (
              <div>
                {/* 用户上报 */}
                <bk-alert
                  class='alert-info'
                  type='info'
                  title={t('Alert 文案占位，用于说明如果用 SDK 上报。')}
                ></bk-alert>
                <div class='operating-area'>
                  {/* <bk-button onClick={handleCleanConfig}>{t('清洗配置')}</bk-button> */}
                  <div>
                    <bk-input
                      placeholder={t('搜索 任务 ID、任务名称、openID、创建方式、任务状态、任务阶段、创建人')}
                      clearable
                      right-icon={'bk-icon icon-search'}
                    ></bk-input>
                  </div>
                </div>
              </div>
            )}
            {/* 表格内容区域 */}
            <section>
              <LogTable
                total={tableData.value.total}
                isAllowedDownload={isAllowedDownload.value}
                data={tableData.value.list}
                indexSetId={indexSetId.value}
                v-bkloading={{ isLoading: isLoading.value }}
                keyword={searchKeyword.value}
                on-clear-keyword={handleClearKeyword}
                on-clone-task={task => handleOperateTask(task, 'clone')}
                on-view-task={task => handleOperateTask(task, 'view')}
              />
            </section>
          </div>
          {/* 新建采集侧边栏 */}
          <CollectionSlider
            showSlider={showSlider.value}
            logData={logData.value}
            operateType={operateType.value}
            onHandleCancelSlider={handleCancelSlider}
            onHandleUpdatedTable={handleUpdatedTable}
          />
        </div>
      );
    };
  },
});
