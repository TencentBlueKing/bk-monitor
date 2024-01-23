<!--
  - Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
  - Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
  - BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
  -
  - License for BK-LOG 蓝鲸日志平台:
  - -------------------------------------------------------------------
  -
  - Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  - documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  - the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
  - and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  - The above copyright notice and this permission notice shall be included in all copies or substantial
  - portions of the Software.
  -
  - THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
  - LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
  - NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
  - WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
  - SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
  -->

<template>
  <div class="retrieve-container">
    <!-- 检索页详情页 -->
    <div class="retrieve-detail-container">
      <result-header
        ref="resultHeader"
        :is-as-iframe="isAsIframe"
        :show-retrieve-condition="showRetrieveCondition"
        :retrieve-params="retrieveParams"
        :date-picker-value="datePickerValue"
        :index-set-item="indexSetItem"
        :is-show-collect="isShowCollect"
        :timezone="timezone"
        @shouldRetrieve="retrieveLog"
        @open="openRetrieveCondition"
        @update:datePickerValue="handleDateChange"
        @datePickerChange="retrieveWhenDateChange"
        @timezoneChange="handleTimezoneChange"
        @settingMenuClick="handleSettingMenuClick"
        @closeRetrieveCondition="closeRetrieveCondition"
        @updateCollectCondition="updateCollectCondition" />
      <div class="page-loading-wrap" v-if="basicLoading || tableLoading">
        <div class="page-loading-bar"></div>
      </div>
      <div class="result-content">
        <!-- 收藏列表 -->
        <collect-index
          :width.sync="collectWidth"
          :is-show.sync="isShowCollect"
          :favorite-loading="favoriteLoading"
          :favorite-list="favoriteList"
          :style="{ width: collectWidth + 'px' }"
          :active-favorite="activeFavorite"
          :active-favorite-i-d="activeFavoriteID"
          :visible-fields="visibleFields"
          @handleClick="handleClickFavoriteItem"
          @isRefreshFavorite="updateActiveFavoriteData"
          @favoriteDialogSubmit="handleSubmitFavorite"
          @requestFavoriteList="getFavoriteList" />
        <!-- 检索详情页左侧 -->
        <div v-show="showRetrieveCondition" class="retrieve-condition" :style="{ width: leftPanelWidth + 'px' }">
          <!-- 监控显示的 tab 切换 -->
          <!-- <div v-if="isAsIframe" class="bk-button-group">
          <bk-button @click="handleCheckMonitor">{{ $t('指标检索') }}</bk-button>
          <bk-button class="is-selected">{{ $t('日志检索') }}</bk-button>
          <bk-button @click="handleCheckEvent">{{ $t('事件检索') }}</bk-button>
        </div> -->

          <div class="king-tab" :class="isAsIframe && 'as-iframe'">
            <div class="tab-header">
              <span class="tab-title">
                <span>{{ isFavoriteNewSearch ? $t('新检索') : getFavoriteName }}</span>
                <span
                  v-show="!isFavoriteNewSearch"
                  class="bk-icon icon-edit-line"
                  @click="handleEditFavorite">
                </span>
              </span>
            </div>
            <div class="tab-content" :style="`height:calc(100% - ${isAsIframe ? 60 : 108}px);`">
              <div class="tab-content-item" data-test-id="retrieve_div_dataQueryBox">
                <!-- 选择索引集 -->
                <div class="tab-item-title">{{ $t('索引集') }}</div>
                <select-indexSet
                  :index-id="indexId"
                  :index-set-list="indexSetList"
                  :basic-loading.sync="basicLoading"
                  @selected="handleSelectIndex"
                  @updateIndexSetList="updateIndexSetList" />
                <search-comp
                  ref="searchCompRef"
                  :index-id="indexId"
                  :table-loading="tableLoading"
                  :is-auto-query="isAutoQuery"
                  :index-set-list="indexSetList"
                  :is-search-allowed="isSearchAllowed"
                  :active-favorite-i-d="activeFavoriteID"
                  :is-sql-search-type="isSqlSearchType"
                  :is-can-storage-favorite="isCanStorageFavorite"
                  :retrieve-params="retrieveParams"
                  :active-favorite="activeFavorite"
                  :visible-fields="visibleFields"
                  :is-show-ui-type="isShowUiType"
                  :total-fields="totalFields"
                  :retrieved-keyword="retrievedKeyword"
                  :history-records="statementSearchrecords"
                  :retrieve-dropdown-data="retrieveDropdownData"
                  :is-favorite-search="isFavoriteSearch"
                  :fav-search-list="favSearchList"
                  :field-alias-map="fieldAliasMap"
                  :catch-ip-chooser="catchIpChooser"
                  :date-picker-value="datePickerValue"
                  @openIpQuick="openIpQuick"
                  @ipSelectorValueClear="({ v, isChangeCatch }) => handleIpSelectorValueChange(v, isChangeCatch)"
                  @updateKeyWords="updateKeyWords"
                  @updateSearchParam="updateSearchParam"
                  @retrieveLog="retrieveLog"
                  @clearCondition="clearCondition"
                  @emitChangeValue="emitChangeValue"
                  @searchAddChange="searchAddChange"
                />
              </div>
              <div class="tab-content-item" data-test-id="retrieve_div_fieldFilterBox">
                <!-- 字段过滤 -->
                <div class="tab-item-title field-filter-title" style="color: #313238;">{{ $t('查询结果统计') }}</div>
                <field-filter
                  :retrieve-params="retrieveParams"
                  :total-fields="totalFields"
                  :visible-fields="visibleFields"
                  :sort-list="sortList"
                  :field-alias-map="fieldAliasMap"
                  :show-field-alias="showFieldAlias"
                  :statistical-fields-data="statisticalFieldsData"
                  :parent-loading="tableLoading"
                  @fieldsUpdated="handleFieldsUpdated" />
              </div>
            </div>
          </div>
        </div>
        <!-- 检索详情页右侧检索结果 -->
        <div class="retrieve-result" :style="{ width: 'calc(100% - ' + sumLeftWidth + 'px)' }">
          <!-- 无权限页面 -->
          <auth-container-page v-if="showAuthInfo" :info="showAuthInfo" />
          <template v-else>
            <!-- 初始化加载时显示这个空的盒子 避免先显示内容 再显示无权限页面 -->
            <div v-if="!hasAuth && !showAuthInfo && !isNoIndexSet" style="height: 100%;background: #f4f7fa;"></div>
            <!-- 无索引集 申请索引集页面 -->
            <no-index-set v-if="isNoIndexSet" />
            <!-- 详情右侧 -->
            <result-main
              ref="resultMainRef"
              v-else
              :sort-list="sortList"
              :table-loading="tableLoading"
              :retrieve-params="retrieveParams"
              :took-time="tookTime"
              :index-set-list="indexSetList"
              :table-data="tableData"
              :visible-fields="visibleFields"
              :total-fields="totalFields"
              :field-alias-map="fieldAliasMap"
              :show-field-alias="showFieldAlias"
              :bk-monitor-url="bkmonitorUrl"
              :async-export-usable="asyncExportUsable"
              :async-export-usable-reason="asyncExportUsableReason"
              :statistical-fields-data="statisticalFieldsData"
              :time-field="timeField"
              :config-data="clusteringData"
              :apm-relation="apmRelationData"
              :clean-config="cleanConfig"
              :date-picker-value="datePickerValue"
              :index-set-item="indexSetItem"
              :operator-config="operatorConfig"
              :retrieve-search-number="retrieveSearchNumber"
              :active-table-tab="activeTableTab"
              :cluster-route-params="clusterRouteParams"
              :is-init-page="isInitPage"
              :is-thollte-field="isThollteField"
              :finger-search-state="fingerSearchState"
              @request-table-data="requestTableData"
              @fieldsUpdated="handleFieldsUpdated"
              @shouldRetrieve="retrieveLog"
              @addFilterCondition="addFilterCondition"
              @backFillClusterRouteParams="backFillClusterRouteParams"
              @showSettingLog="handleSettingMenuClick('clustering')" />
          </template>
        </div>
      </div>
      <!-- 可拖拽页面布局宽度 -->
      <div
        v-show="showRetrieveCondition"
        :class="['drag-bar', isChangingWidth && 'dragging']"
        :style="{ left: sumLeftWidth - 1 + 'px' }">
        <img
          src="../../images/icons/drag-icon.svg"
          alt=""
          draggable="false"
          class="drag-icon"
          @mousedown.left="dragBegin">
      </div>
    </div>

    <!-- 目标选择器 -->
    <log-ip-selector
      mode="dialog"
      :key="bkBizId"
      :height="670"
      :show-dialog.sync="showIpSelectorDialog"
      :value="catchIpChooser"
      @change="handleIpSelectorValueChange"
    />
    <!-- 聚类设置全屏弹窗 -->
    <setting-modal
      :index-set-item="indexSetItem"
      :is-show-dialog="isShowSettingModal"
      :select-choice="clickSettingChoice"
      :total-fields="totalFields"
      :clean-config="cleanConfig"
      :config-data="clusteringData"
      :date-picker-value="datePickerValue"
      :retrieve-params="retrieveParams"
      @closeSetting="isShowSettingModal = false;"
      @updateLogFields="requestFields" />
    <!-- 收藏更新弹窗 -->
    <add-collect-dialog
      is-click-favorite-edit
      v-model="isShowAddNewCollectDialog"
      :favorite-list="favoriteList"
      :add-favorite-data="addFavoriteData"
      :favorite-i-d="activeFavoriteID"
      :replace-data="replaceFavoriteData"
      :visible-fields="visibleFields"
      @submit="handleSubmitFavorite" />
  </div>
</template>

<script>
import { mapGetters, mapState } from 'vuex';
import SelectIndexSet from './condition-comp/select-indexSet';
import LogIpSelector from '@/components/log-ip-selector/log-ip-selector';
// import IpSelectorDialog from '@/components/collection-access/ip-selector-dialog';
import FieldFilter from './condition-comp/field-filter';
import ResultHeader from './result-comp/result-header';
import NoIndexSet from './result-comp/no-index-set';
import ResultMain from './result-comp/result-main';
import AuthContainerPage from '@/components/common/auth-container-page';
import SettingModal from './setting-modal/index.vue';
import CollectIndex from './collect/collect-index';
import AddCollectDialog from './collect/add-collect-dialog';
import SearchComp from './search-comp';
import { readBlobRespToJson, parseBigNumberList, setDefaultTableWidth } from '@/common/util';
import { handleTransformToTimestamp } from '../../components/time-range/utils';
import indexSetSearchMixin from '@/mixins/indexSet-search-mixin';
import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
import axios from 'axios';
import * as authorityMap from '../../common/authority-map';
import { deepClone } from '../../components/monitor-echarts/utils';
import CancelToken from 'axios/lib/cancel/CancelToken';
import { updateTimezone } from '../../language/dayjs';
import dayjs from 'dayjs';

const currentTime = Math.floor(new Date().getTime() / 1000);
const startTime = (currentTime - 15 * 60);
const endTime = currentTime;
const DEFAULT_RETRIEVE_PARAMS = {
  keyword: '*', // 搜索关键字
  start_time: startTime, // 时间范围，格式 YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z]
  end_time: endTime, // 时间范围
  host_scopes: { // ip 快选，modules 和 ips 只能修改其一，另一个传默认值
    // 拓扑选择模块列表，单个模块格式 {bk_inst_id: 2000003580, bk_obj_id: 'module'}
    modules: [],
    // 手动输入 ip，多个 ip 用英文 , 分隔
    ips: '',
    // 目标节点
    target_nodes: [],
    // 目标节点类型
    target_node_type: '',
  },
  ip_chooser: {},
  addition: [],
  begin: 0,
  size: 500,
  interval: 'auto', // 聚合周期
};

export default {
  name: 'Retrieve',
  components: {
    SelectIndexSet,
    LogIpSelector,
    FieldFilter,
    ResultHeader,
    ResultMain,
    NoIndexSet,
    SettingModal,
    AuthContainerPage,
    CollectIndex,
    AddCollectDialog,
    SearchComp,
  },
  mixins: [indexSetSearchMixin, tableRowDeepViewMixin],
  data() {
    return {
      hasAuth: false,
      isSearchAllowed: null, // true 有权限，false 无权限，null 未知权限
      basicLoading: false, // view loading
      tableLoading: false, // 表格 loading
      requesting: false,
      isNoIndexSet: false,
      showRetrieveCondition: true, // 详情页显示检索左侧条件
      isChangingWidth: false, // 拖拽
      leftPanelWidth: 400, // 左栏默认宽度
      leftPanelMinWidth: 350, // 左栏最小宽度
      leftPanelMaxWidth: 750, // 左栏最大宽度
      indexId: '', // 当前选择的索引ID
      indexSetItem: {}, // 当前索引集元素
      indexSetList: [], // 索引集列表,
      datePickerValue: ['now-15m', 'now'], // 日期选择器
      retrievedKeyword: '*', // 记录上一次检索的关键字，避免输入框失焦时重复检索
      retrieveParams: {
        bk_biz_id: this.$store.state.bkBizId,
        ...DEFAULT_RETRIEVE_PARAMS,
      },
      catchIpChooser: {}, // 条件里的ip选择器数据
      isFavoriteSearch: false, // 是否是收藏检索
      isAfterRequestFavoriteList: false, // 是否在检索后更新收藏列表
      statisticalFieldsData: {}, // 字段可选值统计
      retrieveDropdownData: {}, // 检索下拉字段可选值统计
      statementSearchrecords: [], // 查询语句历史记录
      totalFields: [], // 表格字段
      visibleFields: [], // 显示的排序后的字段
      sortList: [], // 排序字段
      notTextTypeFields: [], // 字段类型不为 text 的字段
      fieldAliasMap: {},
      showFieldAlias: localStorage.getItem('showFieldAlias') === 'true',
      tookTime: 0, // 耗时
      tableData: {}, // 表格结果
      bkmonitorUrl: false, // 监控主机详情地址
      asyncExportUsable: true, // 是否支持异步导出
      asyncExportUsableReason: '', // 无法异步导出原因
      isInitPage: true, // 是否初始化页面
      isAutoQuery: localStorage.getItem('logAutoQuery') === 'true',
      isPollingStart: false,
      logList: [], // 当前搜索结果的日志
      isShowSettingModal: false,
      clickSettingChoice: '',
      timeField: '',
      isThollteField: false,
      globalsData: {},
      isCanStorageFavorite: true,
      cleanConfig: {},
      clusteringData: { // 日志聚类参数
        name: '',
        is_active: true,
        extra: {
          collector_config_id: null,
          signature_switch: false,
          clustering_field: '',
        },
      },
      apmRelationData: {},
      showIpSelectorDialog: false,
      isAsIframe: false,
      localIframeQuery: {},
      isFirstLoad: true,
      operatorConfig: {}, // 当前table item操作的值
      authPageInfo: null,
      isShowAddNewCollectDialog: false, // 是否展示新建收藏弹窗
      collectWidth: localStorage.getItem('isAutoShowCollect') === 'true' ? 240 : 0, // 收藏默认栏宽度
      isShowCollect: localStorage.getItem('isAutoShowCollect') === 'true',
      isSqlSearchType: true, // 是否是sql模式
      activeFavorite: {}, // 当前点击的收藏参数
      activeFavoriteID: -1, // 当前点击就的收藏ID
      favoriteList: [],
      favoriteLoading: false,
      favSearchList: [], // 收藏的表单模式列表
      inputSearchList: [], // 鼠标失焦后的表单模式列表
      addFavoriteData: {}, // 新建收藏所需的参数
      replaceFavoriteData: {}, // 收藏判断不同后的替换参数
      retrieveSearchNumber: 0, // 切换采集项或初始进入页面时 检索次数初始化为0 检索一次次数+1;
      mappingKey: { // is is not 值映射
        is: '=',
        'is not': '!=',
      },
      /** text类型字段类型的下钻映射 */
      textMappingKey: {
        is: 'contains match phrase',
        'is not': 'not contains match phrase',
      },
      monitorOperatorMappingKey: { // 监控告警跳转过来的操作符映射
        eq: '=',
        neq: '!=',
      },
      activeTableTab: 'origin', // 当前活跃的table-tab 参数: origin clustering
      clusterRouteParams: {}, // 路由回填的数据指纹参数
      isSetDefaultTableColumn: false,
      /** 是否还需要分页 */
      finishPolling: false,
      timezone: dayjs.tz.guess(),
      fingerSearchState: false,
    };
  },
  computed: {
    ...mapState({
      bkBizId: state => state.bkBizId,
      spaceUid: state => state.spaceUid,
      currentMenu: state => state.currentMenu,
      storedIndexID: state => state.indexId, // 路由切换时缓存当前选择的索引
      isExternal: state => state.isExternal,
      externalMenu: state => state.externalMenu,
    }),
    ...mapGetters(['asIframe', 'iframeQuery']),
    ...mapGetters({
      authMainPageInfo: 'globals/authContainerInfo',
    }),
    showAuthInfo() { // 无业务权限则展示store里的 然后判断是否有索引集权限
      return this.authMainPageInfo || this.authPageInfo;
    },
    sumLeftWidth() { // 收藏和检索左边的页面的合计宽度
      return this.collectWidth + this.leftPanelWidth;
    },
    isShowUiType() { // 判断当前点击的收藏是否展示表单字段
      // eslint-disable-next-line camelcase
      return Boolean(this.activeFavorite?.params?.search_fields?.length);
    },
    isFavoriteNewSearch() { // 是否是新检索
      return this.activeFavoriteID === -1;
    },
    getFavoriteName() { // 获取当前点击的收藏名
      return this.activeFavorite?.name || '--';
    },
  },
  provide() {
    return {
      addFilterCondition: this.addFilterCondition,
    };
  },
  watch: {
    indexId(val) { // 切换索引集和初始化索引 id 时改变
      const option = this.indexSetList.find(item => item.index_set_id === val);
      this.indexSetItem = option ? option : { index_set_name: '', indexName: '', scenario_name: '', scenario_id: '' };
      // eslint-disable-next-line camelcase
      this.isSearchAllowed = !!option?.permission?.[authorityMap.SEARCH_LOG_AUTH];
      if (this.isSearchAllowed) this.authPageInfo = null;
      this.resetRetrieveCondition();
      this.resetFavoriteValue();
      this.$store.commit('updateIndexId', val);
      val && this.requestSearchHistory(val);
      this.clearCondition('*', false);
      this.$refs.searchCompRef?.clearAllCondition();
      this.isSetDefaultTableColumn = false;
    },
    spaceUid: {
      async handler() {
        this.indexId = '';
        this.indexSetList.splice(0);
        this.totalFields.splice(0);
        this.retrieveParams.bk_biz_id = this.bkBizId;
        // 外部版 无检索权限跳转后不更新页面数据
        if (!this.isExternal || (this.isExternal && this.externalMenu.includes('retrieve'))) {
          this.fetchPageData();
        }
        this.resetFavoriteValue();
        this.$refs.searchCompRef?.clearAllCondition();
      },
      immediate: true,
    },
    asIframe: {
      immediate: true,
      handler(val) {
        this.isAsIframe = val;
      },
    },
    iframeQuery: {
      deep: true,
      handler(val) {
        this.localIframeQuery = val;
      },
    },
  },
  created() {
    this.getGlobalsData();
  },
  mounted() {
    window.bus.$on('retrieveWhenChartChange', this.retrieveWhenChartChange);
  },
  beforeDestroy() {
    updateTimezone();
    window.bus.$off('retrieveWhenChartChange', this.retrieveWhenChartChange);
  },
  methods: {
    /** 搜索取消请求方法 */
    searchCancelFn() {
    },
    // 子组件改父组件的值或调用方法;
    emitChangeValue({ type, value, isFunction }) {
      if (isFunction) {
        !!value ? this[type](...value) : this[type]();
        return;
      }
      this[type] = value;
    },
    // 切换到监控指标检索
    handleCheckMonitor() {
      window.parent.postMessage('datarieval-click', '*');
    },
    // 切换到监控事件检索
    handleCheckEvent() {
      window.parent.postMessage('event-click', '*');
    },
    async fetchPageData() {
      // 有spaceUid且有业务权限时 才去请求索引集列表
      if (!this.authMainPageInfo && this.spaceUid) {
        // 收藏侧边栏打开且 则先获取到收藏列表再获取索引集列表
        this.isShowCollect && await this.getFavoriteList();
        this.requestIndexSetList();
      } else {
        this.isFirstLoad = false;
      }
    },
    updateIndexSetList() {
      this.$http.request('retrieve/getIndexSetList', {
        query: {
          space_uid: this.spaceUid,
        },
      }).then((res) => {
        if (res.data.length) { // 有索引集
          // 根据权限排序
          const s1 = [];
          const s2 = [];
          for (const item of res.data) {
            // eslint-disable-next-line camelcase
            if (item.permission?.[authorityMap.SEARCH_LOG_AUTH]) {
              s1.push(item);
            } else {
              s2.push(item);
            }
          }
          const indexSetList = s1.concat(s2);

          // 索引集数据加工
          indexSetList.forEach((item) => {
            item.index_set_id = `${item.index_set_id}`;
            item.indexName = item.index_set_name;
            item.lightenName = ` (${item.indices.map(item => item.result_table_id).join(';')})`;
          });
          this.indexSetList = indexSetList;
        }
      });
    },
    // 初始化索引集
    requestIndexSetList() {
      const spaceUid = (this.$route.query.spaceUid && this.isFirstLoad)
        ? this.$route.query.spaceUid : this.spaceUid;
      this.basicLoading = true;
      this.$http.request('retrieve/getIndexSetList', {
        query: {
          space_uid: spaceUid,
        },
      }).then((res) => {
        if (res.data.length) { // 有索引集
          // 根据权限排序
          const s1 = [];
          const s2 = [];
          for (const item of res.data) {
            // eslint-disable-next-line camelcase
            if (item.permission?.[authorityMap.SEARCH_LOG_AUTH]) {
              s1.push(item);
            } else {
              s2.push(item);
            }
          }
          const indexSetList = s1.concat(s2);

          // 索引集数据加工
          indexSetList.forEach((item) => {
            item.index_set_id = `${item.index_set_id}`;
            item.indexName = item.index_set_name;
            item.lightenName = ` (${item.indices.map(item => item.result_table_id).join(';')})`;
          });
          this.indexSetList = indexSetList;

          const indexId = this.$route.params.indexId?.toString();
          const routeIndexSet = indexSetList.find(item => item.index_set_id === indexId);
          const isRouteIndex = !!routeIndexSet && !routeIndexSet?.permission?.[authorityMap.SEARCH_LOG_AUTH];

          // 如果都没有权限或者路由带过来的索引集无权限则显示索引集无权限
          // eslint-disable-next-line camelcase
          if (!indexSetList[0]?.permission?.[authorityMap.SEARCH_LOG_AUTH] || isRouteIndex) {
            const authIndexID = indexId || indexSetList[0].index_set_id;
            this.$store.dispatch('getApplyData', {
              action_ids: [authorityMap.SEARCH_LOG_AUTH],
              resources: [{
                type: 'indices',
                id: authIndexID,
              }],
            }).then((res) => {
              this.authPageInfo = res.data;
              this.setRouteParams('retrieve', {
                indexId: null,
              }, {
                spaceUid: this.$store.state.spaceUid,
                bizId: this.$store.state.bkBizId,
              });
            })
              .catch((err) => {
                console.warn(err);
              })
              .finally(() => {
                this.basicLoading = false;
              });
            return;
          }
          this.hasAuth = true;


          if (indexId) { // 1、初始进入页面带ID；2、检索ID时切换业务；
            const indexItem = indexSetList.find(item => item.index_set_id === indexId);
            this.indexId = indexItem ? indexItem.index_set_id : indexSetList[0].index_set_id;
            this.retrieveLog();
          } else { // 直接进入检索页
            this.indexId = indexSetList.some(item => item.index_set_id === this.storedIndexID)
              ? this.storedIndexID
              : indexSetList[0].index_set_id;
            if (this.isAsIframe) { // 监控 iframe
              if (this.localIframeQuery.indexId) {
                if (this.indexSetList.some(item => item.index_set_id === this.localIframeQuery.indexId)) {
                  this.indexId = this.localIframeQuery.indexId;
                }
              }
              this.retrieveLog();
            } else {
              const queryObj = {
                spaceUid: this.$store.state.spaceUid,
                bizId: this.$store.state.bkBizId,
              };
              if (this.$route.query.from) {
                queryObj.from = this.$route.query.from;
              }
              this.setRouteParams('retrieve', {
                indexId: null,
              }, queryObj);
              this.retrieveLog();
            }
          }
          this.isNoIndexSet = false;
        } else { // 无索引集
          this.isNoIndexSet = true;
          const queryObj = {
            spaceUid: this.$store.state.spaceUid,
            bizId: this.$store.state.bkBizId,
          };
          if (this.$route.query.from) {
            queryObj.from = this.$route.query.from;
          }
          this.setRouteParams('retrieve', {
            indexId: null,
          }, queryObj);
          this.indexId = '';
          this.indexSetList.splice(0);
        }
      })
        .catch((e) => {
          console.warn(e);
          this.isNoIndexSet = false;
          this.indexId = '';
          this.indexSetList.splice(0);
        })
        .finally(() => {
          this.basicLoading = false;
          this.isFirstLoad = false;
        });
    },
    // 获取检索历史
    requestSearchHistory(indexId) {
      this.$http.request('retrieve/getSearchHistory', {
        params: {
          index_set_id: indexId,
        },
      }).then((res) => {
        this.statementSearchrecords = res.data;
      });
    },
    // 切换索引
    handleSelectIndex(val) {
      this.indexId = val;
      this.activeFavoriteID = -1;
      this.activeFavorite = {};
      this.retrieveLog();
    },
    // 切换索引时重置检索数据
    resetRetrieveCondition() {
      // 重置搜索条件，起始位置、日期相关字段不变
      // Object.assign(this.retrieveParams, {
      //     keyword: '*',
      //     host_scopes: {
      //         modules: [],
      //         ips: ''
      //     },
      //     addition: []
      // })
      // 过滤相关
      const tempList = handleTransformToTimestamp(this.datePickerValue);
      this.retrieveParams = {
        bk_biz_id: this.$store.state.bkBizId,
        ...DEFAULT_RETRIEVE_PARAMS,
        start_time: tempList[0],
        end_time: tempList[1],
      };
      this.statisticalFieldsData = {};
      this.retrieveDropdownData = {};
      this.logList = [];
      // 字段相关
      this.totalFields.splice(0);
    },
    resetFavoriteValue() {
      this.activeFavorite = {};
      this.activeFavoriteID = -1;
      this.retrieveSearchNumber = 0; // 切换业务 检索次数设置为0;
      this.isSqlSearchType = true;
    },
    // 检索参数：日期改变
    handleDateChange(val) {
      this.datePickerValue = val;
      this.formatTimeRange();
    },
    /**
     * @desc 时间选择组件返回时间戳格式转换
     */
    formatTimeRange() {
      const tempList = handleTransformToTimestamp(this.datePickerValue);
      Object.assign(this.retrieveParams, {
        start_time: tempList[0],
        end_time: tempList[1],
      });
    },
    updateSearchParam({ keyword, addition, host }) {
      this.retrieveParams.addition = addition;
      this.retrieveParams.keyword = keyword;
      this.retrieveParams.ip_chooser = host;
      this.catchIpChooser = host;
      this.$refs.searchCompRef.initConditionList(addition, host); // 点击历史记录 更新当前添加条件列表
    },
    // 日期选择器选择时间完毕，检索
    retrieveWhenDateChange() {
      this.shouldUpdateFields = true;
      this.retrieveLog();
    },
    handleTimezoneChange(timezone) {
      this.timezone = timezone;
      updateTimezone(timezone);
    },
    handleSettingMenuClick(val) {
      this.clickSettingChoice = val;
      this.isShowSettingModal = true;
    },
    // 由添加条件来修改的过滤条件
    searchAddChange(addObj) {
      const { addition, isQuery, isForceQuery } = addObj;
      this.retrieveParams.addition = addition;
      if ((isQuery && this.isAutoQuery) || isForceQuery) this.retrieveLog();
    },
    getFieldType(field) {
      const target = this.totalFields.find(item => item.field_name === field);
      return target ? target.field_type : '';
    },
    // 添加过滤条件
    addFilterCondition(field, operator, value, isLink = false) {
      let mappingKey = this.mappingKey;
      const textType = this.getFieldType(field);
      switch (textType) {
        case 'text':
          mappingKey = this.textMappingKey;
          break;
        default:
          break;
      }
      const mapOperator = mappingKey[operator] ?? operator; // is is not 值映射
      const isExist = this.retrieveParams.addition.some((addition) => {
        return addition.field === field
        && addition.operator === mapOperator
        && addition.value.toString() === value.toString();
      });
      // 已存在相同条件
      if (isExist) {
        if (isLink) this.additionLinkOpen();
        return;
      };

      const startIndex = this.retrieveParams.addition.length;
      const newAddition = { field, operator: mapOperator, value };
      if (!isLink) {
        this.retrieveParams.addition.splice(startIndex, 0, newAddition);
        this.$refs.searchCompRef.pushCondition(field, mapOperator, value);
        this.$refs.searchCompRef.setRouteParams();
        this.retrieveLog();
      } else {
        this.additionLinkOpen(newAddition);
      }
    },

    additionLinkOpen(newAddition = {}) {
      const openUrl = this.$refs.searchCompRef.setRouteParams({}, false, newAddition);
      window.open(openUrl, '_blank');
    },

    // 打开 ip 选择弹窗
    openIpQuick() {
      this.showIpSelectorDialog = true;
    },
    // IP 选择
    // handleSaveIpQuick(data) {
    //   const { target_node_type: targetNodeType, target_nodes: targetNodes } = data;
    //   this.retrieveParams.host_scopes.target_node_type = targetNodes.length ? targetNodeType : '';
    //   this.retrieveParams.host_scopes.target_nodes = targetNodes.map((node) => {
    //     const targets = ['TOPO', 'SERVICE_TEMPLATE', 'SET_TEMPLATE'].includes(targetNodeType)
    //       ? {
    //         node_path: node.node_path,
    //         bk_inst_name: node.bk_inst_name,
    //         bk_inst_id: node.bk_inst_id,
    //         bk_obj_id: node.bk_obj_id,
    //       }
    //       : targetNodeType === 'DYNAMIC_GROUP' ? { id: node.id, name: node.name, bk_obj_id: node.bk_obj_id }
    //         : { ip: node.ip, bk_cloud_id: node.bk_cloud_id, bk_supplier_id: node.bk_supplier_id };
    //     return targets;
    //   });
    //   this.showIpSelectorDialog = false;
    //   if (this.isAutoQuery) {
    //     this.retrieveLog();
    //   }
    // },
    /**
     * @desc: ip 选择器选中值发生变化
     * @param {Object} value ip选择器弹窗的值
     * @param {Boolean} isChangeCatch 是否改变缓存的ip选择器的值
     */
    handleIpSelectorValueChange(value, isChangeCatch = true) {
      const ipChooserValue = {}; // 新的ip选择的值
      const nodeType = Object.keys(value).find(item => value[item].length);
      if (nodeType) {
        ipChooserValue[nodeType] = value[nodeType];
      }
      const ipChooserIsOpen = this.$refs.searchCompRef.ipChooserIsOpen; // 当前添加条件是否打开状态
      this.retrieveParams.ip_chooser = ipChooserIsOpen ? ipChooserValue : {}; // 判断条件开关来 赋值ip的值
      const catchValueStr = JSON.stringify(this.catchIpChooser);
      const chooserValueStr = JSON.stringify(ipChooserValue);
      let isQuery = false; // 是否检索
      if (isChangeCatch) {
        this.catchIpChooser = ipChooserValue; // 改变缓存的值
        isQuery = (catchValueStr !== chooserValueStr) && ipChooserIsOpen;
      } else {
        isQuery = Boolean(Object.keys(this.catchIpChooser).length);
      }
      if (isQuery) this.retrieveLog();
      this.$refs.searchCompRef.setIPChooserFilter(this.catchIpChooser); // 设置添加条件的ip选择器的值 并更新路由
    },
    /**
     * @desc: 清空条件
     * @param {String} clearStr 检索keywords
     * @param {Boolean} isRetrieveLog 是否检索表格
     */
    clearCondition(clearStr = '*', isRetrieveLog = true) {
      Object.assign(this.retrieveParams, {
        keyword: this.isSqlSearchType ? clearStr : this.retrieveParams.keyword, // 若是表单模式的清空则不删除keyword
        ip_chooser: {},
        addition: [],
      });
      this.catchIpChooser = {};
      this.$refs.searchCompRef.clearValue();
      if (this.isSqlSearchType) this.$refs.searchCompRef.handleBlurSearchInput('*');
      if (isRetrieveLog) this.retrieveLog();
    },
    // 搜索记录
    retrieveFavorite({ index_set_id: indexSetID, params }) {
      if (this.indexSetList.find(item => item.index_set_id === String(indexSetID))) {
        this.isFavoriteSearch = true;
        this.indexId = String(indexSetID);
        const { search_fields, ...reset } = params;
        this.retrieveLog(reset);
      } else {
        this.messageError(this.$t('没有找到该记录下相关索引集'));
      }
    },
    /**
     * @desc: 检索日志
     * @param {Any} historyParams 历史数据
     * @param {Boolean} isRequestChartsAndHistory 检索时是否请求历史记录和图表
     */
    async retrieveLog(historyParams, isRequestChartsAndHistory = true) {
      if (!this.indexId) return;
      await this.$nextTick();
      this.basicLoading = true;
      this.$refs.resultHeader && this.$refs.resultHeader.pauseRefresh();

      // 是否有检索的权限
      const paramData = {
        action_ids: [authorityMap.SEARCH_LOG_AUTH],
        resources: [{
          type: 'indices',
          id: this.indexId,
        }],
      };
      if (this.isSearchAllowed === null) { // 直接从 url 进入页面 checkAllowed && getApplyData
        try {
          this.resultLoading = true;
          const res = await this.$store.dispatch('checkAndGetData', paramData);
          if (res.isAllowed === false) {
            this.isSearchAllowed = false;
            this.$store.commit('updateAuthDialogData', res.data);
            return;
          }
        } catch (err) {
          console.warn(err);
          return;
        } finally {
          this.resultLoading = false;
        }
      } else if (this.isSearchAllowed === false) { // 已知当前选择索引无权限
        try {
          this.basicLoading = true;
          const res = await this.$store.dispatch('getApplyData', paramData);
          this.$store.commit('updateAuthDialogData', res.data);
        } catch (err) {
          console.warn(err);
        } finally {
          this.basicLoading = false;
        }
        return;
      }

      // 设置检索参数，历史记录或收藏的参数
      if (historyParams) {
        Object.assign(this.retrieveParams, historyParams);
        // 禁用 IP 快选时过滤历史记录或收藏中相关字段
        // if (!this.showIpQuick) {
        //   this.retrieveParams.host_scopes.ips = '';
        // }
      }
      // 通过 url 查询参数设置检索参数
      let queryParams = {};
      let queryParamsStr = {};
      const clusteringParams = {};
      const urlRetrieveParams = this.$route.query.retrieveParams;
      if (urlRetrieveParams) { // 兼容之前的语法
        try {
          queryParams = JSON.parse(decodeURIComponent(urlRetrieveParams));
          queryParamsStr = JSON.parse(decodeURIComponent(urlRetrieveParams));
          if (queryParams.start_time && queryParams.end_time) {
            this.datePickerValue = [queryParams.start_time, queryParams.end_time];
          }
        } catch (e) {
          console.warn('url 查询参数解析失败', e);
        }
      } else {
        const shouldCoverParamFields = [
          'keyword',
          'host_scopes',
          'ip_chooser',
          'addition',
          'start_time',
          'end_time',
          // 'time_range',
          'activeTableTab', // 表格活跃的lab
          'clusterRouteParams', // 日志聚类参数
          'timezone',
        ];
        // 判断路由是否带有下载历史的检索的数据 如果有 则使用路由里的数据初始化
        const routerQuery = this.$route.query;
        const initRetrieveParams = routerQuery.routeParams
          ? JSON.parse(decodeURIComponent(routerQuery.routeParams))
          : routerQuery;
        for (const field of shouldCoverParamFields) {
          const param = initRetrieveParams[field]; // 指定查询参数
          if (this.isInitPage) {
            if (param) {
              switch (field) {
                case 'activeTableTab':
                case 'clusterRouteParams':
                  queryParamsStr[field] = param;
                  clusteringParams[field] = (field === 'activeTableTab' ? param : JSON.parse(param));
                  break;
                case 'addition': {
                  const additionParamsList = JSON.parse(decodeURIComponent(param));
                  queryParams[field] = additionParamsList
                    .filter(item => (item.isInclude ?? true))
                    .map((item) => {
                      const { field, operator, value } = item;
                      return {
                        field,
                        operator: this.monitorOperatorMappingKey[operator] ?? operator, // 监控跳转过来时的操作符映射
                        value,
                      };
                    });
                  queryParamsStr.addition = JSON.stringify(
                    additionParamsList.map(item => ({
                      ...item,
                      operator: this.monitorOperatorMappingKey[item.operator] ?? item.operator, // 监控跳转过来时的操作符映射
                      isInclude: item?.isInclude ?? true })), // 若没有启动开关参数则直接显示为开
                  );
                }
                  break;
                case 'ip_chooser': {
                  if (Object.keys(param).length) {
                    this.catchIpChooser = JSON.parse(param);
                    if (this.$route.query?.isIPChooserOpen !== 'false') queryParams.ip_chooser = JSON.parse(param);
                  }
                  queryParamsStr.ip_chooser = param;
                }
                  break;
                default:
                  queryParams[field] = ['keyword', 'start_time', 'end_time', 'timezone', 'activeTableTab'].includes(field)
                    ? decodeURIComponent(param)
                    : decodeURIComponent(param) ? JSON.parse(decodeURIComponent(param)) : param;
                  queryParamsStr[field] = param;
                  break;
              }
            }
            if (queryParams.start_time && queryParams.end_time) {
              this.datePickerValue = [queryParams.start_time, queryParams.end_time];
            }
          } else {
            switch (field) {
              case 'keyword':
              // case 'start_time':
              // case 'end_time':
              // case 'time_range':
                queryParamsStr[field] = this.retrieveParams[field] === '' ? '*' : encodeURIComponent(this.retrieveParams[field]);
                break;
              case 'host_scopes':
                if (this.retrieveParams[field].ips !== ''
                || this.retrieveParams[field].modules.length
                || this.retrieveParams[field].target_nodes.length) {
                  queryParamsStr[field] = (JSON.stringify(this.retrieveParams[field]));
                }
                break;
              case 'start_time':
                queryParamsStr[field] = this.datePickerValue?.[0] ?? undefined;
                break;
              case 'end_time':
                queryParamsStr[field] = this.datePickerValue?.[1] ?? undefined;
                break;
              case 'activeTableTab':
              case 'clusterRouteParams':
                if (param) {
                  queryParamsStr[field] = (field === 'activeTableTab' ? this[field] : JSON.stringify(this[field]));
                }
                break;
              case 'timezone':
                queryParamsStr[field] = this.timezone;
                break;
              default:
                break;
            }
          }
        }
      }
      // 进入检索详情页
      const queryObj = {
        ...this.$route.query,
        spaceUid: this.$store.state.spaceUid,
        bizId: this.$store.state.bkBizId,
        ...queryParamsStr,
        keyword: queryParamsStr?.keyword,
      };
      this.$router.push({
        name: 'retrieve',
        params: {
          indexId: this.indexId,
        },
        query: queryObj,
      });
      // 接口请求
      try {
        this.tableLoading = true;
        this.resetResult();
        // 表格loading处理
        this.$refs.resultMainRef.reset();
        if (!this.totalFields.length || this.shouldUpdateFields) {
          window.bus.$emit('openChartLoading');
          await this.requestFields();
          this.shouldUpdateFields = false;
        }
        // 指纹请求监听放在这里是要等字段更新完后才会去请求数据指纹
        this.fingerSearchState = !this.fingerSearchState;

        if (this.isInitPage) {
          Object.assign(this.retrieveParams, queryParams); // 回填查询参数中的检索条件
          if (queryParams.start_time && queryParams.end_time) {
            this.handleDateChange([queryParams.start_time, queryParams.end_time]);
          }
          if (queryParams.timezone) {
            this.timezone = queryParams.timezone;
            updateTimezone(queryParams.timezone);
          }
          // 回填数据指纹的数据
          Object.entries(clusteringParams).forEach(([key, val]) => {
            this[key] = val;
          });
          await this.$nextTick();
          // 初始化 回填添加条件
          const addition = !!queryParamsStr.addition ? JSON.parse(queryParamsStr?.addition) : undefined;
          const chooserSwitch = Boolean(queryParams.ip_chooser);
          this.$refs.searchCompRef.initConditionList(addition, this.catchIpChooser, chooserSwitch); // 初始化 更新当前添加条件列表
          // this.$store.commit('updateIsNotVisibleFieldsShow', !this.visibleFields.length);
          this.isInitPage = false;
        }

        this.retrieveParams.keyword = this.retrieveParams.keyword.trim();
        if (isRequestChartsAndHistory) { // 是否请求图表和历史记录
          this.requestChart();
          this.requestSearchHistory(this.indexId);
        }
        // this.searchCancelFn();
        await this.requestTable();
        if (this.isAfterRequestFavoriteList) await this.getFavoriteList();

        // 已检索 判断当前检索是否是初始化的收藏检索 添检索次数
        const beAddedNumber = (!this.retrieveSearchNumber && this.isFavoriteSearch) ? 2 : 1;
        this.retrieveSearchNumber += beAddedNumber;
      } catch (e) {
        console.warn(e);
        if (!e.message.includes('request canceled')) { // 接口出错、非重复请求被取消
          this.tableLoading = false;
        }
      } finally {
        // 如果是收藏检索并且开启检索显示, 合并当前字段和收藏字段 更新显示字段
        // eslint-disable-next-line camelcase
        if (this.isFavoriteSearch && this.activeFavorite?.is_enable_display_fields) {
          const { display_fields: favoriteDisplayFields } = this.activeFavorite;
          const sessionShownFieldList = this.sessionShowFieldObj()?.[this.indexId] ?? [];
          const displayFields = [...new Set([...sessionShownFieldList, ...favoriteDisplayFields])];
          this.handleFieldsUpdated(displayFields, undefined, false);
        };
        if (this.isFavoriteSearch) {
          this.initSearchList();
          this.isSqlSearchType = !this.isShowUiType; // 判断是否有表单模式的数组值 如果有 则切换为表单模式
          this.$refs.searchCompRef.initConditionList(); // 点击收藏 更新添加条件列表
          this.catchIpChooser = this.retrieveParams.ip_chooser; // 更新ip的条件显示
        }
        // 搜索完毕后，如果开启了自动刷新，会在 timeout 后自动刷新
        this.$refs.resultHeader && this.$refs.resultHeader.setRefreshTime();
        this.isFavoriteSearch = false;
        this.isAfterRequestFavoriteList = false;
        this.basicLoading = false;
      }
    },
    // 更新路由参数
    setRouteParams(name = 'retrieve', params, query) {
      this.$router.replace({
        name,
        params,
        query,
      });
    },
    // 请求字段
    async requestFields() {
      if (this.isThollteField) return;
      this.isThollteField = true;
      try {
        const res = await this.$http.request('retrieve/getLogTableHead', {
          params: { index_set_id: this.indexId },
          query: {
            start_time: this.retrieveParams.start_time,
            end_time: this.retrieveParams.end_time,
            is_realtime: 'True',
          },
        });
        const notTextTypeFields = [];
        const { data } = res;
        const {
          fields,
          config,
          display_fields: displayFields,
          time_field: timeField,
          sort_list: sortList,
          config_id,
        } = data;
        const localConfig = {};
        config.forEach((item) => {
          localConfig[item.name] = { ...item };
        });
        const {
          bkmonitor,
          ip_topo_switch: ipTopoSwitch,
          context_and_realtime: contextAndRealtime,
          bcs_web_console: bcsWebConsole,
          async_export: asyncExport,
          clean_config: cleanConfig,
          clustering_config: clusteringConfig,
          apm_relation: apmRelation,
        } = localConfig;

        this.operatorConfig = { // 操作按钮配置信息
          bkmonitor,
          bcsWebConsole,
          contextAndRealtime,
          timeField,
        };
        // 初始化操作按钮消息
        this.operatorConfig.toolMessage = this.initToolTipsMessage(this.operatorConfig);
        this.cleanConfig = cleanConfig;
        this.clusteringData = clusteringConfig;
        this.apmRelationData = apmRelation;

        fields.forEach((item) => {
          item.minWidth = 0;
          item.filterExpand = false; // 字段过滤展开
          item.filterVisible = true; // 字段过滤搜索字段名是否显示
          if (item.field_type !== 'text') {
            notTextTypeFields.push(item.field_name);
          }
        });
        this.notTextTypeFields = notTextTypeFields;
        this.ipTopoSwitch = ipTopoSwitch.is_active;
        this.bkmonitorUrl = bkmonitor.is_active;
        this.asyncExportUsable = asyncExport.is_active;
        this.asyncExportUsableReason = !asyncExport.is_active ? asyncExport.extra.usable_reason : '';
        this.timeField = timeField;
        this.totalFields = fields;
        // 请求字段时 判断当前索引集是否有更改过字段 若更改过字段则使用session缓存的字段显示
        const sessionShownFieldList = this.sessionShowFieldObj()?.[this.indexId];
        // 后台给的 display_fields 可能有无效字段 所以进行过滤，获得排序后的字段
        this.initVisibleFields(sessionShownFieldList ?? displayFields);
        this.sortList = sortList;

        const fieldAliasMap = {};
        fields.forEach((item) => {
          fieldAliasMap[item.field_name] = item.field_alias || item.field_name;
        });
        this.fieldAliasMap = fieldAliasMap;
        this.isThollteField = false;
        this.$store.commit('retrieve/updateFiledSettingConfigID', config_id); // 当前配置ID
        this.$nextTick(() => {
          this.$refs.searchCompRef?.initAdditionDefault();
        });
      } catch (e) {
        this.ipTopoSwitch = true;
        this.bkmonitorUrl = false;
        this.asyncExportUsable = true;
        this.asyncExportUsableReason = '';
        this.timeField = '';
        this.totalFields.splice(0);
        this.visibleFields.splice(0);
        this.isThollteField = false;
        throw e;
      }
    },
    /**
     * @desc: 初始化展示字段
     * @param {Array<str>} displayFieldNames 显示字段
     */
    initVisibleFields(displayFieldNames) {
      this.visibleFields = displayFieldNames.map((displayName) => {
        for (const field of this.totalFields) {
          if (field.field_name === displayName) {
            return field;
          }
        }
      }).filter(Boolean);
      this.$store.commit('updateIsNotVisibleFieldsShow', !this.visibleFields.length);
      if (!this.isSetDefaultTableColumn) {
        this.setDefaultTableColumn();
      }
      this.isSetDefaultTableColumn = false;
    },
    sessionShowFieldObj() { // 显示字段缓存
      const showFieldStr = sessionStorage.getItem('showFieldSession');
      return !showFieldStr ? {} : JSON.parse(showFieldStr);
    },
    /**
     * @desc: 字段设置更新了
     * @param {Array} displayFieldNames 展示字段
     * @param {Boolean} showFieldAlias 是否别名
     * @param {Boolean} isRequestFields 是否请求字段
     */
    async handleFieldsUpdated(displayFieldNames, showFieldAlias, isRequestFields = true) {
      this.$store.commit('updateClearTableWidth', 1);
      // requestFields已经更新过一次了展示了 不需要再更新
      if (!isRequestFields) this.initVisibleFields(displayFieldNames);
      // 缓存展示字段
      const showFieldObj = this.sessionShowFieldObj();
      Object.assign(showFieldObj, { [this.indexId]: displayFieldNames });
      sessionStorage.setItem('showFieldSession', JSON.stringify(showFieldObj));
      if (showFieldAlias !== undefined) {
        this.showFieldAlias = showFieldAlias;
        window.localStorage.setItem('showFieldAlias', showFieldAlias);
      }
      await this.$nextTick();
      isRequestFields && this.requestFields();
    },
    requestTableData() {
      if (this.requesting) return;

      this.requestTable();
    },
    // 表格
    async requestTable() {
      if (this.requesting) return;

      this.requesting = true;

      const { startTimeStamp, endTimeStamp } = this.getRealTimeRange();
      if (!this.isPollingStart) {
        // 获取坐标分片间隔
        this.handleIntervalSplit(startTimeStamp, endTimeStamp);
        this.isPollingStart = true;
      }

      const { currentPage, pageSize } = this.$refs.resultMainRef;
      const begin = currentPage === 1 ? 0 : (currentPage - 1) * pageSize;
      this.formatTimeRange();
      try {
        const baseUrl = process.env.NODE_ENV === 'development' ? 'api/v1' : window.AJAX_URL_PREFIX;
        const params = {
          method: 'post',
          url: `/search/index_set/${this.indexId}/search/`,
          cancelToken: new CancelToken((c) => {
            this.searchCancelFn = c;
          }),
          withCredentials: true,
          baseURL: baseUrl,
          responseType: 'blob',
          data: {
            ...this.retrieveParams,
            begin,
            size: pageSize,
            interval: this.interval,
          },
        };
        if (this.isExternal) {
          params.headers = {
            'X-Bk-Space-Uid': this.spaceUid,
          };
        }
        const res = await axios(params).then((res) => {
          return readBlobRespToJson(res.data);
        });

        if (!res.data && res.message) { // 接口报错提示
          this.messageError(res.message);
        }
        // 判断分页
        this.finishPolling = res.data?.list?.length < pageSize;

        this.retrievedKeyword = this.retrieveParams.keyword;
        this.tookTime = this.tookTime + Number(res.data?.took) || 0;
        this.tableData = { ...(res.data || {}), finishPolling: this.finishPolling };
        if (!this.isSetDefaultTableColumn) {
          this.setDefaultTableColumn();
        }
        this.logList = this.logList.concat(parseBigNumberList(res.data?.list ?? []));
        this.statisticalFieldsData = this.getStatisticalFieldsData(this.logList);
        this.computeRetrieveDropdownData(this.logList);
      } catch (err) {
        this.$refs.resultMainRef.isPageOver = false;
        this.isCanStorageFavorite = false; // 不能收藏
      } finally {
        if (this.finishPolling) this.$refs.resultMainRef.isPageOver = false;
        this.requesting = false;
        this.tableLoading = false;
      }
    },
    // 首次加载设置表格默认宽度自适应
    setDefaultTableColumn() {
      // 如果浏览器记录过当前索引集表格拖动过 则不需要重新计算
      const columnObj = JSON.parse(localStorage.getItem('table_column_width_obj'));
      const { params: { indexId }, query: { bizId } } = this.$route;
      const catchFieldsWidthObj = columnObj?.[bizId]?.fields[indexId];
      const tableList = this.tableData?.list ?? [];
      this.isSetDefaultTableColumn = setDefaultTableWidth(this.visibleFields, tableList, catchFieldsWidthObj);
    },
    // 根据表格数据统计字段值及出现次数
    getStatisticalFieldsData(listData) {
      const result = {};
      listData.forEach((dataItem) => {
        this.recursiveObjectData(result, dataItem);
      });
      return result;
    },
    recursiveObjectData(result, dataItem, prefixFieldKey = '') {
      dataItem && Object.entries(dataItem).forEach(([field, value]) => {
        if (typeof value === 'object') {
          this.recursiveObjectData(result, value, `${prefixFieldKey + field}.`);
        } else {
          const fullFieldKey = prefixFieldKey ? prefixFieldKey + field : field;
          const fieldData = result[fullFieldKey] || (result[fullFieldKey] = Object.defineProperties({}, {
            __totalCount: { // 总记录数量
              value: 0,
              writable: true,
            },
            __validCount: { // 有效值数量
              value: 0,
              writable: true,
            },
          }));
          fieldData.__totalCount += 1;
          if (value || value === 0) {
            fieldData.__validCount += 1;
            if (fieldData[value]) {
              fieldData[value] += 1;
            } else {
              fieldData[value] = 1;
            }
          }
        }
      });
    },
    // 更新下拉字段可选值信息
    computeRetrieveDropdownData(listData) {
      listData.forEach((dataItem) => {
        this.recursiveIncreaseData(dataItem);
      });
    },
    recursiveIncreaseData(dataItem, prefixFieldKey = '') {
      dataItem && Object.entries(dataItem).forEach(([field, value]) => {
        if (typeof value === 'object') {
          this.recursiveIncreaseData(value, `${prefixFieldKey + field}.`);
        } else {
          const fullFieldKey = prefixFieldKey ? prefixFieldKey + field : field;
          if (value || value === 0) {
            let fieldData = this.retrieveDropdownData[fullFieldKey];
            if (!fieldData) {
              this.$set(this.retrieveDropdownData, fullFieldKey, Object.defineProperties({}, {
                __fieldType: { // 该字段下的值的数据类型，可能是数值、字符串、布尔值
                  value: typeof value,
                },
              }));
              fieldData = this.retrieveDropdownData[fullFieldKey];
            }
            if (this.notTextTypeFields.includes(field) && !fieldData[value]) {
              // 非 text 类型字段统计可选值，text 则由用户手动输入
              fieldData[value] = 1;
            }
          }
        }
      });
    },
    // 图表
    requestChart() {
      this.formatTimeRange();
      this.$store.commit('retrieve/updateChartKey');
    },
    // 图表款选或双击回正时请求相关数据
    async retrieveWhenChartChange() {
      this.$refs.resultHeader && this.$refs.resultHeader.pauseRefresh();
      this.$refs.resultMainRef.reset();
      this.isSetDefaultTableColumn = false;
    },

    // 重置搜索结果
    resetResult() {
      // 内容
      this.tookTime = 0;
      this.tableData = {};
      // 字段过滤展开
      this.totalFields.forEach((item) => {
        item.filterExpand = false;
      });
      // 字段值统计数据
      this.statisticalFieldsData = {};
      this.logList = [];
    },
    // 控制页面布局宽度
    dragBegin(e) {
      this.isChangingWidth = true;
      this.currentTreeBoxWidth = this.leftPanelWidth;
      this.currentScreenX = e.screenX;
      window.addEventListener('mousemove', this.dragMoving, { passive: true });
      window.addEventListener('mouseup', this.dragStop, { passive: true });
    },
    dragMoving(e) {
      const newTreeBoxWidth = this.currentTreeBoxWidth + e.screenX - this.currentScreenX;
      if (newTreeBoxWidth < this.leftPanelMinWidth) {
        this.leftPanelWidth = 0;
        this.showRetrieveCondition = false;
        this.dragStop();
      } else if (newTreeBoxWidth >= this.leftPanelMaxWidth) {
        this.leftPanelWidth = this.leftPanelMaxWidth;
      } else {
        this.leftPanelWidth = newTreeBoxWidth;
      }
      // window.bus.$emit('set-chart-width');
    },
    dragStop() {
      this.isChangingWidth = false;
      this.currentTreeBoxWidth = null;
      this.currentScreenX = null;
      window.removeEventListener('mousemove', this.dragMoving);
      window.removeEventListener('mouseup', this.dragStop);
    },
    openRetrieveCondition() {
      // window.bus.$emit('set-chart-width');
      this.leftPanelWidth = this.leftPanelMinWidth;
      this.showRetrieveCondition = true;
    },
    closeRetrieveCondition() {
      this.leftPanelWidth = 0;
      this.showRetrieveCondition = false;
    },
    updateCollectCondition(status) {
      this.collectWidth = status ? 240 : 0;
      localStorage.setItem('isAutoShowCollect', `${status}`);
      this.isShowCollect = status;
      if (!status) {
        this.activeFavorite = {};
        this.activeFavoriteID = -1;
        this.isSqlSearchType = true;
      }
    },
    // 获取全局数据和 判断是否可以保存 已有的日志聚类
    getGlobalsData() {
      if (Object.keys(this.globalsData).length) return;
      this.$http.request('collect/globals').then((res) => {
        this.$store.commit('globals/setGlobalsData', res.data);
      })
        .catch((e) => {
          console.warn(e);
        });
    },
    initToolTipsMessage(config) {
      const { contextAndRealtime, bcsWebConsole } = config;
      return {
        webConsole: bcsWebConsole.is_active ? 'WebConsole' : bcsWebConsole?.extra.reason,
        realTimeLog: contextAndRealtime.is_active ? this.$t('实时日志') : contextAndRealtime?.extra.reason,
        contextLog: contextAndRealtime.is_active ? this.$t('上下文') : contextAndRealtime?.extra.reason,
      };
    },
    // 检索头部点击编辑收藏
    handleEditFavorite() {
      if (this.basicLoading) return;
      // 获取检索页面的数据替换当前收藏详情参数
      this.replaceFavoriteData = this.getRetrieveFavoriteData();
      this.isShowAddNewCollectDialog = true;
    },
    // 当前检索监听的收藏参数
    getRetrieveFavoriteData() {
      return {
        params: {
          ip_chooser: this.retrieveParams.ip_chooser,
          addition: this.retrieveParams.addition,
          keyword: this.retrieveParams.keyword,
        },
        display_fields: this.visibleFields.map(item => item?.field_name),
      };
    },

    /** 获取收藏列表 */
    async getFavoriteList() {
      // 第一次显示收藏列表时因路由更变原因 在本页面第一次请求
      try {
        this.favoriteLoading = true;
        const { data } = await this.$http.request('favorite/getFavoriteByGroupList', {
          query: {
            space_uid: this.spaceUid,
            order_type: localStorage.getItem('favoriteSortType') || 'NAME_ASC',
          },
        });
        const provideFavorite = data[0];
        const publicFavorite = data[data.length - 1];
        const sortFavoriteList = data.slice(1, data.length - 1)
          .sort((a, b) => a.group_name.localeCompare(b.group_name));
        const sortAfterList = [provideFavorite, ...sortFavoriteList, publicFavorite];
        this.favoriteList = sortAfterList;
      } catch (err) {
        this.favoriteLoading = false;
        this.favoriteList = [];
      } finally {
        // 获取收藏列表后 若当前不是新检索 则判断当前收藏是否已删除 若删除则变为新检索
        if (this.activeFavoriteID !== -1) {
          let isFindCheckValue = false; // 是否从列表中找到匹配当前收藏的id
          for (const gItem of this.favoriteList) {
            const findFavorites = gItem.favorites.find(item => item.id === this.activeFavoriteID);
            if (!!findFavorites) {
              isFindCheckValue = true; // 找到 中断循环
              break;
            }
          }
          if (!isFindCheckValue) this.handleClickFavoriteItem(undefined); // 未找到 清空当前收藏 变为新检索
        }
        this.favoriteLoading = false;
      }
    },
    updateKeyWords(keyword) {
      // 表单模式 更新keywords
      Object.assign(this.retrieveParams, { keyword });
      if (this.isAutoQuery) {
        this.retrieveLog();
      }
    },
    async handleSubmitFavorite({ isCreate, resValue }) {
      await this.getFavoriteList(); // 编辑或新增刷新收藏列表
      if (isCreate) { // 新建收藏 刷新收藏列表同时高亮显示新增的收藏
        this.handleClickFavoriteItem(resValue);
        if (!this.isShowCollect) this.collectWidth = 240;
        this.isShowCollect = true;
      } else {
        this.initSearchList();
      };
    },
    // 点击收藏列表的收藏
    async handleClickFavoriteItem(value) {
      if (value === undefined) { // 点击为新检索时 清空收藏
        this.activeFavoriteID = -1;
        this.activeFavorite = {};
        this.isSqlSearchType = true;
        this.isFavoriteSearch = false;
        this.clearCondition('*');
        this.$refs.searchCompRef.clearValue();
        return;
      }
      const data = deepClone(value);
      if (!Object.keys(data.params.ip_chooser || []).length) {
        data.params.ip_chooser = {};
      }
      // 无host_scopes补充空的 host_scopes
      // if (!value.params?.host_scopes?.target_node_type) {
      //   value.params.host_scopes = { ...value.params?.host_scopes };
      //   value.params.host_scopes.target_node_type = '';
      //   value.params.host_scopes.target_nodes = [];
      // }
      this.addFavoriteData = {}; // 清空新建收藏的数据
      this.isFavoriteSearch = true;
      this.activeFavorite = deepClone(data);
      this.activeFavoriteID = data.id;
      this.retrieveFavorite(data);
    },
    // 收藏列表刷新, 判断当前是否有点击活跃的收藏 如有则进行数据更新
    updateActiveFavoriteData(value) {
      this.activeFavorite = value;
      this.initSearchList();
      this.isSqlSearchType = !this.isShowUiType;
    },
    // 当点击有表单模式的收藏时 初始化search列表
    initSearchList() {
      if (this.isShowUiType) {
        this.favSearchList = this.activeFavorite.params?.search_fields || [];
        this.$refs.searchCompRef.handleBlurSearchInput(this.activeFavorite.params?.keyword || '*');
      }
    },
    // 表格tab切换或聚类参数回填
    backFillClusterRouteParams(activeTableTab = 'origin', clusterParams) {
      this.activeTableTab = activeTableTab;
      const { query, params } = this.$route;
      const newQuery = { ...query };
      newQuery.activeTableTab = activeTableTab;
      // 切换为日志聚类且数据指纹有操作时 url添加日志聚类的操作参数
      if (clusterParams && activeTableTab === 'clustering') {
        this.clusterRouteParams = clusterParams;
        newQuery.clusterRouteParams = JSON.stringify(clusterParams);
      } else { // 切换为原始日志时 清空日志聚类的数据指纹操作参数
        this.clusterRouteParams = {};
        delete newQuery.clusterRouteParams;
      }
      this.$router.push({
        name: 'retrieve',
        params,
        query: newQuery,
      });
    },
  },
};
</script>

<style lang="scss" scoped>
  @import '../../scss/mixins/scroller.scss';

  .retrieve-container {
    min-width: 1280px;
    height: 100%;

    .page-loading-wrap {
      position: absolute;
      top: 0;
      width: 100%;
      height: 4px;
      z-index: 2400;
      overflow: hidden;
      background: pink;

      @keyframes animate-loading-bar {
        0% {
          transform: translateX(0);
          transform: translateX(0);
        }

        to {
          transform: translateX(-50%);
          transform: translateX(-50%);
        }
      }

      .page-loading-bar {
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        position: absolute;
        z-index: 10;
        visibility: visible;
        display: block;
        animation: animate-loading-bar 2s linear infinite;
        background-color: transparent;
        background-image: linear-gradient(
          to right,
          #ff5656 0,
          #ff5656 50%,
          #ff9c01 50%,
          #ff9c01 85%,
          #2dcb56 85%,
          #2dcb56 100%
        );
        background-repeat: repeat-x;
        background-size: 50%;
        width: 200%;
      }
    }

    /*详情页*/
    .retrieve-detail-container {
      position: relative;
      // display: flex;
      height: 100%;

      .result-content {
        display: flex;
        height: calc(100% - 52px);
      }

      .retrieve-condition {
        display: flow-root;
        width: 450px;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, .1);
        background: #fff;

        .bk-button-group {
          display: flex;
          width: 100%;
          height: 52px;

          .bk-button {
            flex: 1;
            height: 100%;
            border-top: 0;
            background: #fafbfd;
            border-color: #dcdee5;
            box-sizing: content-box;

            &.is-selected {
              background: #fff;
              border-top: none;
              border-bottom: none;
            }

            &.is-selected {
              border-color: #dcdee5;
              color: #3a84ff;
            }

            &:hover {
              border-color: #dcdee5;
            }
          }
        }

        .biz-menu-box {
          position: relative;
          margin: 16px 16px 0;
        }

        .king-tab {
          height: 100%;
          padding-top: 10px;

          .tab-content {
            /* stylelint-disable-next-line declaration-no-important */
            height: calc(100% - 52px) !important;
            overflow-y: auto;
            background-color: #fbfbfb;

            @include scroller;
          }

          .tab-content-item {
            padding: 0 24px;

            &:first-child {
              padding-bottom: 4px;
              background-color: #fff;
            }

            &:last-child {
              padding-top: 6px;
              padding-bottom: 26px;
            }
          }

          &.as-iframe {
            height: calc(100% + 10px);
          }

          .tab-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 24px 18px;
            color: #313238;
            font-size: 16px;

            .tab-title {
              font-size: 14px;
            }

            .icon-edit-line {
              color: #979ba5;
              cursor: pointer;
            }

            .icon-cog {
              font-size: 18px;
              color: #979ba5;
              cursor: pointer;
            }

            .icon-angle-double-left-line {
              margin-left: 8px;
              color: #979ba5;
              font-size: 16px;
              cursor: pointer;
            }
          }

          .tab-item-title {
            display: flex;
            align-items: center;
            margin: 16px 0 6px;
            line-height: 20px;
            font-size: 12px;
            color: #63656e;

            &.ip-quick-title {
              margin-top: 13px;
            }

            &:first-child {
              margin-top: 0;
            }
          }

          .field-filter-title {
            margin-bottom: 0;
            padding-top: 18px;
            font-size: 14px;
            font-weight: 500;
            color: #313238;
          }

          .flex-item-title {
            display: flex;
            justify-content: space-between;

            .filter-item {
              display: flex;

              span {
                margin-left: 24px;
                color: #3a84ff;
                cursor: pointer;
              }
            }
          }

          .add-filter-condition-container {
            display: flex;
            flex-wrap: wrap;
          }

          .cut-line {
            margin: 0 8px 0 4px;
            width: 1px;
            height: 32px;
            opacity: 1;
            background: #eceef5;
          }
        }
      }

      .retrieve-result {
        position: relative;
        width: calc(100% - 450px);
        height: 100%;
        background: #f5f6fa;
        z-index: 1;
      }

      .drag-bar {
        position: absolute;
        left: 449px;
        top: 52px;
        width: 1px;
        height: 100%;
        background: #dcdee5;

        .drag-icon {
          position: absolute;
          top: 50%;
          left: -3px;
          width: 7px;
          cursor: col-resize;
          transform: translateY(-50%);
          z-index: 50;
        }

        &.dragging {
          z-index: 100;
        }
      }
    }
  }
</style>

<style lang="scss">
  .auto-query-popover-content {
    display: flex;
    align-items: center;
    padding: 6px 0;
    color: #63656e;

    > span {
      margin: 0 12px 0 4px;
    }

    .confirm-btn {
      margin-left: 12px;
      color: #3a84ff;
      cursor: pointer;
    }
  }

  .condition-filter-popper {
    .tippy-tooltip {
      padding: 0;
    }
  }
</style>
