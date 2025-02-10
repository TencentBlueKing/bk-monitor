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

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import useFieldNameHook from '@/hooks/use-field-name';
import TimeFormatterSwitcher from '../original-log/time-formatter-switcher';

export default () => {
  const store = useStore();
  const { $t } = useLocale();

  const indexFieldInfo = computed(() => store.state.indexFieldInfo);
  const fieldAliasMap = computed(() =>
    (indexFieldInfo.value.fields ?? []).reduce(
      (out, field) => ({ ...out, [field.field_name]: field.field_alias || field.field_name }),
      {},
    ),
  );
  const showFieldAlias = computed(() => store.state.showFieldAlias);
  const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);
  const isUnionSearch = computed(() => store.getters.isUnionSearch);
  const unionIndexItemList = computed(() => store.getters.unionIndexItemList);
  const visibleFields = computed(() => store.state.visibleFields);
  const isNotVisibleFieldsShow = computed(() => store.state.isNotVisibleFieldsShow);
  const sortList = computed(() => indexFieldInfo.value.sort_list);

  const renderHead = (field, onClickFn) => {
    const currentSort = sortList.value.find(s => s[0] === field.field_name)?.[1];
    const isDesc = currentSort === 'desc';
    const isAsc = currentSort === 'asc';
    const isShowSwitcher = ['date', 'date_nanos'].includes(field?.field_type);
    if (field) {
      const { getQueryAlias } = useFieldNameHook({ store });
      const fieldName = getQueryAlias(field);
      const fieldType = field.field_type;
      const isUnionSource = field?.tag === 'union-source';
      const fieldIcon = fieldTypeMap.value?.[fieldType]?.icon ?? 'bklog-icon bklog-unkown';
      const fieldIconColor = fieldTypeMap.value?.[fieldType]?.color ?? '#EAEBF0';
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
      const sortable = field.es_doc_values && field.tag !== 'union-source';

      return h(
        'div',
        {
          class: 'bklog-header-cell',
          on: {
            click: (e: MouseEvent) => {
              let nextOrder = 'ascending';
              const targets = (e.target as HTMLElement).parentElement.querySelectorAll('.bk-table-sort-caret');
              targets.forEach(element => {
                if (element.classList.contains('active')) {
                  element.classList.remove('active');
                  if (element.classList.contains('ascending')) {
                    nextOrder = 'descending';
                  }

                  if (element.classList.contains('descending')) {
                    nextOrder = null;
                  }
                }
              });

              if (nextOrder !== null) {
                targets.forEach(el => {
                  if (el.classList.contains(nextOrder)) {
                    el.classList.add('active');
                  }
                });
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
          h(TimeFormatterSwitcher, {
            class: 'timer-formatter',
            style: {
              display: isShowSwitcher ? 'inline-block' : 'none',
            },
          }),
          sortable
            ? h('span', { class: 'bk-table-caret-wrapper' }, [
                h('i', { class: `bk-table-sort-caret ascending ${isAsc ? 'active' : ''}` }),
                h('i', { class: `bk-table-sort-caret descending ${isDesc ? 'active' : ''}` }),
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
                const displayFieldNames = [];
                visibleFields.value.forEach(field => {
                  if (field.field_name !== fieldName) {
                    displayFieldNames.push(field.field_name);
                  }
                });
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
