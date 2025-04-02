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
import { defineComponent, provide, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { Table, TableColumn } from '@blueking/table';
import { Button, DatePicker, InfoBox, Message, Pagination, SearchSelect } from 'bkui-vue';
import { disableShield, frontendShieldList } from 'monitor-api/modules/shield';
import { commonPageSizeGet, commonPageSizeSet } from 'monitor-common/utils';

import EmptyStatus, { type EmptyStatusType } from '../../components/empty-status/empty-status';
import TableSkeleton from '../../components/skeleton/table-skeleton';
import { getAuthorityMap, useAuthorityStore } from '../../store/modules/authority';
import AlarmShieldDetail from './alarm-shield-detail';
import * as authMap from './authority-map';
import { EColumn, type ITableData } from './typing';

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
    const dateRange = ref([]);
    /* 参数范围 */
    const backDisplayMap = ref({});
    /* 搜索内容 */
    const searchData = ref([]);
    const searchValues = ref([]);
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
    const shieldStatus = ref(0);
    const shieldStatusList = [
      { name: t('屏蔽中'), id: 0, type: 'effct' },
      { name: t('屏蔽失效'), id: 1, type: 'overdue' },
    ];
    /* 表格数据 */
    const tableData = reactive<ITableData>({
      loading: false,
      data: [],
      columns: [
        {
          id: EColumn.id,
          name: 'ID',
          width: 100,
          disabled: true,
          sortable: true,
        },
        {
          id: EColumn.shieldType,
          name: t('分类'),
          width: 150,
          disabled: true,
          filterMultiple: true,
          filter: [
            { label: t('告警事件屏蔽'), value: 'alert' },
            { label: t('范围屏蔽'), value: 'scope' },
            { label: t('策略屏蔽'), value: 'strategy' },
            { label: t('维度屏蔽'), value: 'dimension' },
          ],
        },
        {
          id: EColumn.shieldContent,
          name: t('屏蔽内容'),
          width: 250,
          disabled: false,
        },
        {
          id: EColumn.beginTime,
          name: t('开始时间'),
          width: 150,
          disabled: false,
          sortable: true,
        },
        {
          id: EColumn.failureTime,
          name: t('失效时间'),
          width: 150,
          disabled: false,
          sortable: true,
        },
        {
          id: EColumn.cycleDuration,
          name: t('持续周期及时长'),
          width: 150,
          disabled: false,
        },
        {
          id: EColumn.description,
          name: t('屏蔽原因'),
          width: 230,
          disabled: false,
        },
        {
          id: EColumn.status,
          name: t('状态'),
          width: 150,
          disabled: false,
        },
        {
          id: EColumn.updateUser,
          name: t('更新人'),
          width: 150,
          disabled: false,
        },
        {
          id: EColumn.operate,
          name: t('操作'),
          width: 150,
          disabled: true,
        },
      ],
      pagination: {
        current: 1,
        count: 0,
        limit: 10,
      },
      sort: {
        field: '',
        order: '',
      },
      filter: {},
    });
    const settings = reactive({
      checked: tableData.columns.map(item => item.id),
      size: 'small',
      fields: tableData.columns
        .filter(item => {
          if (shieldStatus.value === 0) {
            return ![EColumn.failureTime, EColumn.status].includes(item.id);
          }
          return ![EColumn.cycleDuration].includes(item.id);
        })
        .map(item => ({
          label: item.name,
          field: item.id,
          disabled: item.disabled,
        })),
    });
    const emptyType = ref<EmptyStatusType>('empty');
    /* 详情数据 */
    const detailData = reactive({
      show: false,
      id: '',
    });

    provide('authority', authority);

    init();
    async function init() {
      const pageSize = commonPageSizeGet();
      tableData.pagination.limit = pageSize;
      tableData.loading = true;
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
      const map = backDisplayMap.value;
      Object.keys(map).forEach((key: string) => {
        const { name, id, list } = map[key];
        res.push({
          name,
          id,
          multiple: true,
          children: list || [],
        });
      });
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
        } catch (err) {
          router
            .replace({
              ...route,
              query: { queryString: undefined },
            })
            .catch(() => {});
        }
        if (queryStringObj) {
          const ids = Object.keys(backDisplayMap.value);
          const searchValues_ = [];
          queryStringObj?.forEach(item => {
            if (ids.includes(item.key)) {
              if (item.value?.length)
                searchValues_.push({
                  id: item.key,
                  multiple: true,
                  name: backDisplayMap.value[item.key].name,
                  values: Array.isArray(item.value) ? item.value.map(item => ({ id: item, name: item })) : [item.value],
                });
            } else {
              if (item.key) searchValues_.push({ id: item.key, name: item.key });
            }
          });
          searchValues.value = searchValues_;
          searchCondition = routerParamsReplace();
        }
      }
    }
    /**
     * @description 屏蔽状态切换
     * @param item
     */
    function handleStatusChange(item) {
      if (tableData.loading) {
        return;
      }
      if (shieldStatus.value !== item.id) {
        shieldStatus.value = item.id;
        tableData.pagination.current = 1;
        settings.fields = tableData.columns
          .filter(item => {
            if (shieldStatus.value === 0) {
              return ![EColumn.failureTime, EColumn.status].includes(item.id);
            }
            return ![EColumn.cycleDuration].includes(item.id);
          })
          .map(item => ({
            label: item.name,
            field: item.id,
            disabled: item.disabled,
          }));
        settings.checked = settings.fields.map(item => item.field);
        tableData.sort = {
          field: '',
          order: '',
        };
        handleGetShieldList();
      }
    }
    /**
     * @description 获取屏蔽列表
     */
    async function handleGetShieldList() {
      tableData.loading = true;
      // tableData.data = [];

      let categories = tableData.filter[EColumn.shieldType];
      if (!categories?.length) {
        categories = tableData.columns.find(item => item.id === EColumn.shieldType).filter.map(item => item.value);
      }

      const params = {
        page: tableData.pagination.current,
        page_size: tableData.pagination.limit,
        time_range: (() => {
          if (dateRange.value?.every(item => !!item)) {
            return dateRange.value.join('--');
          }
          return undefined;
        })(),
        categories,
        search: '',
        order: (() => {
          if (tableData.sort.order) {
            if (tableData.sort.order === 'asc') {
              return (tableData.sort as any).field;
            }
            return `-${(tableData.sort as any).field}`;
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
      tableData.data = [...data.shield_list];
      tableData.pagination.count = data.count;
      tableData.loading = false;
    }
    /**
     * @description 条件搜索
     * @param v
     */
    function handleSearchCondition(v) {
      searchValues.value = v;
      tableData.pagination.current = 1;
      searchCondition = routerParamsReplace();
      emptyType.value = searchCondition.length ? 'search-empty' : 'empty';
      handleGetShieldList();
    }
    function routerParamsReplace() {
      const query = [];
      const ids = Object.keys(backDisplayMap.value);
      searchValues.value.forEach(item => {
        if (ids.includes(item.id)) {
          if (item.values?.length) query.push({ key: item.id, value: item.values.map(v => v.id) });
        } else {
          if (item.id) query.push({ key: 'query', value: item.id });
        }
      });
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
    function handleSortChange({ field, order }) {
      const sort = {
        field: '',
        order: '',
      };
      if (order !== null) {
        sort.field = field;
        sort.order = order;
      } else {
        sort.field = field;
      }
      tableData.sort = sort;
      tableData.pagination.current = 1;
      handleGetShieldList();
    }
    /**
     * @description 当前筛选
     * @param opt
     */
    function handleFilterChange(opt) {
      const columns = tableData.columns.find(item => item.id === opt.field);
      columns.filter = columns.filter.map(item => ({
        ...item,
        checked: opt.values.includes(item.value),
      }));
      tableData.filter[opt.field] = opt.values;
      tableData.pagination.current = 1;
      handleGetShieldList();
    }
    /**
     * @description 当前页切换
     * @param page
     */
    function handlePageChange(page: number) {
      if (tableData.pagination.current !== page) {
        tableData.pagination.current = page;
        handleGetShieldList();
      }
    }
    /**
     * @description limit切换
     * @param limit
     */
    function handleLimitChange(limit: number) {
      tableData.pagination.current = 1;
      tableData.pagination.limit = limit;
      commonPageSizeSet(limit);
      handleGetShieldList();
    }

    function handleDatePick() {
      emptyType.value = 'search-empty';
      tableData.pagination.current = 1;
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

    function handleSettingChange(opt) {
      console.log(opt);
      // settings.checked = opt.checked;
      // settings.size = opt.size;
    }
    /**
     * @description 清空时间范围
     */
    function handleDatePickClear() {
      setTimeout(() => {
        tableData.pagination.current = 1;
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
        case EColumn.shieldType: {
          return <span>{row.category_name}</span>;
        }
        case EColumn.shieldContent: {
          return <span>{row.content}</span>;
        }
        case EColumn.beginTime: {
          return <span>{row.begin_time}</span>;
        }
        case EColumn.failureTime: {
          return <span>{row.failure_time}</span>;
        }
        case EColumn.cycleDuration: {
          return <span>{row.cycle_duration}</span>;
        }
        case EColumn.description: {
          return <span>{row.description || '--'}</span>;
        }
        case EColumn.status: {
          return <span class={statusMap[row.status].className}>{statusMap[row.status].des}</span>;
        }
        case EColumn.updateUser: {
          return <span>{row.update_user || '--'}</span>;
        }
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
      tableData,
      settings,
      authorityStore,
      authority,
      handleAdd,
      shieldStatusList,
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
      handleSettingChange,
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
            {!this.tableData.loading ? (
              <Table
                class='shield-table'
                v-slots={{
                  empty: () => (
                    <EmptyStatus
                      type={this.emptyType}
                      onOperation={this.handleEmptyOperation}
                    />
                  ),
                }}
                data={this.tableData.data}
                pagination={false}
                settings={this.settings}
                show-overflow='tooltip'
                showSettings={true}
                sort-config={{ remote: true, defaultSort: this.tableData.sort, trigger: 'cell' }}
                onFilterChange={this.handleFilterChange}
                onSettingChange={this.handleSettingChange}
                onSortChange={this.handleSortChange}
              >
                {this.tableData.columns
                  .filter(item => {
                    if (this.shieldStatus === 0) {
                      return (
                        ![EColumn.failureTime, EColumn.status].includes(item.id) &&
                        this.settings.checked.includes(item.id)
                      );
                    }
                    return ![EColumn.cycleDuration].includes(item.id) && this.settings.checked.includes(item.id);
                  })
                  .map(item => (
                    <TableColumn
                      key={item.id}
                      v-slots={{
                        default: ({ row }) => this.handleSetFormat(row, item.id),
                      }}
                      field={item.id}
                      filterMultiple={item.filterMultiple}
                      filters={item.filter}
                      minWidth={item.width}
                      sortable={item.sortable}
                      title={item.name}
                    ></TableColumn>
                  ))}
              </Table>
            ) : (
              <TableSkeleton />
            )}

            {!!this.tableData.data.length && (
              <Pagination
                class='mt-14'
                align={'right'}
                count={this.tableData.pagination.count}
                layout={['total', 'limit', 'list']}
                limit={this.tableData.pagination.limit}
                location={'right'}
                modelValue={this.tableData.pagination.current}
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
