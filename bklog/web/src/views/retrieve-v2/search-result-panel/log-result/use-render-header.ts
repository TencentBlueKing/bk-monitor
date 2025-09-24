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
import { h, computed } from 'vue';

import useFieldNameHook from '@/hooks/use-field-name';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

export default () => {
  const store = useStore();
  const { $t } = useLocale();
  const { getFieldNameByField } = useFieldNameHook({ store });

  const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);
  const isUnionSearch = computed(() => store.getters.isUnionSearch);
  const unionIndexItemList = computed(() => store.getters.unionIndexItemList);
  const visibleFields = computed(() => store.state.visibleFields);
  const isNotVisibleFieldsShow = computed(() => store.state.isNotVisibleFieldsShow);
  const activeSortField = computed(() => store.state.indexItem.sort_list);
  const sortShow = (field_name, currentSortField) => {
    const requiredFields = ['gseIndex', 'iterationIndex', 'dtEventTimeStamp'];
    if (requiredFields.includes(field_name) && requiredFields.includes(currentSortField)) {
      return true;
    }
    return currentSortField === field_name;
  };
  const renderHead = (field, onClickFn) => {
    const currentSort = activeSortField.value?.[0] || null;
    const currentSortField = currentSort ? currentSort[0] : null;
    const isSortShow = sortShow(field.field_name, currentSortField);
    const isDesc = currentSort ? currentSort[1] === 'desc' : false;
    const isAsc = currentSort ? currentSort[1] === 'asc' : false;

    if (field) {
      const fieldName = getFieldNameByField(field);
      const fieldType = field.field_type;
      const isUnionSource = field?.tag === 'union-source';
      const fieldIcon = fieldTypeMap.value?.[fieldType]?.icon ?? 'bklog-icon bklog-unkown';
      const fieldIconColor = fieldTypeMap.value?.[fieldType]?.color ?? '#EAEBF0';
      const fieldIconTextColor = fieldTypeMap.value?.[fieldType]?.textColor;
      const content = fieldTypeMap.value[fieldType]?.name;
      let unionContent = '';
      // 联合查询判断字段来源 若indexSetIDs缺少已检索的索引集内容 则增加字段来源判断
      if (isUnionSearch.value) {
        const indexSetIDs = field.index_set_ids?.map(item => String(item)) || [];
        const isDifferentFields = indexSetIDs.length !== unionIndexItemList.value.length;
        if (isDifferentFields && !isUnionSource) {
          const lackIndexNameList = unionIndexItemList.value
            .filter(item => indexSetIDs.includes(item.index_set_id))
            .map(item => item.index_set_name);
          unionContent = `${$t('字段来源')}: ${lackIndexNameList.join(' ,')}`;
        }
      }
      const isLackIndexFields = !!unionContent && isUnionSearch.value;
      const sortable =
        !['dtEventTimeStamp'].includes(field.field_name) &&
        field.es_doc_values &&
        field.tag !== 'union-source' &&
        field.field_type !== 'flattened';

      return h(
        'div',
        {
          class: 'bklog-header-cell',
          on: {
            click: (e: MouseEvent) => {
              let nextOrder = 'ascending';
              const targets = (e.target as HTMLElement).parentElement.querySelectorAll('.bk-table-sort-caret');
              for (const element of targets) {
                if (element.classList.contains('active')) {
                  element.classList.remove('active');
                  if (element.classList.contains('ascending')) {
                    nextOrder = 'descending';
                  }

                  if (element.classList.contains('descending')) {
                    nextOrder = null;
                  }
                }
              }

              const sortMap = {
                ascending: 'asc',
                descending: 'desc',
              };
              onClickFn(sortMap[nextOrder]);
            },
          },
        },
        [
          h('span', {
            class: `field-type-icon ${fieldIcon}`,
            style: {
              ...{
                marginRight: '4px',
              },
              backgroundColor: fieldIconColor,
              color: fieldIconTextColor,
            },

            directives: [
              {
                name: 'bk-tooltips',
                value: content,
              },
            ],
          }),
          h(
            'span',
            {
              directives: [
                {
                  name: 'bk-tooltips',
                  value: { allowHTML: false, content: isLackIndexFields ? unionContent : fieldName },
                },
              ],
              class: { 'lack-index-filed': isLackIndexFields },
            },
            [fieldName],
          ),

          sortable
            ? h('span', { class: 'bk-table-caret-wrapper' }, [
                h('i', {
                  class: `bk-table-sort-caret ascending ${isSortShow && isAsc ? 'active' : ''}`,
                }),
                h('i', {
                  class: `bk-table-sort-caret descending ${isSortShow && isDesc ? 'active' : ''}`,
                }),
              ])
            : '',
          h('i', {
            class: `bk-icon icon-minus-circle-shape toggle-display ${isNotVisibleFieldsShow.value ? 'is-hidden' : ''}`,
            directives: [
              {
                name: 'bk-tooltips',
                value: $t('将字段从表格中移除'),
              },
            ],
            on: {
              click: e => {
                e.stopPropagation();
                const displayFieldNames: string[] = [];
                for (const newField of visibleFields.value) {
                  if (newField.field_name !== fieldName) {
                    displayFieldNames.push(newField.field_name);
                  }
                }
                store.dispatch('userFieldConfigChange', {
                  displayFields: displayFieldNames,
                });
                store.commit('resetVisibleFields', displayFieldNames);
                store.commit('updateIsSetDefaultTableColumn');
              },
            },
          }),
        ],
      );
    }
  };

  return { renderHead };
};
