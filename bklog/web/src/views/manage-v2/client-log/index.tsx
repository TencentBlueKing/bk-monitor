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

import { defineComponent, onMounted, ref, watch } from 'vue';

import useStore from '@/hooks/use-store';
import useRouter from '@/hooks/use-router';
import { t } from '@/hooks/use-locale';
import * as authorityMap from '../../../common/authority-map';

import CollectionDeploy from './collection-deploy';
import UserReport from './user-report';

import http from '@/api';

import './index.scss';
// import useUtils from '@/hooks/use-utils';

// tab类型常量定义
const TAB_TYPES = {
  COLLECT: t('采集下发'),
  REPORT: t('用户上报'),
} as const;

type TabType = (typeof TAB_TYPES)[keyof typeof TAB_TYPES];

export default defineComponent({
  name: 'ClientLog',
  components: {
    CollectionDeploy,
    UserReport,
  },
  setup() {
    const store = useStore();
    const router = useRouter();

    // 从路由查询参数获取初始 tab 值
    const getInitialTab = (): TabType => {
      const tabQuery = router.currentRoute.query.tab;

      if (tabQuery === 'collect') {
        return TAB_TYPES.COLLECT;
      }
      if (tabQuery === 'report') {
        return TAB_TYPES.REPORT;
      }
      // 默认值
      return TAB_TYPES.COLLECT;
    };

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
    const activeTab = ref<TabType>(getInitialTab()); // 激活的tab
    const isAllowedCreate = ref(false); // 是否允许创建
    const isAllowedDownload = ref(false); // 是否允许下载
    const isGrayRelease = ref(false); // 是否为灰度业务
    const indexSetId = ref<string>(''); // 索引集ID

    // 分页配置
    const paginationConfig = ref({
      limit: 10,
      limitList: [10, 20, 50, 100],
    });

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

    // 获取tab数量
    const getTgpaCount = async () => {
      try {
        const params = {
          query: {
            bk_biz_id: store.state.bkBizId,
          },
        };

        const response = await http.request('collect/getTgpaCount', params);
        if (response.data) {
          if (response.data.task !== undefined) {
            updateTabCount(TAB_TYPES.COLLECT, response.data.task);
          }
          if (response.data.report !== undefined) {
            updateTabCount(TAB_TYPES.REPORT, response.data.report);
          }
        }
      } catch (error) {
        console.warn('获取tab数量失败:', error);
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

    // 计算分页大小
    const calculatePaginationLimit = () => {
      const fixedHeight = 368; // 需要减去的固定高度
      const rowHeight = 43; // 行固定高度

      // 获取浏览器高度
      const clientHeight = document.documentElement.offsetHeight;

      // 计算可以显示的行数
      const rows = Math.ceil((clientHeight - fixedHeight) / rowHeight);

      // 根据可显示行数设置合适的limit
      if (rows < 10) {
        paginationConfig.value.limit = 10;
      } else if (rows < 20) {
        paginationConfig.value.limit = 20;
      } else if (rows < 50) {
        paginationConfig.value.limit = 50;
      } else {
        paginationConfig.value.limit = 100;
      }
    };

    // 立即计算分页大小
    calculatePaginationLimit();

    // tab点击事件
    const handleTabClick = (title: TabType) => {
      activeTab.value = title;

      // 更新路由查询参数
      const currentQuery = { ...router.currentRoute.query };

      // 根据 tab 类型设置查询参数
      if (title === TAB_TYPES.COLLECT) {
        currentQuery.tab = 'collect';
      } else if (title === TAB_TYPES.REPORT) {
        currentQuery.tab = 'report';
      }

      // 更新路由
      router.replace({
        ...router.currentRoute,
        query: currentQuery,
      });
    };

    onMounted(async () => {
      // 如果是灰度业务，则不做任何处理
      if (isGrayRelease.value) {
        return;
      }

      // 获取索引集ID
      getIndexSetId();

      // 获取tab数量
      getTgpaCount();

      // 检查权限(新建采集、下载文件)
      checkAllowed();
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

    // 检查创建权限
    const checkAllowed = async () => {
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

    // 更新tab数量
    const updateTabCount = (tabType: TabType, count: number) => {
      const tab = tabs.value.find(tab => tab.title === tabType);
      if (tab) {
        tab.count = count;
      }
    };

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
            {/* 内容区域 */}
            {activeTab.value === TAB_TYPES.COLLECT && (
              <CollectionDeploy
                indexSetId={indexSetId.value}
                isAllowedCreate={isAllowedCreate.value}
                isAllowedDownload={isAllowedDownload.value}
                paginationConfig={paginationConfig.value}
                onUpdate-total={(total: number) => updateTabCount(TAB_TYPES.COLLECT, total)}
              />
            )}
            {activeTab.value === TAB_TYPES.REPORT && (
              <UserReport
                isAllowedDownload={isAllowedDownload.value}
                indexSetId={indexSetId.value}
                paginationConfig={paginationConfig.value}
                onUpdate-total={(total: number) => updateTabCount(TAB_TYPES.REPORT, total)}
              />
            )}
          </div>
        </div>
      );
    };
  },
});
