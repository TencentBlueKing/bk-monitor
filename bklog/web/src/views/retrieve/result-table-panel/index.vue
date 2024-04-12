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
  <div class="result-table-panel">
    <bk-tab
      :active.sync="active"
      type="unborder-card"
      @tab-change="handleChangeTab"
    >
      <bk-tab-panel
        v-for="(panel, index) in panelList"
        v-bind="panel"
        :key="index"
      >
      </bk-tab-panel>
    </bk-tab>
    <div class="panel-content-wrap">
      <keep-alive>
        <original-log
          v-if="active === 'origin'"
          v-bind="$attrs"
          v-on="$listeners"
        />
        <log-clustering
          v-if="active === 'clustering'"
          v-bind="$attrs"
          ref="logClusteringRef"
          :active-table-tab="active"
          :config-data="configData"
          v-on="$listeners"
          @showOriginLog="showOriginLog"
        />
      </keep-alive>
    </div>
  </div>
</template>

<script>
import { mapState, mapGetters } from 'vuex';
import OriginalLog from './original-log/index.vue';
import LogClustering from './log-clustering/index.vue';
import reportLogStore from '@/store/modules/report-log';

export default {
  components: { OriginalLog, LogClustering },
  inheritAttrs: false,
  props: {
    configData: {
      type: Object,
      require: true
    },
    activeTableTab: {
      type: String,
      require: true
    },
    isInitPage: {
      type: Boolean,
      require: true
    }
  },
  data() {
    return {
      active: 'origin',
      isReported: false
    };
  },
  computed: {
    ...mapState({
      bkBizId: state => state.bkBizId,
      isExternal: state => state.isExternal
    }),
    ...mapGetters({
      isUnionSearch: 'isUnionSearch'
    }),
    isAiopsToggle() {
      // 日志聚类总开关
      if (this.isExternal || this.isUnionSearch) return false; // 外部版或联合查询时不包含日志聚类
      if (window.FEATURE_TOGGLE.bkdata_aiops_toggle !== 'on') return false;
      const aiopsBizList = window.FEATURE_TOGGLE_WHITE_LIST?.bkdata_aiops_toggle;

      return aiopsBizList ? aiopsBizList.some(item => item.toString() === this.bkBizId) : false;
    },
    panelList() {
      const list = [{ name: 'origin', label: this.$t('原始日志') }];
      if (this.isAiopsToggle) {
        list.push({ name: 'clustering', label: this.$t('日志聚类') });
      }

      return list;
    }
  },
  watch: {
    isInitPage() {
      if (this.activeTableTab === 'clustering' && this.isAiopsToggle) this.active = 'clustering';
    },
    active(val) {
      if (val === 'clustering' && !this.isReported) {
        const { name, meta } = this.$route;
        reportLogStore.reportRouteLog({
          route_id: name,
          nav_id: meta.navId,
          nav_name: '日志聚类'
        });
        this.isReported = true;
      }
    }
  },
  methods: {
    showOriginLog() {
      this.active = 'origin';
      this.handleChangeTab('origin');
    },
    async handleChangeTab(name) {
      this.$refs?.logClusteringRef?.$refs.fingerRef?.$refs.groupPopover.instance?.hide();
      await this.$nextTick();
      const clusterRef = this.$refs.logClusteringRef;
      const clusterParams =
        name === 'clustering'
          ? {
              activeNav: clusterRef?.active,
              requestData: clusterRef?.requestData
            }
          : null;
      this.$emit('backFillClusterRouteParams', name, clusterParams);
    }
  }
};
</script>

<style lang="scss">
.result-table-panel {
  position: relative;
  padding: 10px 24px 20px;
  margin: 0 0 16px;
  background: #fff;

  .bk-tab {
    margin-bottom: 16px;

    .bk-tab-section {
      display: none;
    }
  }

  .is-last {
    border-bottom: 1px solid #dfe0e5;
  }
}
</style>
