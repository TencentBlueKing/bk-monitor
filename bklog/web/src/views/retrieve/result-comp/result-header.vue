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
  <div class="result-header">
    <!-- 检索左侧 -->
    <div class="result-left">
      <div class="icon-container">
        <bk-popover
          ref="showFavoriteBtnRef"
          :disabled="showCollectIntroGuide"
          :tippy-options="expandTips"
        >
          <div
            :class="[
              'result-icon-box',
              {
                'light-icon': !isShowCollect,
                disabled: showCollectIntroGuide,
              },
            ]"
            @click="handleClickResultIcon('collect')"
          >
            <span class="bk-icon icon-star"></span>
          </div>
          <template #content>
            <div>{{ iconFavoriteStr }}</div>
          </template>
        </bk-popover>
        <bk-popover
          ref="showSearchBtnRef"
          :tippy-options="expandTips"
        >
          <div
            :class="['result-icon-box', { 'light-icon': !showRetrieveCondition }]"
            @click="handleClickResultIcon('search')"
          >
            <span class="bk-icon bklog-icon bklog-jiansuo"></span>
          </div>
          <template #content>
            <div>{{ iconSearchStr }}</div>
          </template>
        </bk-popover>
      </div>
      <!-- <div
        v-if="!isAsIframe"
        id="bizSelectorGuide"
        class="biz-menu-box"
      >
        <biz-menu-select theme="light"></biz-menu-select>
      </div> -->
    </div>
    <!-- 检索结果 -->
    <!-- <div class="result-text"></div> -->
    <!-- 检索日期 -->
    <div class="result-right">
      <VersionSwitch version="v1"></VersionSwitch>
      <time-range
        :timezone="timezone"
        :value="datePickerValue"
        @change="handleTimeRangeChange"
        @timezone-change="handleTimezoneChange"
      />
      <!-- 自动刷新 -->
      <bk-popover
        ref="autoRefreshPopper"
        :distance="15"
        :offset="0"
        :on-hide="handleDropdownHide"
        :on-show="handleDropdownShow"
        animation="slide-toggle"
        placement="bottom-start"
        theme="light bk-select-dropdown"
        trigger="click"
      >
        <slot name="trigger">
          <div class="auto-refresh-trigger">
            <span
              :class="['bklog-icon', isAutoRefresh ? 'icon-auto-refresh' : 'icon-no-refresh']"
              data-test-id="retrieve_span_periodicRefresh"
              @click.stop="handleRefreshDebounce"
            ></span>
            <span :class="isAutoRefresh && 'active-text'">{{ refreshTimeText }}</span>
            <span
              class="bk-icon icon-angle-down"
              :class="refreshActive && 'active'"
            ></span>
          </div>
        </slot>
        <template #content>
          <div class="bk-select-dropdown-content auto-refresh-content">
            <div class="bk-options-wrapper">
              <ul class="bk-options bk-options-single">
                <li
                  v-for="item in refreshTimeList"
                  :class="['bk-option', refreshTimeout === item.id && 'is-selected']"
                  :key="item.id"
                  @click="handleSelectRefreshTimeout(item.id)"
                >
                  <div class="bk-option-content">{{ item.name }}</div>
                </li>
              </ul>
            </div>
          </div>
        </template>
      </bk-popover>
      <bk-popover
        v-if="isShowRetrieveSetting"
        :distance="11"
        :offset="0"
        animation="slide-toggle"
        placement="bottom-end"
        theme="light bk-select-dropdown"
        trigger="click"
      >
        <slot name="trigger">
          <div
            class="more-operation"
            id="more-operator"
          >
            <i class="bklog-icon bklog-ellipsis-more"></i>
          </div>
        </slot>
        <template #content>
          <div class="retrieve-setting-container">
            <ul
              ref="menu"
              class="list-menu"
            >
              <li
                v-for="menu in showSettingMenuList"
                class="list-menu-item"
                :key="menu.id"
                @click="handleMenuClick(menu.id)"
              >
                {{ menu.name }}
              </li>
            </ul>
          </div>
        </template>
      </bk-popover>
    </div>
    <step-box
      v-if="showCollectIntroGuide"
      :tip-styles="{
        top: '50px',
        left: '14px',
      }"
      :has-border="true"
      placement="bottom"
    >
      <template #title>
        <div>{{ $t('检索收藏功能支持分组和管理') }}</div>
      </template>
      <template #action>
        <div
          class="action-text"
          @click="handleCloseGuide"
        >
          {{ $t('知道了') }}
        </div>
      </template>
    </step-box>
  </div>
</template>

<script>
  import BizMenuSelect from '@/global/bk-space-choice/index'
  import StepBox from '@/components/step-box';
  import { debounce } from 'throttle-debounce';
  import { mapGetters, mapState } from 'vuex';
  import VersionSwitch from '@/global/version-switch.vue';
  import TimeRange from '../../../components/time-range/time-range';

  export default {
    components: {
      BizMenuSelect,
      VersionSwitch,
      TimeRange,
      StepBox,
    },
    props: {
      showRetrieveCondition: {
        type: Boolean,
        required: true,
      },
      retrieveParams: {
        type: Object,
        required: true,
      },
      datePickerValue: {
        type: Array,
        required: true,
      },
      latestFavoriteId: {
        type: [Number, String],
        default: '',
      },
      indexSetItem: {
        type: Object,
        required: true,
      },
      isAsIframe: {
        type: Boolean | String,
        required: true,
      },
      isShowCollect: {
        type: Boolean,
        required: true,
      },
      timezone: {
        type: String,
        required: true,
      },
      clusteringData: {
        type: Object,
        required: true,
      },
    },
    data() {
      return {
        expandTips: {
          placement: 'bottom',
          trigger: 'mouseenter',
        },
        expandText: '',
        refreshActive: false, // 自动刷新下拉激活
        refreshTimer: null, // 自动刷新定时器
        refreshTimeout: 0, // 0 这里表示关闭自动刷新
        refreshTimeList: [
          {
            id: 0,
            name: `off ${this.$t('关闭')}`,
          },
          {
            id: 60000,
            name: '1m',
          },
          {
            id: 300000,
            name: '5m',
          },
          {
            id: 900000,
            name: '15m',
          },
          {
            id: 1800000,
            name: '30m',
          },
          {
            id: 3600000,
            name: '1h',
          },
          {
            id: 7200000,
            name: '2h',
          },
          {
            id: 86400000,
            name: '1d',
          },
        ],
        settingMenuList: [
          // { id: 'index', name: '全文索引' },
          // !!TODO 先关闭字段清洗入口
          // { id: 'extract', name: this.$t('button-字段清洗').replace('button-', '') },
          { id: 'clustering', name: this.$t('日志聚类') },
        ],
        accessList: [
          {
            id: 'logMasking',
            name: this.$t('日志脱敏'),
          },
          {
            id: 'logInfo',
            name: this.$t('采集详情'),
          },
        ],
        routeNameList: {
          // 路由跳转name
          log: 'manage-collection',
          custom: 'custom-report-detail',
          bkdata: 'bkdata-index-set-manage',
          es: 'es-index-set-manage',
          indexManage: 'log-index-set-manage',
        },
        /** 日志脱敏路由跳转key */
        maskingRouteKey: 'log',
        /** 日志脱敏路由 */
        maskingConfigRoute: {
          log: 'collectMasking',
          es: 'es-index-set-masking',
          custom: 'custom-report-masking',
          bkdata: 'bkdata-index-set-masking',
          setIndex: 'log-index-set-masking',
        },
        detailJumpRouteKey: 'log', // 路由key log采集列表 custom自定义上报 es、bkdata、setIndex 第三方ED or 计算平台 or 索引集
        isFirstCloseCollect: false,
        showSettingMenuList: [],
        catchSettingMenuList: [],
        showCollectIntroGuide: false,
      };
    },
    computed: {
      ...mapState({
        bkBizId: state => state.bkBizId,
        userGuideData: state => state.userGuideData,
        isExternal: state => state.isExternal,
        storeIsShowClusterStep: state => state.storeIsShowClusterStep,
      }),
      ...mapGetters({
        isShowMaskingTemplate: 'isShowMaskingTemplate',
        isUnionSearch: 'isUnionSearch',
      }),
      isShowRetrieveSetting() {
        return !this.isExternal && !this.isUnionSearch;
      },
      refreshTimeText() {
        if (!this.refreshTimeout) return 'off';
        return this.refreshTimeList.find(item => item.id === this.refreshTimeout).name;
      },
      isAutoRefresh() {
        return this.refreshTimeout !== 0;
      },
      isAiopsToggle() {
        // 日志聚类总开关
        const { bkdata_aiops_toggle: bkdataAiopsToggle } = window.FEATURE_TOGGLE;
        const aiopsBizList = window.FEATURE_TOGGLE_WHITE_LIST?.bkdata_aiops_toggle;

        switch (bkdataAiopsToggle) {
          case 'on':
            return true;
          case 'off':
            return false;
          default:
            return aiopsBizList ? aiopsBizList.some(item => item.toString() === this.bkBizId) : false;
        }
      },
      /** 日志聚类开关 */
      clusterSwitch() {
        return this.clusteringData?.is_active;
      },
      iconFavoriteStr() {
        return this.$t('点击{n}收藏', {
          n: !this.isShowCollect
            ? this.$t('label-展开').replace('label-', '')
            : this.$t('label-收起').replace('label-', ''),
        });
      },
      iconSearchStr() {
        return this.$t('点击{n}检索', {
          n: !this.showRetrieveCondition
            ? this.$t('label-展开').replace('label-', '')
            : this.$t('label-收起').replace('label-', ''),
        });
      },
    },
    watch: {
      indexSetItem: {
        immediate: true,
        handler(val) {
          this.setShowLiList(val);
        },
      },
      clusteringData: {
        immediate: true,
        handler() {
          this.handleShowSettingMenuListChange();
        },
      },
      storeIsShowClusterStep() {
        this.handleShowSettingMenuListChange();
      },
    },
    created() {
      this.showCollectIntroGuide = this.userGuideData?.function_guide?.search_favorite ?? false;
      this.handleRefreshDebounce = debounce(300, this.handleRefresh);
    },
    mounted() {
      document.addEventListener('visibilitychange', this.handleVisibilityChange);
      window.bus.$on('changeTimeByChart', this.handleChangeTimeByChart);
    },
    beforeUnmount() {
      document.removeEventListener('visibilitychange', this.handleVisibilityChange);
      window.bus.$off('changeTimeByChart', this.handleChangeTimeByChart);
    },
    methods: {
      removeFavorite(id) {
        this.$emit('remove', id);
      },
      // retrieveFavorite(data) {
      //   this.$emit('retrieveFavorite', data);
      // },
      // 日期变化
      handleTimeRangeChange(val) {
        if (val.every(item => typeof item === 'string')) {
          localStorage.setItem('SEARCH_DEFAULT_TIME', JSON.stringify(val));
        }
        this.$emit('update:date-picker-value', val);
        this.setRefreshTime(0);
        this.$emit('date-picker-change');
      },
      handleTimezoneChange(timezone) {
        this.$emit('timezone-change', timezone);
        this.$emit('date-picker-change');
      },
      handleChangeTimeByChart(val) {
        this.handleTimeRangeChange(val);
        window.bus.$emit('retrieveWhenChartChange');
      },
      // 自动刷新
      handleDropdownShow() {
        this.refreshActive = true;
      },
      handleDropdownHide() {
        this.refreshActive = false;
      },
      handleSelectRefreshTimeout(timeout) {
        this.setRefreshTime(timeout);
        this.$refs.autoRefreshPopper.instance.hide();
      },
      // 清除定时器，供父组件调用
      pauseRefresh() {
        clearTimeout(this.refreshTimer);
      },
      // 如果没有参数就是检索后恢复自动刷新
      setRefreshTime(timeout = this.refreshTimeout) {
        clearTimeout(this.refreshTimer);
        this.refreshTimeout = timeout;
        if (timeout) {
          this.refreshTimer = setTimeout(() => {
            this.$emit('should-retrieve');
          }, timeout);
        }
      },
      handleVisibilityChange() {
        // 窗口隐藏时取消轮询，恢复时恢复轮询（原来是自动刷新就恢复自动刷新，原来不刷新就不会刷新）
        document.hidden ? clearTimeout(this.refreshTimer) : this.setRefreshTime();
      },
      handleMenuClick(val) {
        // 不属于新开页面的操作
        if (['index', 'extract', 'clustering'].includes(val)) {
          this.$emit('setting-menu-click', val);
          return;
        }
        const params = {
          indexSetId: this.indexSetItem?.index_set_id,
          collectorId: this.indexSetItem?.collector_config_id,
        };
        // 判断当前是否是脱敏配置 分别跳不同的路由
        const routeName =
          val === 'logMasking'
            ? this.maskingConfigRoute[this.maskingRouteKey]
            : this.routeNameList[this.detailJumpRouteKey];
        // 不同的路由跳转 传参不同
        const { href } = this.$router.resolve({
          name: routeName,
          params,
          query: {
            spaceUid: this.$store.state.spaceUid,
            type: val === 'logMasking' ? 'masking' : undefined,
          },
        });
        window.open(href, '_blank');
      },
      handleShowSettingMenuListChange() {
        const isShowClusterSet = this.clusteringData?.is_active || this.storeIsShowClusterStep;
        this.showSettingMenuList = this.catchSettingMenuList.filter(item => {
          return item.id === 'clustering' ? isShowClusterSet : true;
        });
      },
      setShowLiList(setItem) {
        if (JSON.stringify(setItem) === '{}') return;
        if (setItem.scenario_id === 'log') {
          // 索引集类型为采集项或自定义上报
          if (setItem.collector_scenario_id === null) {
            // 若无日志类型 则类型为索引集
            this.initJumpRouteList('setIndex');
            return;
          }
          // 判断是否是自定义上报类型
          this.initJumpRouteList(setItem.collector_scenario_id === 'custom' ? 'custom' : 'log');
          return;
        }
        // 当scenario_id不为log（采集项，索引集，自定义上报）时，不显示字段设置
        this.initJumpRouteList(setItem.scenario_id, true);
      },
      /**
       * @desc: 初始化选择列表
       * @param {String} detailStr 当前索引集类型
       * @param {Boolean} isFilterExtract 是否过滤字段设置
       */
      initJumpRouteList(detailStr, isFilterExtract = false) {
        if (!['log', 'es', 'bkdata', 'custom', 'setIndex'].includes(detailStr)) {
          this.catchSettingMenuList = this.isAiopsToggle ? this.settingMenuList : [];
          return;
        }
        // 赋值详情路由的key
        if (detailStr === 'setIndex') {
          this.detailJumpRouteKey = 'indexManage';
        } else {
          this.detailJumpRouteKey = detailStr;
        }
        // 日志脱敏的路由key
        this.maskingRouteKey = detailStr;
        // 判断是否展示字段设置
        const filterMenuList = this.isAiopsToggle
          ? this.settingMenuList.filter(item => (isFilterExtract ? item.id !== 'extract' : true))
          : [];
        const accessList = this.accessList.filter(item =>
          this.isShowMaskingTemplate ? true : item.id !== 'logMasking',
        );
        // 合并其他
        this.catchSettingMenuList = filterMenuList.concat(accessList);
      },
      handleClickResultIcon(type) {
        if (type === 'collect') {
          this.$emit('update-collect-condition', !this.isShowCollect);
        } else {
          this.showRetrieveCondition ? this.$emit('close-retrieve-condition') : this.$emit('open');
        }
      },
      handleCloseGuide() {
        this.$http
          .request('meta/updateUserGuide', {
            data: { function_guide: 'search_favorite' },
          })
          .then(() => {
            this.showCollectIntroGuide = false;
            this.updateUserGuide();
          })
          .catch(e => {
            console.warn(e);
          });
      },
      /** 更新用户指引 */
      updateUserGuide() {
        this.$http.request('meta/getUserGuide').then(res => {
          this.$store.commit('setUserGuideData', res.data);
        });
      },
      handleRefresh() {
        this.$emit('should-retrieve');
      },
    },
  };
</script>

<style lang="scss">
  .result-header {
    position: relative;
    display: flex;
    justify-content: space-between;
    // align-items: center;
    width: 100%;
    height: 48px;
    font-size: 12px;
    color: #63656e;
    background: #fff;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.1);

    &:after {
      position: absolute;
      bottom: 0;
      z-index: 800;
      width: 100%;
      height: 4px;
      content: '';
      box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.1);
    }

    .result-left {
      display: flex;
      align-items: center;

      .icon-container {
        position: relative;
        display: flex;
        margin: 17px 25px 17px 14px;
        background: #f0f1f5;
        border-radius: 2px;

        > :first-child {
          margin-right: 2px;
        }

        // &::after {
        //   position: absolute;
        //   top: 6px;
        //   right: -25px;
        //   width: 1px;
        //   height: 14px;
        //   content: '';
        //   background-color: #dcdee5;
        // }

        .result-icon-box {
          width: 32px;
          height: 24px;
          font-size: 14px;
          line-height: 20px;
          color: #fff;
          text-align: center;
          cursor: pointer;
          background: #699df4;
          border-radius: 2px;

          &.light-icon {
            color: #63656e;
            background: #f0f1f5;
          }

          .icon-jiansuo {
            display: inline-block;
            font-size: 18px;
            transform: translateY(2px);
          }

          &.disabled {
            /* stylelint-disable-next-line declaration-no-important */
            pointer-events: none !important;
            cursor: not-allowed;
          }

          &.light-icon:hover {
            background: #dcdee5;
          }
        }
      }

      .biz-menu-box {
        position: relative;
      }
    }

    .result-right {
      display: flex;
      align-items: center;
    }

    .open-condition {
      display: flex;
      flex-shrink: 0;
      align-items: center;
      justify-content: center;
      width: 49px;
      height: 100%;
      font-size: 24px;
      color: #979ba5;
      cursor: pointer;
      border-right: 1px solid #f0f1f5;

      &:hover {
        color: #3a84ff;
      }
    }

    .result-text {
      width: 100%;
    }

    .time-range-wrap {
      position: relative;
      display: flex;
      align-items: center;

      &::before {
        position: absolute;
        top: 8px;
        left: 0;
        width: 1px;
        height: 14px;
        content: '';
        background-color: #dcdee5;
      }
    }

    .auto-refresh-trigger {
      display: flex;
      align-items: center;
      height: 52px;
      line-height: 22px;
      white-space: nowrap;
      cursor: pointer;

      .bklog-icon {
        padding: 0 5px 0 17px;
        font-size: 14px;
        color: #63656e;
      }

      .active-text {
        color: #3a84ff;
      }

      .icon-angle-down {
        margin: 0 10px;
        font-size: 22px;
        color: #63656e;
        transition: transform 0.3s;

        &.active {
          transition: transform 0.3s;
          transform: rotate(-180deg);
        }
      }

      &:hover > span {
        color: #3a84ff;
      }

      &::before {
        position: absolute;
        top: 20px;
        left: 0;
        width: 1px;
        height: 14px;
        content: '';
        background-color: #dcdee5;
      }
    }

    .more-operation {
      display: flex;
      align-items: center;
      height: 52px;
      padding: 0 16px 0 12px;
      line-height: 22px;
      white-space: nowrap;
      cursor: pointer;

      .bklog-ellipsis-more {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        overflow: hidden;
        font-size: 18px;

        &:hover {
          color: #0083ff;
          cursor: pointer;
          background-color: #e1ecff;
          border-radius: 2px;
        }
      }

      &::before {
        position: absolute;
        top: 20px;
        left: 0;
        width: 1px;
        height: 14px;
        content: '';
        background-color: #dcdee5;
      }
    }

    .step-box {
      z-index: 1001;
      min-height: 60px;

      .target-arrow {
        /* stylelint-disable-next-line declaration-no-important */
        top: -5px !important;

        /* stylelint-disable-next-line declaration-no-important */
        left: 10px !important;
        border-top: 1px solid #dcdee5;
        border-left: 1px solid #dcdee5;
      }
    }
  }

  .auto-refresh-content {
    width: 84px;

    .bk-options .bk-option-content {
      padding: 0 13px;
    }
  }

  .retrieve-setting-container {
    .list-menu {
      display: flex;
      flex-direction: column;
      padding: 6px 0;
      color: #63656e;
      background-color: white;

      &-item {
        display: flex;
        align-items: center;
        min-width: 150px;
        height: 32px;
        padding: 0 10px;

        &:hover {
          color: #3a84ff;
          cursor: pointer;
          background-color: #eaf3ff;
        }
      }
    }
  }
</style>
