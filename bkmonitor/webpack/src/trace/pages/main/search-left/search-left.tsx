/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { computed, defineComponent } from 'vue';
import type { PropType } from 'vue';

import * as authorityMap from 'apm/pages/home/authority-map';
import { Button, ResizeLayout, Select } from 'bkui-vue';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';

import ChartFiltering from '../../../components/chart-filtering/chart-filtering';
import { useAuthorityStore } from '../../../store/modules/authority';
import { useTraceStore } from '../../../store/modules/trace';
import FieldFiltering from '../event-retrieval/field-filtering';

import type { IAppItem, ISearchTypeItem, ISpanListItem, ITraceListItem, SearchType } from '../../../typings';
import type { IFilterCondition } from 'monitor-pc/pages/data-retrieval/typings';

import './search-left.scss';

export function formItem(label: JSX.Element | string, content: JSX.Element, key?: string) {
  return (
    <div
      key={key || ''}
      class='left-form-item'
    >
      <div class='item-label'>{label}</div>
      <div class='item-content'>{content}</div>
    </div>
  );
}
export default defineComponent({
  name: 'SearchLeft',
  props: {
    showBottom: {
      type: Boolean,
      default: true,
    },
    app: {
      type: String,
      default: '',
    },
    appList: {
      type: Array as PropType<IAppItem[]>,
      default: () => [],
    },
    searchType: {
      type: String as PropType<SearchType>,
      default: 'scope',
    },
  },
  emits: ['update:app', 'update:searchType', 'appChange', 'searchTypeChange', 'addCondition'],
  setup(props, { slots, emit }) {
    const store = useTraceStore();
    const { filterSpanList, filterTraceList, listType, spanList, traceList } = storeToRefs(store);

    /** trace列表数据 */
    const listData = computed(() => (listType.value === 'trace' ? traceList.value : spanList.value));

    const filterList = computed(() => (listType.value === 'trace' ? filterTraceList.value : filterSpanList.value));

    const filterListChange = (val: ISpanListItem[] | ITraceListItem[]) => {
      if (listType.value === 'trace') {
        store.setFilterTraceList(val as ITraceListItem[]);
      } else {
        store.setFilterSpanList(val as ISpanListItem[]);
      }
    };

    const authorityStore = useAuthorityStore();
    const placement = 'top';
    const { t } = useI18n();
    const searchTypeList: ISearchTypeItem[] = [
      { id: 'accurate', name: t('ID 精准查询') },
      { id: 'scope', name: t('范围查询') },
    ];

    function handleSearchTypeChange(id: string) {
      if (id === props.searchType) return;

      emit('update:searchType', id);
      emit('searchTypeChange', id);
    }

    function handleApplyApp(id: number) {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const action_ids = authorityMap.VIEW_AUTH;
      const resources = [{ id, type: 'apm_application' }];
      authorityStore.getIntanceAuthDetail(action_ids, resources);
    }

    function handleCreateApp() {
      const url = location.href.replace(location.hash, '#/apm/home');
      window.open(url, '_blank');
    }

    const topContent = () => (
      <div class='top-content'>
        {[
          formItem(
            t('应用'),
            <Select
              class='w-100'
              v-model={props.app}
              v-slots={{
                extension: () => (
                  <div
                    class='create-app-extension'
                    onClick={() => handleCreateApp()}
                  >
                    <span class='icon-monitor icon-jia' />
                    <span>{t('新建应用')}</span>
                  </div>
                ),
                default: () => {
                  return props.appList.map((item, index) => (
                    <Select.Option
                      id={item.app_name}
                      key={index}
                      name={`${item.app_alias}（${item.app_name}）`}
                    >
                      <div
                        class={['app-option-wrap', { 'is-disabled': !item.permission?.[authorityMap.VIEW_AUTH] }]}
                        onClick={e => {
                          if (!item.permission?.[authorityMap.VIEW_AUTH]) {
                            e.stopPropagation();
                          }
                        }}
                      >
                        <span class='app-name'>{`${item.app_alias}（${item.app_name}）`}</span>
                        {!item.permission?.[authorityMap.VIEW_AUTH] && (
                          <span
                            class='apply-btn'
                            onClick={e => {
                              e.stopPropagation();
                              handleApplyApp(item.application_id);
                            }}
                          >
                            {t('申请权限')}
                          </span>
                        )}
                      </div>
                    </Select.Option>
                  ));
                },
              }}
              clearable={false}
              filterable={true}
              popoverOptions={{ theme: 'light bk-select-popover trace-search-select-popover' }}
              onChange={v => emit('appChange', v)}
            />
          ),
          formItem(
            t('查询方式'),
            <Button.ButtonGroup class='inquiry-button-container'>
              {searchTypeList.map(item => (
                <Button
                  key={item.id}
                  class={{ 'is-selected': props.searchType === item.id }}
                  onClick={() => handleSearchTypeChange(item.id)}
                >
                  {item.name}
                </Button>
              ))}
            </Button.ButtonGroup>
          ),
          slots.query?.(),
        ]}
      </div>
    );
    function handleAddCondition(val: IFilterCondition.localValue) {
      emit('addCondition', val);
    }
    return () => (
      <div class='inquire-left-layout-component'>
        {props.showBottom ? (
          <ResizeLayout
            style={{ height: '100%' }}
            v-slots={{
              aside: () => topContent(),
              main: () =>
                props.searchType === 'scope' ? (
                  <div class='bottom-content'>
                    <div class='results-statistics'>
                      <div class='title'>{t('查询结果统计')}</div>
                      <ChartFiltering
                        filterList={filterList.value}
                        list={listData.value}
                        listType={listType.value}
                        onFilterListChange={filterListChange}
                      />
                      <FieldFiltering
                        class='field-filtering'
                        onAddCondition={handleAddCondition}
                      />
                    </div>
                  </div>
                ) : undefined,
            }}
            initialDivide={610}
            placement={placement}
            immediate
          />
        ) : (
          topContent()
        )}
      </div>
    );
  },
});
