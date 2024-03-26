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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { listSpaces, listStickySpaces, stickSpace } from 'monitor-api/modules/commons';
import { getAuthorityDetail } from 'monitor-api/modules/iam';
import { Debounce, mergeSpaceList, random } from 'monitor-common/utils';
import bus from 'monitor-common/utils/event-bus';

import { SPACE_TYPE_MAP } from '../../common/constant';
import { ETagsType } from '../../components/biz-select/list';
import EmptyStatus from '../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../components/empty-status/types';
import { ISpaceItem } from '../../types';
import CommonStatus from '../monitor-k8s/components/common-status/common-status'; /** 监听空间置顶列表数据事件key */

import SpaceAddList from './space-add-list/space-add-list';

import './space-manage.scss';

export const WATCH_SPACE_STICKY_LIST = 'WATCH_SPACE_STICKY_LIST';

const SPACE_FEATURE_LIST = [
  {
    id: 'APM',
    name: 'APM'
  },
  {
    id: 'CUSTOM_REPORT',
    name: window.i18n.tc('自定义上报')
  },
  {
    id: 'HOST_COLLECT',
    name: window.i18n.tc('插件采集')
  },
  // {
  //   id: 'CONTAINER_COLLECT',
  //   name: window.i18n.tc('容器采集')
  // },
  {
    id: 'HOST_PROCESS',
    name: window.i18n.tc('主机/进程')
  },
  {
    id: 'UPTIMECHECK',
    name: window.i18n.tc('自建拨测')
  },
  {
    id: 'K8S',
    name: window.i18n.tc('Kubernetes')
  }
  // {
  //   id: 'CI_BUILDER',
  //   name: window.i18n.tc('CI构建机')
  // },
  // {
  //   id: 'PAAS_APP',
  //   name: window.i18n.tc('PaaS应用')
  // },
];
enum SpaceType {
  mine /** 我的空间 */,
  all /** 全部空间 */
}
/** 空间状态 */
enum SpaceStatus {
  normal = 'success' /** 正常 */,
  stoped = 'failed' /** 被停用 */
}
/** 功能状态 */
enum FuncType {
  normal = 'normal' /** 正常的 */,
  stop = 'stoped' /** 停用的 */
}
interface ITableItem {
  name: string;
  enName: string;
  collected: boolean;
  status: SpaceStatus;
  statusText: string;
  types: Array<{ id: ETagsType; name: string }>;
  function: IFuncItem[];
  uid: string;
  bizId: number;
  hasAuth: boolean;
}
interface IFuncItem {
  name: string;
  status: FuncType;
  type: 'status' | 'select';
}
/**
 * 空间管理页面
 */
@Component
export default class SpaceManage extends tsc<{}> {
  @Ref() tableRef: any;
  loading = false;
  /** 选中的空间类型tab */
  spaceType: SpaceType = SpaceType.mine;

  /** 新增空间显示 */
  showAdd = false;

  keyword = '';

  /** 刷选数据 */
  filtersData: Record<string, string[]> = {};

  /** 强制刷新table */
  refreshTable = random(8);
  /** 分页数据 */
  pagination = {
    current: 1,
    count: 0,
    limit: 10
  };
  /** 置顶空间数据 */
  stickyList: string[] = [];
  /** 空间数据数据 */
  tableData: ITableItem[] = [];

  emptyStatusType: EmptyStatusType = 'empty';

  /** 分页 */
  get currentPageTableData() {
    const { current, limit } = this.pagination;
    return this.filterTableData.slice((current - 1) * limit, current * limit);
  }
  /**
   * 置顶排序、搜索、筛选的过滤
   * 主要依赖数据: this.tableData, this.keyword, this.filtersData
   */
  get filterTableData() {
    /** 置顶排序 */
    const sortList = this.tableData.sort((a, b) => {
      a.collected = this.stickyList.includes(a.uid);
      b.collected = this.stickyList.includes(b.uid);
      return a.collected && !b.collected ? -1 : 1;
    });
    return sortList.filter(item => {
      /** 搜索 */
      const isMatch =
        item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()) > -1 ||
        item.enName.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()) > -1;
      /** 筛选 */
      const filterList = Object.entries(this.filtersData);
      const isFilter = filterList.length
        ? filterList.every(filter => {
            const [key, values] = filter;
            const itemValue = item[key];
            if (Array.isArray(itemValue)) {
              // 数组类型
              const itemValues = itemValue.map(item => item.id);
              return itemValues.some(val => values.includes(val));
            } // 非数组
            return values.includes(itemValue);
          })
        : true;
      return isMatch && isFilter;
    });
  }

  /** 状态筛选数据 */
  get statusFilterOptions() {
    const map = new Map();
    return this.tableData.reduce((total, item) => {
      if (!map.get(item.status)) {
        total.push({
          text: item.statusText,
          value: item.status
        });
        map.set(item.status, true);
      }
      return total;
    }, []);
  }
  /** 类型筛选数据 */
  get typeFilterOptions() {
    const map = new Map();
    return this.tableData.reduce((total, item) => {
      item.types.forEach(type => {
        if (!map.get(type.id)) {
          total.push({
            text: type.name,
            value: type.id
          });
          map.set(type.id, true);
        }
      });
      return total;
    }, []);
  }

  async created() {
    this.handleFetchList(this.spaceType === SpaceType.all);
  }

  /**
   * 获取空间数据, 以及置顶数据
   * @param showAll 空间数据类型
   */
  handleFetchList(showAll = true) {
    return Promise.all([this.handleFetchSpaceList(showAll), this.handleFetchStickyList()]).finally(() => {
      this.pagination.count = this.tableData.length;
      this.loading = false;
    });
  }
  /**
   * 获取空间数据
   */
  async handleFetchSpaceList(showAll = true) {
    this.loading = true;
    const data = await listSpaces({ show_all: showAll, show_detail: true }).catch(() => {
      this.emptyStatusType = '500';
      return [];
    });
    if (showAll) {
      const list = await listSpaces({ show_all: false, show_detail: false }).catch(() => []);
      list?.length && this.handleMergeBizList(list);
    } else if (!showAll && data?.length) {
      // 全局space_list bizList
      this.handleMergeBizList(data);
    }
    this.tableData = this.handleFormatterList(data);
  }
  // 更新全局space_list bizList bk_biz_list
  handleMergeBizList(spaceList: ISpaceItem[]) {
    mergeSpaceList(spaceList);
    this.$store.commit('app/SET_APP_STATE', {
      bizList: window.space_list,
      bizId: this.$store.getters.bizId
    });
    window.bk_biz_list = window.space_list.map(({ id, is_demo, text }) => ({
      id,
      is_demo,
      text
    })) as any;
  }
  /**
   * 获取置顶列表
   */
  async handleFetchStickyList() {
    const params = {
      username: this.$store.getters.userName
    };
    const res = await listStickySpaces(params).catch(() => []);
    this.stickyList = res;
  }

  /**
   * 格式化空间接口数据
   * @param data 空间接口数据
   * @returns ITableItem[]
   */
  handleFormatterList(data: Record<string, any>[]): ITableItem[] {
    data.sort((a, b) => (a.bk_biz_id > 0 && b.bk_biz_id > 0 ? a.bk_biz_id - b.bk_biz_id : b.bk_biz_id - a.bk_biz_id));
    return data.map<ITableItem>(item => {
      const types = [{ id: item.space_type_id, name: item.type_name }];
      if (item.space_type_id === ETagsType.BKCI && item.space_code) {
        types.push({
          id: 'bcs',
          name: this.$t('容器项目')
        });
      }
      return {
        name: item.space_name,
        enName: ETagsType.BKCC === item.space_type_id ? `#${item.space_id}` : item.space_id || item.space_code,
        status: item.status === 'normal' ? SpaceStatus.normal : SpaceStatus.stoped,
        statusText: this.$tc(item.status === 'normal' ? '正常' : '被停用'),
        types,
        collected: false,
        function: item.func_info,
        uid: item.space_uid,
        bizId: item.bk_biz_id,
        hasAuth: this.getHasAuthority(item.space_uid)
      };
    });
  }

  handleAddShow() {
    this.showAdd = true;
  }

  @Debounce(300)
  handleSearch(val: string) {
    this.emptyStatusType = val ? 'search-empty' : 'empty';
    this.pagination.current = 1;
    this.keyword = val;
    this.pagination.count = this.filterTableData.length;
  }

  /**
   * 置顶操作
   * @param row
   */
  async handleCollected(row: ITableItem) {
    const params = {
      username: this.$store.getters.userName,
      space_uid: row.uid,
      action: row.collected ? 'off' : 'on'
    };
    const res = await stickSpace(params).catch(() => false);
    if (res) {
      row.collected = !row.collected;
      this.stickyList = res;
      bus.$emit(WATCH_SPACE_STICKY_LIST, res);
    }
  }

  /**
   * 分页操作
   * @param page 页码
   */
  handlePageChange(page: number) {
    this.pagination.current = page;
  }
  handleLimitChange(limit: number) {
    this.pagination.current = 1;
    this.pagination.limit = limit;
  }

  /**
   * 切换空间类型
   * @param type 空间类型
   */
  handleChangeSpace(type: SpaceType) {
    this.spaceType = type;
    this.pagination.current = 1;
    this.pagination.count = 0;
    this.keyword = '';
    this.refreshTable = random(8);
    this.filtersData = {};
    this.tableData = [];
    this.stickyList = [];
    this.handleFetchList(this.spaceType === SpaceType.all);
  }

  /**
   * 获取所有筛选的值
   * @param _val
   * @param val 参与筛选的值
   */
  handleFilterChange(_val, val: Object = {}) {
    const { columns } = this.tableRef;
    this.filtersData = Object.entries(val).reduce((total, item) => {
      const column = columns.find(col => col.id === item[0]);
      item[1].length && (total[column.property] = item[1]);
      return total;
    }, {});
    this.pagination.current = 1;
    this.pagination.count = this.filterTableData.length;
  }

  handleShowChange(v: boolean) {
    this.showAdd = v;
  }
  handleSaveSuccess() {
    this.handleChangeSpace(this.spaceType);
    this.showAdd = false;
  }
  // 判断是否有权限
  getHasAuthority(spaceUid: string) {
    return this.$store.getters.bizList.some(item => item.space_uid === spaceUid);
  }
  // 无权限跳转权限中心
  async handleApplyAuth(item: ITableItem) {
    const url = await getAuthorityDetail({
      action_ids: ['view_business_v2'],
      bk_biz_id: item.bizId
    })
      .then(res => res.apply_url)
      .catch(() => false);
    url && window.open(url);
  }

  handleOperation(val: EmptyStatusOperationType) {
    switch (val) {
      case 'clear-filter':
        this.keyword = '';
        break;
      case 'refresh':
        this.handleFetchList(this.spaceType === SpaceType.all);
        break;
    }
  }

  render() {
    return (
      <div
        class='space-manage-wrap'
        v-bkloading={{ isLoading: this.loading, zIndex: 1 }}
      >
        <div class='space-manage-main'>
          <div class='space-manage-header'>
            <bk-button
              theme='primary'
              icon='plus'
              class='space-add-btn'
              onClick={this.handleAddShow}
            >
              {this.$tc('新增')}
            </bk-button>
            <div class='bk-button-group'>
              <bk-button
                class={{ 'is-selected': this.spaceType === SpaceType.mine }}
                onClick={() => this.handleChangeSpace(SpaceType.mine)}
              >
                {this.$tc('我的空间')}
              </bk-button>
              <bk-button
                class={{ 'is-selected': this.spaceType === SpaceType.all }}
                onClick={() => this.handleChangeSpace(SpaceType.all)}
              >
                {this.$tc('全部空间')}
              </bk-button>
            </div>
            <bk-input
              class='search-input'
              value={this.keyword}
              placeholder={this.$tc('输入')}
              right-icon='bk-icon icon-search'
              onInput={this.handleSearch}
            ></bk-input>
          </div>
          <bk-table
            class='table-wrap'
            ref='tableRef'
            key={this.refreshTable}
            outer-border={false}
            pagination={this.pagination}
            data={this.currentPageTableData}
            on-filter-change={this.handleFilterChange}
            on-page-change={this.handlePageChange}
            on-page-limit-change={this.handleLimitChange}
          >
            <EmptyStatus
              type={this.emptyStatusType}
              slot='empty'
              onOperation={this.handleOperation}
            />
            <bk-table-column
              label={this.$t('空间名')}
              width={150}
              formatter={(row: ITableItem) => (
                <div class='space-name-wrap'>
                  <i
                    class={['icon-monitor', row.collected ? 'icon-yizhiding' : 'icon-zhiding']}
                    onClick={() => this.handleCollected(row)}
                  />
                  <div
                    class='space-name-main'
                    v-authority={{ active: !row.hasAuth }}
                    onClick={() => !row.hasAuth && this.handleApplyAuth(row)}
                  >
                    <div
                      class='space-name'
                      style={{ color: !row.hasAuth ? '#ccc' : '#3a84ff' }}
                      v-bk-overflow-tips
                    >
                      {row.name}
                    </div>
                    <div
                      class='space-enname'
                      style={{ color: !row.hasAuth ? '#ccc' : '#979BA5' }}
                      v-bk-overflow-tips
                    >
                      {row.enName}
                    </div>
                  </div>
                </div>
              )}
            />
            <bk-table-column
              label={this.$t('状态')}
              width={90}
              property={'status'}
              filters={this.statusFilterOptions}
              formatter={(row: ITableItem) => (
                <CommonStatus
                  type={row.status}
                  text={row.statusText}
                ></CommonStatus>
              )}
            />
            <bk-table-column
              label={this.$t('类型')}
              width={110}
              property={'types'}
              filters={this.typeFilterOptions}
              formatter={(row: ITableItem) =>
                row.types.map(item => (
                  <span
                    class='space-type'
                    style={{ ...SPACE_TYPE_MAP[item.id]?.light }}
                  >
                    {item.name}
                  </span>
                ))
              }
            />
            {
              <bk-table-column
                label={this.$t('具备功能')}
                min-width={660}
                formatter={(row: ITableItem) => (
                  <div class='function-wrap'>
                    {
                      SPACE_FEATURE_LIST.map(item => (
                        <CommonStatus
                          class='func-item'
                          type={row.function[item.id] ? 'normal' : 'stoped'}
                          key={item.id}
                          icon={!row.function[item.id] ? 'icon-monitor icon-mc-target-link' : ''}
                          v-bk-tooltips={{ content: row.function[item.id] ? this.$t('已关联') : this.$t('未关联') }}
                          text={item.name}
                        />
                      ))
                      // row.function?.length ? row.function.map(item => (
                      //   item.type === 'status'
                      //     ? <CommonStatus
                      //       class="func-item"
                      //       type={item.status as CommonStatusType}
                      //       text={item.name} />
                      //     : <CustomSelect
                      //       class="func-item select"
                      //       options={[{ id: '2', name: 'sdd' }]}>
                      //       <span slot="target" >
                      //         <i class="icon-monitor icon-copy-link"></i>
                      //         { item.name}
                      //       </span>
                      //       <bk-option id="2" name="sdd"></bk-option>
                      //     </CustomSelect>
                      // )) : '--'
                    }
                  </div>
                )}
              />
            }
          </bk-table>
        </div>
        <SpaceAddList
          show={this.showAdd}
          onShowChange={this.handleShowChange}
          onSaveSuccess={this.handleSaveSuccess}
        ></SpaceAddList>
      </div>
    );
  }
}
