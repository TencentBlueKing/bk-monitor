<!--
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
-->
<template>
  <guide-page
    v-if="showGuidePage"
    :guide-data="curIntroduceData"
  />
  <div
    v-else
    class="collector-config"
    v-monitor-loading="{ isLoading: delayLoading }"
  >
    <page-tips
      style="margin-bottom: 16px"
      :tips-text="
        $t('监控数据采集是通过下发监控插件来实现数据采集的全生命周期管理，该功能依赖服务器安装bkmonitorbeat采集器')
      "
      :link-text="$t('采集器安装前往节点管理')"
      :link-url="`${$store.getters.bkNodemanHost}#/plugin-manager/list`"
      doc-link="collectorConfigMd"
    />
    <div>
      <div
        class="collector-config-panel"
        v-if="filterTabList.length"
      >
        <bk-tab
          class="panel-tab"
          :active="panel.active"
          :label-height="54"
          @tab-change="handleTabItemClick"
        >
          <bk-tab-panel
            v-for="(item, index) in filterTabList"
            :key="index"
            :name="index"
            :label="item.name"
          >
            <template slot="label">
              <div class="panel-tab-item">
                <span class="tab-name">{{ item.name }}</span>
                <span class="tab-mark">{{ item.total }}</span>
              </div>
            </template>
          </bk-tab-panel>
        </bk-tab>
        <!-- <ul class="panel-tab">
          <li class="panel-tab-item" v-for="(item,index) in filterTabList"
              :key="index" :class="{ 'tab-active': index === panel.active }"
              :style="{ borderRightColor: index === panel.active - 1 ? '#DCDEE5' : '' }"
              @click="index !== panel.active && handleTabItemClick(index)">
            <span class="tab-name">{{item.name}}</span>
            <span class="tab-mark">{{item.total}}</span>
          </li>
          <li class="panel-tab-blank"></li>
        </ul> -->
        <ul
          class="panel-content"
          v-if="activeTabItem.data"
        >
          <li
            class="panel-content-item"
            :class="{ 'active-num': key === panel.itemActive }"
            v-for="(num, key) in activeTabItem.data"
            @click="handleTabNumClick(key, num)"
            :key="key"
          >
            <span class="content-num">{{ num }}</span>
            <span class="content-desc">{{ tabItemMap[key] }}</span>
          </li>
        </ul>
      </div>
      <div class="collector-config-tool">
        <div class="tool-btn">
          <bk-button
            v-authority="{ active: !authority.MANAGE_AUTH }"
            theme="primary"
            @click="authority.MANAGE_AUTH ? handleShowAdd('add') : handleShowAuthorityDetail()"
            class="mc-btn-add"
            style="margin-right: 8px"
          >
            <span class="icon-monitor icon-plus-line mr-6"></span>
            {{ $t('新建') }}
          </bk-button>
          <!-- <bk-button theme="default" @click="handleToLogCollection"> {{ $t('日志采集') }} </bk-button> -->
        </div>
        <bk-input
          :placeholder="$t('采集配置名称/ID')"
          right-icon="bk-icon icon-search"
          class="tool-search"
          v-model="panel.keyword"
          @change="handleSearch"
        />
      </div>
      <div
        ref="tableWrapper"
        class="collector-config-table"
      >
        <div class="table-wrap">
          <bk-table
            class="config-table"
            ref="table"
            @row-mouse-enter="i => (table.hoverIndex = i)"
            @row-mouse-leave="i => (table.hoverIndex = -1)"
            :row-style="handleStoppedRow"
            @sort-change="handleSortChange"
            :data="table.data"
            :size="table.size"
          >
            <div slot="empty">
              <empty-status
                :type="emptyType"
                @operation="handleEmptyOperation"
              />
            </div>
            <bk-table-column
              v-for="column of selectedColumns"
              :key="column.prop"
              :label="column.label"
              :prop="column.prop"
              :sortable="column.sortable"
              :width="column.width"
              :min-width="column.minWidth"
              :show-overflow-tooltip="column.tooltip"
            >
              <template slot-scope="scope">
                <template v-if="column.prop === 'id'">
                  {{ `#${scope.row.id}` }}
                </template>
                <template v-else-if="column.prop === 'name'">
                  <div class="col-name">
                    <span
                      class="col-name-desc"
                      v-if="scope.$index !== table.editIndex"
                      @click.stop="handleShowDetail(scope.row)"
                    >{{ scope.row.name }}</span>
                    <span
                      v-if="scope.row.needUpdate && scope.$index !== table.editIndex && scope.row.status !== 'STOPPED'"
                      v-en-style="'flex: 0 0 50px'"
                      class="col-name-update"
                      @click="handleConfigUpdate(scope.row)"
                    >
                      <span> {{ $t('升级') }} </span>
                    </span>
                  </div>
                </template>
                <template v-else-if="column.prop === 'status'">
                  <span
                    class="col-status"
                    :class="'status-' + scope.row.status"
                    :style="{ color: ['PREPARING', 'STOPPED'].includes(scope.row.status) ? '#C4C6CC' : '#63656E' }"
                  >
                    <img
                      src="../../static/images/svg/spinner.svg"
                      v-if="scope.row.doingStatus"
                      class="status-loading"
                      alt=''
                    >
                    <div
                      v-if="['FAILED', 'WARNING', 'SUCCESS', 'STOPPED'].includes(scope.row.taskStatus)"
                      class="col-status-circle"
                      :style="{
                        backgroundColor: startedBack[scope.row.taskStatus],
                        borderColor: startedBorder[scope.row.taskStatus]
                      }"
                    />
                    <span
                      :class="{ 'pointer-active': !['PREPARING', 'STOPPED'].includes(scope.row.status) }"
                      @click="!['PREPARING', 'STOPPED'].includes(scope.row.status) && handleCheckStatus(scope.row)"
                    >{{ scope.row.statusName }}</span>
                  </span>
                </template>
                <template v-else-if="column.prop === 'targetString'">
                  <span class="col-target">
                    {{ scope.row.status === 'PREPARING' ? '--' : scope.row.targetString || '--' }}
                  </span>
                </template>
                <template v-else-if="column.prop === 'updateUser'">
                  <div class="col-update-log">
                    <div class="col-update-log-label">
                      {{ scope.row.updateUser || '--' }}
                    </div>
                    <div>{{ scope.row.updateTime || '--' }}</div>
                  </div>
                </template>
                <template v-else>
                  {{ scope.row[column.prop] }}
                </template>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('操作')"
              :width="$store.getters.lang === 'en' ? '300' : '260'"
            >
              <template slot-scope="scope">
                <div class="col-operator">
                  <span
                    v-if="scope.row.bizId === bizId"
                    v-authority="{
                      active: !authority.MANAGE_AUTH && !(scope.row.taskStatus === 'STOPPED' || scope.row.doingStatus)
                    }"
                    class="col-operator-btn"
                    :class="{ 'btn-disabled': scope.row.taskStatus === 'STOPPED' || scope.row.doingStatus }"
                    @click="
                      authority.MANAGE_AUTH || scope.row.taskStatus === 'STOPPED' || scope.row.doingStatus
                        ? scope.row.taskStatus !== 'STOPPED' && !scope.row.doingStatus && handleUpdateTarget(scope.row)
                        : handleShowAuthorityDetail()
                    "
                  >
                    {{ $t('增删目标') }}
                  </span>
                  <span
                    v-authority="{
                      active: !authority.MANAGE_AUTH && !(scope.row.taskStatus === 'STOPPED' || scope.row.doingStatus)
                    }"
                    class="col-operator-btn"
                    :class="{ 'btn-disabled': scope.row.taskStatus === 'STOPPED' }"
                    @click="scope.row.taskStatus !== 'STOPPED' && handleCheckView(scope.row)"
                  >
                    {{ $t('可视化') }}
                    <span
                      style="min-width: 23px; color: #ea3636"
                      :style="!!scope.row.errorNum ? 'visibility: visible;' : 'visibility: hidden;'"
                    >({{ scope.row.errorNum }})</span>
                  </span>
                  <span
                    v-if="scope.row.bizId === bizId"
                    class="col-operator-btn"
                    v-authority="{
                      active: !authority.MANAGE_AUTH && !(scope.row.taskStatus === 'STOPPED' || scope.row.doingStatus)
                    }"
                    @click="scope.row.taskStatus !== 'STOPPED' && handleShowAdd('edit', scope.row)"
                    :class="{ 'btn-disabled': scope.row.taskStatus === 'STOPPED' }"
                  >
                    {{ $t('编辑') }}
                  </span>
                  <span
                    v-if="scope.row.bizId === bizId"
                    v-authority="{ active: !authority.MANAGE_AUTH && !scope.row.doingStatus }"
                    class="col-operator-more"
                    data-popover="true"
                    :ref="'operator-' + scope.$index"
                    :class="{
                      'operator-active': popover.hover === scope.$index,
                      'btn-disabled': scope.row.doingStatus
                    }"
                    @click="
                      authority.MANAGE_AUTH || scope.row.doingStatus
                        ? !scope.row.doingStatus && handleOperatorOver(scope.row, $event, scope.$index)
                        : handleShowAuthorityDetail()
                    "
                  >
                    <i
                      data-popover="true"
                      class="bk-icon icon-more"
                    />
                  </span>
                </div>
              </template>
            </bk-table-column>
            <bk-table-column type="setting">
              <bk-table-setting-content
                :fields="table.columns"
                :selected="selectedColumns"
                :size="table.size"
                value-key="prop"
                @setting-change="handleSettingChange"
              />
            </bk-table-column>
          </bk-table>
          <bk-pagination
            v-if="isShowPagination"
            class="config-pagination"
            align="right"
            size="small"
            pagination-able
            :current="pagination.page"
            :limit="pagination.pageSize"
            :count="pagination.total"
            :limit-list="tableInstance.pageList"
            @change="handlePageChange"
            @limit-change="handleLimitChange"
            show-total-count
          />
        </div>
      </div>
    </div>
    <collector-config-detail
      :side-data="side.data"
      :side-show="side.show"
      @update-name="handleChangeCollectName"
      @edit-plugin="handleEditPlugin"
      @edit="handleToEdit"
      @set-hide="handleSideHidden"
    />
    <bk-dialog
      v-model="dialog.update.show"
      :show-footer="false"
      width="850"
    >
      <collector-config-update
        v-if="dialog.update.params"
        :update-params="dialog.update.params"
        @on-submit="handleOpenUpgradePage"
        @close-update="handleCloseUpdate"
      />
    </bk-dialog>
    <bk-dialog
      v-model="dialog.delete.show"
      :show-footer="false"
    >
      <div class="dialog-del">
        <div class="dialog-del-title">
          {{ $t('确定删除该采集配置？') }}
        </div>
        <div class="dialog-del-content">
          {{ $t('删除该采集配置后将无法撤消！') }}
        </div>
        <div class="dialog-del-footer">
          <bk-button
            theme="primary"
            class="footer-btn"
            :loading="dialog.delete.loading"
            @click="handleSubmitDelete"
            style="margin-right: 10px"
          >
            {{ $t('确定') }}
          </bk-button>
          <bk-button
            @click="dialog.delete.show = false"
            class="footer-btn"
          >
            {{ $t('取消') }}
          </bk-button>
        </div>
      </div>
    </bk-dialog>
    <div v-show="false">
      <div
        class="operator-group"
        ref="operatorGroup"
      >
        <span
          class="operator-group-btn"
          @click="handleDeleteRow"
        >
          {{ $t('删除') }}
        </span>
        <span
          class="operator-group-btn"
          @click="handleOpenOrClose"
        >{{ popover.status === 'STOPPED' ? $t('启用') : $t('停用') }}</span>
        <span
          class="operator-group-btn"
          @click="handleCloneConfig"
        >
          {{ $t('克隆') }}
        </span>
      </div>
    </div>
    <delete-collector
      :collector-task-data="collectorTaskData"
      :show.sync="delDialogShow"
    />
  </div>
</template>
<script>
import { createNamespacedHelpers } from 'vuex';
import { addListener, removeListener } from '@blueking/fork-resize-detector';
// import { isCancel } from 'axios'
import { debounce } from 'throttle-debounce';

import {
  collectConfigList,
  deleteCollectConfig,
  // cloneCollectConfig,
  fetchCollectConfigStat
} from '../../../monitor-api/modules/collecting';
import introduce from '../../common/introduce';
import { commonPageSizeMixin } from '../../common/mixins';
import EmptyStatus from '../../components/empty-status/empty-status.tsx';
import GuidePage from '../../components/guide-page/guide-page';
import pageTips from '../../components/pageTips/pageTips';
import authorityMixinCreate from '../../mixins/authorityMixin';
import { SET_ADD_DATA, SET_ADD_MODE, SET_OBJECT_TYPE } from '../../store/modules/collector-config';

import CollectorConfigDetail from './collector-config-detail/collector-config-detail';
import CollectorConfigUpdate from './collector-config-update/collector-config-update';
import DeleteCollector from './collector-dialog-delete/collector-dialog-delete';
import * as collectAuth from './authority-map';
import TableStore from './store.ts';

const { mapMutations } = createNamespacedHelpers('collector-config');
export default {
  name: 'CollectorConfig',
  components: {
    CollectorConfigDetail,
    CollectorConfigUpdate,
    DeleteCollector,
    pageTips,
    EmptyStatus,
    GuidePage
  },
  mixins: [commonPageSizeMixin, authorityMixinCreate(collectAuth)],
  provide() {
    return {
      authority: this.authority,
      handleShowAuthorityDetail: this.handleShowAuthorityDetail
    };
  },
  data() {
    return {
      loading: false,
      tableInstance: {},
      panel: {
        active: 0,
        itemActive: '',
        keyword: '',
        handleSearch() {}
      },
      topology: {
        show: false
      },
      table: {
        data: [],
        statusMap: [],
        loading: false,
        hoverIndex: -1,
        editIndex: -1,
        columns: [
          { label: 'ID', prop: 'id', show: true, width: 70, sortable: true },
          { label: this.$tc('名称'), prop: 'name', show: true, minWidth: 150, tooltip: true },
          { label: this.$tc('所属'), prop: 'space_name', show: false, minWidth: 90 },
          { label: this.$tc('方式'), prop: 'collectName', show: true, width: 100 },
          { label: this.$tc('运行状态'), prop: 'status', show: true, width: 140 },
          { label: this.$tc('对象'), prop: 'objectLabel', show: true, minWidth: 150 },
          { label: this.$tc('目标'), prop: 'targetString', show: true, minWidth: 180, tooltip: true },
          { label: this.$tc('更新记录'), prop: 'updateUser', show: true, width: 180, tooltip: true }
        ],
        size: 'small'
      },
      popover: {
        instance: null,
        hover: -1,
        edit: false,
        status: '',
        data: {}
      },
      view: {
        show: false
      },
      addAndDel: {
        show: false
      },
      dialog: {
        delete: {
          show: false,
          loading: false
        },
        update: {
          show: false,
          params: null,
          data: null
        }
      },
      side: {
        pluginId: '',
        show: false,
        data: null
      },
      headTitle: null,
      headBack: null,
      add: {
        show: false,
        mode: 'add',
        data: {}
      },
      stopStart: {
        show: false,
        type: 'STOPPED',
        upgradeParams: {}
      },
      lisenResize: null,
      timer: null,
      startedBack: {
        SUCCESS: '#94F5A4',
        WARNING: '#FFD695',
        FAILED: '#FD9C9C',
        STOPPED: '#F0F1F5'
      },
      startedBorder: {
        SUCCESS: '#2DCB56',
        WARNING: '#FF9C01',
        FAILED: '#EA3636',
        STOPPED: '#C4C6CC'
      },
      isLeave: false,
      filterEnterRouter: [
        'service-classify',
        'plugin-manager',
        'plugin-edit',
        'export-configuration',
        'custom-scenes',
        'custom-scenes-view'
      ],
      cancelFetch: null,
      delDialogShow: false,
      collectorTaskData: {
        status: 'STARTED',
        id: ''
      },
      // 表格分页数据
      pagination: {
        page: 1,
        pageSize: +localStorage.getItem('__common_page_size__') || 10,
        total: 0
      },
      // 头部筛选卡片数据
      filterTabList: [],
      // 页面出现loading延时
      delayLoading: false,
      // 空状态
      emptyType: 'empty'
    };
  },
  computed: {
    selectedColumns() {
      return this.table.columns.filter(item => item.show);
    },
    bizId() {
      return this.$store.getters.bizId;
    },
    activeTabItem() {
      return this.filterTabList[this.panel.active] || {};
    },
    tabItemMap() {
      return this.tableInstance.tabItemMap || {};
    },
    retrievalUrl() {
      if (process.env.NODE_ENV === 'development') {
        return `${process.env.loginHost}/t/log-search-4#/manage/collect?bizId=${this.bizId}`;
      }
      return `${this.$store.getters.bkLogSearchUrl}#/manage/collect?bizId=${this.bizId}`;
    },
    /** 是否展示分页 */
    isShowPagination() {
      const { total } = this.pagination;
      return !!total;
    },
    /** 列表接口search字段给的搜索条件 */
    getSearchOfParams() {
      const search = {};
      /** 采集分类 */
      if (this.filterTabList.length) {
        const collectType = this.filterTabList[this.panel.active];
        collectType.key !== 'All' && (search.collect_type = collectType.key);
      }
      /** 采集状态
       * startedNum 启用
       * stoppedNum 停用
       * errTargetNum 异常
       * needUpdateNum 待更新
       */
      const status = this.panel.itemActive;
      if (status) {
        switch (status) {
          case 'needUpdateNum':
            search.need_upgrade = 'true';
            break;
          case 'errTargetNum':
            search.task_status = 'WARNING';
            break;
          case 'startedNum':
            search.status = 'STARTED';
            break;
          case 'stoppedNum':
            search.status = 'STOPPED';
            break;
          default:
            break;
        }
      }
      /** 搜索条件 */
      const keywork = this.panel.keyword?.trim?.() || '';
      if (keywork) {
        const pluginIdKey = this.$t('插件ID:');
        const idKey = this.$t('ID:');
        const pluginId = keywork.match(pluginIdKey);
        const id = keywork.match(idKey);
        switch (pluginId?.[0] || id?.[0]) {
          case pluginIdKey:
            search.plugin_id = keywork.replace(pluginIdKey, '');
            break;
          case idKey:
            search.id = keywork.replace(idKey, '');
            break;
          default:
            search.fuzzy = keywork;
            break;
        }
      }
      return search;
    },
    curIntroduceData() {
      return introduce.data['collect-config'].introduce;
    },
    // 是否显示引导页
    showGuidePage() {
      return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
    }
  },
  watch: {
    delDialogShow(bool) {
      if (!bool) {
        this.getCollectionConfigList(false, true);
      }
    },
    loading(val) {
      setTimeout(() => (this.delayLoading = val ? this.loading : false), 200);
    }
  },
  created() {
    this.handleSearch = debounce(300, this.handleKeywordChange);
    this.lisenResize = debounce(100, this.handleTableWrapperChange);
  },
  activated() {
    this.isLeave = false;
    setTimeout(() => {
      !this.loading && this.initPageData();
    }, 50);
  },
  deactivated() {
    this.isLeave = true;
    this.timer && window.clearTimeout(this.timer);
    this.timer = 0;
  },
  beforeRouteEnter(to, from, next) {
    next((vm) => {
      if (vm.showGuidePage) {
        vm.loading = false;
        return;
      }
      if (
        ![
          'collect-config-view',
          'collect-config-add',
          'collect-config-edit',
          'collect-config-node',
          'collect-config-update',
          'collect-config-operate-detail'
        ].includes(from.name)
      ) {
        vm.panel.keyword = '';
        vm.panel.active = 0;
        vm.panel.itemActive = '';
      }
      if (to.query.id) {
        vm.panel.keyword = `ID：${to.query.id}`;
      }
      if (vm.filterEnterRouter.includes(from.name)) {
        if (to.params.serviceCategory) {
          vm.panel.keyword = vm.$t('分类') + to.params.serviceCategory;
        } else if (to.params.pluginId) {
          vm.panel.keyword = vm.$t('插件ID:') + to.params.pluginId;
        }
        if (vm.tableInstance) {
          vm.tableInstance.keyword = vm.panel.keword;
        }
      }
      if (!vm.loading) {
        vm.initPageData();
      }
    });
  },
  beforeRouteLeave(to, from, next) {
    typeof this.cancelFetch === 'function' && this.cancelFetch();
    this.side.show = false;
    next();
  },
  mounted() {
    this.$refs.tableWrapper && addListener(this.$refs.tableWrapper, this.lisenResize);
  },
  beforeDestroy() {
    this.isLeave = true;
    this.$refs.tableWrapper && removeListener(this.$refs.tableWrapper, this.lisenResize);
    this.timer && window.clearTimeout(this.timer);
  },
  errorCaptured() {
    this.timer && window.clearTimeout(this.timer);
  },
  methods: {
    ...mapMutations([SET_ADD_DATA, SET_ADD_MODE, SET_OBJECT_TYPE]),
    /**
     * @description: 初始化页面数据
     * 切换采集类型和采集状态时也需要初始化数据
     * 更新筛选的统计数据和列表数据
     */
    initPageData() {
      this.pagination.page = 1;
      const promiseList = [
        /** 统计数据 */
        this.fetchCollectConfigStat(),
        /** 当前分页数据 */
        this.getCollectionConfigListProxy()
      ];
      this.loading = true;
      Promise.all(promiseList).finally(() => {
        this.loading = false;
        /** 带采集id进入页面打开详情侧栏 */
        if (this.$route.query.id && this.table.data.length) {
          const [{ id, name, status }] = this.table.data;
          const params = { id, name, status };
          this.handleShowDetail(params);
        }
      });
    },
    /**
     * @description: 初始化页面数据时更新状态轮询间隔为1s，只执行一次
     */
    getCollectionConfigListProxy() {
      return this.getCollectionConfigList(false, false, false).then(() => {
        const timer = setTimeout(() => {
          this.getCollectionConfigList(true);
          clearTimeout(timer);
        }, 1000);
      });
    },
    /**
     * @description: 获取采集列表头部过滤筛选操作栏的统计信息
     */
    fetchCollectConfigStat() {
      return fetchCollectConfigStat().then((res) => {
        this.filterTabList = [];
        this.filterTabList = this.getFilterTabList(res);
      });
    },
    /**
     * @description: 获取采集列表分页数据
     * @param {*} status 是否为刷新数据状态
     * @param {*} needLoading 是否需要页面loading
     * @param {*} needPolling 成功执行后是否继续轮询
     * @return {*}
     */
    getCollectionConfigList(status = false, needLoading = false, needPolling = true) {
      const params = {
        search: this.getSearchOfParams,
        page: this.pagination.page,
        limit: this.pagination.pageSize
      };
      this.emptyType = this.getSearchOfParams?.fuzzy ? 'search-empty' : 'empty';
      needLoading && (this.loading = true);
      /** 取消pendding的请求 */
      typeof this.cancelFetch === 'function' && this.cancelFetch();
      if (this.timer) {
        clearTimeout(this.timer);
        this.timer = null;
      }
      return collectConfigList(
        {
          bk_biz_id: this.bizId,
          refresh_status: status,
          order: '-create_time',
          ...params
        },
        {
          needRes: true,
          needMessage: false,
          needCancel: true,
          cancelFn: c => (this.cancelFetch = c.bind(this, 'cancelFetch'))
        }
      )
        .then((res) => {
          const data = res.data || { config_list: [], total: 0, type_list: [] };
          this.pagination.total = data.total;
          this.tableInstance = new TableStore(data, this.$store.getters.bizList);
          const tableData = this.tableInstance.getTableAllData();
          this.table.data = this.getTargetString(tableData);
          if (!this.isLeave && needPolling) {
            this.timer = setTimeout(() => {
              this.getCollectionConfigList(true);
            }, 5000);
          }
          return data;
        })
        .catch((err) => {
          console.error(err);
          this.emptyType = '500';
        })
        .finally(() => (this.loading = false));
    },
    /**
     * @description: 处理头部筛选tab的展示数据
     * @param {*} typeList 后端返回的类型统计数据
     */
    getFilterTabList(typeList = []) {
      let tabData = [
        {
          data: {
            startedNum: 0,
            stoppedNum: 0,
            errTargetNum: 0,
            needUpdateNum: 0
          },
          total: 0,
          key: 'All',
          name: this.$t('全部')
        }
      ];
      const itemOfAll = tabData.find(item => item.key === 'All');
      typeList.forEach((item) => {
        const {
          STARTED: startedNum = 0, // 已启用
          STOPPED: stoppedNum = 0, // 已停用
          WARNING: errTargetNum = 0, // 异常
          need_upgrade: needUpdateNum = 0 // 待升级
        } = item.nums;
        if (item.id !== 'log' && item.id !== 'Built-In') {
          const tabItem = {
            data: {
              startedNum,
              stoppedNum,
              errTargetNum,
              needUpdateNum
            },
            total: startedNum + stoppedNum,
            key: item.id,
            name: item.name
          };
          itemOfAll.data.startedNum += startedNum;
          itemOfAll.data.stoppedNum += stoppedNum;
          itemOfAll.data.errTargetNum += errTargetNum;
          itemOfAll.data.needUpdateNum += needUpdateNum;
          itemOfAll.total += tabItem.total;
          tabData.push(tabItem);
        }
      });
      tabData = tabData.sort((a, b) => b.total - a.total);
      return tabData;
    },
    getTargetString(tableData) {
      const textMap = {
        TOPO: '{0}个拓扑节点',
        SERVICE_TEMPLATE: '{0}个服务模板',
        SET_TEMPLATE: '{0}个集群模板'
      };
      tableData.forEach((item) => {
        if (item.objectTypeEn === 'HOST') {
          if (['SERVICE_TEMPLATE', 'SET_TEMPLATE', 'TOPO'].includes(item.nodeType)) {
            // eslint-disable-next-line vue/max-len
            item.targetString = `${this.$t(textMap[item.nodeType], [item.targetNodesCount])} （${this.$t(
              '共{0}台主机',
              [item.totalInstanceCount]
            )}）`;
          } else if (item.nodeType === 'INSTANCE') {
            item.targetString = this.$t('{0}台主机', [item.totalInstanceCount]);
          }
        } else if (item.objectTypeEn === 'SERVICE') {
          if (['SERVICE_TEMPLATE', 'SET_TEMPLATE', 'TOPO'].includes(item.nodeType)) {
            // eslint-disable-next-line vue/max-len
            item.targetString = `${this.$t(textMap[item.nodeType], [item.targetNodesCount])} （${this.$t(
              '共{0}个实例',
              [item.totalInstanceCount]
            )}）`;
          }
        }
      });
      return tableData;
    },
    /**
     * @description: 切换采集状态
     * @param {*} key
     */
    handleTabNumClick(key) {
      if (this.panel.keyword) {
        this.panel.keyword = '';
      }
      this.panel.itemActive = key === this.panel.itemActive ? '' : key;
      this.pagination.page = 1;
      const tempIndex = this.panel.active;
      const tempPage = this.pagination.page;
      this.getCollectionConfigList(false, true).catch((err) => {
        this.panel.active = tempIndex;
        this.pagination.page = tempPage;
        console.log(err);
      });
    },
    handleTableDataChange(v, needLoading = true) {
      this.table.loading = needLoading;
      setTimeout(() => {
        v.forEach((item, index) => {
          const ref = this.$refs[`table-row-${index}`];
          item.overflow = ref && ref.clientHeight > 32;
        });
        this.table.loading = false;
      }, 50);
    },
    handleOperatorOver(data, e, index) {
      if (this.popover.index === index) {
        return;
      }
      this.popover.hover = index;
      this.popover.edit = data.needUpdate;
      this.popover.status = data.status;
      this.popover.data = data;
      this.popover.collectType = data.collectType;
      if (!this.popover.instance) {
        this.popover.instance = this.$bkPopover(e.target, {
          content: this.$refs.operatorGroup,
          arrow: false,
          trigger: 'manual',
          placement: 'bottom',
          theme: 'light common-monitor',
          maxWidth: 520,
          duration: [275, 0],
          onHidden: () => {
            this.popover.instance.destroy();
            this.popover.hover = -1;
            this.popover.instance = null;
          }
        });
      } else {
        this.popover.instance.reference = e.target;
      }
      this.popover?.instance?.show?.(100);
    },
    // 提示升级的弹窗
    updataInfo(data) {
      const h = this.$createElement;
      const deleteInfoInstance = this.$bkInfo({
        title: this.$t('插件已变更，请先升级'),
        type: 'warning',
        showFooter: false,
        maskClose: true,
        escClose: true,
        extCls: 'dialog-delete',
        subHeader: h(
          'div',
          {
            class: {
              'dialog-delete-content': true
            },
            on: {
              click: () => {
                this.handleConfigUpdate(data);
                deleteInfoInstance.close();
              }
            }
          },
          this.$t('前去升级配置')
        )
      });
    },
    handleUpdateTarget(data) {
      if (data.needUpdate) {
        this.updataInfo(data);
        return false;
      }
      // 更新采集对象组的类型
      this[SET_OBJECT_TYPE](data.objectTypeEn);
      this.$router.push({
        name: 'collect-config-node',
        params: {
          id: data.id
        }
      });
    },
    handleCheckView(data) {
      this.$router.push({
        name: 'collect-config-view',
        params: {
          id: data.id,
          title: data.name
        },
        query: {
          name: data.name,
          customQuery: JSON.stringify({
            pluginId: data.updateParams.pluginId,
            bizId: data.bizId
          })
        }
      });
    },
    handleConfigUpdate(data) {
      if (data.doingStatus) {
        this.$bkNotify({
          title: this.$t('配置升级'),
          message: this.$t('正在执行中的配置暂不能升级'),
          theme: 'warning',
          offsetY: 80,
          position: 'bottom-left'
        });
      } else {
        const { update } = this.dialog;
        update.show = true;
        update.params = data.updateParams;
        update.data = data;
      }
    },
    handleShowDetail({ id /*  name, status */ }) {
      // this.side.data = { id, name, status };
      // this.side.show = true;
      this.$router.push({
        name: 'collect-config-detail',
        params: {
          id
        }
      });
    },
    handleChangeCollectName(id, name) {
      const curCollect = this.table.data.find(item => item.id === id);
      curCollect && (curCollect.name = name);
    },
    handleShowAdd(mode, data) {
      if (mode === 'edit' && !!data) this.popover.data = data;
      this[SET_ADD_MODE](mode);
      if (mode === 'edit' && this.popover.data.needUpdate) {
        this.updataInfo(this.popover.data);
        return false;
      }
      const params = { title: mode === 'edit' ? this.popover.data.name : this.$t('新建配置') };
      if (mode === 'edit') {
        this[SET_ADD_DATA](this.popover.data);
        params.id = this.popover.data.id;
        params.pluginId = this.popover.data.updateParams.pluginId;
      }
      if (this.panel.active > 0 && mode === 'add') {
        params.pluginType = this.filterTabList[this.panel.active].name;
        if (params.pluginType === 'Process') {
          params.objectId = 'host_process';
        }
      }
      this.$router.push({
        name: mode === 'edit' ? 'collect-config-edit' : 'collect-config-add',
        params
      });
    },
    handleTargetChange() {
      this.targetPage.show = false;
    },
    /**
     * @description: 分页操作
     * @param {*} page 当前页
     */
    handlePageChange(page) {
      const temp = this.pagination.page;
      this.pagination.page = page;
      this.getCollectionConfigList(false, true).catch((err) => {
        if (err.message !== 'cancelFetch') {
          this.pagination.page = temp;
        }
      });
    },
    /**
     * @description: 切换分页数量
     * @param {*} limit 每页数量
     */
    handleLimitChange(limit) {
      const tempPage = this.pagination.page;
      const tempPageSize = this.pagination.pageSize;
      this.pagination.page = 1;
      this.pagination.pageSize = limit;
      this.getCollectionConfigList(false, true).catch(() => {
        this.pagination.page = tempPage;
        this.pagination.pageSize = tempPageSize;
      });
    },
    /**
     * @description: tab切换采集类型
     * @param {*} index 索引
     */
    handleTabItemClick(index) {
      if (this.panel.keyword) {
        this.panel.keyword = '';
      }
      this.panel.active = index;
      this.pagination.page = 1;
      const tempIndex = this.panel.active;
      const tempPage = this.pagination.page;
      this.getCollectionConfigList(false, true).catch((err) => {
        this.panel.active = tempIndex;
        this.pagination.page = tempPage;
        console.log(err);
      });
    },
    /**
     * @description: 发起搜索请求
     */
    handleKeywordChange() {
      this.getCollectionConfigList(false, true);
    },
    handleTableWrapperChange() {
      this.table.data.length && this.handleTableDataChange(this.table.data, false);
    },
    handleSideHidden() {
      this.side.show = false;
    },
    handleCloseUpdate(v) {
      const { update } = this.dialog;
      update.show = false;
      if (v && update.data) {
        update.data.needUpdate = false;
        const allItem = this.filterTabList.find(item => item.key === 'All');
        const curItem = this.filterTabList.find(item => item.key === update.data.collectType);
        allItem.data.needUpdateNum -= 1;
        curItem.data.needUpdateNum -= 1;
      }
      update.data = null;
    },
    handleDeleteRow() {
      const { data } = this.popover;
      this.collectorTaskData.status = data.status;
      this.collectorTaskData.id = data.id;
      this.collectorTaskData.name = data.name;
      this.delDialogShow = true;
      //   const { data } = this.popover
      //   if (data.status === 'STOPPED') {
      //     const deleteData = this.dialog.delete
      //     deleteData.show = true
      //   } else if (data.status === 'STARTED') {
      //     const h = this.$createElement
      //     const deleteInfoInstance = this.$bkInfo({
      //       title: this.$t('仅可删除已停用的配置'),
      //       type: 'warning',
      //       showFooter: false,
      //       maskClose: true,
      //       escClose: true,
      //       extCls: 'dialog-delete',
      //       subHeader: h('div', {
      //         class: {
      //           'dialog-delete-content': true
      //         },
      //         on: {
      //           click: () => {
      //             this.handleOpenOrClose()
      //             deleteInfoInstance.close()
      //           }
      //         }
      //       }, this.$t('前往停用配置'))
      //     })
      //   }
    },
    // 克隆采集配置
    handleCloneConfig() {
      this.$router.push({
        name: 'collect-config-clone',
        params: {
          id: this.popover.data.id,
          pluginId: this.popover.data.updateParams.pluginId
        }
      });
    },
    handleSubmitDelete() {
      const deleteData = this.dialog.delete;
      deleteData.loading = true;
      deleteCollectConfig({
        id: this.popover.data.id
      })
        .then(() => {
          this.tableInstance.deleteDataById(this.popover.data.id);
          this.table.data = this.tableInstance.getTableData(
            this.filterTabList[this.panel.active].key,
            this.panel.itemActive
          );
          this.handleTableDataChange(this.table.data);
          this.$bkMessage({
            theme: 'success',
            message: this.$t('删除成功')
          });
        })
        .finally(() => {
          deleteData.loading = false;
          deleteData.show = false;
        });
    },
    handleOpenOrClose() {
      const { data } = this.popover;
      this.stopStart.type = data.status;
      this.$router.push({
        name: 'collect-config-update',
        params: {
          data,
          stopStart: this.stopStart
        }
      });
    },
    handleOpenUpgradePage(params) {
      this.dialog.update.show = false;
      this.popover.data = this.dialog.update.data;
      this.stopStart.params = params;
      this.stopStart.type = 'UPGRADE';
      this.$router.push({
        name: 'collect-config-update',
        params: {
          data: this.dialog.update.data,
          stopStart: this.stopStart,
          id: this.dialog.update.data.id
        }
      });
    },
    handleCheckStatus(row) {
      if (row.status !== 'STOPPED') {
        this.$router.push({
          name: 'collect-config-operate-detail',
          params: {
            id: row.id,
            title: row.name,
            taskStatus: row.taskStatus
          }
        });
      }
    },
    handleStoppedRow({ row }) {
      if (row.taskStatus === 'STOPPED') {
        return {
          background: '#FAFBFD',
          color: '#C4C6CC'
        };
      }
    },
    handleToEdit(id) {
      this.side.show = false;
      this.table.data.forEach((item) => {
        if (item.id === id) {
          this.popover.data = item;
        }
      });
      this.handleShowAdd('edit');
    },
    handleEditPlugin(data) {
      this.handleSideHidden();
      this.$router.push({
        name: 'plugin-edit',
        params: {
          title: `${this.$t('编辑插件')} ${data.plugin_id}`,
          pluginId: data.plugin_id
        }
      });
    },
    handleToLogCollection() {
      window.open(this.retrievalUrl, '_blank');
    },
    /**
     * @description: 表格排序
     * @param {*} order
     * @param {*} prop
     * @return {*}
     */
    handleSortChange({ order, prop }) {
      this.tableInstance.sortOrder = order;
      this.tableInstance.sortProp = prop;
      this.table.data = this.tableInstance.getTableAllData();
    },
    /** 空状态操作 */
    handleEmptyOperation(type) {
      if (type === 'refresh') {
        this.getCollectionConfigList(false, true);
        return;
      }
      if (type === 'clear-filter') {
        this.panel.keyword = '';
        this.getCollectionConfigList(false, true);
        return;
      }
    },
    /**
     * 表格设置发生变化时的事件
     * @param {*} param fields: 变化列 size: 变化大小
     */
    handleSettingChange({ fields, size }) {
      this.table.size = size;
      this.table.columns.forEach((column) => {
        column.show = fields.some(item => item.prop === column.prop);
      });
    }
  }
};
</script>
<style
  lang="scss"
  scoped
>
.mr-6 {
  margin-right: 6px;
}

.collector-config {
  margin: 24px;
  font-size: 12px;

  &-panel {
    height: 170px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px 2px 0 0;

    .panel-tab {
      padding: 0;
      margin: 0;
      background: #fafbfd;

      &-item {
        display: flex;
        flex: 0 0 auto;
        align-items: center;
        justify-content: center;
        min-width: 140px;
        height: 54px;
        font-size: 14px;
        color: #63656e;
        // border-bottom: 1px solid #dcdee5;
        // border-right: 1px solid #fafbfd;
        cursor: pointer;

        .tab-name {
          margin-right: 6px;
          font-weight: bold;
        }

        &:hover {
          .tab-name {
            color: #3a84ff;
            cursor: pointer;
          }
        }

        .tab-mark {
          display: flex;
          align-items: center;
          justify-content: center;
          min-width: 24px;
          height: 16px;
          padding: 0px 4px;
          font-size: 12px;
          line-height: 14px;
          color: #fff;
          background: #c4c6cc;
          border-radius: 12px;
        }

        &.tab-active {
          color: #3a84ff;
          background: #fff;
          border-right-color: #dcdee5;
          border-bottom-color: transparent;

          .tab-mark {
            color: #fff;
            background: #3a84ff;
          }
        }

        &:first-child {
          /* stylelint-disable-next-line declaration-no-important */
          border-left-color: transparent !important;
        }
      }

      :deep(.bk-tab-header) {
        /* stylelint-disable-next-line declaration-no-important */
        background-image: linear-gradient(transparent 53px, rgb(220, 222, 229) 1px) !important;
        border: 0;
      }

      :deep(.bk-tab-section) {
        display: none;
      }

      :deep(.bk-tab-label-item) {
        padding: 0;
        border-right: 0;

        &.active {
          border-right: 1px solid #dcdee5;
          border-left: 1px solid #dcdee5;
        }

        &:nth-of-type(1) {
          &.active {
            border-left: 0;
          }
        }
      }

      &-blank {
        flex: 1;
        height: 54px;
        border-bottom: 1px solid #dcdee5;
      }
    }

    .panel-content {
      display: flex;
      align-items: center;
      height: 115px;
      border: 1px solid transparent;
      border-bottom-color: #dcdee5;

      &-item {
        position: relative;
        display: flex;
        flex: 1;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 115px;
        cursor: pointer;
        border-bottom: 2px solid transparent;

        &:hover {
          border-bottom-color: #3a84ff;
        }

        &.active-num {
          border-bottom-color: #3a84ff;
        }

        &:not(:last-child):after {
          position: absolute;
          top: 31px;
          right: 0;
          width: 1px;
          height: 53px;
          content: ' ';
          background: #dcdee5;
        }

        .content-num {
          font-size: 32px;
          color: #313238;
        }

        .content-desc {
          color: #979ba5;
        }
      }
    }
  }

  &-tool {
    display: flex;
    align-items: center;
    height: 60px;

    .tool-btn {
      margin-right: auto;
    }

    .tool-search {
      width: 360px;
    }

    .tool-icon {
      width: 32px;
      height: 32px;
      font-size: 32px;
      line-height: 32px;
      color: #979ba5;
      text-align: center;
      cursor: pointer;
      border: 1px solid #c4c6cc;
      border-radius: 2px;
    }
  }

  &-table {
    display: flex;

    .config-topology {
      flex: 0 0 240px;
      border: 1px solid #dcdee5;
      border-right: 0;
      border-radius: 0px 0 0 2px;
    }

    .table-wrap {
      flex: 1;
      width: calc(100% - 240px);

      .config-table {
        overflow: visible;
        color: #63656e;

        .col-name {
          display: flex;
          align-items: center;
          line-height: 26px;
          color: #3a84ff;
          cursor: pointer;

          &-update {
            display: flex;
            flex: 0 0 32px;
            align-items: center;
            justify-content: center;
            height: 16px;
            margin-left: 5px;
            color: #fff;
            background: #ff9c01;
            border-radius: 2px;

            span {
              *font-size: 10px;
              transform: scale(.83, .83);
            }
          }

          &-desc {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          &-icon {
            font-size: 24px;
          }
        }

        .col-update-log {
          display: flex;
          flex-direction: column;
          justify-content: center;
          height: 58px;

          &-label {
            margin-bottom: 3px;
          }
        }

        .col-status {
          display: flex;
          align-items: center;

          .pointer-active {
            &:hover {
              color: #3a84ff;
              cursor: pointer;
            }
          }

          .status-loading {
            width: 16px;
            height: 16px;
            margin-right: 6px;
            margin-left: -4px;
          }
        }

        .col-status-circle {
          width: 8px;
          height: 8px;
          margin-right: 10px;
          border: 1px solid;
          border-radius: 50%;
        }

        .col-classifiy {
          position: relative;
          height: 30px;

          &-wrap {
            margin-right: 25px;
            overflow: hidden;

            .classifiy-label {
              float: left;
              padding: 2px 6px;
              margin: 6px;
              font-size: 12px;
              // &:first-child{
              //     margin-left: 0;
              // }
              background: #f0f1f5;
              // .label-name {
              //     display: inline-block;
              //     height: 24px;
              //     line-height: 24px;
              //     padding: 0 7px;
              //     text-align: center;
              //     &:first-child {
              //        border-right: 1px solid #DCDEE5;
              //        background: #FFFFFF;
              //     }
              // }
            }

            .classifiy-overflow {
              position: absolute;
              top: 0;
              float: left;
              height: 20px;
              padding: 2px 6px;
              margin: 6px 0;
              font-size: 12px;
              background: #f0f1f5;
            }
          }
        }

        .col-operator {
          display: flex;
          align-items: center;

          .btn-disabled {
            color: #c4c6cc;
            cursor: not-allowed;

            &:hover {
              cursor: not-allowed;
              background: transparent;
            }

            i {
              color: #c4c6cc;
            }
          }

          &-btn {
            margin-right: 12px;
            color: #3a84ff;
            cursor: pointer;
          }

          &-more {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            border-radius: 50%;

            .icon-more {
              font-size: 14px;
              color: #3a84ff;
            }

            &:hover {
              cursor: pointer;
              background: #ddd;
            }

            &.operator-active {
              background: #ddd;
            }
          }
        }
      }

      .config-pagination {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        height: 60px;
        padding: 0 20px;
        background: #fff;
        border: 1px solid #dcdee5;
        border-top: 0;

        :deep(.bk-page-count) {
          margin-right: auto;
        }
      }
    }
  }
}

.operator-group {
  display: flex;
  flex-direction: column;
  width: 68px;
  padding: 6px 0;
  font-size: 12px;
  color: #63656e;
  border: 1px solid #dcdee5;

  &-btn {
    display: flex;
    align-items: center;
    height: 32px;
    padding-left: 10px;
    background: #fff;

    &:hover {
      color: #3a84ff;
      cursor: pointer;
      background: #f0f1f5;
    }

    &.btn-disabled {
      color: #c4c6cc;
      cursor: not-allowed;

      /* stylelint-disable-next-line declaration-no-important */
      background: #fff !important;
    }
  }
}

.dialog-del {
  font-size: 12px;
  color: #63656e;
  text-align: center;

  &-title {
    height: 26px;
    margin-top: 17px;
    margin-bottom: 16px;
    font-size: 20px;
    color: #313238;
  }

  &-content {
    margin-bottom: 25px;
    text-align: center;
  }

  &-footer {
    margin-bottom: 14px;
    font-size: 0;
    text-align: center;

    .footer-btn {
      width: 86px;
      height: 32px;
      font-size: 12px;
    }
  }
}

.dialog-delete {
  .bk-dialog-content .bk-dialog-type-sub-header {
    padding-top: 0;
    padding-bottom: 40px;
  }

  &-content {
    margin-bottom: -3px;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
  }
}

.table-edit-disbaled {
  color: #c4c6cc;

  &:hover {
    color: #c4c6cc;
    cursor: not-allowed;
    background-color: #fff;
  }
}
</style>
