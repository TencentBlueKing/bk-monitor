<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
-->
<template>
  <div
    v-monitor-loading="{ isLoading: loading }"
    class="strategy-list-wrapper"
  >
    <div class="top-container">
      <bk-button
        v-authority="{ active: !authority.MANAGE_AUTH }"
        class="left mc-btn-add"
        theme="primary"
        @click="authority.MANAGE_AUTH ? handleAddShield() : handleShowAuthorityDetail()"
      >
        {{ $t('新建') }}
      </bk-button>
      <div class="right">
        <bk-date-picker
          v-model="right.dateRange"
          :placeholder="$t('选择屏蔽时间范围')"
          format="yyyy-MM-dd HH:mm:ss"
          type="datetimerange"
          @clear="handleClearDate"
          @open-change="handleHideDatePicker"
          @pick-success="handleDateRangeChange"
        />
        <!-- <bk-input
          :placeholder="$t('输入屏蔽内容、ID')"
          v-model="right.keyword"
          right-icon="bk-icon icon-search"
          @change="handleSearch"
        >
        </bk-input> -->
        <div class="right-search">
          <search-select
            :model-value="searchValues"
            :data="searchData"
            :clearable="false"
            :placeholder="$t('输入屏蔽内容、ID')"
            @change="handleSearchCondition"
          />
        </div>
      </div>
    </div>
    <div class="content-wrapper">
      <ul class="tab-list">
        <li
          v-for="(item, index) in tab.list"
          :key="item.name"
          class="tab-list-item"
          :class="{ 'tab-active': index === tab.active }"
          @click="handleTabChange(index)"
        >
          <span class="tab-name">{{ item.name }}</span>
        </li>
        <li class="tab-list-blank" />
      </ul>
      <div v-bkloading="{ isLoading: table.loading }">
        <!-- 屏蔽中 -->
        <bk-table
          v-show="tab.active === 0"
          class="shield-table"
          :data="table.data"
          @sort-change="handleSort"
        >
          <div slot="empty">
            <empty-status
              :type="emptyType"
              @operation="handleEmptyOperation"
            />
          </div>
          <bk-table-column
            v-slot="scope"
            width="100"
            sortable="custom"
            label="ID"
            prop="id"
          >
            <span
              class="shield-id"
              @click="handleToDetail(scope.row.id)"
            >
              #{{ scope.row.id }}
            </span>
          </bk-table-column>
          <bk-table-column
            width="150"
            class="shield-type"
            :render-header="renderHeader"
            show-overflow-tooltip
            prop="shieldTypeName"
          />
          <bk-table-column
            v-slot="scope"
            min-width="250"
            class-name="shield-content"
            :label="$t('屏蔽内容')"
          >
            <!-- <span v-if="scope.row.shieldType === 'strategy'" class="link">{{scope.row.shieldContent}}<i class="icon-monitor icon-mc-wailian" @click="handleToOtherPages(scope.row)"></i></span> -->
            <span class="content">{{ scope.row.shieldContent }}</span>
          </bk-table-column>
          <bk-table-column
            v-if="!tab.active"
            min-width="150"
            :label="$t('开始时间')"
            prop="beginTime"
            sortable="custom"
            show-overflow-tooltip
          />
          <bk-table-column
            v-if="!tab.active"
            min-width="150"
            :label="$t('持续周期及时长')"
            prop="cycleDuration"
          />
          <bk-table-column
            v-slot="scope"
            min-width="230"
            :label="$t('屏蔽原因')"
            prop="description"
          >
            <span class="content">{{ scope.row.description || '--' }}</span>
          </bk-table-column>
          <bk-table-column
            v-slot="scope"
            width="150"
            :label="$t('操作')"
          >
            <bk-button
              v-authority="{ active: !authority.MANAGE_AUTH }"
              :text="true"
              theme="primary"
              class="clone-btn"
              @click="
                authority.MANAGE_AUTH
                  ? handleCloneShield(scope.row.id, scope.row.shieldType)
                  : handleShowAuthorityDetail()
              "
            >
              {{ $t('克隆') }}
            </bk-button>
            <bk-button
              v-authority="{ active: !authority.MANAGE_AUTH }"
              class="edit-btn"
              :text="true"
              theme="primary"
              @click="
                authority.MANAGE_AUTH
                  ? handleEditShield(scope.row.id, scope.row.shieldType)
                  : handleShowAuthorityDetail()
              "
            >
              {{ $t('button-编辑') }}
            </bk-button>
            <bk-button
              v-authority="{ active: !authority.MANAGE_AUTH }"
              :text="true"
              theme="primary"
              @click="authority.MANAGE_AUTH ? handleDeleteShield(scope.row.id) : handleShowAuthorityDetail()"
            >
              {{ $t('解除') }}
            </bk-button>
          </bk-table-column>
        </bk-table>
        <!-- 屏蔽失效 -->
        <bk-table
          v-show="tab.active === 1"
          class="shield-table"
          :data="table.data"
          @sort-change="handleSort"
        >
          <div slot="empty">
            <empty-status
              :type="emptyType"
              @operation="handleEmptyOperation"
            />
          </div>
          <bk-table-column
            v-slot="scope"
            width="100"
            sortable="custom"
            label="ID"
            prop="id"
          >
            <span
              class="shield-id"
              @click="handleToDetail(scope.row.id)"
            >
              #{{ scope.row.id }}
            </span>
          </bk-table-column>
          <bk-table-column
            width="150"
            class="shield-type"
            :render-header="renderHeader"
            prop="shieldTypeName"
          />
          <bk-table-column
            v-slot="scope"
            min-width="250"
            class-name="shield-content"
            :label="$t('屏蔽内容')"
          >
            <!-- <span v-if="scope.row.shieldType === 'strategy'" class="link">{{scope.row.shieldContent}}<i class="icon-monitor icon-mc-wailian" @click="handleToOtherPages(scope.row)"></i></span> -->
            <span class="content">{{ scope.row.shieldContent }}</span>
          </bk-table-column>
          <bk-table-column
            width="180"
            :label="$t('开始时间')"
            prop="beginTime"
            sortable="custom"
          />
          <bk-table-column
            width="180"
            :label="$t('失效时间')"
            prop="failureTime"
            sortable="custom"
          />
          <bk-table-column
            v-slot="scope"
            min-width="230"
            :label="$t('屏蔽原因')"
            prop="description"
          >
            <span class="content">{{ scope.row.description || '--' }}</span>
          </bk-table-column>
          <bk-table-column
            v-slot="scope"
            width="120"
            :label="$t('状态')"
          >
            <span :class="statusMap[scope.row.status].className">{{ statusMap[scope.row.status].des }}</span>
          </bk-table-column>
          <bk-table-column
            v-slot="scope"
            width="150"
            :label="$t('操作')"
          >
            <bk-button
              v-authority="{ active: !authority.MANAGE_AUTH }"
              :text="true"
              theme="primary"
              class="clone-btn"
              @click="
                authority.MANAGE_AUTH
                  ? handleCloneShield(scope.row.id, scope.row.shieldType)
                  : handleShowAuthorityDetail()
              "
            >
              {{ $t('克隆') }}
            </bk-button>
          </bk-table-column>
        </bk-table>
      </div>
      <template v-if="tableInstance">
        <bk-pagination
          v-show="table.data.length"
          class="shield-pagination list-pagination"
          align="right"
          size="small"
          pagination-able
          :current="tableInstance.page"
          :limit="tableInstance.pageSize"
          :count="tableInstance.count"
          :limit-list="tableInstance.pageList"
          show-total-count
          @change="handlePageChange"
          @limit-change="handleLimitChange"
        />
      </template>
    </div>
    <div v-show="false">
      <div
        ref="labelMenu"
        class="label-menu-wrapper"
      >
        <ul class="label-menu-list">
          <li
            v-for="(item, index) in shieldType.list"
            :key="index"
            class="item"
            @click="handleSelectType(item)"
          >
            <bk-checkbox
              :value="item.value"
              :true-value="item.checked"
              :false-value="item.cancel"
            />
            <span class="name">{{ item.name }}</span>
          </li>
        </ul>
        <div class="footer">
          <div class="btn-group">
            <bk-button
              :text="true"
              @click="handleTypeChange"
            >
              {{ $t('确定') }}
            </bk-button>
            <bk-button
              :text="true"
              @click="handleResetSelected"
            >
              {{ $t('重置') }}
            </bk-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import SearchSelect from '@blueking/search-select-v3/vue2';
import dayjs from 'dayjs';
import { disableShield, frontendShieldList } from 'monitor-api/modules/shield.js';
import { debounce } from 'throttle-debounce';

import { commonPageSizeMixin } from '../../../common/mixins';
import EmptyStatus from '../../../components/empty-status/empty-status.tsx';
import TableStore from '../store.ts';

import '@blueking/search-select-v3/vue2/vue2.css';

export default {
  name: 'AlarmShield',
  components: {
    EmptyStatus,
    SearchSelect,
  },
  mixins: [commonPageSizeMixin],
  inject: ['authority', 'handleShowAuthorityDetail', 'authorityMap'],
  props: {
    fromRouteName: {
      type: String,
      default: '',
    },
  },
  data() {
    return {
      loading: false,
      isShow: false,
      tab: {
        active: 0,
        list: [
          { name: this.$t('屏蔽中'), id: 0, type: 'effct' },
          { name: this.$t('屏蔽失效'), id: 1, type: 'overdue' },
        ],
      },
      shieldType: {
        list: [
          {
            name: this.$t('告警事件屏蔽'),
            id: 'alert',
            checked: 'alert',
            value: '',
            cancel: '',
          },
          {
            name: this.$t('范围屏蔽'),
            id: 'scope',
            checked: 'scope',
            value: '',
            cancel: '',
          },
          {
            name: this.$t('策略屏蔽'),
            id: 'strategy',
            checked: 'strategy',
            value: '',
            cancel: '',
          },
          {
            name: this.$t('维度屏蔽'),
            id: 'dimension',
            checked: 'dimension',
            value: '',
            cancel: '',
          },
        ],
        instance: null,
        effct: new Set(),
        overdue: new Set(),
        selectedLabels: [],
      },
      right: {
        dateRange: [],
        keyword: '',
      },
      table: {
        loading: false,
        data: [],
        effct: {
          isFilter: false,
        },
        overdue: {
          isFilter: false,
        },
      },
      cache: {
        dateRange: [],
        overdueData: [],
        effectiveData: [],
      },
      cacheDate: [],
      order: {
        effct: {
          isTimeSort: false,
          isIdSort: false,
          id: 'id',
          effct: 'begin_time',
          overdue: 'failure_time',
        },
        overdue: {
          isTimeSort: false,
          isIdSort: false,
          id: 'id',
          effct: 'begin_time',
          overdue: 'failure_time',
        },
      },
      tableInstance: null,
      statusMap: {
        1: {
          des: this.$t('屏蔽中'),
          className: 'shield',
          code: 1,
        },
        2: {
          des: this.$t('已过期'),
          className: 'overdue',
          code: 2,
        },
        3: {
          des: this.$t('被解除'),
          className: 'release',
          code: 3,
        },
      },
      /* 搜索内容 */
      searchValues: [],
      searchData: [],
      /* 参数范围 */
      backDisplayMap: {},
      /* 此数据传入到后端 */
      searchCondition: [],
      handleSearch() {},
      emptyType: 'empty',
    };
  },
  computed: {
    shieldTypeStr() {
      return this.shieldType.list
        .filter(item => item.value)
        .map(item => item.value)
        .join(',');
    },
    tabName() {
      return this.tab.list[this.tab.active].type;
    },
    curOrder() {
      return this.order[this.tabName];
    },
    curTable() {
      return this.table[this.tabName];
    },
  },
  created() {
    this.handleSearch = debounce(300, () => this.handleGetShiledList());
    this.createdConditionList();
    !this.loading && this.handleGetShiledList(false, true);
  },
  activated() {
    if (!['alarm-shield-add', 'alarm-shield-edit', 'alarm-shield-detail'].includes(this.fromRouteName)) {
      this.right.keyword = '';
      this.tableInstance?.setDefaultStore?.();
      this.right.dateRange = [];
      this.tab && this.handleTabChange(0);
    }
    !this.loading && this.handleGetShiledList(false, true);
  },
  deactivated() {
    this.handleDestroyFilterPopover();
  },
  beforeDestroy() {
    this.handleDestroyFilterPopover();
  },
  methods: {
    handleToDetail(id) {
      this.$router.push({ name: 'alarm-shield-detail', params: { id } });
    },
    handleAddShield() {
      this.$router.push({ name: 'alarm-shield-add' });
    },
    // ID和时间的筛选
    handleSort(v) {
      if (!v.order) {
        this.curOrder.isIdSort = false;
        this.curOrder.isTimeSort = false;
      } else {
        v.column.label === 'ID' ? this.handleIdOrder(v) : this.handleTimeOrder(v);
      }
      this.handleGetShiledList();
    },
    handleTimeOrder(sort) {
      this.curOrder.isIdSort = false;
      this.curOrder.isTimeSort = true;
      if (this.tab.active === 0) {
        this.curOrder.effct = sort.order === 'descending' ? '-begin_time' : 'begin_time';
      } else {
        const propMap = {
          beginTime: 'begin_time',
          failureTime: 'failure_time',
        };
        this.curOrder.overdue = sort.order === 'descending' ? `-${propMap[sort.prop]}` : propMap[sort.prop];
      }
    },
    handleIdOrder(sort) {
      this.curOrder.isIdSort = true;
      this.curOrder.isTimeSort = false;
      this.curOrder.id = sort.order === 'descending' ? '-id' : 'id';
    },
    // 日历面板选择事件
    handleDateRangeChange() {
      this.cache.dateRange = this.right.dateRange.join('');
      this.emptyType = 'search-empty';
      this.handleGetShiledList(true);
    },
    // 日历面板弹出收起事件
    handleHideDatePicker(state) {
      const dateRangeStr = this.right.dateRange.join('');
      if (!state && !!dateRangeStr && dateRangeStr !== this.cache.dateRange) {
        this.handleGetShiledList(true);
        this.cache.dateRange = this.right.dateRange.join('');
      }
    },

    // 点击克隆按钮
    handleCloneShield(id, type) {
      this.$router.push({
        name: 'alarm-shield-clone',
        params: { id, type },
      });
    },

    // 点击编辑按钮
    handleEditShield(id, type) {
      this.$router.push({
        name: 'alarm-shield-edit',
        params: { id, type },
      });
    },

    // 解除告警屏蔽事件
    handleDeleteShield(id) {
      this.$bkInfo({
        title: this.$t('是否解除该屏蔽?'),
        confirmFn: () => {
          this.loading = true;
          disableShield({ id })
            .then(() => {
              this.handleGetShiledList(true);
              this.$bkMessage({
                theme: 'success',
                message: this.$t('解除屏蔽成功'),
              });
            })
            .catch(() => {
              this.loading = false;
            });
        },
      });
    },
    // tab栏切换事件
    handleTabChange(index) {
      if (this.tab.active !== index) {
        this.tab.active = index;
        this.table.data = [];
        this.handleUpdateFilterVal();
        this.handleGetShiledList(true);
        this.handleDestroyFilterPopover();
      }
    },
    handleDestroyFilterPopover() {
      if (this.shieldType.instance) {
        this.shieldType.instance.hide(0);
        this.shieldType.instance.destroy();
        this.shieldType.instance = null;
      }
    },
    async handleGetShiledList(needReset = false, needLoading = false) {
      this.loading = needLoading;
      this.table.loading = !needLoading;
      this.table.data = [];
      const params = {
        page: needReset || !this.tableInstance ? 1 : this.tableInstance.page,
        page_size: needReset || !this.tableInstance ? this.handleGetCommonPageSize() : this.tableInstance.pageSize,
        categories: this.shieldType.selectedLabels?.length
          ? this.shieldType.selectedLabels
          : ['alert', 'scope', 'strategy', 'dimension'],
        search: this.right.keyword,
        conditions: this.searchCondition,
        is_active: this.tab.active === 0,
      };
      if (this.curOrder.isTimeSort) {
        params.order = this.tab.active === 0 ? this.curOrder.effct : this.curOrder.overdue;
      }
      if (this.curOrder.isIdSort) {
        params.order = this.curOrder.id;
      }
      if (this.right.dateRange.join('').length) {
        params.time_range =
          `${dayjs.tz(this.right.dateRange[0]).format('YYYY-MM-DD HH:mm:ssZZ')}` +
          '--' +
          `${dayjs.tz(this.right.dateRange[1]).format('YYYY-MM-DD HH:mm:ssZZ')} `;
      }
      const data = await frontendShieldList(params).catch(() => {
        this.emptyType = '500';
        return {
          shield_list: [],
          count: 0,
        };
      });
      if (!this.tableInstance) {
        this.tableInstance = new TableStore(data.shield_list);
      } else {
        this.tableInstance.setDefaultData(data.shield_list);
      }
      this.tableInstance.count = data.count;
      this.table.data = this.tableInstance.getTableData();
      this.loading = false;
      this.table.loading = false;
    },
    handlePageChange(page) {
      this.tableInstance.page = page;
      this.handleGetShiledList();
    },
    handleLimitChange(pageSize) {
      this.handleSetCommonPageSize(pageSize);
      this.tableInstance.pageSize = pageSize;
      this.handleGetShiledList();
    },
    handleTypeChange() {
      if (this.shieldTypeStr.length) {
        this.shieldType.instance.hide(100);
        this.shieldType.selectedLabels = this.shieldTypeStr.split(',');
        this.curTable.isFilter = true;
        this.handleGetShiledList();
      } else if (this.curTable.isFilter) {
        this.handleResetSelected();
      }
    },
    handleResetSelected() {
      this.shieldType.instance.hide(100);
      this.shieldType.list.forEach(item => {
        item.value = '';
      });
      this.shieldType.selectedLabels = [];
      if (this.curTable.isFilter) {
        this.curTable.isFilter = false;
        this.handleGetShiledList();
      }
      this.shieldType[this.tabName] = new Set();
    },
    handleUpdateFilterVal() {
      const labelSet = this.shieldType[this.tabName];
      this.shieldType.selectedLabels = [];
      this.shieldType.list.forEach(item => {
        if (labelSet.has(item.id)) {
          item.value = item.id;
          this.shieldType.selectedLabels.push(item.value);
        } else {
          item.value = '';
        }
      });
    },
    handleShow(e) {
      const target = e.target.tagName === 'SPAN' ? e.target : e.target.parentNode;
      if (!this.shieldType.instance) {
        this.shieldType.instance = this.$bkPopover(target, {
          content: this.$refs.labelMenu,
          trigger: 'click',
          arrow: false,
          theme: 'light common-monitor shield',
          maxWidth: 520,
          offset: '0, -11',
          sticky: true,
          duration: [275, 0],
          interactive: true,
          onHidden: () => {
            this.shieldType.instance.destroy();
            this.shieldType.instance = null;
            this.shieldType[this.tabName] = new Set(this.shieldType.selectedLabels);
            this.shieldType.list.forEach(item => {
              item.value = this.shieldType.selectedLabels.includes(item.id) ? item.id : '';
            });
          },
        });
      }
      this.shieldType?.instance?.show?.(100);
    },
    handleSelectType(item) {
      const labelSet = this.shieldType[this.tabName];
      if (!labelSet.has(item.value)) {
        item.value = item.id;
        labelSet.add(item.value);
      } else {
        labelSet.delete(item.value);
        item.value = '';
      }
    },
    renderHeader(h) {
      return h(
        'span',
        {
          class: {
            'dropdown-trigger': true,
            ' plugin-label': true,
            selected: this.shieldTypeStr,
          },
          on: {
            click: this.handleShow,
          },
        },
        [
          this.$t('分类'),
          h('i', {
            class: {
              'icon-monitor icon-filter-fill': true,
            },
          }),
        ]
      );
    },
    handleToOtherPages(row) {
      if (row.shieldType === 'strategy') {
        this.$router.push({
          name: 'strategy-config-detail',
          params: { id: row.dimensionConfig.id },
        });
      } else if (row.shieldType === 'event') {
        this.$router.push({
          name: 'event-center-detail',
          params: { id: row.dimensionConfig.id },
        });
      }
    },
    handleClearDate() {
      this.right.dateRange = [];
      this.cache.dateRange = this.right.dateRange.join('');
      this.emptyType = 'empty';
      this.handleGetShiledList();
    },
    /* 创建搜索可选条件 */
    createdConditionList() {
      this.backDisplayMap = {
        id: {
          name: `${this.$t('屏蔽')}ID`,
          value: [],
          id: 'id',
        },
      };
      const res = [];
      const map = this.backDisplayMap;
      Object.keys(map).forEach(key => {
        const { name, id, list } = map[key];
        res.push({
          name,
          id,
          multiple: true,
          children: list ? list : [],
        });
      });
      this.searchData = res;
      this.getRouterParams();
    },
    handleSearchCondition(v) {
      this.searchValues = v;
      this.searchCondition = this.routerParamsReplace();
      this.emptyType = this.searchCondition.length ? 'search-empty' : 'empty';
      this.handleGetShiledList();
    },
    /* 更新路由参数 */
    routerParamsReplace() {
      const query = [];
      const ids = Object.keys(this.backDisplayMap);
      this.searchValues.forEach(item => {
        if (ids.includes(item.id)) {
          if (item.values?.length) query.push({ key: item.id, value: item.values.map(v => v.id) });
        } else {
          if (item.id) query.push({ key: 'query', value: item.id });
        }
      });
      const queryStr = JSON.stringify(query);
      this.$router
        .replace({
          ...this.$route,
          query: {
            queryString: query?.length ? queryStr : undefined,
          },
        })
        .catch(() => {});
      return query;
    },
    /* 获取路由参数 */
    getRouterParams() {
      /* 需要 此类格式的数据 queryString： [{key: 'xxx/query', value: ['xx', 'xx']}] */
      const queryString = this.$route.query?.queryString;
      if (queryString) {
        let queryStringObj = null;
        try {
          queryStringObj = JSON.parse(queryString);
        } catch (_err) {
          this.$router
            .replace({
              ...this.$route,
              query: { queryString: undefined },
            })
            .catch(() => {});
        }
        if (queryStringObj) {
          const ids = Object.keys(this.backDisplayMap);
          const searchValues = [];
          queryStringObj?.forEach(item => {
            if (ids.includes(item.key)) {
              if (item.value?.length)
                searchValues.push({
                  id: item.key,
                  multiple: true,
                  name: this.backDisplayMap[item.key].name,
                  values: Array.isArray(item.value) ? item.value.map(item => ({ id: item, name: item })) : [item.value],
                });
            } else {
              if (item.key) searchValues.push({ id: item.key, name: item.key });
            }
          });
          this.searchValues = searchValues;
          this.searchCondition = this.routerParamsReplace();
        }
      }
    },
    /** 空状态操作 */
    handleEmptyOperation(type) {
      if (type === 'refresh') {
        this.emptyType = 'empty';
        this.handleGetShiledList();
        return;
      }
      if (type === 'clear-filter') {
        this.searchValues = [];
        this.right.dateRange = [];
        this.searchCondition = [];
        this.handleGetShiledList();
        return;
      }
    },
  },
};
</script>
<style lang="scss" scope>
.strategy-list-wrapper {
  min-height: calc(100vh - 80px);

  .top-container {
    display: flex;
    justify-content: space-between;

    .right {
      display: flex;

      .bk-date-picker {
        width: 301px;
        margin-right: 10px;

        .bk-picker-confirm {
          .bk-picker-confirm-time {
            text-decoration: none;
          }

          .confirm {
            text-decoration: none;
          }
        }
      }

      .bk-form-control {
        width: 301px;
      }

      .right-search {
        width: 400px;
        background: #fff;
      }
    }
  }

  .content-wrapper {
    margin-top: 16px;
    background: #fff;
    border: 1px solid #dcdee5;

    .tab-list {
      display: flex;
      flex-direction: row;
      align-items: center;
      justify-content: flex-start;
      padding: 0;
      margin: 0 0 16px;
      font-size: 14px;
      line-height: 42px;
      background: #fafbfd;

      &-item {
        flex: 0 0 120px;
        color: #63656e;
        text-align: center;
        border-right: 1px solid #dcdee5;
        border-bottom: 1px solid #dcdee5;

        &.tab-active {
          color: #3a84ff;
          background: #fff;
          border-bottom-color: transparent;

          .tab-num {
            background: #3a84ff;
          }
        }

        &:hover {
          color: #3a84ff;
          cursor: pointer;
        }
      }

      &-blank {
        flex: 1 1 auto;
        height: 42px;
        border-bottom: 1px solid #dcdee5;
      }
    }

    .shield-table {
      border-right: 0;
      border-left: 0;

      &::before {
        width: 0;
      }

      &::after {
        width: 0;
      }

      .content {
        /* stylelint-disable-next-line value-no-vendor-prefix */
        display: -webkit-box;
        margin: 12px 0;
        overflow: hidden;
        text-overflow: ellipsis;

        /* stylelint-disable-next-line property-no-vendor-prefix */
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
      }

      .link {
        display: flex;
        align-items: center;
      }

      .shield-id {
        color: #3a84ff;
        cursor: pointer;

        &:hover {
          color: #699df4;
        }
      }

      .edit-btn,
      .clone-btn {
        padding-right: 0;
        padding-left: 0;
        margin-right: 8px;
      }

      .dropdown-trigger {
        display: inline-block;
        width: 100%;
        height: 42px;
        cursor: pointer;

        .icon-filter-fill {
          margin-left: 6px;
          color: #64656e;
        }

        &.selected {
          color: #3a84ff;

          .icon-filter-fill {
            color: #3a84ff;
          }
        }
      }

      .bk-dropdown-content {
        left: -16px;
        background: #fff;
      }

      .dropdown-menu-list {
        display: flex;
        flex-direction: column;
        width: 150px;
        padding: 6px 0;
        background: #fff;

        .list-item {
          display: flex;
          flex: 0 0 32px;
          align-items: center;
          padding-left: 15px;

          &:hover {
            color: #3a84ff;
            cursor: pointer;
            background: #e1ecff;
          }
        }
      }

      .icon-mc-wailian {
        margin-left: 2px;
        font-size: 22px;
        color: #c4c6cc;
        cursor: pointer;

        &:hover {
          color: #3a84ff;
        }
      }

      .release {
        color: #ff9c01;
      }

      .overdue {
        color: #c4c6cc;
      }
    }

    .shield-pagination {
      margin: 15px;
    }
  }
}

.label-menu-wrapper {
  .label-menu-list {
    display: flex;
    flex-direction: column;
    padding: 6px 0;
    background-color: #fff;
    border-radius: 2px;

    .item {
      display: flex;
      align-items: center;
      height: 32px;
      min-height: 32px;
      padding: 0 10px;
      color: #63656e;
      cursor: pointer;

      .name {
        display: inline-block;
        height: 18px;
        margin-left: 6px;
        line-height: 18px;
      }

      &:hover {
        color: #3a84ff;
        background: #e1ecff;
      }
    }
  }

  .footer {
    display: flex;
    justify-content: center;
    height: 29px;
    background-color: #fff;
    border-top: solid 2px #f0f1f5;

    .btn-group {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 70px;
      height: 100%;
    }

    .bk-button-text {
      position: relative;
      top: -1px;
      padding: 0;
      font-size: 12px;
      line-height: 22px;
    }
  }
}
</style>
