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
  <metric-dimension
    v-monitor-loading="{ isLoading: loading }"
    :metric-json="metricData"
    :plugin-data="pluginData"
    :is-from-home="true"
    :plugin-type="pluginType"
  />
</template>

<script>
import { retrieveCollectorPlugin } from 'monitor-api/modules/model';

import authorityMixinCreate from '../../mixins/authorityMixin';
import * as pluginManageAuth from './authority-map';
import MetricDimension from './plugin-instance/set-steps/metric-dimension/metric-dimension-dialog.vue';

export default {
  name: 'PluginSetmetric',
  components: {
    MetricDimension,
  },
  provide() {
    return {
      authority: this.authority,
      handleShowAuthorityDetail: this.handleShowAuthorityDetail,
    };
  },
  mixins: [authorityMixinCreate(pluginManageAuth)],
  data() {
    return {
      loading: false,
      metricData: [],
      pluginData: {},
      pluginType: null, // 插件类型
    };
  },
  created() {
    this.handleSowNav();
    this.getDeteilData();
  },
  methods: {
    async getDeteilData() {
      this.loading = true;
      let detailData = {};
      this.$store.commit('app/SET_NAV_TITLE', this.$t('加载中...'));
      await retrieveCollectorPlugin(this.$route.params.pluginId)
        .then(data => {
          detailData = data;
          this.$store.commit(
            'app/SET_NAV_TITLE',
            `${this.$t('route-' + '设置指标&维度').replace('route-', '')} - ${this.$route.params.pluginId}`
          );
        })
        .finally(() => {
          this.loading = false;
        });
      this.metricData = detailData.metric_json;
      this.pluginType = detailData.plugin_type;
      this.metricData.forEach(group => {
        group.fields.forEach(item => {
          item.isCheck = false;
          item.isDel = true;
          item.errValue = false;
          item.reValue = false;
          item.descReValue = false;
          item.showInput = false;
          item.isFirst = false;
          if (item.monitor_type === 'metric') {
            item.order = 0;
          } else {
            item.order = 1;
          }
        });
      });
      this.pluginData = {
        plugin_id: detailData.plugin_id,
        plugin_type: detailData.plugin_type,
        config_version: detailData.config_version,
        info_version: detailData.info_version,
      };
    },
    handleSowNav() {
      const routeList = [];
      const {
        options: { routes },
      } = this.$router;
      const { meta, name } = this.$route;
      this.showNav = !meta.noNavBar && !!name;
      if (this.showNav) {
        this.needCopyLink = meta.needCopyLink ?? false;
        this.needBack = meta.needBack ?? false;
        routeList.unshift({ name: this.$t(`route-${meta.title}`), id: name });
        const getRouteItem = meta => {
          const parentRoute = routes.find(item => item.name === meta?.route?.parent);
          parentRoute &&
            routeList.unshift({ name: this.$t(`route-${parentRoute?.meta?.title}`), id: parentRoute.name });
          if (parentRoute?.meta?.route?.parent) {
            getRouteItem(parentRoute?.meta);
          }
        };
        getRouteItem(meta);
      }
      /** 设置默认的路由 */
      this.$store.commit('app/SET_NAV_ROUTE_LIST', routeList);
    },
  },
};
</script>
