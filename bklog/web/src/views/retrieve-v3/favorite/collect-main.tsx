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

import { computed, defineComponent, ref, watch } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import RetrieveHelper from '../../retrieve-helper';
import CollectHead from './components/collect-head/collect-head';
import CollectList from './components/collect-list/collect-list';
import CollectTab from './components/collect-tab/collect-tab';
import CollectTool from './components/collect-tool/collect-tool';
import { useFavorite } from './hooks/use-favorite';
import { ITabItem } from './types';
import { getGroupNameRules } from './utils';

import './collect-main.scss';

export default defineComponent({
  name: 'CollectMainNew',

  props: {
    isShowCollect: {
      type: Boolean,
      required: true,
    },
  },

  emits: ['show-change'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    // 使用自定义 hook 管理状态
    const {
      favoriteLoading,
      activeTab,
      isShowCurrentIndexList,
      searchValue,
      isCollapseList,
      activeFavorite,
      originFavoriteList,
      chartFavoriteList,
      filterDataList,
      isSearchEmpty,
      getFavoriteList,
      selectFavoriteItem,
      handleSearchInput,
    } = useFavorite();

    const collectToolRef = ref(null);

    /**
     * 获取每个tab类型数据量
     */
    const getTypeCount = (data: any[]): number => {
      return data.reduce((pre: number, cur) => pre + cur.favorites.length, 0);
    };

    /**
     * Tab 切换处理
     */
    const handleTabChange = (tab: string) => {
      activeTab.value = tab;
    };

    /**
     * 是否仅查看当前索引集
     */
    const handleChangeIndex = (val: boolean) => {
      isShowCurrentIndexList.value = val;
      RetrieveHelper.setViewCurrentIndexn(val);
    };

    /**
     * 展开/收起收藏夹
     */
    const handleCollapse = () => {
      emit('show-change', !props.isShowCollect);
    };

    /**
     * 列表展开收起
     */
    const handleCollapseList = (val: boolean) => {
      isCollapseList.value = val;
    };

    /**
     * 刷新处理
     */
    const handleRefresh = () => {
      getFavoriteList();
    };

    /**
     * 渲染空状态
     */
    const renderEmpty = (emptyType: string) => {
      return (
        <div
          class='data-empty-box'
          v-bkloading={{ isLoading: favoriteLoading.value }}
        >
          <bk-exception
            class='exception-wrap-item exception-part'
            scene='part'
            type={emptyType}
          />
        </div>
      );
    };

    /**
     * 工具栏相关操作
     */
    const toolHandle = (type: string, data: any) => {
      switch (type) {
        case 'refresh':
          handleRefresh();
          break;
        case 'change-index':
          handleChangeIndex(data);
          break;
        case 'collapse':
          handleCollapseList(data);
          break;
      }
    };

    // 计算属性
    const allFavoriteNumber = computed(
      () => store.state.favoriteList?.reduce((pre: number, cur: any) => pre + cur.favorites.length, 0) || 0,
    );

    const tabList = computed((): ITabItem[] => [
      {
        name: t('原始日志'),
        icon: 'bklog-table-2',
        key: 'origin',
        count: getTypeCount(originFavoriteList.value),
      },
      {
        name: t('图表分析'),
        icon: 'bklog-chart-2',
        key: 'chart',
        count: getTypeCount(chartFavoriteList.value),
      },
    ]);

    const rulesData = computed(() => getGroupNameRules(filterDataList.value));

    // 监听显示状态变化
    watch(
      () => props.isShowCollect,
      value => {
        if (value) {
          getFavoriteList();
        } else {
          activeFavorite.value = null;
          searchValue.value = '';
        }
      },
      { immediate: true },
    );

    return () => (
      <div class='collect-main-box'>
        <div class='collect-main-top'>
          <CollectHead
            total={allFavoriteNumber.value}
            on-collapse={handleCollapse}
          />
          <bk-input
            class='collect-main-search-input'
            clearable={true}
            placeholder={t('请输入')}
            right-icon='bk-icon icon-search'
            value={searchValue.value}
            onInput={handleSearchInput}
          />
          <CollectTab
            active={activeTab.value}
            list={tabList.value}
            on-tab-change={handleTabChange}
          />
          <CollectTool
            ref={collectToolRef}
            collapseAll={isCollapseList.value}
            isChecked={isShowCurrentIndexList.value}
            rules={rulesData.value}
            on-handle={toolHandle}
          />
        </div>
        {!isSearchEmpty.value ? (
          filterDataList.value.length ? (
            <CollectList
              isCollapse={isCollapseList.value}
              isSearch={!!searchValue.value}
              list={filterDataList.value}
              loading={favoriteLoading.value}
              on-refresh={handleRefresh}
              on-select-item={selectFavoriteItem}
            />
          ) : (
            renderEmpty('empty')
          )
        ) : (
          renderEmpty('search-empty')
        )}
      </div>
    );
  },
});
