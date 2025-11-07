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

import { defineComponent, onBeforeUnmount, onMounted, ref, nextTick, watch, computed, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
// import useStore from '@/hooks/use-store';
import ItemSkeleton from '@/skeleton/item-skeleton';
import tippy, { type Instance } from 'tippy.js';

import $http from '@/api';
// import { useRouter } from 'vue-router/composables';

import { useCollectList } from '../../hook/useCollectList';
import { STATUS_ENUM, SETTING_FIELDS, MENU_LIST, GLOBAL_CATEGORIES_ENUM, COLLECTOR_SCENARIO_ENUM } from '../../utils';
import TagMore from '../common-comp/tag-more';

import type { IListItemData } from '../../type';

import './table-list.scss';

export type SearchKeyItem = {
  id: string;
  name: string;
  values: any[];
};

export default defineComponent({
  name: 'TableList',
  props: {
    indexSet: {
      type: Object as PropType<IListItemData>,
      default: () => ({}),
    },
    data: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },

  emits: [],

  setup(props, { emit }) {
    const { t } = useLocale();
    // const router = useRouter();
    // const store = useStore();
    // 使用自定义 hook 管理状态
    const { authGlobalInfo, operateHandler, checkCreateAuth, spaceUid, bkBizId } = useCollectList();
    const tableList = ref([]);
    const listLoading = ref(false);

    let tippyInstances: Instance[] = [];
    const searchKey = ref<SearchKeyItem[]>([]);
    const createdValues = ref([]); // 创建者筛选值
    const updatedByValues = ref([]); // 更新者筛选值
    const tableKey = ref(0); // 表格重新渲染key

    const pagination = ref({
      current: 1,
      count: props.data.length,
      limit: 10,
      limitList: [10, 20, 50],
    });
    const settingFields = SETTING_FIELDS;
    const data2 = [];
    /** 状态渲染 */
    const renderStatus = (key: string) => {
      const info = STATUS_ENUM.find(item => item.value === key);
      return info ? <span class={`table-status ${info.value}`}>{info.text}</span> : '--';
    };

    const columns = computed(() => [
      {
        label: t('采集名'),
        prop: 'name',
        sortable: true,
        renderFn: (row: any) => <span class='link'>{row.name}</span>,
        fixed: 'left',
        'min-width': 180,
      },
      {
        label: t('日用量'),
        prop: 'daily_usage',
        sortable: true,
        'min-width': 100,
      },
      {
        label: t('总用量'),
        prop: 'total_usage',
        sortable: true,
        'min-width': 100,
      },
      {
        label: t('存储名'),
        prop: 'bk_data_name',
        width: 180,
        renderFn: (row: any) => <div>{row.bk_data_name || '--'}</div>,
      },
      {
        label: t('所属索引集'),
        prop: 'index_set_name',
        width: 200,
        renderFn: (row: any) =>
          row.index_set_name?.length > 0 ? (
            <TagMore
              tags={row.index_set_name}
              title={t('所属索引集')}
            />
          ) : (
            '--'
          ),
      },
      {
        label: t('接入类型'),
        prop: 'category_name',
        width: 100,
        filters: GLOBAL_CATEGORIES_ENUM,
      },
      {
        label: t('日志类型'),
        prop: 'collector_scenario_name',
        width: 100,
        filters: COLLECTOR_SCENARIO_ENUM,
      },
      {
        label: t('集群名'),
        prop: 'storage_cluster_name',
        'min-width': 140,
        renderFn: (row: any) => <span>{row.storage_cluster_name || '--'}</span>,
      },
      {
        label: t('过期时间'),
        prop: 'retention',
        renderFn: (row: any) => (
          <span class={{ 'text-disabled': row.status === 'stop' }}>
            {row.retention ? `${row.retention} ${t('天')}` : '--'}
          </span>
        ),
        width: 100,
      },
      {
        label: t('标签'),
        prop: 'tags',
        showTips: false,
        renderFn: (row: any) =>
          row.tags.length > 0 ? (
            <TagMore
              tags={row.tags}
              title={t('标签')}
            />
          ) : (
            '--'
          ),
        width: 200,
      },
      {
        label: t('采集状态'),
        prop: 'status',
        width: 100,
        renderFn: (row: any) => renderStatus(row.status),
        filters: STATUS_ENUM,
      },
      {
        label: t('创建人'),
        prop: 'created_by',
        width: 100,
        filterValue: createdValues.value,
        filters: [
          { text: 'jayjhwu', value: 'jayjhwu' },
          {
            text: 'kyliewang',
            value: 'kyliewang',
          },
          {
            text: 'v_cwcgcui',
            value: 'v_cwcgcui',
          },
        ],
      },
      {
        label: t('创建时间'),
        prop: 'created_at',
        sortable: true,
        width: 180,
      },
      {
        label: t('更新人'),
        width: 100,
        prop: 'updated_by',
        filterValue: updatedByValues.value,
        filters: [
          {
            text: 'kyliewang',
            value: 'kyliewang',
          },
          {
            text: 'yuxiaogao',
            value: 'yuxiaogao',
          },
          {
            text: 'jayjhwu',
            value: 'jayjhwu',
          },
        ],
      },
      {
        label: t('更新时间'),
        prop: 'updated_at',
        sortable: true,
        width: 180,
      },
    ]);

    /** 销毁所有tippy */
    const destroyTippyInstances = () => {
      // biome-ignore lint/complexity/noForEach: <explanation>
      tippyInstances.forEach(i => {
        try {
          i.hide();
          i.destroy();
        } catch (_) {}
      });
      tippyInstances = [];
    };
    watch(
      () => listLoading.value,
      val => {
        if (!val) {
          nextTick(() => {
            initMenuPop();
          });
        }
      },
      { immediate: true },
    );
    watch(
      () => props.indexSet,
      () => {
        pagination.value.current = 1;
        getTableList();
      },
    );

    /** 渲染操作下拉列表 */
    const initMenuPop = () => {
      // 销毁旧实例，避免重复绑定
      destroyTippyInstances();

      const targets = document.querySelectorAll(
        '.v2-log-collection-table .bk-table-fixed-body-wrapper .table-more-btn',
      );
      if (!targets.length) {
        return;
      }

      const instances = tippy(targets as unknown as HTMLElement[], {
        trigger: 'click',
        placement: 'bottom-end',
        theme: 'light table-menu-popover',
        interactive: true,
        hideOnClick: true,
        arrow: false,
        offset: [0, 4],
        appendTo: () => document.body,
        onShow(instance) {
          (instance.reference as HTMLElement).classList.add('is-hover');
        },
        onHide(instance) {
          (instance.reference as HTMLElement).classList.remove('is-hover');
        },
        content(reference) {
          const btn = reference as HTMLElement;
          // 约定：内容紧跟在按钮后的兄弟元素中
          const container = btn.nextElementSibling as HTMLElement | null;
          const contentNode = container?.querySelector('.row-menu-content') as HTMLElement | null;
          return (contentNode ?? container ?? document.createElement('div')) as unknown as Element;
        },
      });

      // tippy 返回单个或数组，这里统一转为数组
      tippyInstances = Array.isArray(instances) ? instances : [instances];
    };

    onMounted(() => {
      nextTick(() => {
        !authGlobalInfo.value && checkCreateAuth();
        listLoading.value = true;
        // getTableList();
      });
    });

    onBeforeUnmount(() => {
      destroyTippyInstances();
    });
    /**
     * 获取列表数据
     */
    const getTableList = async () => {
      try {
        listLoading.value = true;
        const { current, limit } = pagination.value;
        const params = {
          space_uid: spaceUid.value,
          page: current,
          pagesize: limit,
        };
        if (props.indexSet.index_set_id !== 'all') {
          Object.assign(params, {
            parent_index_set_id: props.indexSet.index_set_id,
          });
        }
        const res = await $http.request('collect/newCollectList', {
          data: params,
        });
        console.log(res, 'res');
        tableList.value = res.data?.list || [];
        pagination.value.count = res.data?.total || 0;
      } catch (e) {
        console.warn(e);
      } finally {
        listLoading.value = false;
      }
    };

    const handleMenuClick = (key: string, row: any) => {
      // 关闭 tippy
      for (const i of tippyInstances) {
        i?.hide();
      }
      // 业务处理
      console.log(key, row);
    };
    const handlePageChange = (page: number) => {
      pagination.value.current = page;
      getTableList();
    };
    const handlePageLimitChange = (limit: number) => {
      pagination.value.limit = limit;
      getTableList();
    };
    /** 新增采集项 */
    const handleCreateOperation = () => {
      operateHandler({}, 'add');
    };
    /** 表格过滤 */
    const handleFilterMethod = (value, row, column) => {
      const property = column.property;
      // console.log(value, row, column, 'handleFilterMethod', property);
      return row[property] === value;
    };

    const handleFilterChange = (filters: any) => {
      // 处理筛选器变化，将值同步到搜索框
      console.log('Filter changed:', filters);

      // 创建新的搜索条件数组
      const newSearchKey = [...searchKey.value];

      // 处理createdBy筛选器
      if (filters.created_by && filters.created_by.length > 0) {
        // 查找是否已存在creator条件
        const creatorIndex = newSearchKey.findIndex(item => item.id === 'created_by');
        const creatorValues = filters.created_by.map((value: string) => ({ id: value, name: value }));

        if (creatorIndex >= 0) {
          // 更新现有条件
          newSearchKey[creatorIndex] = {
            id: 'created_by',
            name: t('创建人'),
            values: creatorValues,
          };
        } else {
          // 添加新条件
          newSearchKey.push({
            id: 'created_by',
            name: t('创建人'),
            values: creatorValues,
          });
        }
      } else {
        // 移除creator条件
        const creatorIndex = newSearchKey.findIndex(item => item.id === 'created_by');
        if (creatorIndex >= 0) {
          newSearchKey.splice(creatorIndex, 1);
        }
      }

      // 处理updatedBy筛选器 (注意：表格列中使用的是updatedBy)
      if (filters.updated_by && filters.updated_by.length > 0) {
        // 查找是否已存在updater条件
        const updaterIndex = newSearchKey.findIndex(item => item.id === 'updated_by');
        const updaterValues = filters.updated_by.map((value: string) => ({ id: value, name: value }));

        if (updaterIndex >= 0) {
          // 更新现有条件
          newSearchKey[updaterIndex] = {
            id: 'updated_by',
            name: t('更新人'),
            values: updaterValues,
          };
        } else {
          // 添加新条件
          newSearchKey.push({
            id: 'updated_by',
            name: t('更新人'),
            values: updaterValues,
          });
        }
      } else {
        // 移除updater条件
        const updaterIndex = newSearchKey.findIndex(item => item.id === 'updated_by');
        if (updaterIndex >= 0) {
          newSearchKey.splice(updaterIndex, 1);
        }
      }

      // 更新搜索条件
      searchKey.value = newSearchKey;
      console.log('Updated searchKey:', searchKey.value);

      // 重新获取表格数据
      // this.getTableData();
    };

    const handleSearchChange = (val: string) => {
      // 提取创建者和更新者的筛选值
      const creatorCondition = searchKey.value.find(item => item.id === 'created_by');
      const updaterCondition = searchKey.value.find(item => item.id === 'updated_by');

      // 更新筛选值
      createdValues.value = creatorCondition ? creatorCondition.values.map((item: any) => item.id) : [];
      updatedByValues.value = updaterCondition ? updaterCondition.values.map((item: any) => item.id) : [];
      console.log('createdValues', createdValues.value);

      // 强制重新渲染表格
      tableKey.value += 1;
      searchKey.value = val;
      console.log('搜索', val);
    };

    return () => (
      <div class='v2-log-collection-table'>
        <div class='v2-log-collection-table-header'>
          {props.indexSet.index_set_name}
          <span class='table-header-count'>{props.indexSet.index_count}</span>
        </div>
        <div class='v2-log-collection-table-tool'>
          <div class='tool-btns'>
            <bk-button
              icon='plus'
              theme='primary'
              on-Click={handleCreateOperation}
            >
              {t('采集项')}
            </bk-button>
          </div>
          <bk-search-select
            class='tool-search-select'
            data={data2}
            placeholder={t('搜索 采集名、存储名、索引集、集群名、创建人、更新人')}
            value={searchKey.value}
            on-change={handleSearchChange}
          />
        </div>
        <div class='v2-log-collection-table-main'>
          <bk-table
            // key={tableKey.value}
            ext-cls='collection-table-box'
            data={tableList.value}
            on-filter-change={handleFilterChange}
          >
            {columns.value.map((item, ind) => (
              <bk-table-column
                key={`${item.prop}_${ind}`}
                width={item.width}
                scopedSlots={{
                  default: ({ row }) => {
                    /** 自定义 */
                    if (item?.renderFn) {
                      return (item as any)?.renderFn(row);
                    }
                    return row[item.prop] ?? '--';
                  },
                }}
                column-key={item.prop}
                filter-method={handleFilterMethod}
                filter-multiple={false}
                filtered-value={item?.filterValue}
                filters={item?.filters}
                fixed={!!item.fixed}
                label={item.label}
                min-width={item['min-width']}
                prop={item.prop}
                show-overflow-tooltip={!!item.showTips}
                sortable={!!item?.sortable}
              />
            ))}
            <bk-table-column
              width={70}
              class='table-operation'
              scopedSlots={{
                default: ({ row }) => {
                  return (
                    <div>
                      <span class='link mr-6'>{t('检索')}</span>
                      <span
                        class={{
                          link: true,
                          disabled: row.is_editable,
                        }}
                      >
                        {t('编辑')}
                      </span>
                      <span class='bk-icon icon-more more-btn table-more-btn' />
                      <div
                        style={{ display: 'none' }}
                        class='row-menu-popover'
                      >
                        <div class='row-menu-content'>
                          {MENU_LIST.map(item => (
                            <span
                              key={item.key}
                              class='menu-item'
                              on-Click={(e: MouseEvent) => handleMenuClick(item.key, row, e)}
                            >
                              {item.label}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                },
              }}
              fixed={'right'}
              label={t('操作')}
            />
            <bk-table-column
              tippy-options={{ zIndex: 3000 }}
              type='setting'
            >
              <bk-table-setting-content
                fields={settingFields}
                // :selected="setting.selectedFields"
                // @setting-change="handleSettingChange"
              />
            </bk-table-column>
          </bk-table>
          {listLoading.value && (
            <div class='table-skeleton-box'>
              <ItemSkeleton
                style={{ padding: '0 16px' }}
                columns={5}
                gap={'14px'}
                rowHeight={'28px'}
                rows={6}
                widths={['25%', '25%', '20%', '20%', '10%']}
              />
            </div>
          )}
          {tableList.value?.length > 0 && (
            <bk-pagination
              class='table-pagination-box'
              align='right'
              count={pagination.value.count}
              current={pagination.value.current}
              limit={pagination.value.limit}
              limit-list={pagination.value.limitList}
              show-limit={true}
              size='small'
              show-total-count
              on-change={handlePageChange}
              on-limit-change={handlePageLimitChange}
              {...{ on: { 'update:current': v => (pagination.value.current = v) } }}
            />
          )}
        </div>
      </div>
    );
  },
});
