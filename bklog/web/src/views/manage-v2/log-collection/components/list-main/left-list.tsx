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

import AddIndexSet from '../business-comp/add-index-set';
import ListItem from './list-item';

import './left-list.scss';
import 'tippy.js/themes/light.css';

export default defineComponent({
  name: 'LeftList',
  props: {
    list: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['choose'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const activeKey = ref('all');
    const addPanelRef = ref();
    const addIndexSetRef = ref();
    const rootRef = ref();
    const formData = ref({ label: '' });
    const isHover = ref(false);
    let tippyInstance: Instance | null = null;
    const searchValue = ref('');

    const baseItem = computed(() => [
      { label: t('全部采集项'), count: 1124, key: 'all', icon: 'all2', unEditable: true },
      // { label: t('未归属索引集'), count: 23, key: 'unassigned', icon: 'weiguishu', unEditable: true },
    ]);
    /** 过滤后的数据 */
    const filterDataList = computed(() => (props.list || []).filter(item => item.label.includes(searchValue.value)));

    /** 选中索引集 */
    const handleItem = item => {
      activeKey.value = item.key;
      emit('choose', item);
    };

    const renderBaseItem = item => (
      <ListItem
        activeKey={activeKey.value}
        data={item}
        on-choose={handleItem}
      />
    );

    const initActionPop = () => {
      tippyInstance = tippy(rootRef.value as SingleTarget, {
        content: addPanelRef.value as any,
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
    const handleEditGroupSubmit = () => {
      tippyInstance?.hide();
    };

    onMounted(initActionPop);

    onBeforeUnmount(() => {
      tippyInstance?.hide();
      tippyInstance?.destroy();
    });

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
              onInput={val => (searchValue.value = val)}
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
          <div class='list-main-content'>
            {props.loading ? (
              <ItemSkeleton
                style={{ padding: '0 16px' }}
                rowHeight={'30px'}
                rows={6}
                widths={['100%']}
              />
            ) : (
              (filterDataList.value || []).map(item => renderBaseItem(item))
            )}
          </div>
        </div>
      </div>
    );
  },
});
