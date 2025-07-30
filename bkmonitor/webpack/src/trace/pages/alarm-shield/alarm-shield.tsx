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
import { ref as deepRef, defineComponent, provide, reactive, shallowRef } from 'vue';

import {
  type FilterValue,
  type SortInfo,
  type TableFilterChangeContext,
  type TableRowData,
  type TableSort,
  PrimaryTable,
} from '@blueking/tdesign-ui';
import { Button, DatePicker, InfoBox, Message, Pagination, SearchSelect } from 'bkui-vue';
import { disableShield, frontendShieldList } from 'monitor-api/modules/shield';
import { commonPageSizeGet, commonPageSizeSet } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import EmptyStatus, { type EmptyStatusType } from '../../components/empty-status/empty-status';
import TableSkeleton from '../../components/skeleton/table-skeleton';
import { getAuthorityMap, useAuthorityStore } from '../../store/modules/authority';
import AlarmShieldDetail from './alarm-shield-detail';
import * as authMap from './authority-map';
import { type AlarmShieldTableItem, type IColumn, EColumn } from './typing';

import type { IAuthority } from '../../typings/authority';

import './alarm-shield.scss';

export default defineComponent({
  name: 'AlarmShield',
  setup() {
    const { t } = useI18n();
    const route = useRoute();
    const router = useRouter();
    const authorityStore = useAuthorityStore();
    const authority = reactive<IAuthority>({
      map: authMap,
      auth: {},
      showDetail: authorityStore.getAuthorityDetail,
    });
    /* 时间范围 */
    const dateRange = deepRef([]);
    /* 参数范围 */
    const backDisplayMap = deepRef({});
    /* 搜索内容 */
    const searchData = deepRef([]);
    const searchValues = deepRef([]);
    const filterValue = shallowRef<FilterValue>({});
    let searchCondition = [];
    /* 状态映射 */
    const statusMap = {
      1: {
        des: t('屏蔽中'),
        className: 'shield',
        code: 1,
      },
      2: {
        des: t('已过期'),
        className: 'overdue',
        code: 2,
      },
      3: {
        des: t('被解除'),
        className: 'release',
        code: 3,
      },
    };
    /* 屏蔽状态 */
    const shieldStatus = deepRef(0);
    const shieldStatusList = [
      { name: t('屏蔽中'), id: 0, type: 'effct' },
      { name: t('屏蔽失效'), id: 1, type: 'overdue' },
    ];
    const columns = shallowRef<IColumn[]>([
      {
        id: EColumn.id,
        name: 'ID',
        width: 80,
        disabled: true,
        sortable: true,
      },
      // {
      //   id: EColumn.shieldType,
      //   name: t('分类'),
      //   width: 150,
      //   disabled: true,
      //   filterMultiple: true,
      //   filter: [
      //     { label: t('告警事件屏蔽'), value: 'alert' },
      //     { label: t('范围屏蔽'), value: 'scope' },
      //     { label: t('策略屏蔽'), value: 'strategy' },
      //     { label: t('维度屏蔽'), value: 'dimension' },
      //   ],
      // },
      {
        id: EColumn.shieldContent,
        name: t('屏蔽内容'),
        disabled: false,
        minWidth: 250,
      },
      {
        id: EColumn.beginTime,
        name: t('开始时间'),
        width: 200,
        disabled: false,
        sortable: true,
      },
      // {
      //   id: EColumn.failureTime,
      //   name: t('失效时间'),
      //   width: 150,
      //   disabled: false,
      //   sortable: true,
      // },
      // {
      //   id: EColumn.cycleDuration,
      //   name: t('持续周期及时长'),
      //   width: 150,
      //   disabled: false,
      // },
      {
        id: EColumn.endTime,
        name: t('结束时间'),
        width: 200,
        disabled: false,
      },
      {
        id: EColumn.shieldCycle,
        name: t('屏蔽周期'),
        width: 300,
        disabled: false,
      },
      {
        id: EColumn.currentCycleRamainingTime,
        name: t('当前周期剩余时长'),
        width: 200,
        disabled: false,
      },
      {
        id: EColumn.description,
        name: t('屏蔽原因'),
        minWidth: 230,
        disabled: false,
      },
      {
        id: EColumn.status,
        name: t('状态'),
        width: 150,
        disabled: false,
      },
      // {
      //   id: EColumn.updateUser,
      //   name: t('更新人'),
      //   width: 150,
      //   disabled: false,
      // },
      {
        id: EColumn.operate,
        name: t('操作'),
        width: 100,
        disabled: true,
      },
    ]);
    const tableLoading = deepRef(false);

    const pagination = reactive({
      current: 1,
      count: 0,
      limit: 10,
    });

    const sort = deepRef<SortInfo>({
      sortBy: '',
      descending: false,
    });

    const tableList = shallowRef<AlarmShieldTableItem[]>([]);

    const emptyType = deepRef<EmptyStatusType>('empty');
    /* 详情数据 */
    const detailData = reactive({
      show: false,
      id: '',
    });

    provide('authority', authority);

    init();

    async function init() {
      const pageSize = commonPageSizeGet();
      pagination.limit = pageSize;
      tableLoading.value = true;
      authority.auth = await getAuthorityMap(authMap);
      createdConditionList();
      await handleGetShieldList();
    }

    function createdConditionList() {
      backDisplayMap.value = {
        id: {
          name: `${t('屏蔽ID')}`,
          value: [],
          id: 'id',
        },
        strategy_id: {
          name: `${t('策略ID')}`,
          value: [],
          id: 'strategy_id',
        },
      };
      const res = [];
      const map: Record<string, any> = backDisplayMap.value;
      for (const { name, id, list } of Object.values(map)) {
        res.push({
          name,
          id,
          multiple: true,
          children: list || [],
        });
      }
      searchData.value = res;
      getRouterParams();
    }

    /**
     * @description 获取路由参数
     */
    function getRouterParams() {
      /* 需要 此类格式的数据 queryString： [{key: 'xxx/query', value: ['xx', 'xx']}] */
      const queryString = route.query?.queryString;
      if (queryString) {
        let queryStringObj = null;
        try {
          queryStringObj = JSON.parse(queryString as any);
        } catch {
          router
            .replace({
              ...route,
              query: { queryString: undefined },
            })
            .catch(() => {});
        }
        if (queryStringObj) {
          const ids = Object.keys(backDisplayMap.value);
          const searchValueList = [];
          for (const item of queryStringObj) {
            if (ids.includes(item.key)) {
              if (item.value?.length)
                searchValueList.push({
                  id: item.key,
                  multiple: true,
                  name: backDisplayMap.value[item.key].name,
                  values: Array.isArray(item.value) ? item.value.map(item => ({ id: item, name: item })) : [item.value],
                });
            } else {
              if (item.key) searchValueList.push({ id: item.key, name: item.key });
            }
          }
          searchValues.value = searchValueList;
          searchCondition = routerParamsReplace();
        }
      }
    }
    /**
     * @description 屏蔽状态切换
     * @param item
     */
    function handleStatusChange(item) {
      if (tableLoading.value) {
        return;
      }
      if (shieldStatus.value !== item.id) {
        shieldStatus.value = item.id;
        pagination.current = 1;
        sort.value = {
          sortBy: '',
          descending: false,
        };
        handleGetShieldList();
      }
    }
    /**
     * @description 获取屏蔽列表
     */
    async function handleGetShieldList() {
      tableLoading.value = true;
      // tableData.data = [];

      // let categories = filterValue.value[EColumn.shieldType];
      // if (!categories?.length) {
      //   categories = columns.value.find(item => item.id === EColumn.shieldType).filter.map(item => item.value);
      // }
      const categories = ['alert', 'scope', 'strategy', 'dimension'];

      const params = {
        page: pagination.current,
        page_size: pagination.limit,
        time_range: (() => {
          if (dateRange.value?.every(item => !!item)) {
            return dateRange.value.join('--');
          }
          return undefined;
        })(),
        categories, // 2025-06-03更新：取消分类列的展示，该入参维持原状
        search: '',
        order: (() => {
          if (sort.value.sortBy) {
            if (!sort.value.descending) {
              return sort.value.sortBy;
            }
            return `-${sort.value.sortBy}`;
          }
          return undefined;
        })(),
        conditions: searchCondition,
        is_active: shieldStatus.value === 0,
      };
      const data = await frontendShieldList(params).catch(() => {
        emptyType.value = '500';
        return {
          shield_list: [],
          count: 0,
        };
      });
      tableList.value = [...data.shield_list];

      pagination.count = data.count;
      tableLoading.value = false;
    }
    /**
     * @description 条件搜索
     * @param v
     */
    function handleSearchCondition(v) {
      searchValues.value = v;
      pagination.current = 1;
      searchCondition = routerParamsReplace();
      emptyType.value = searchCondition.length ? 'search-empty' : 'empty';
      handleGetShieldList();
    }
    function routerParamsReplace() {
      const query = [];
      const ids = Object.keys(backDisplayMap.value);
      for (const item of searchValues.value) {
        if (ids.includes(item.id)) {
          if (item.values?.length) query.push({ key: item.id, value: item.values.map(v => v.id) });
        } else {
          if (item.id) query.push({ key: 'query', value: item.id });
        }
      }
      const queryStr = JSON.stringify(query);
      router
        .replace({
          ...route,
          query: {
            queryString: query?.length ? queryStr : undefined,
          },
        })
        .catch(() => {});
      return query;
    }
    /**
     * @description 新建
     */
    function handleAdd() {
      router.push({
        name: 'alarm-shield-add',
      });
    }
    /**
     * @description 详情
     * @param row
     */
    function handleToDetail(row) {
      detailData.id = row.id;
      handleDetailShowChange(true);
    }
    function handleDetailShowChange(v: boolean) {
      detailData.show = v;
    }

    /**
     * @description 跳转到编辑
     * @param row
     */
    function handleToEdit(row) {
      router.push({
        name: 'alarm-shield-edit',
        params: {
          id: row.id,
        },
      });
    }
    /**
     * @description 克隆屏蔽
     * @param row
     */
    function handleToClone(row) {
      router.push({
        name: 'alarm-shield-clone',
        params: {
          id: row.id,
        },
      });
    }

    /**
     * @description 删除屏蔽
     * @param row
     */
    function handleDelete(row) {
      InfoBox({
        title: t('是否解除该屏蔽?'),
        onConfirm: () => {
          disableShield({ id: row.id }).then(() => {
            handleGetShieldList();
            Message({
              theme: 'success',
              message: t('解除屏蔽成功'),
            });
          });
        },
      });
    }
    /**
     * @description 当前排序
     * @param opt
     */
    function handleSortChange(info: TableSort) {
      if (info) {
        sort.value = { ...info };
      } else {
        sort.value = {
          sortBy: '',
          descending: false,
        };
      }
      pagination.current = 1;
      handleGetShieldList();
    }
    /**
     * @description 当前筛选
     * @param opt
     */
    function handleFilterChange(value: FilterValue, context: TableFilterChangeContext<TableRowData>) {
      const field = context?.col?.colKey;
      filterValue.value = value;
      if (!field) return;
      pagination.current = 1;
      handleGetShieldList();
    }
    /**
     * @description 当前页切换
     * @param page
     */
    function handlePageChange(page: number) {
      if (pagination.current !== page) {
        pagination.current = page;
        handleGetShieldList();
      }
    }
    /**
     * @description limit切换
     * @param limit
     */
    function handleLimitChange(limit: number) {
      pagination.current = 1;
      pagination.limit = limit;
      commonPageSizeSet(limit);
      handleGetShieldList();
    }

    function handleDatePick() {
      emptyType.value = 'search-empty';
      pagination.current = 1;
      handleGetShieldList();
    }
    /**
     * @description 空状态操作
     * @param type
     * @returns
     */
    function handleEmptyOperation(type) {
      if (type === 'refresh') {
        emptyType.value = 'empty';
        handleGetShieldList();
        return;
      }
      if (type === 'clear-filter') {
        searchValues.value = [];
        dateRange.value = [];
        searchCondition = routerParamsReplace();
        emptyType.value = searchCondition.length ? 'search-empty' : 'empty';
        handleGetShieldList();
        return;
      }
    }

    /**
     * @description 清空时间范围
     */
    function handleDatePickClear() {
      setTimeout(() => {
        pagination.current = 1;
        handleGetShieldList();
      }, 50);
    }

    function handleSetFormat(row, column) {
      switch (column) {
        case EColumn.id: {
          return (
            <Button
              theme='primary'
              text
              onClick={() => handleToDetail(row)}
            >{`#${row.id}`}</Button>
          );
        }
        // case EColumn.shieldType: {
        //   return <span>{row.category_name}</span>;
        // }
        case EColumn.shieldContent: {
          return <span>{row.content}</span>;
        }
        case EColumn.beginTime: {
          return <span>{row.begin_time}</span>;
        }
        // case EColumn.failureTime: {
        //   return <span>{row.failure_time}</span>;
        // }
        // case EColumn.cycleDuration: {
        //   return <span>{row.cycle_duration}</span>;
        // }
        case EColumn.endTime: {
          return <span>{row.end_time}</span>;
        }
        case EColumn.shieldCycle: {
          return <span>{row.shield_cycle}</span>;
        }
        case EColumn.currentCycleRamainingTime: {
          // 后端null：不在屏蔽周期内
          return (
            <span class={!row.current_cycle_ramaining_time ? 'overdue' : ''}>
              {row.current_cycle_ramaining_time || t('不在屏蔽周期内')}
            </span>
          );
        }
        case EColumn.description: {
          return <span>{row.description || '--'}</span>;
        }
        case EColumn.status: {
          return <span class={statusMap[row.status].className}>{statusMap[row.status].des}</span>;
        }
        // case EColumn.updateUser: {
        //   return <span>{row.update_user || '--'}</span>;
        // }
        case EColumn.operate: {
          return (
            <div>
              {row.category !== 'alert' && (
                <Button
                  class='mr-8'
                  v-authority={{ active: !authority.auth.MANAGE_AUTH }}
                  text={true}
                  theme='primary'
                  onClick={() =>
                    authority.auth.MANAGE_AUTH ? handleToClone(row) : authority.showDetail([authority.map.MANAGE_AUTH])
                  }
                >
                  {t('克隆')}
                </Button>
              )}
              {shieldStatus.value === 0
                ? [
                    <Button
                      key='edit'
                      class='mr-8'
                      v-authority={{ active: !authority.auth.MANAGE_AUTH }}
                      text={true}
                      theme='primary'
                      onClick={() =>
                        authority.auth.MANAGE_AUTH
                          ? handleToEdit(row)
                          : authority.showDetail([authority.map.MANAGE_AUTH])
                      }
                    >
                      {t('编辑')}
                    </Button>,
                    <Button
                      key='delete'
                      v-authority={{ active: !authority.auth.MANAGE_AUTH }}
                      text={true}
                      theme='primary'
                      onClick={() =>
                        authority.auth.MANAGE_AUTH
                          ? handleDelete(row)
                          : authority.showDetail([authority.map.MANAGE_AUTH])
                      }
                    >
                      {t('解除')}
                    </Button>,
                  ]
                : undefined}
            </div>
          );
        }
        default: {
          return <span>--</span>;
        }
      }
    }

    return {
      columns,
      sort,
      tableLoading,
      tableList,
      pagination,
      authorityStore,
      authority,
      handleAdd,
      shieldStatusList,
      filterValue,
      t,
      shieldStatus,
      handleStatusChange,
      dateRange,
      handleDatePick,
      searchValues,
      searchData,
      emptyType,
      detailData,
      handleSearchCondition,
      handleSetFormat,
      handleSortChange,
      handleFilterChange,
      handleEmptyOperation,
      handlePageChange,
      handleLimitChange,
      handleDetailShowChange,
      handleDatePickClear,
    };
  },
  render() {
    return (
      <div class='alarm-shield-page'>
        <div class='alarm-shield-wrap'>
          <div class='top-container'>
            <div class='left'>
              <Button
                class='add-btn'
                v-authority={{ active: !this.authority.auth.MANAGE_AUTH }}
                theme='primary'
                onClick={() =>
                  this.authority.auth.MANAGE_AUTH
                    ? this.handleAdd()
                    : this.authority.showDetail([this.authority.map.MANAGE_AUTH])
                }
              >
                <span class='icon-monitor icon-plus-line mr-6' />
                {this.t('新增屏蔽')}
              </Button>
              <div class='shield-status status-tab-wrap'>
                {this.shieldStatusList.map(item => (
                  <span
                    key={item.id}
                    class={['status-tab-item', { active: item.id === this.shieldStatus }]}
                    onClick={() => this.handleStatusChange(item)}
                  >
                    <span class={['status-point', `status-${item.type}`]}>
                      <span class={item.type} />
                    </span>
                    <span class='status-name'>{item.name}</span>
                  </span>
                ))}
              </div>
            </div>
            <div class='right'>
              <DatePicker
                class='shield-time'
                appendToBody={true}
                format={'yyyy-MM-dd HH:mm:ss'}
                modelValue={this.dateRange}
                placeholder={this.t('选择屏蔽时间范围')}
                type='datetimerange'
                onChange={v => (this.dateRange = v)}
                onClear={() => this.handleDatePickClear()}
                onPick-success={this.handleDatePick}
              />
              <SearchSelect
                class='shield-search'
                data={this.searchData}
                modelValue={this.searchValues}
                placeholder={this.t('输入屏蔽内容、ID、策略ID')}
                onUpdate:modelValue={v => this.handleSearchCondition(v)}
              />
            </div>
          </div>
          <div class='table-wrap'>
            {!this.tableLoading ? (
              <PrimaryTable
                class='shield-table'
                v-slots={{
                  empty: () => (
                    <EmptyStatus
                      type={this.emptyType}
                      onOperation={this.handleEmptyOperation}
                    />
                  ),
                }}
                bkUiSettings={{
                  checked: this.columns.map(item => item.id),
                }}
                columns={this.columns.map(item => ({
                  title: item.name,
                  minWidth: item.minWidth || item.width,
                  resizable: true,
                  cellKey: item.id,
                  colKey: item.id,
                  ellipsis: {
                    popperOptions: {
                      strategy: 'fixed',
                    },
                  },
                  sortType: 'all',
                  sorter: item.sortable,
                  filter: item.filter?.length
                    ? {
                        resetValue: [],
                        type: 'multiple',
                        list: item.filter,
                        showConfirmAndReset: true,
                        props: {},
                      }
                    : undefined,
                  cell: (_, { row }) => this.handleSetFormat(row, item.id),
                }))}
                pagination={{
                  total: this.pagination.count,
                }}
                data={this.tableList}
                filterValue={this.filterValue}
                rowKey='id'
                showSortColumnBgColor={true}
                sort={this.sort}
                resizable
                onFilterChange={this.handleFilterChange}
                onSortChange={this.handleSortChange}
              />
            ) : (
              <TableSkeleton />
            )}

            {!!this.tableList.length && (
              <Pagination
                class='mt-14'
                align={'right'}
                count={this.pagination.count}
                layout={['total', 'limit', 'list']}
                limit={this.pagination.limit}
                location={'right'}
                modelValue={this.pagination.current}
                onChange={v => this.handlePageChange(v)}
                onLimitChange={v => this.handleLimitChange(v)}
              />
            )}
          </div>
        </div>
        <AlarmShieldDetail
          id={this.detailData.id}
          show={this.detailData.show}
          onShowChange={this.handleDetailShowChange}
        />
      </div>
    );
  },
});
