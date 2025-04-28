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
import useLocale from '@/hooks/use-locale';
import useIndexSet from './use-index-set';
import IndexSetList from './index-set-list';

export default defineComponent({
  props: {
    indexSetList: {
      type: Array,
      default: () => [],
    },
    type: {
      type: String,
      default: 'single',
    },
    value: {
      type: Array,
      default: () => [],
    },
    textDir: {
      type: String,
      default: 'ltr',
    },
  },
  emits: ['type-change', 'value-change'],
  setup(props, { emit }) {
    const { $t } = useLocale();

    const hiddenEmptyItem = ref(true);

    const tagItem = ref({
      id: undefined,
      name: undefined,
      color: undefined,
    });

    const searchText = ref('');
    const list = computed(() => props.indexSetList);

    const { indexSetTagList } = useIndexSet({ indexSetList: list });

    const noDataReg = /^No\sData$/i;
    const filterList = computed(() =>
      props.indexSetList
        .filter((item: any) => item.tags.some(tag => tag.id === tagItem.value.id))
        .filter((item: any) => {
          if (hiddenEmptyItem.value) {
            return (
              !item.tags.some(tag => noDataReg.test(tag.name)) && item.index_set_name.indexOf(searchText.value) !== -1
            );
          }

          return item.index_set_name.indexOf(searchText.value) !== -1;
        }),
    );

    const handleValueChange = val => emit('value-change', val);

    const renderContentBody = () => {
      return [
        <IndexSetList
          class='bklog-v3-content-list'
          list={filterList.value}
          type={props.type}
          value={props.value}
          textDir={props.textDir}
          on-value-change={handleValueChange}
        ></IndexSetList>,
        <div class='bklog-v3-item-info'></div>,
      ];
    };

    const tabList = computed(() => [
      { name: $t('单选'), id: 'single', render: renderContentBody },
      { name: $t('多选'), id: 'union', render: renderContentBody },
      { name: $t('历史记录'), id: 'history' },
      { name: $t('我的收藏'), id: 'favorite' },
    ]);

    const activeTab = computed(() => tabList.value.find(item => item.id === props.type));

    const handleHiddenEmptyItemChange = (val: boolean) => {
      hiddenEmptyItem.value = val;
    };

    const handleTabItemClick = (e: MouseEvent, item: { name: string; id: string }) => {
      emit('type-change', item.id);
    };

    const handleTagItemClick = (tag: { id: number; name: string; color: string }) => {
      Object.assign(tagItem.value, tag);
    };

    return () => (
      <div class='bklog-v3-content-root'>
        <div class='content-header'>
          <div class='bklog-v3-tabs'>
            {tabList.value.map(item => (
              <span
                class={[{ 'is-active': props.type === item.id }, 'tab-item']}
                key={item.id}
                onClick={e => handleTabItemClick(e, item)}
              >
                {item.name}
              </span>
            ))}
          </div>
          <div class='bklog-v3-keys'>
            <span class='key-item'>
              <span class='key-code text'>tab</span>
              <span class='key-name'>快速切换标签</span>
            </span>
            <span class='key-item'>
              <span class='key-code up-icon bklog-icon bklog-arrow-down-filled-2'></span>
              <span class='key-code bklog-icon bklog-arrow-down-filled-2'></span>
              <span class='key-name'>移动光标</span>
            </span>
            <span class='key-item'>
              <span class='key-code text'>enter</span>
              <span class='key-name'>选中</span>
            </span>
          </div>
        </div>
        <div class='bklog-v3-content-filter'>
          <div class='bklog-v3-search-input'>
            <bk-input
              clearable
              placeholder='请输入 索引集、采集项 搜索'
              right-icon="'bk-icon icon-search'"
              style='width: 650px; margin-right: 12px;'
              value={searchText.value}
              on-input={val => (searchText.value = val)}
            ></bk-input>
            <bk-checkbox
              checked={hiddenEmptyItem.value}
              true-value={true}
              false-value={false}
              on-change={handleHiddenEmptyItemChange}
            >
              <span class='hidden-empty-icon'></span>
              <span>隐藏无数据</span>
            </bk-checkbox>
          </div>
          <div class='bklog-v3-tag-list'>
            {indexSetTagList.value.map(item => (
              <span
                class='tag-item'
                onClick={() => handleTagItemClick(item)}
              >
                {item.name}
              </span>
            ))}
          </div>
        </div>

        <div class='bklog-v3-content-body'>{activeTab.value.render?.()}</div>
      </div>
    );
  },
});
