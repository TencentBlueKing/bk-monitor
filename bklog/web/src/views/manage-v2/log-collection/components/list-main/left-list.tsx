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

import { computed, defineComponent, ref, onMounted, onBeforeUnmount } from 'vue';

import useLocale from '@/hooks/use-locale';
import ItemSkeleton from '@/skeleton/item-skeleton';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';

import { useOperation } from '../../hook/useOperation';
import { showMessage } from '../../utils';
import AddIndexSet from '../business-comp/step2/add-index-set';
import ListItem from './list-item';
import $http from '@/api';

import type { IListItemData } from '../../type';

import './left-list.scss';
import 'tippy.js/themes/light.css';

export default defineComponent({
  name: 'LeftList',
  emits: ['choose'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const { indexGroupLoading, getIndexGroupList } = useOperation();
    const activeKey = ref<number | string>('all');
    const addPanelRef = ref();
    const addIndexSetRef = ref();
    const rootRef = ref();
    const formData = ref<IListItemData>({ index_set_name: '' });
    const isHover = ref(false);
    let tippyInstance: Instance | null = null;
    const searchValue = ref<string>('');
    const listData = ref<IListItemData[]>([]);
    const total = ref(0);

    const baseItem = computed(() => [
      {
        index_set_name: t('全部采集项'),
        index_count: total.value,
        index_set_id: 'all',
        icon: 'all2',
        unEditable: true,
      },
    ]);
    /**
     *
     * 过滤后的数据
     */
    const filterDataList = computed(() =>
      (listData.value || []).filter((item: IListItemData) => (item.index_set_name ?? '').includes(searchValue.value)),
    );

    /** 选中索引集 */
    const handleItem = (item: IListItemData) => {
      activeKey.value = item.index_set_id ?? '';
      emit('choose', item);
    };

    const handelDelItem = (item: IListItemData) => {
      $http
        .request('collect/delIndexGroup', {
          params: {
            index_set_id: item.index_set_id,
          },
        })
        .then(res => {
          if (res.result) {
            showMessage(t('删除成功'));
            getListData();
          }
        })
        .catch(err => {
          console.log(err);
        });
    };

    const renderBaseItem = (item: IListItemData) => (
      <ListItem
        activeKey={activeKey.value}
        data={item}
        on-choose={handleItem}
        on-delete={handelDelItem}
      />
    );
    /**
     * 获取列表数据
     */
    const getListData = () => {
      getIndexGroupList((data: {list: IListItemData[], total: number}) => {
        listData.value = data.list;
        total.value = data.total;
        initActionPop();
      });
    };

    const initActionPop = () => {
      tippyInstance = tippy(rootRef.value as SingleTarget, {
        content: addPanelRef.value,
        trigger: 'click',
        placement: 'bottom-end',
        theme: 'light add-index-set-popover',
        interactive: true,
        hideOnClick: true,
        appendTo: () => document.body,
        onShow: () => {
          isHover.value = true;
          addIndexSetRef.value?.autoFocus?.();
        },
        onHide: () => {
          isHover.value = false;
        },
      });
    };
    const handleEditGroupCancel = () => {
      tippyInstance?.hide();
    };
    /**
     * 新增/修改索引集
     */
    const handleEditGroupSubmit = () => {
      getListData();
    };

    onMounted(async () => {
      await getListData();
      setTimeout(() => {
        handleItem(baseItem.value[0]);
      }, 1500);
    });

    onBeforeUnmount(() => {
      tippyInstance?.hide();
      tippyInstance?.destroy();
    });
    /**
     * 列表内容render
     * @returns
     */
    const renderListMain = () => {
      if (indexGroupLoading.value) {
        return (
          <ItemSkeleton
            style={{ padding: '0 16px' }}
            rowHeight={'30px'}
            rows={6}
            widths={['100%']}
          />
        );
      }
      if (filterDataList.value.length > 0) {
        return (filterDataList.value || []).map(item => renderBaseItem(item));
      }
      return (
        <bk-exception
          class='list-main-empty'
          type={searchValue.value ? 'search-empty' : 'empty'}
        >
          <span>{searchValue.value ? t('搜索结果为空') : t('暂无索引集')}</span>
          {searchValue.value ? (
            <span
              class='list-main-empty-text'
              on-click={() => {
                searchValue.value = '';
              }}
            >
              {t('清空筛选条件')}
            </span>
          ) : (
            <p class='list-main-text'>{t('创建索引集可合并多采集项一同使用')}</p>
          )}
        </bk-exception>
      );
    };

    return () => (
      <div class='log-collection-left-list'>
        <div class='list-top'>{baseItem.value.map(item => renderBaseItem(item))}</div>
        <div class='list-main'>
          <div class='list-main-title'>{t('索引集列表')}</div>
          <div class='list-main-search'>
            <span
              ref={rootRef}
              class={{
                'add-btn': true,
                'is-hover': isHover.value,
              }}
            >
              +
            </span>
            <bk-input
              class='search-input'
              placeholder={t('搜索 索引集名称')}
              right-icon='bk-icon icon-search'
              value={searchValue.value}
              clearable
              onClear={() => {
                searchValue.value = '';
              }}
              onInput={val => {
                searchValue.value = val;
              }}
            />
          </div>
          <div style='display: none'>
            <div ref={addPanelRef}>
              <AddIndexSet
                ref={addIndexSetRef}
                data={formData.value}
                isAdd={true}
                on-cancel={handleEditGroupCancel}
                on-submit={handleEditGroupSubmit}
              />
            </div>
          </div>
          <div class='list-main-content'>{renderListMain()}</div>
        </div>
      </div>
    );
  },
});
