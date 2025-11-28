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

import { defineComponent, ref, watch } from 'vue';

import useStore from '@/hooks/use-store';
import { useRouter } from 'vue-router/composables';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { t } from '@/hooks/use-locale';
import * as authorityMap from '../../../common/authority-map';

import LogTable from './components/log-table';
import CollectionSlider from './collection-slider';

import http from '@/api';

import './index.scss';

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
    const router = useRouter();

    const tabs = ref([
      // tab配置
      {
        title: TAB_TYPES.COLLECT,
        count: 0,
      },
      {
        title: TAB_TYPES.REPORT,
        count: 0,
      },
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
          tableData.value = response.data;
          tabs.value[0].count = response.data.total;
        }
      } catch (error) {
        console.warn('获取采集下发列表失败:', error);
      } finally {
        isLoading.value = false;
      }
    };

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
    const handleCleanConfig = () => {
      router.push({
        name: 'clean-config',
        query: {
          spaceUid: store.state.spaceUid,
        },
      });
    };

    // 检查创建权限
    const checkCreateAuth = async () => {
      try {
        const res = await store.dispatch('checkAllowed', {
          action_ids: [authorityMap.CREATE_CLIENT_COLLECTION_AUTH],
          resources: [
            {
              type: 'space',
              id: store.state.spaceUid,
            },
          ],
        });
        isAllowedCreate.value = res.isAllowed;
      } catch (err) {
        console.warn(err);
        isAllowedCreate.value = false;
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
        console.log(res);
        store.commit('updateState', { authDialogData: res.data });
      }
    };

    // 检查创建权限
    checkCreateAuth();

    // 监听activeTab变化
    watch(
      activeTab,
      (newValue) => {
        if (newValue === TAB_TYPES.COLLECT) {
          requestData();
        }
        if (newValue === TAB_TYPES.REPORT) {
          // 暂无用户上报接口
          isLoading.value = true;
          tableData.value = {
            total: 0,
            list: [],
          };
          isLoading.value = false;
        }
      },
      { immediate: true },
    );

    return () => (
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
                  v-cursor={{ active: isAllowedCreate.value === false }}
                  onClick={handleCreateTask}
                  disabled={isLoading.value}
                >
                  {t('新建采集')}
                </bk-button>
                <bk-button
                  disabled={isLoading.value}
                  onClick={handleCleanConfig}
                >
                  {t('清洗配置')}
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
          ) : (
            <div>
              {/* 用户上报 */}
              <bk-alert
                class='alert-info'
                type='info'
                title={t('Alert 文案占位，用于说明如果用 SDK 上报。')}
              ></bk-alert>
              <div class='operating-area'>
                <bk-button onClick={handleCleanConfig}>{t('清洗配置')}</bk-button>
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
              data={tableData.value.list}
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
  },
});
