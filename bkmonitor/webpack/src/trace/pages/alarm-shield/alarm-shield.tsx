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

import { Button, DatePicker, InfoBox, Message, Pagination, SearchSelect, Table } from 'bkui-vue';
import { disableShield, frontendShieldList } from 'monitor-api/modules/shield';
import { commonPageSizeGet, commonPageSizeSet } from 'monitor-common/utils';

import EmptyStatus, { type EmptyStatusType } from '../../components/empty-status/empty-status';
import TableSkeleton from '../../components/skeleton/table-skeleton';
import { getAuthorityMap, useAuthorityStore } from '../../store/modules/authority';
import AlarmShieldDetail from './alarm-shield-detail';
import * as authMap from './authority-map';

import type { IAuthority } from '../../typings/authority';

import './alarm-shield.scss';

enum EColunm {
  beginTime = 'begin_time',
  cycleDuration = 'cycleDuration',
  description = 'description',
  failureTime = 'failure_time',
  id = 'id',
  operate = 'operate',
  shieldContent = 'shieldContent',
  shieldType = 'shieldType',
  status = 'status',
  updateUser = 'update_user',
}
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
    const tableData = reactive({
      loading: false,
      data: [],
      columns: [
        {
          id: EColunm.id,
          name: 'ID',
          width: 100,
          disabled: true,
          checked: true,
          sort: {
            value: '',
          },
        },
        {
          id: EColunm.shieldType,
          name: t('分类'),
          width: 150,
          disabled: true,
          checked: true,
          filter: {
            filterFn: () => true,
            checked: [],
            list: [
              { text: t('告警事件屏蔽'), value: 'alert' },
              { text: t('范围屏蔽'), value: 'scope' },
              { text: t('策略屏蔽'), value: 'strategy' },
              { text: t('维度屏蔽'), value: 'dimension' },
            ],
          },
        },
        {
          id: EColunm.shieldContent,
          name: t('屏蔽内容'),
          width: 250,
          disabled: false,
          checked: true,
        },
        {
          id: EColunm.beginTime,
          name: t('开始时间'),
          width: 150,
          disabled: false,
          checked: true,
          sort: {
            value: '',
          },
        },
        {
          id: EColunm.failureTime,
          name: t('失效时间'),
          width: 150,
          disabled: false,
          checked: true,
          sort: {
            value: '',
          },
        },
        {
          id: EColunm.cycleDuration,
          name: t('持续周期及时长'),
          width: 150,
          disabled: false,
          checked: true,
        },
        {
          id: EColunm.description,
          name: t('屏蔽原因'),
          width: 230,
          disabled: false,
          checked: true,
        },
        {
          id: EColunm.status,
          name: t('状态'),
          width: 150,
          disabled: false,
          checked: true,
        },
        {
          id: EColunm.updateUser,
          name: t('更新人'),
          width: 150,
          disabled: false,
          checked: true,
        },
        {
          id: EColunm.operate,
          name: t('操作'),
          width: 150,
          disabled: true,
          checked: true,
        },
      ],
      pagination: {
        current: 1,
        count: 0,
        limit: 10,
      },
      filter: {
        shieldType: {
          checked: [],
        },
      },
      sort: {
        column: '',
        type: '',
      },
    });
    const settings = reactive({
      checked: tableData.columns.map(item => item.id),
      size: 'small',
      fields: tableData.columns
        .filter(item => {
          if (shieldStatus.value === 0) {
            return ![EColunm.failureTime, EColunm.status].includes(item.id);
          }
          return ![EColunm.cycleDuration].includes(item.id);
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
      await handleGetShiledList();
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
              return ![EColunm.failureTime, EColunm.status].includes(item.id);
            }
            return ![EColunm.cycleDuration].includes(item.id);
          })
          .map(item => ({
            label: item.name,
            field: item.id,
            disabled: item.disabled,
          }));
        settings.checked = settings.fields.map(item => item.field);
        tableData.sort = {
          column: '',
          type: '',
        };
        tableData.columns.forEach(item => {
          if (item?.sort) {
            item.sort.value = '';
          }
        });
        handleGetShiledList();
      }
    }
    /**
     * @description 获取屏蔽列表
     */
    async function handleGetShiledList() {
      tableData.loading = true;
      // tableData.data = [];
      const params = {
        page: tableData.pagination.current,
        page_size: tableData.pagination.limit,
        time_range: (() => {
          if (dateRange.value?.every(item => !!item)) {
            return dateRange.value.join('--');
          }
          return undefined;
        })(),
        categories: (() => {
          const filterItem: any = tableData.columns.find(item => item.id === EColunm.shieldType);
          const checked = filterItem.filter.checked || [];
          if (checked.length) {
            return checked;
          }
          return filterItem.filter.list.map(item => item.value);
        })(),
        search: '',
        order: (() => {
          if (tableData.sort.type) {
            if (tableData.sort.type === 'asc') {
              return (tableData.sort as any).column;
            }
            return `-${(tableData.sort as any).column}`;
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
      handleGetShiledList();
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
            handleGetShiledList();
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
    function handleColumnSort(opt) {
      const sort = {
        column: '',
        type: '',
      };
      if (opt.type !== 'null') {
        sort.column = opt.column.id;
        sort.type = opt.type;
      } else {
        sort.column = opt.column.id;
      }
      tableData.sort = sort;
      const tableColumn = tableData.columns.find(item => item.id === sort.column);
      tableData.columns.forEach(item => {
        if (item.id !== sort.column && !!item?.sort) {
          item.sort.value = '';
        }
      });
      if (tableColumn?.sort) {
        tableColumn.sort.value = sort.type || '';
      }
      tableData.pagination.current = 1;
      handleGetShiledList();
    }
    /**
     * @description 当前筛选
     * @param opt
     */
    function handleColumnFilter() {
      tableData.pagination.current = 1;
      handleGetShiledList();
    }
    /**
     * @description 当前页切换
     * @param page
     */
    function handlePageChange(page: number) {
      if (tableData.pagination.current !== page) {
        tableData.pagination.current = page;
        handleGetShiledList();
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
      handleGetShiledList();
    }

    function handleDatePick() {
      emptyType.value = 'search-empty';
      tableData.pagination.current = 1;
      handleGetShiledList();
    }
    /**
     * @description 空状态操作
     * @param type
     * @returns
     */
    function handleEmptyOperation(type) {
      if (type === 'refresh') {
        emptyType.value = 'empty';
        handleGetShiledList();
        return;
      }
      if (type === 'clear-filter') {
        searchValues.value = [];
        dateRange.value = [];
        searchCondition = routerParamsReplace();
        emptyType.value = searchCondition.length ? 'search-empty' : 'empty';
        handleGetShiledList();
        return;
      }
    }

    function handleSettingChange(opt) {
      settings.checked = opt.checked;
      settings.size = opt.size;
    }
    /**
     * @description 清空时间范围
     */
    function handleDatePickClear() {
      setTimeout(() => {
        tableData.pagination.current = 1;
        handleGetShiledList();
      }, 50);
    }

    function handleSetFormater(row, column) {
      switch (column) {
        case EColunm.id: {
          return (
            <Button
              theme='primary'
              text
              onClick={() => handleToDetail(row)}
            >{`#${row.id}`}</Button>
          );
        }
        case EColunm.shieldType: {
          return <span>{row.category_name}</span>;
        }
        case EColunm.shieldContent: {
          return <span>{row.content}</span>;
        }
        case EColunm.beginTime: {
          return <span>{row.begin_time}</span>;
        }
        case EColunm.failureTime: {
          return <span>{row.failure_time}</span>;
        }
        case EColunm.cycleDuration: {
          return <span>{row.cycle_duration}</span>;
        }
        case EColunm.description: {
          return <span>{row.description || '--'}</span>;
        }
        case EColunm.status: {
          return <span class={statusMap[row.status].className}>{statusMap[row.status].des}</span>;
        }
        case EColunm.updateUser: {
          return <span>{row.update_user || '--'}</span>;
        }
        case EColunm.operate: {
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
      handleSetFormater,
      handleColumnSort,
      handleColumnFilter,
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
                columns={this.tableData.columns
                  .filter(item => {
                    if (this.shieldStatus === 0) {
                      return (
                        ![EColunm.failureTime, EColunm.status].includes(item.id) &&
                        this.settings.checked.includes(item.id)
                      );
                    }
                    return ![EColunm.cycleDuration].includes(item.id) && this.settings.checked.includes(item.id);
                  })
                  .map(item => {
                    return {
                      ...item,
                      label: (col: any) => col.name,
                      render: ({ row }) => this.handleSetFormater(row, item.id),
                    };
                  })}
                darkHeader={true}
                data={this.tableData.data}
                pagination={false}
                settings={this.settings}
                showOverflowTooltip={true}
                onColumnFilter={this.handleColumnFilter}
                onColumnSort={this.handleColumnSort}
                onSettingChange={this.handleSettingChange}
              >
                {{
                  empty: () => (
                    <EmptyStatus
                      type={this.emptyType}
                      onOperation={this.handleEmptyOperation}
                    />
                  ),
                }}
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
