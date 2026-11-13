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

import { Loading as TLoading } from '@/shared/ui/loading/native';


import { useApplicationStore } from '@/app/state/domains/application-store';
import { computed, defineComponent, ref, watch } from 'vue';
import { Input as TInput, Empty as TEmpty } from 'tdesign-vue-next';

import useLocale from '@/shared/composables/use-locale';


import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import useRetrieveEvent from '@/shared/composables/use-retrieve-event';
import CollectHead from './components/collect-head/collect-head';
import CollectList from './components/collect-list/collect-list';
import CollectTab from './components/collect-tab/collect-tab';
import CollectTool from './components/collect-tool/collect-tool';
import { useFavorite } from './hooks/use-favorite';
import { ITabItem } from './types/index';
import { getGroupNameRules } from './utils/index';

import './collect-main.scss';

export default defineComponent({
  name: 'CollectMainNew',

  props: {
    isShowCollect: {
      type: Boolean,
      required: true,
    },
  },

  emits: ['show-change', 'showChange'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useApplicationStore();

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
        <TLoading class='data-empty-box' loading={favoriteLoading.value}>
          <TEmpty
            class='exception-wrap-item exception-part'
            type='empty'
            title={emptyType === 'search-empty' ? t('bk.exception.searchEmpty') : t('暂无数据')}
          />
        </TLoading>
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
      () => store.favoriteList?.reduce((pre: number, cur: any) => pre + cur.favorites.length, 0) || 0,
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
      (value) => {
        if (value) {
          getFavoriteList();
        } else {
          activeFavorite.value = null;
          searchValue.value = '';
        }
      },
      { immediate: true },
    );

    // 监听收藏列表刷新事件（切换检索模式时触发）
    const { addEvent } = useRetrieveEvent();
    addEvent(RetrieveEvent.FAVORITE_LIST_REFRESH, () => {
      activeFavorite.value = null;
      searchValue.value = '';
      getFavoriteList();
    });

    return () => (
      <div class='collect-main-box'>
        <div class='collect-main-top'>
          <CollectHead total={allFavoriteNumber.value} onCollapse={handleCollapse} onRefresh={handleRefresh} />
          <TInput
            class='collect-main-search-input'
            clearable={true}
            placeholder={t('请输入')}
            suffixIcon={() => <i class='bk-icon icon-search' />}
            value={searchValue.value}
            onChange={(value) => handleSearchInput(String(value ?? ''))}
          />
          <CollectTab active={activeTab.value} list={tabList.value} onTabChange={handleTabChange} />
          <CollectTool
            ref={collectToolRef}
            collapseAll={isCollapseList.value}
            isChecked={isShowCurrentIndexList.value}
            rules={rulesData.value}
            onHandle={toolHandle}
          />
        </div>
        {!isSearchEmpty.value ? (
          filterDataList.value.length ? (
            <CollectList
              isCollapse={isCollapseList.value}
              isSearch={!!searchValue.value}
              list={filterDataList.value}
              loading={favoriteLoading.value}
              onRefresh={handleRefresh}
              onSelectItem={selectFavoriteItem}
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
