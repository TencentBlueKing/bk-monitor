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
import { defineComponent, provide, reactive, ref, shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { Button, InfoBox, Loading, Message, Pagination, Popover, SearchSelect, Switcher, Table, Tag } from 'bkui-vue';
import { destroyDutyRule, listDutyRule, switchDutyRule } from 'monitor-api/modules/model';

import { useAppStore } from '../../store/modules/app';
import { getAuthorityMap, useAuthorityStore } from '../../store/modules/authority';
import { IAuthority } from '../../typings/authority';

import { EStatus, getEffectiveStatus, statusMap } from './typings/common';
import * as authMap from './authority-map';
import RotationDetail from './rotation-detail';

import './rotation.scss';

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

enum Ecategory {
  regular = 'regular',
  handoff = 'handoff'
}

enum EColunm {
  name = 'name',
  type = 'type',
  label = 'label',
  relation = 'relation',
  status = 'status',
  scope = 'scope',
  enabled = 'enabled',
  operate = 'operate'
}

export default defineComponent({
  // eslint-disable-next-line vue/multi-word-component-names
  name: 'Rotation',
  setup() {
    const { t } = useI18n();
    const router = useRouter();
    const appStore = useAppStore();
    const authorityStore = useAuthorityStore();
    const authority = reactive<IAuthority>({
      map: authMap,
      auth: {},
      showDetail: authorityStore.getAuthorityDetail
    });
    const tableData = reactive({
      loading: false,
      data: [],
      pagination: {
        current: 1,
        count: 0,
        limit: 10
      },
      sort: {
        column: '',
        type: ''
      },
      columns: [
        {
          id: EColunm.name,
          name: t('规则名称'),
          minWidth: 160,
          disabled: true,
          checked: true
        },
        {
          id: EColunm.type,
          name: t('轮值类型'),
          disabled: false,
          checked: true,
          filter: {
            filterFn: () => true,
            checked: [],
            list: [
              {
                text: t('日常值班'),
                value: Ecategory.regular
              },
              {
                text: t('交替轮值'),
                value: Ecategory.handoff
              }
            ]
          }
        },
        {
          id: EColunm.label,
          name: t('标签'),
          disabled: false,
          checked: true,
          filter: {
            filterFn: () => true,
            checked: [],
            list: []
          }
        },
        {
          id: EColunm.relation,
          name: t('关联告警组'),
          width: 134,
          disabled: false,
          checked: true,
          sort: {
            value: ''
          }
        },
        {
          id: EColunm.status,
          name: t('状态'),
          width: 176,
          disabled: false,
          checked: true,
          filter: {
            filterFn: () => true,
            checked: [],
            list: [
              { text: statusMap[EStatus.Effective], value: EStatus.Effective },
              { text: statusMap[EStatus.WaitEffective], value: EStatus.WaitEffective },
              { text: statusMap[EStatus.NoEffective], value: EStatus.NoEffective },
              { text: statusMap[EStatus.Deactivated], value: EStatus.Deactivated }
            ]
          }
        },
        {
          id: EColunm.scope,
          name: t('生效时间范围'),
          minWidth: 330,
          disabled: false,
          checked: true,
          sort: {
            value: ''
          }
        },
        {
          id: EColunm.enabled,
          name: t('启/停'),
          width: 100,
          disabled: true,
          checked: true
        },
        {
          id: EColunm.operate,
          name: t('操作'),
          disabled: true,
          checked: true
        }
      ]
    });
    /* 表格设置 */
    const settings = reactive({
      checked: tableData.columns.map(item => item.id),
      size: 'small',
      fields: tableData.columns.map(item => ({
        label: item.name,
        field: item.id,
        disabled: item.disabled
      }))
    });
    const searchData = reactive({
      data: [
        {
          name: 'ID',
          id: 'id'
        },
        {
          name: t('规则名称'),
          id: 'name'
        }
      ],
      value: []
    });
    const detailData = reactive({
      show: false,
      id: ''
    });
    /* 轮值列表全量数据 */
    const allRotationList = shallowRef([]);
    const loading = ref(false);

    provide('authority', authority);

    /**
     * @description 跳转到新增页
     */
    init();
    async function init() {
      loading.value = true;
      authority.auth = await getAuthorityMap(authMap);
      const list = await listDutyRule().catch(() => []);
      const labelsSet = new Set();
      const filterLabelOptions = [];
      allRotationList.value = list.map(item => {
        item.labels.forEach(l => {
          if (!labelsSet.has(l)) {
            labelsSet.add(l);
            filterLabelOptions.push({
              text: l,
              value: l
            });
          }
        });
        return {
          ...item,
          status: getEffectiveStatus([item.effective_time, item.end_time], item.enabled)
        };
      });
      (tableData.columns.find(item => item.id === EColunm.label).filter as any).list = filterLabelOptions;
      tableData.pagination.count = allRotationList.value.length;
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
        query: []
      };
      if (searchData.value.length) {
        needSearch = true;
        searchData.value.forEach(item => {
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
        });
      }
      /* 筛选 */
      const filterParams = {
        category: [],
        labels: [],
        status: []
      };
      tableData.columns.forEach(item => {
        if (item.id === EColunm.type) {
          filterParams.category = JSON.parse(JSON.stringify((item.filter as any).checked));
        }
        if (item.id === EColunm.label) {
          filterParams.labels = JSON.parse(JSON.stringify((item.filter as any).checked));
        }
        if (item.id === EColunm.status) {
          filterParams.status = JSON.parse(JSON.stringify((item.filter as any).checked));
        }
      });
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
      if (!!tableData.sort.column) {
        if (tableData.sort.column === EColunm.relation) {
          filterAllRotationList.sort((a, b) =>
            tableData.sort.type === 'asc'
              ? a.user_groups_count - b.user_groups_count
              : b.user_groups_count - a.user_groups_count
          );
        }
        if (tableData.sort.column === EColunm.scope) {
          filterAllRotationList.sort((a, b) =>
            tableData.sort.type === 'asc'
              ? new Date(a.effective_time).getTime() - new Date(b.effective_time).getTime()
              : new Date(b.effective_time).getTime() - new Date(a.effective_time).getTime()
          );
        }
      }
      /* 分页 */
      tableData.pagination.count = filterAllRotationList.length;
      const list = filterAllRotationList.slice(
        (tableData.pagination.current - 1) * tableData.pagination.limit,
        tableData.pagination.current * tableData.pagination.limit
      );
      tableData.data = list;
    }
    function handleAdd() {
      router.push({
        name: 'rotation-add'
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
              enabled: value
            })
              .then(() => {
                resolve(value);
                listDutyRule()
                  .then(list => {
                    const labelsSet = new Set();
                    const filterLabelOptions = [];
                    allRotationList.value = list.map(item => {
                      item.labels.forEach(l => {
                        if (!labelsSet.has(l)) {
                          labelsSet.add(l);
                          filterLabelOptions.push({
                            text: l,
                            value: l
                          });
                        }
                      });
                      if (item.id === row.id) {
                        const cur = tableData.data.find(t => t.id === row.id);
                        if (cur) {
                          cur.status = getEffectiveStatus([item.effective_time, item.end_time], item.enabled);
                        }
                      }
                      return {
                        ...item,
                        status: getEffectiveStatus([item.effective_time, item.end_time], item.enabled)
                      };
                    });
                  })
                  .catch(() => []);
              })
              .catch(() => {
                reject();
              });
          },
          onClosed: () => {
            reject();
          }
        });
      });
    }

    /**
     * @description 排序
     * @param _opt
     */
    function handleColumnSort(opt) {
      const sort = {
        column: '',
        type: ''
      };
      if (opt.type !== 'null') {
        sort.column = opt.column.id;
        sort.type = opt.type;
      }
      tableData.sort = sort;
      const tableColumn = tableData.columns.find(item => item.id === sort.column);
      if (tableColumn?.sort) {
        tableColumn.sort.value = sort.type || 'null';
      }

      tableData.pagination.current = 1;
      setFilterList();
    }
    /**
     * @description 筛选
     * @param _opt
     */
    function handleColumnFilter(_opt) {
      tableData.pagination.current = 1;
      setFilterList();
    }
    /**
     * @description 表格设置
     * @param opt
     */
    function handleSettingChange(opt) {
      settings.checked = opt.checked;
      settings.size = opt.size;
    }
    /**
     * @description 分页
     * @param page
     */
    function handlePageChange(page: number) {
      if (tableData.pagination.current !== page) {
        tableData.pagination.current = page;
        setFilterList();
      }
    }
    /**
     * @description 分页
     * @param limit
     */
    function handleLimitChange(limit: number) {
      tableData.pagination.current = 1;
      tableData.pagination.limit = limit;
      setFilterList();
    }

    function handleShowDetail(row) {
      detailData.id = row.id;
      detailData.show = true;
    }

    function handleSearch(v) {
      searchData.value = v;
      tableData.pagination.current = 1;
      setFilterList();
    }

    function handleEdit(row) {
      router.push({
        name: 'rotation-edit',
        params: {
          id: row.id
        }
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
                  tableData.pagination.current = 1;
                  setFilterList();
                  loading.value = false;
                  Message({
                    theme: 'success',
                    message: t('删除成功')
                  });
                })
                .catch(() => {
                  Message({
                    theme: 'danger',
                    message: t('删除失败')
                  });
                });
            }, 2000);
          }
        },
        onClosed: () => {
          //
        }
      });
    }

    function handleToAlarmGroup(item) {
      const url = `${location.origin}${location.pathname}?bizId=${appStore.bizId}#/alarm-group?dutyRule=${item.name}`;
      window.open(url);
    }

    function handleSetFormater(row, column: EColunm) {
      switch (column) {
        case EColunm.name: {
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
        case EColunm.type: {
          return <span>{row.category === Ecategory.regular ? t('日常值班') : t('交替轮值')}</span>;
        }
        case EColunm.label: {
          return row.labels.map(label => <Tag>{label}</Tag>);
        }
        case EColunm.relation: {
          return !!row.user_groups_count ? (
            <Button
              text
              theme='primary'
              onClick={() => handleToAlarmGroup(row)}
            >
              {row.user_groups_count}
            </Button>
          ) : (
            '--'
          );
        }
        case EColunm.status: {
          const statusClass = {
            [EStatus.Deactivated]: 'status-red',
            [EStatus.Effective]: 'status-green',
            [EStatus.WaitEffective]: 'status-yellow',
            [EStatus.NoEffective]: 'status-grey'
          };
          return (
            <span class={['status-label', statusClass[row.status]]}>
              <div class='point'>
                <div class='small-point'></div>
              </div>
              <span class='ml-7'>{statusMap[row.status]}</span>
            </span>
          );
        }
        case EColunm.scope: {
          return <span>{`${getTimeStr(row.effective_time)} - ${getTimeStr(row.end_time)}`}</span>;
        }
        case EColunm.enabled: {
          return (
            <Popover
              placement='top'
              arrow={true}
              trigger={'hover'}
              popoverDelay={[300, 0]}
              disabled={row.enabled ? row.delete_allowed : true}
            >
              {{
                default: () => (
                  <Switcher
                    size='small'
                    theme='primary'
                    value={row.enabled}
                    disabled={!row.delete_allowed && row.enabled}
                    beforeChange={v => handleEnableBeforeChange(v, row)}
                    onChange={v => (row.enabled = v)}
                  ></Switcher>
                ),
                content: () => <span>{t('存在关联的告警组')}</span>
              }}
            </Popover>
          );
        }
        case EColunm.operate: {
          return (
            <span>
              <Popover
                placement='top'
                arrow={true}
                trigger={'hover'}
                popoverDelay={[300, 0]}
                disabled={row.edit_allowed}
              >
                {{
                  default: () => (
                    <Button
                      text
                      theme='primary'
                      class='mr-8'
                      disabled={!row.edit_allowed}
                      onClick={() =>
                        authority.auth.MANAGE_AUTH ? handleEdit(row) : authority.showDetail([authority.map.MANAGE_AUTH])
                      }
                      v-authority={{ active: !authority.auth.MANAGE_AUTH }}
                    >
                      {t('编辑')}
                    </Button>
                  ),
                  content: () => <span>{t('当前为全局的')}</span>
                }}
              </Popover>
              <Popover
                placement='top'
                arrow={true}
                trigger={'hover'}
                popoverDelay={[300, 0]}
                disabled={row.delete_allowed}
              >
                {{
                  default: () => (
                    <Button
                      text
                      theme='primary'
                      disabled={!row.delete_allowed}
                      onClick={() =>
                        authority.auth.MANAGE_AUTH
                          ? handleDelete(row)
                          : authority.showDetail([authority.map.MANAGE_AUTH])
                      }
                      v-authority={{ active: !authority.auth.MANAGE_AUTH }}
                    >
                      {t('删除')}
                    </Button>
                  ),
                  content: () => <span>{t('存在关联的告警组')}</span>
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
      settings,
      searchData,
      detailData,
      loading,
      allRotationList,
      t,
      handleAdd,
      handleSetFormater,
      handleColumnSort,
      handleColumnFilter,
      handleSettingChange,
      handlePageChange,
      handleLimitChange,
      handleSearch
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
                <span class='icon-monitor icon-plus-line mr-6'></span>
                <span>{this.t('新建')}</span>
              </Button>
              <SearchSelect
                class='width-350'
                placeholder={`ID / ${this.t('规则名称')}`}
                modelValue={this.searchData.value}
                data={this.searchData.data}
                onUpdate:modelValue={v => this.handleSearch(v)}
              ></SearchSelect>
            </div>
            <Loading loading={this.loading}>
              <div class='table-content'>
                <Table
                  data={this.tableData.data}
                  settings={this.settings}
                  showOverflowTooltip={true}
                  darkHeader={true}
                  pagination={false}
                  onColumnSort={this.handleColumnSort}
                  onColumnFilter={this.handleColumnFilter}
                  onSettingChange={this.handleSettingChange}
                  columns={this.tableData.columns
                    .filter(item => this.settings.checked.includes(item.id))
                    .map(item => {
                      return {
                        ...item,
                        label: (col: any) => col.name,
                        render: ({ row, _column }) => this.handleSetFormater(row, item.id)
                      };
                    })}
                ></Table>
                <Pagination
                  class='mt-14'
                  modelValue={this.tableData.pagination.current}
                  count={this.tableData.pagination.count}
                  limit={this.tableData.pagination.limit}
                  location={'right'}
                  align={'right'}
                  layout={['total', 'limit', 'list']}
                  onChange={v => this.handlePageChange(v)}
                  onLimitChange={v => this.handleLimitChange(v)}
                ></Pagination>
              </div>
            </Loading>
          </div>
        </div>

        <RotationDetail
          show={this.detailData.show}
          id={this.detailData.id}
          onShowChange={v => (this.detailData.show = v)}
        ></RotationDetail>
      </div>
    );
  }
});
