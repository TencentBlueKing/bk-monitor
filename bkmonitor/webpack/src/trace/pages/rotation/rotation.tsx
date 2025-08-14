/* eslint-disable vue/multi-word-component-names */
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
import { defineComponent, provide, reactive, shallowRef } from 'vue';
import { shallowReactive } from 'vue';

import { type FilterValue, type SortInfo, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { Button, InfoBox, Message, Pagination, Popover, SearchSelect, Switcher, Tag } from 'bkui-vue';
import { destroyDutyRule, listDutyRule, switchDutyRule } from 'monitor-api/modules/model';
import { commonPageSizeGet, commonPageSizeSet } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';

import EmptyStatus from '../../components/empty-status/empty-status';
import TableSkeleton from '../../components/skeleton/table-skeleton';
import { useAppStore } from '../../store/modules/app';
import { getAuthorityMap, useAuthorityStore } from '../../store/modules/authority';
import * as authMap from './authority-map';
import RotationDetail from './rotation-detail';
import { EStatus, getEffectiveStatus, statusMap } from './typings/common';

import type { IAuthority } from '../../typings/authority';

import './rotation.scss';

enum ECategory {
  handoff = 'handoff',
  regular = 'regular',
}

enum EColumn {
  enabled = 'enabled',
  label = 'label_',
  name = 'name',
  operate = 'operate',
  relation = 'relation',
  scope = 'scope',
  status = 'status',
  type = 'type',
}

function getTimeStr(time: string) {
  if (time === 'null' || !time) {
    return window.i18n.t('永久');
  }
  const date = new Date(time);
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()} ${
    date.getHours() < 10 ? `${0}${date.getHours()}` : date.getHours()
  }:${date.getMinutes() < 10 ? `${0}${date.getMinutes()}` : date.getMinutes()}:${
    date.getSeconds() < 10 ? `${0}${date.getSeconds()}` : date.getSeconds()
  }`;
}

export default defineComponent({
  name: 'Rotation',
  setup() {
    const { t } = useI18n();
    const router = useRouter();
    const appStore = useAppStore();
    const authorityStore = useAuthorityStore();
    const authority = reactive<IAuthority>({
      map: authMap,
      auth: {},
      showDetail: authorityStore.getAuthorityDetail,
    });
    const tableColumns = shallowRef([
      {
        field: EColumn.name,
        title: t('规则名称'),
        minWidth: 160,
        disabled: true,
        checked: true,
      },
      {
        field: EColumn.type,
        title: t('轮值类型'),
        disabled: false,
        checked: true,
        filters: [
          {
            label: t('日常值班'),
            value: ECategory.regular,
            checked: false,
          },
          {
            label: t('交替轮值'),
            value: ECategory.handoff,
            checked: false,
          },
        ],
      },
      {
        field: EColumn.label,
        title: t('标签'),
        disabled: false,
        checked: true,
        filters: [],
      },
      {
        field: EColumn.relation,
        title: t('关联告警组'),
        width: 134,
        disabled: false,
        checked: true,
        sortable: true,
      },
      {
        field: EColumn.status,
        title: t('状态'),
        width: 176,
        disabled: false,
        checked: true,
        filters: [
          { label: statusMap[EStatus.Effective], value: EStatus.Effective, checked: false },
          { label: statusMap[EStatus.WaitEffective], value: EStatus.WaitEffective, checked: false },
          { label: statusMap[EStatus.NoEffective], value: EStatus.NoEffective, checked: false },
          { label: statusMap[EStatus.Deactivated], value: EStatus.Deactivated, checked: false },
        ],
      },
      {
        field: EColumn.scope,
        title: t('生效时间范围'),
        minWidth: 330,
        disabled: false,
        checked: true,
        sortable: true,
      },
      {
        field: EColumn.enabled,
        title: t('启/停'),
        width: 100,
        disabled: true,
        checked: true,
      },
      {
        field: EColumn.operate,
        title: t('操作'),
        disabled: true,
        checked: true,
      },
    ]);
    const tableData = shallowRef([]);
    const tablePagination = shallowReactive({
      current: 1,
      count: 0,
      limit: 10,
    });
    const tableSort = shallowRef<SortInfo>({
      sortBy: '',
      descending: false,
    });
    const tableFilters = shallowRef<FilterValue>({});
    const searchData = reactive({
      data: [
        {
          name: 'ID',
          id: 'id',
        },
        {
          name: t('规则名称'),
          id: 'name',
        },
      ],
      value: [],
    });
    const detailData = reactive({
      show: false,
      id: '',
    });
    /* 轮值列表全量数据 */
    const allRotationList = shallowRef([]);
    const loading = shallowRef(false);

    provide('authority', authority);

    /**
     * @description 跳转到新增页
     */
    init();
    async function init() {
      loading.value = true;
      const pageSize = commonPageSizeGet();
      tablePagination.limit = pageSize;
      authority.auth = await getAuthorityMap(authMap);
      const list = await listDutyRule().catch(() => []);
      const labelsSet = new Set();
      const filterLabelOptions = [];
      allRotationList.value = list.map(item => {
        for (const l of item.labels) {
          if (!labelsSet.has(l)) {
            labelsSet.add(l);
            filterLabelOptions.push({
              label: l,
              value: l,
              checked: false,
            });
          }
        }
        return {
          ...item,
          status: getEffectiveStatus([item.effective_time, item.end_time], item.enabled),
        };
      });
      const tableColumnsCopy = tableColumns.value.slice();
      for (const item of tableColumnsCopy) {
        if (item.field === EColumn.label) {
          item.filters = filterLabelOptions;
          break;
        }
      }
      tableColumns.value = tableColumnsCopy;
      tablePagination.count = allRotationList.value.length;
      setFilterList();
      loading.value = false;
    }
    /**
     * @description 排序、筛选、分页、搜索
     */
    function setFilterList() {
      const targetAllRotationList = JSON.parse(JSON.stringify(allRotationList.value));
      /* 搜索 */
      let needSearch = false;
      const condition = {
        id: [],
        name: [],
        query: [],
      };
      if (searchData.value.length) {
        needSearch = true;
        for (const item of searchData.value) {
          if (item.type === 'text') {
            condition.query.push(item.id);
          } else if (item.values?.length) {
            if (item.id === 'id') {
              condition.id.push(...item.values.map(v => v.id));
            }
            if (item.id === 'name') {
              condition.name.push(...item.values.map(v => v.id));
            }
          }
        }
      }
      /* 筛选 */
      const filterParams = {
        category: [],
        labels: [],
        status: [],
      };
      for (const [key, val] of Object.entries(tableFilters.value)) {
        if (key === EColumn.type) {
          filterParams.category = val;
        } else if (key === EColumn.label) {
          filterParams.labels = val;
        } else if (key === EColumn.status) {
          filterParams.status = val;
        }
      }
      const filterAllRotationList = targetAllRotationList.filter(item => {
        let need = true;
        if (filterParams.category.length) {
          need = need && filterParams.category.indexOf(item.category) >= 0;
        }
        if (filterParams.labels.length) {
          need = need && filterParams.labels.some(l => item.labels.indexOf(l) >= 0);
        }
        if (filterParams.status.length) {
          need = need && filterParams.status.some(l => item.status === l);
        }
        /* 是否包含条件搜索 */
        if (needSearch) {
          if (condition.id.length) {
            need = need && condition.id.some(str => String(item.id) === str);
          }
          if (condition.name.length) {
            need = need && condition.name.some(str => item.name === str);
          }
          if (condition.query.length) {
            need = need && condition.query.some(str => item.name.indexOf(str) >= 0);
          }
        }
        return need;
      });
      /* 排序 */
      if (tableSort.value.sortBy) {
        if (tableSort.value.sortBy === EColumn.relation) {
          filterAllRotationList.sort((a, b) =>
            !tableSort.value.descending
              ? a.user_groups_count - b.user_groups_count
              : b.user_groups_count - a.user_groups_count
          );
        } else if (tableSort.value.sortBy === EColumn.scope) {
          filterAllRotationList.sort((a, b) =>
            !tableSort.value.descending
              ? new Date(a.effective_time).getTime() - new Date(b.effective_time).getTime()
              : new Date(b.effective_time).getTime() - new Date(a.effective_time).getTime()
          );
        }
      }
      /* 分页 */
      tablePagination.count = filterAllRotationList.length;
      const list = filterAllRotationList.slice(
        (tablePagination.current - 1) * tablePagination.limit,
        tablePagination.current * tablePagination.limit
      );
      tableData.value = list;
    }
    function handleAdd() {
      router.push({
        name: 'rotation-add',
      });
    }
    /**
     * @description 启停
     * @param value
     * @returns
     */
    function handleEnableBeforeChange(value, row) {
      return new Promise((resolve, reject) => {
        InfoBox({
          title: value ? t('确认启用') : t('确认停用'),
          subTitle: `${t('规则名称')}: ${row.name}`,
          onConfirm: () => {
            switchDutyRule({
              ids: [row.id],
              enabled: value,
            })
              .then(() => {
                resolve(value);
                listDutyRule()
                  .then(list => {
                    const labelsSet = new Set();
                    const filterLabelOptions = [];
                    allRotationList.value = list.map(item => {
                      for (const l of item.labels) {
                        if (!labelsSet.has(l)) {
                          labelsSet.add(l);
                          filterLabelOptions.push({
                            text: l,
                            value: l,
                          });
                        }
                      }
                      if (item.id === row.id) {
                        const cur = tableData.value.find(t => t.id === row.id);
                        if (cur) {
                          cur.status = getEffectiveStatus([item.effective_time, item.end_time], item.enabled);
                        }
                      }
                      return {
                        ...item,
                        status: getEffectiveStatus([item.effective_time, item.end_time], item.enabled),
                      };
                    });
                  })
                  .catch(() => []);
              })
              .catch(() => {
                reject();
              });
          },
        });
      });
    }

    /**
     * @description 排序
     * @param _opt
     */
    function handleColumnSort(opt: TableSort) {
      tableSort.value = opt
        ? (opt as SortInfo)
        : {
            sortBy: '',
            descending: false,
          };
      tablePagination.current = 1;
      setFilterList();
    }
    /**
     * @description 筛选
     * @param _opt
     */
    function handleColumnFilter(value: FilterValue) {
      tableFilters.value = value;
      tablePagination.current = 1;
      setFilterList();
    }
    /**
     * @description 表格设置
     * @param opt
     */
    function handleSettingChange() {}
    /**
     * @description 分页
     * @param page
     */
    function handlePageChange(page: number) {
      if (tablePagination.current !== page) {
        tablePagination.current = page;
        setFilterList();
      }
    }
    /**
     * @description 分页
     * @param limit
     */
    function handleLimitChange(limit: number) {
      tablePagination.current = 1;
      tablePagination.limit = limit;
      commonPageSizeSet(limit);
      setFilterList();
    }

    function handleShowDetail(row) {
      detailData.id = row.id;
      detailData.show = true;
    }

    function handleSearch(v) {
      searchData.value = v;
      tablePagination.current = 1;
      setFilterList();
    }

    function handleEdit(row) {
      router.push({
        name: 'rotation-edit',
        params: {
          id: row.id,
        },
      });
    }

    function handleDelete(row) {
      InfoBox({
        title: t('确认删除'),
        subTitle: `${t('规则名称')}: ${row.name}`,
        onConfirm: () => {
          const delIndex = allRotationList.value.findIndex(item => item.id === row.id);
          if (delIndex >= 0) {
            loading.value = true;
            setTimeout(() => {
              destroyDutyRule(row.id)
                .then(() => {
                  allRotationList.value.splice(delIndex, 1);
                  tablePagination.current = 1;
                  setFilterList();
                  loading.value = false;
                  Message({
                    theme: 'success',
                    message: t('删除成功'),
                  });
                })
                .catch(() => {
                  Message({
                    theme: 'danger',
                    message: t('删除失败'),
                  });
                });
            }, 2000);
          }
        },
      });
    }

    function handleToAlarmGroup(item) {
      const url = `${location.origin}${location.pathname}?bizId=${appStore.bizId}#/alarm-group?dutyRule=${item.name}`;
      window.open(url);
    }

    function handleClearSearch() {
      handleSearch([]);
    }

    function handleSetFormatter(row, column: EColumn) {
      switch (column) {
        case EColumn.name: {
          return (
            <span
              class='rotation-name'
              onClick={() => handleShowDetail(row)}
            >
              {/* <Button
            text
            theme='primary'
            onClick={() => handleShowDetail(row)}
          >
            {row.name}
          </Button> */}
              {row.name}
            </span>
          );
        }
        case EColumn.type: {
          return <span>{row.category === ECategory.regular ? t('日常值班') : t('交替轮值')}</span>;
        }
        case EColumn.label: {
          return row.labels.length ? row.labels.map((label, index) => <Tag key={index}>{label}</Tag>) : '--';
        }
        case EColumn.relation: {
          return row.user_groups_count ? (
            <Button
              theme='primary'
              text
              onClick={() => handleToAlarmGroup(row)}
            >
              {row.user_groups_count}
            </Button>
          ) : (
            '--'
          );
        }
        case EColumn.status: {
          const statusClass = {
            [EStatus.Deactivated]: 'status-red',
            [EStatus.Effective]: 'status-green',
            [EStatus.WaitEffective]: 'status-yellow',
            [EStatus.NoEffective]: 'status-grey',
          };
          return (
            <span class={['status-label', statusClass[row.status]]}>
              <div class='point'>
                <div class='small-point' />
              </div>
              <span class='ml-7'>{statusMap[row.status]}</span>
            </span>
          );
        }
        case EColumn.scope: {
          return <span>{`${getTimeStr(row.effective_time)} - ${getTimeStr(row.end_time)}`}</span>;
        }
        case EColumn.enabled: {
          return (
            <Popover
              arrow={true}
              disabled={row.enabled ? row.delete_allowed : true}
              placement='top'
              popoverDelay={[300, 0]}
              trigger={'hover'}
            >
              {{
                default: () => (
                  <Switcher
                    beforeChange={v => handleEnableBeforeChange(v, row)}
                    disabled={!row.delete_allowed && row.enabled}
                    size='small'
                    theme='primary'
                    value={row.enabled}
                    onChange={v => (row.enabled = v)}
                  />
                ),
                content: () => <span>{t('存在关联的告警组')}</span>,
              }}
            </Popover>
          );
        }
        case EColumn.operate: {
          return (
            <span>
              <Popover
                arrow={true}
                disabled={row.edit_allowed}
                placement='top'
                popoverDelay={[300, 0]}
                trigger={'hover'}
              >
                {{
                  default: () => (
                    <Button
                      class='mr-8'
                      v-authority={{ active: !authority.auth.MANAGE_AUTH }}
                      disabled={!row.edit_allowed}
                      theme='primary'
                      text
                      onClick={() =>
                        authority.auth.MANAGE_AUTH ? handleEdit(row) : authority.showDetail([authority.map.MANAGE_AUTH])
                      }
                    >
                      {t('编辑')}
                    </Button>
                  ),
                  content: () => <span>{t('当前为全局的')}</span>,
                }}
              </Popover>
              <Popover
                arrow={true}
                disabled={row.delete_allowed}
                placement='top'
                popoverDelay={[300, 0]}
                trigger={'hover'}
              >
                {{
                  default: () => (
                    <Button
                      v-authority={{ active: !authority.auth.MANAGE_AUTH }}
                      disabled={!row.delete_allowed}
                      theme='primary'
                      text
                      onClick={() =>
                        authority.auth.MANAGE_AUTH
                          ? handleDelete(row)
                          : authority.showDetail([authority.map.MANAGE_AUTH])
                      }
                    >
                      {t('删除')}
                    </Button>
                  ),
                  content: () => <span>{t('存在关联的告警组')}</span>,
                }}
              </Popover>
            </span>
          );
        }
        default: {
          return '--';
        }
      }
    }

    return {
      tableData,
      tableColumns,
      tablePagination,
      searchData,
      detailData,
      loading,
      allRotationList,
      t,
      handleAdd,
      handleSetFormatter,
      handleColumnSort,
      handleColumnFilter,
      handleSettingChange,
      handlePageChange,
      handleLimitChange,
      handleSearch,
      handleClearSearch,
    };
  },

  render() {
    return (
      <div class='rotation-page'>
        <div class='rotation-page-header'>
          <span>{this.t('轮值')}</span>
        </div>
        <div class='rotation-page-content-wrap'>
          <div class='rotation-page-content'>
            <div class='content-header'>
              <Button
                theme='primary'
                onClick={this.handleAdd}
              >
                <span class='icon-monitor icon-plus-line mr-6' />
                <span>{this.t('新建')}</span>
              </Button>
              <SearchSelect
                class='width-350'
                data={this.searchData.data}
                modelValue={this.searchData.value}
                placeholder={`ID / ${this.t('规则名称')}`}
                onUpdate:modelValue={v => this.handleSearch(v)}
              />
            </div>
            <div class='table-content'>
              {!this.loading ? (
                [
                  <PrimaryTable
                    key={'rotation-table'}
                    v-slots={{
                      empty: () => (
                        <EmptyStatus
                          scene='page'
                          type={this.searchData.value.length ? 'search-empty' : 'empty'}
                          onOperation={this.handleClearSearch}
                        />
                      ),
                    }}
                    bkUiSettings={{
                      checked: this.tableColumns.map(item => item.field),
                    }}
                    columns={this.tableColumns.map(column => ({
                      colKey: column.field,
                      cell: (_, { row }) => this.handleSetFormatter(row, column.field),
                      title: column.title,
                      ellipsis: {
                        popperOptions: {
                          strategy: 'fixed',
                        },
                        onVisibleChange(v, ctx) {
                          console.info(v, ctx);
                        },
                      },
                      filter: column.filters?.length
                        ? {
                            list: column.filters,
                            type: 'multiple',
                            showConfirmAndReset: true,
                            resetValue: [],
                          }
                        : undefined,
                      sorter: column.sortable,
                    }))}
                    pagination={{
                      total: this.tablePagination.count,
                    }}
                    data={this.tableData}
                    filterRow={undefined}
                    resizable={true}
                    rowKey='name'
                    showSortColumnBgColor={true}
                    onFilterChange={this.handleColumnFilter}
                    onSortChange={this.handleColumnSort}
                  />,
                  <Pagination
                    key={'rotation-pagination'}
                    class='mt-14'
                    align={'right'}
                    count={this.tablePagination.count}
                    layout={['total', 'limit', 'list']}
                    limit={this.tablePagination.limit}
                    location={'right'}
                    modelValue={this.tablePagination.current}
                    onChange={v => this.handlePageChange(v)}
                    onLimitChange={v => this.handleLimitChange(v)}
                  />,
                ]
              ) : (
                <TableSkeleton />
              )}
            </div>
          </div>
        </div>

        <RotationDetail
          id={this.detailData.id}
          show={this.detailData.show}
          onShowChange={v => (this.detailData.show = v)}
        />
      </div>
    );
  },
});
