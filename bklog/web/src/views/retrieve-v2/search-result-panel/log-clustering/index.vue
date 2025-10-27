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
  <div class="log-cluster-table-container-main">
    <div
      v-if="!globalLoading"
      class="log-cluster-table-container"
    >
      <div
        v-if="isShowTopNav"
        class="cluster-nav"
        data-test-id="cluster_div_fingerOperate"
      >
        <strategy
          :cluster-switch="clusterSwitch"
          :is-cluster-active="isClusterActive"
          :strategy-submit-status="watchStrategySubmitStatus"
        />

        <finger-operate
          :finger-operate-data="fingerOperateData"
          :request-data="requestData"
          :total-fields="totalFields"
          :cluster-switch="clusterSwitch"
          :strategy-have-submit="strategyHaveSubmit"
          :is-cluster-active="isClusterActive"
          @handle-finger-operate="handleFingerOperate"
        />
      </div>

      <div
        v-if="isShowGroupTag"
        style="margin: 0 0 16px -6px"
      >
        <bk-tag v-if="getDimensionStr">
          {{ getDimensionStr }}
        </bk-tag>
        <bk-tag
          v-if="getGroupStr"
          closable
          @close="handleCloseGroupTag"
        >
          {{ getGroupStr }}
        </bk-tag>
        <bk-tag
          v-if="getYearStr"
          closable
          @close="handleCloseYearTag"
        >
          {{ getYearStr }}
        </bk-tag>
      </div>

      <bk-alert
        v-if="clusterSwitch && !exhibitAll"
        :title="$t('日志聚类必需至少有一个text类型的字段，当前无该字段类型，请前往日志清洗进行设置。')"
        type="info"
        closable
      >
      </bk-alert>

      <template v-if="exhibitAll">
        <clustering-loader
          v-if="tableLoading"
          :width-list="smallLoaderWidthList"
          is-loading
        />
        <quick-cluster-step
          v-else-if="isShowClusterStep"
          style="min-height: calc(100vh - 410px)"
          ref="stepRef"
          :cluster-step-data="clusterStepData"
        />
        <quick-open-cluster
          v-else-if="!clusterSwitch"
          style="min-height: calc(100vh - 410px)"
          :retrieve-params="retrieveParams"
          :total-fields="totalFields"
          @cluster-created="handleClusterCreated"
        />
        <data-fingerprint
          v-else-if="dataFingerprintShow"
          v-bind="$attrs"
          ref="fingerTableRef"
          v-on="$listeners"
          :all-finger-list="allFingerList"
          :clustering-config="clusteringConfig"
          :finger-list="fingerList"
          :is-page-over="isPageOver"
          :loader-width-list="smallLoaderWidthList"
          :request-data="requestData"
          @handle-finger-operate="handleFingerOperate"
          @handle-scroll-is-show="handleScrollIsShow"
          @pagination-options="paginationOptions"
          @update-request="requestFinger"
          @show-change="v => $emit('show-change', v)"
        />
      </template>

      <bk-table
        v-else
        class="no-text-table"
        :data="[]"
      >
        <template #empty>
          <div>
            <empty-status
              class="empty-text"
              :show-text="false"
              empty-type="empty"
            >
              <p v-if="indexSetItem?.scenario_id !== 'log' && !isHaveAnalyzed">
                <i18n path="无分词字段 请前往 {0} 调整清洗">
                  <span
                    class="empty-leave"
                    @click="handleLeaveCurrent"
                    >{{ $t('计算平台') }}</span
                  >
                </i18n>
              </p>
              <div v-else>
                <p>{{ exhibitText }}</p>
                <span
                  class="empty-leave"
                  @click="handleLeaveCurrent"
                >
                  {{ exhibitOperate }}
                </span>
              </div>
            </empty-status>
          </div>
        </template>
      </bk-table>

      <div
        class="fixed-scroll-top-btn"
        v-show="showScrollTop"
        @click="scrollToTop"
      >
        <i class="bk-icon icon-angle-up"></i>
      </div>
    </div>
    <clustering-loader
      v-else
      :width-list="loadingWidthList.global"
      is-loading
    />
  </div>
</template>

<script>
  import EmptyStatus from '@/components/empty-status';
  import ClusteringLoader from '@/skeleton/clustering-loader';
  import { mapGetters } from 'vuex';
  import FingerOperate from './components/finger-operate';
  import DataFingerprint from './data-fingerprint';
  import QuickOpenCluster from './components/quick-open-cluster-step/quick-open-cluster';
  import QuickClusterStep from './components/quick-open-cluster-step/quick-cluster-step';
  import Strategy from './components/strategy';
  import { RetrieveUrlResolver } from '@/store/url-resolver';
  import useFieldNameHook from '@/hooks/use-field-name';

  import { BK_LOG_STORAGE } from '@/store/store.type';

  export default {
    components: {
      DataFingerprint,
      ClusteringLoader,
      FingerOperate,
      EmptyStatus,
      Strategy,
      QuickOpenCluster,
      QuickClusterStep,
    },
    inheritAttrs: false,
    props: {
      retrieveParams: {
        type: Object,
        required: true,
      },
      height: {
        type: Number,
      },
    },
    data() {
      return {
        tableLoading: false, // 详情loading
        isShowCustomize: true, // 是否显示自定义
        fingerOperateData: {
          patternSize: 0, // slider当前值
          sliderMaxVal: 0, // pattern最大值
          comparedList: [], // 同比List
          patternList: [], // pattern敏感度List
          isShowCustomize: true, // 是否显示自定义
          dimensionList: [], // 维度字段列表
          selectGroupList: [], // 选中的字段分组列表
          yearSwitch: false, // 同比开关
          yearOnYearHour: 0, // 同比的值
          groupList: [], // 所有的字段分组列表
          alarmObj: {}, // 是否需要告警对象
        },
        requestData: {
          // 数据请求
          pattern_level: '05',
          year_on_year_hour: 0,
          show_new_pattern: false,
          group_by: [],
          size: 10000,
          remark_config: 'all',
          owner_config: 'all',
          owners: [],
        },
        isPageOver: false,
        fingerPage: 1,
        fingerPageSize: 50,
        loadingWidthList: {
          // loading表头宽度列表
          global: [''],
          notCompared: [150, 90, 90, ''],
          compared: [150, 90, 90, 100, 100, ''],
        },
        fingerList: [],
        allFingerList: [], // 所有数据指纹List
        showScrollTop: false, // 是否展示返回顶部icon
        isInitPage: true, // 是否是第一次进入数据指纹
        /** 是否创建过策略 */
        strategyHaveSubmit: false,
        isShowClusterStep: true,
        clusterStepDataLoading: false,
        clusterStepData: {},
        isFieldInit: false,
        statusTimer: null,
        isClickSearch: false,
        isClusterActive: true,
        dataFingerprintShow: false,
      };
    },
    computed: {
      ...mapGetters({
        globalsData: 'globals/globalsData',
      }),
      indexFieldInfo() {
        return this.$store.state.indexFieldInfo;
      },
      indexSetFieldConfig() {
        return this.$store.state.indexSetFieldConfig;
      },
      smallLoaderWidthList() {
        return this.requestData.year_on_year_hour > 0
          ? this.loadingWidthList.compared
          : this.loadingWidthList.notCompared;
      },
      exhibitText() {
        return this.collectorConfigId
          ? this.$t('当前无可用字段，请前往日志清洗进行设置')
          : this.$t('当前索引集不支持日志聚类设置');
      },
      exhibitOperate() {
        return this.collectorConfigId ? this.$t('跳转到日志清洗') : '';
      },
      bkBizId() {
        return this.$store.state.bkBizId;
      },
      showFieldAlias() {
        return this.$store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS];
      },
      isHaveAnalyzed() {
        return this.totalFields.some(item => item.is_analyzed);
      },
      totalFields() {
        return this.indexFieldInfo.fields || [];
      },
      clusteringConfig() {
        return this.indexSetFieldConfig.clustering_config;
      },
      collectorConfigId() {
        return this.indexSetFieldConfig.clean_config.extra?.collector_config_id;
      },
      /** 日志聚类开关 */
      clusterSwitch() {
        return this.clusteringConfig?.is_active || false;
      },
      exhibitAll() {
        /**
         *  无字段提取或者聚类开关没开时直接不显示聚类nav和table
         *  来源如果是数据平台并且日志聚类大开关有打开则进入text判断
         *  有text则提示去开启日志聚类 无则显示跳转计算平台
         */
        return this.totalFields.some(el => el.field_type === 'text');
      },
      globalLoading() {
        // 判断是否可以字段提取的全局loading
        return this.indexFieldInfo.is_loading || this.isFieldInit;
      },
      routerIndexSet() {
        return window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId;
      },
      getDimensionStr() {
        return this.fingerOperateData.dimensionList.length
          ? `${this.$t('维度')} : ${this.fingerOperateData.dimensionList.join(', ')}`
          : '';
      },
      getGroupStr() {
        return this.fingerOperateData.selectGroupList.length
          ? `${this.$t('分组')} : ${this.fingerOperateData.selectGroupList.join(', ')}`
          : '';
      },
      getYearStr() {
        return this.requestData.year_on_year_hour ? `${this.$t('同比')} : ${this.requestData.year_on_year_hour}h` : '';
      },
      isShowGroupTag() {
        return (
          this.clusterSwitch && !this.isShowClusterStep && (this.getGroupStr || this.getDimensionStr || this.getYearStr)
        );
      },
      isShowTopNav() {
        return this.exhibitAll && this.clusterSwitch && !this.isShowClusterStep;
      },
      indexSetItem() {
        return this.$store.state.indexItem;
      },
      isSearchIng() {
        return this.$store.state.indexSetQueryResult?.is_loading || false;
      },
      clusterParams() {
        return this.$store.state.clusterParams;
      },
    },
    watch: {
      totalFields: {
        deep: true,
        immediate: true,
        handler(newVal, oldVal) {
          if (newVal === oldVal) {
            return;
          }
          // 当前nav为数据指纹且数据指纹开启点击指纹nav则不再重复请求
          this.fingerList = [];
          this.allFingerList = [];
          /**
           *  无字段提取或者聚类开关没开时直接不显示聚类nav和table
           *  来源如果是数据平台并且日志聚类大开关有打开则进入text判断
           *  有text则提示去开启日志聚类 无则显示跳转计算平台
           */
          this.fieldsChangeQuery();
        },
      },
      isSearchIng(v) {
        this.isClickSearch = true;
        if (this.exhibitAll && !this.isInitPage && this.isClusterActive && v) this.requestFinger();
      },
      routerIndexSet() {
        this.isShowClusterStep = true;
        this.confirmClusterStepStatus();
      },
      isShowClusterStep(v) {
        this.$store.commit('updateState', {'storeIsShowClusterStep': v});
      },
      showFieldAlias() {
        this.filterGroupList();
      },
    },
    methods: {
      setRouteParams() {
        const route = this.$route;
        const store = this.$store;
        const router = this.$router;

        const query = { ...route.query };

        const resolver = new RetrieveUrlResolver({
          clusterParams: store.state.clusterParams,
        });

        Object.assign(query, resolver.resolveParamsToUrl());

        router.replace({
          query,
        });
      },
      /**
       * @desc: 初始化table所需的一些参数
       */
      async initTableOperator() {
        const { log_clustering_level_year_on_year: yearOnYearList, log_clustering_level: clusterLevel } =
          this.globalsData;
        let patternLevel;
        if (clusterLevel && clusterLevel.length > 0) {
          // 判断奇偶数来取pattern中间值
          if (clusterLevel.length % 2 === 1) {
            patternLevel = (clusterLevel.length + 1) / 2;
          } else {
            patternLevel = clusterLevel.length / 2;
          }
        }
        const patternList = clusterLevel.sort((a, b) => Number(b) - Number(a));
        // clusterLevel[patternLevel - 1]
        const queryRequestData = {
          pattern_level: '05',
          group_by: [],
          remark_config: 'all',
          owner_config: 'all',
          owners: [],
        };
        // 通过路由返回的值 初始化数据指纹的操作参数 url是否有缓存的值
        if (this.isInitPage && !!this.clusterParams) {
          const paramData = structuredClone(this.clusterParams);
          const findIndex = clusterLevel.findIndex(item => item === String(paramData.pattern_level));
          if (findIndex >= 0) patternLevel = findIndex + 1;
          Object.assign(queryRequestData, paramData, {
            pattern_level: paramData.pattern_level ? paramData.pattern_level : clusterLevel[patternLevel - 1],
          });
        }
        const { year_on_year_hour: yearOnYearHour } = queryRequestData;
        Object.assign(this.fingerOperateData, {
          patternSize: patternLevel - 1,
          sliderMaxVal: clusterLevel.length - 1,
          patternList,
          comparedList: yearOnYearList.filter(item => item.id !== 0),
          yearOnYearHour: yearOnYearHour > 0 ? yearOnYearHour : 1,
          yearSwitch: yearOnYearHour > 0,
          dimensionList: [],
          selectGroupList: queryRequestData.group_by || [], // 未请求维度时 默认是所有字段的分组
        });
        // 这里判断是否有保存过所有人都显示一样的分组 如果有则直接显示相应的分组
        const groupFields = await this.getInitGroupFields();
        if (groupFields?.length) {
          const selectGroupList = this.fingerOperateData.selectGroupList.filter(item => !groupFields.includes(item));
          // 如果初始化时有默认维度的字段 将维度和分组分开来处理
          Object.assign(queryRequestData, { group_by: [...groupFields, ...selectGroupList] });
          Object.assign(this.fingerOperateData, {
            dimensionList: groupFields,
            selectGroupList,
          });
        }
        Object.assign(this.requestData, queryRequestData);
        this.$store.commit('updateState', {'clusterParams': this.requestData});
        this.setRouteParams();
        this.isInitPage = false;
      },
      /**
       * @desc: 获取分组状态
       * @returns {Array<string>}
       */
      async getInitGroupFields() {
        try {
          if (this.clusterSwitch) {
            const params = { index_set_id: this.routerIndexSet };
            const data = { collector_config_id: this.collectorConfigId };
            const res = await this.$http.request('/logClustering/getConfig', { params, data });
            return res.data.group_fields;
          }
          return [];
        } catch (err) {
          console.warn(err);
          return [];
        }
      },
      /**
       * @desc: 数据指纹操作
       * @param { String } operateType 操作类型
       * @param { Any } val 具体值
       */
      handleFingerOperate(operateType, val = {}, isQuery = false) {
        switch (operateType) {
          case 'requestData': // 数据指纹的请求参数
            Object.assign(this.requestData, val);
            // 数据指纹对请求参数修改过的操作将数据回填到url上
            this.$store.commit('updateState', {'clusterParams': this.requestData});
            this.setRouteParams();
            break;
          case 'fingerOperateData': // 数据指纹操作的参数
            Object.assign(this.fingerOperateData, val);
            break;
          case 'editAlarm':
            {
              // 更新新类告警请求
              const {
                alarmObj: { strategy_id: strategyID },
              } = this.fingerOperateData;
              if (strategyID) this.$refs.fingerTableRef.policyEditing(strategyID);
            }
            break;
        }
        if (isQuery) this.requestFinger();
      },
      handleLeaveCurrent() {
        // 不显示字段提取时跳转计算平台
        if (this.indexSetItem?.scenario_id !== 'log' && !this.isHaveAnalyzed) {
          const jumpUrl = `${window.BKDATA_URL}`;
          window.open(jumpUrl, '_blank');
          return;
        }
        // 无清洗 去清洗
        if (!!this.collectorConfigId) {
          this.$router.push({
            name: 'clean-edit',
            params: { collectorId: this.collectorConfigId },
            query: {
              spaceUid: this.$store.state.spaceUid,
              backRoute: this.$route.name,
            },
          });
        }
      },
      /**
       * @desc: 数据指纹请求
       */
      requestFinger() {
        // loading中，或者没有开启数据指纹功能，或当前页面初始化或者切换索引集时不允许起请求
        if (this.tableLoading || !this.clusterSwitch || !this.isClusterActive) return;
        const {
          start_time,
          end_time,
          addition,
          size,
          keyword = '*',
          ip_chooser,
          host_scopes,
          interval,
          timezone,
        } = this.retrieveParams;
        this.tableLoading = true;
        this.$http
          .request(
            '/logClustering/clusterSearch',
            {
              params: {
                index_set_id: this.routerIndexSet,
              },
              data: {
                addition,
                size,
                keyword,
                ip_chooser,
                host_scopes,
                interval,
                timezone,
                start_time,
                end_time,
                ...this.requestData,
              },
            },
            { cancelWhenRouteChange: false },
          ) // 由于回填指纹的数据导致路由变化，故路由变化时不取消请求
          .then(res => {
            this.fingerPage = 1;
            this.fingerList = [];
            this.allFingerList = res.data;
            const sliceFingerList = res.data.slice(0, this.fingerPageSize);
            this.fingerList.push(...sliceFingerList);
            this.showScrollTop = false;
          })
          .finally(() => {
            this.isClickSearch = false;
            this.tableLoading = false;
          });
      },
      /**
       * @desc: 数据指纹分页操作
       */
      async paginationOptions() {
        if (this.isPageOver || this.fingerList.length >= this.allFingerList.length) {
          return;
        }
        this.isPageOver = true;
        this.fingerPage += 1;
        const { fingerPage: page, fingerPageSize: pageSize } = this;
        const sliceFingerList = this.allFingerList.slice(pageSize * (page - 1), pageSize * page);
        setTimeout(() => {
          this.fingerList.push(...sliceFingerList);
          this.isPageOver = false;
        }, 300);
      },
      /**
       * @desc: 初始化分组select数组
       */
      filterGroupList() {
        const { getConcatenatedFieldName } = useFieldNameHook({ store: this.$store });
        const filterList = this.totalFields
          .filter(el => el.es_doc_values && !/^__dist_/.test(el.field_name)) // 过滤__dist字段
          .map(item => {
            return getConcatenatedFieldName(item);
          });
        this.fingerOperateData.groupList = filterList;
      },
      scrollToTop() {
        const scrollEl = document.querySelector('.finger-container');
        this.$easeScroll(0, 300, scrollEl);
      },
      handleScrollIsShow() {
        const scrollEl = document.querySelector('.finger-container');
        this.showScrollTop = scrollEl.scrollTop > 550;
      },
      handleCloseGroupTag() {
        Object.assign(this.fingerOperateData, { selectGroupList: [] });
        this.handleFingerOperate('requestData', { group_by: this.fingerOperateData.dimensionList }, true);
      },
      handleCloseYearTag() {
        Object.assign(this.fingerOperateData, { yearSwitch: false });
        this.handleFingerOperate('requestData', { year_on_year_hour: 0 }, true);
      },
      watchStrategySubmitStatus(v) {
        this.strategyHaveSubmit = v;
      },
      handleClusterCreated() {
        this.isShowClusterStep = true;
        this.startPolling();
        this.clusterPolling();
      },
      async clusterPolling() {
        const isActiveCluster = await this.confirmClusterStepStatus();
        if (isActiveCluster) {
          this.filterGroupList();
          await this.initTableOperator(); // 初始化分组下拉列表
          this.requestFinger();
          this.stopPolling();
        }
      },
      startPolling(pollingTime = 10000) {
        this.stopPolling();
        this.statusTimer = setInterval(this.clusterPolling, pollingTime);
      },
      async confirmClusterStepStatus() {
        if (!this.isShowClusterStep) return;
        try {
          this.clusterStepDataLoading = true;
          const res = await this.getClusterConfigStatus();
          if (res.code === 0) {
            // 未完成，展示step步骤
            if (!res.data.access_finished) this.clusterStepData = res.data;
            this.isShowClusterStep = !res.data.access_finished;
            return res.data.access_finished;
          }
        } catch (error) {
          // 报错就证明没开日志聚类
          this.isShowClusterStep = false;
          this.stopPolling();
          return false;
        } finally {
          // 如果有报错信息，也直接停止轮询
          this.$nextTick(() => {
            if (this.$refs?.stepRef?.errorMessage) this.stopPolling();
          });
          this.clusterStepDataLoading = false;
        }
      },
      getClusterConfigStatus() {
        return this.$http.request(
          'retrieve/getClusteringConfigStatus',
          {
            params: {
              index_set_id: window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId,
            },
          },
          {
            catchIsShowMessage: false,
          },
        );
      },
      stopPolling() {
        // 清除定时器
        if (this.statusTimer) {
          clearInterval(this.statusTimer);
          this.statusTimer = null;
        }
      },
      async fieldsChangeQuery() {
        if (this.totalFields.length && !this.isFieldInit) {
          this.isFieldInit = true;
          this.startPolling();
          await this.clusterPolling();
          this.isFieldInit = false;
        }
      },
      async onMountedLoad() {
        if (!this.isClusterActive) {
          this.isClusterActive = true;
          await this.confirmClusterStepStatus();
          if (this.isClickSearch && !this.isInitPage) this.requestFinger();
          if (!this.isInitPage) {
            this.$store.commit('updateState', {'clusterParams': this.requestData});
            this.setRouteParams();
          }
        }
      },
      async onUnMountedLoad() {
        if (this.isClusterActive) {
          this.isClusterActive = false;
          this.$store.commit('updateState', {'clusterParams': null});
          this.setRouteParams();
          this.stopPolling(); // 停止状态轮询
        }
      },
    },
    async mounted() {
      await this.onMountedLoad();
    },
    async activated() {
      this.dataFingerprintShow = true;
      await this.onMountedLoad();
    },
    deactivated() {
      this.onUnMountedLoad();
      this.dataFingerprintShow = false;
    },
    unmounted() {
      this.onUnMountedLoad();
    },
    beforeDestroy() {
      this.$store.commit('updateState', {'clusterParams': null});
      this.stopPolling(); // 停止状态轮询
    },
  };
</script>

<style lang="scss">
  @import '@/scss/mixins/flex.scss';

  .log-cluster-table-container-main {
    height: 100%;
  }

  /* stylelint-disable no-descending-specificity */
  .log-cluster-table-container {
    height: 100%;

    .cluster-nav {
      flex-wrap: nowrap;
      align-items: center;
      height: 32px;
      margin-bottom: 12px;
      color: #63656e;
      @include flex-justify(space-between);
    }

    .bk-alert {
      margin-bottom: 16px;
    }
  }

  .no-text-table {
    .bk-table-empty-block {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: calc(100vh - 348px);
    }

    .empty-text {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: space-between;

      .bk-icon {
        font-size: 65px;
      }

      .empty-leave {
        margin-top: 8px;
        color: #3a84ff;
        cursor: pointer;
      }
    }
  }

  .fixed-scroll-top-btn {
    position: fixed;
    right: 14px;
    bottom: 24px;
    z-index: 2100;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    color: #63656e;
    cursor: pointer;
    background: #f0f1f5;
    border: 1px solid #dde4eb;
    border-radius: 4px;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.2);
    transition: all 0.2s;

    &:hover {
      color: #fff;
      background: #979ba5;
      transition: all 0.2s;
    }

    .bk-icon {
      font-size: 20px;
      font-weight: bold;
    }
  }
</style>
