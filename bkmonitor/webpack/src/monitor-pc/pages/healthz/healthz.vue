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
  <div style="width: 100%">
    <!--服务状态-->
    <mo-healthz-header-view :msg.sync="msg" />
    <!--异常告警-->
    <mo-healthz-alarm-config :msg.sync="msg" />
  </div>
</template>
<script>
import store from './store/healthz/store';
import MoHealthzAlarmConfig from './healthz-error';
import MoHealthzHeaderView from './healthz-header';
// const configData = require('./config')
export default {
  store,
  name: 'MoHealthzView',
  components: {
    MoHealthzHeaderView,
    MoHealthzAlarmConfig
  },
  data() {
    return {
      msg: 1,
      dashLoading: true, // 控制页面是否载入中
      isShowBackend: !window.is_container_mode, // 容器化部署不展示自监控服务后台状态
      configData: {
        saasComponentNeedToTest: ['cmdb', 'bk_data', 'job', 'metadata', 'nodeman', 'gse'],
        displayedMetrics: ['system.cpu.percent', 'system.disk.ioutil', 'system.disk.usage', 'system.mem.process.usage'],
        displayedMetricsDescription: {
          'system.cpu.percent': this.$t('CPU使用率'),
          'system.disk.ioutil': this.$t('磁盘IO使用率'),
          'system.disk.usage': this.$t('磁盘使用率'),
          'system.mem.process.usage': this.$t('应用内存使用率')
        },
        backendCollectorComponent: ['gse_data', 'pre_kafka', 'transfer', 'influxdb_proxy', 'influxdb'],
        backendDataFlowComponent: [
          'access_data',
          'access_real_time_data',
          'access_event',
          'detect',
          'trigger',
          'alert_builder',
          'alert_manager',
          'composite',
          'converge',
          'action',
          'kernel_api'
        ],
        backendDependenciesComponent: [
          'kafka',
          'mysql',
          'elasticsearch',
          'supervisor',
          'redis',
          'celery',
          'graph_exporter'
        ],
        saasDependenciesComponent: ['cmdb', 'job', 'bk_data', 'metadata', 'nodeman', 'gse', 'rabbitmq', 'saas_celery']
      }
    };
  },
  mounted() {
    this.getGlobalData();
  },
  methods: {
    // 请求网络获取到全局数据
    getGlobalData() {
      // eslint-disable-next-line @typescript-eslint/no-this-alias
      // const self = this;
      // this.$api.healthz.getGlobalStatus({}, { needRes: true }).then((res) => {
      //   if (res.result && res.data.length) {
      //     // 将获取到的全局数据放入store中
      //     store.commit('loadGlobalData', res.data);
      //     // 数据加载完成后，需要将数据中的所有 ip 聚合放在列表里面
      //     const tmpIPlist = [];
      //     res.data.forEach((tmpData) => {
      //       if (
      //         tmpData.node_name === 'system'
      //         && Object.prototype.hasOwnProperty.call(tmpData, 'server_ip')
      //         && tmpData.server_ip !== ''
      //         && tmpIPlist.indexOf(tmpData.server_ip) === -1
      //       ) {
      //         tmpIPlist.push(tmpData.server_ip);
      //       }
      //     });
      //     // 首次加载选中的和全部的ip列表相同
      //     store.commit('changeSelectedIPs', tmpIPlist);
      //     store.commit('changeAllIPs', tmpIPlist);
      //   }
      //   // 取消 loading 状态
      //   self.dashLoading = false;
      // });
      // 填充配置信息
      this.loadConfigData();
    },
    // 读取配置信息，并且填充相关的参数
    loadConfigData() {
      // 填充对应的配置
      // 剔除tsdb-proxy
      if (this.$platform.ce) {
        const index = this.configData.backendCollectorComponent.indexOf('tsdb_proxy');
        this.configData.backendCollectorComponent.splice(index, 1);
      }
      store.commit('loadConfigSaasComponentNeedToTest', this.configData.saasComponentNeedToTest);
      store.commit('loadConfigBackendDataFlowComponent', this.configData.backendDataFlowComponent);
      store.commit('loadConfigBackendDependenciesComponent', this.configData.backendDependenciesComponent);
      store.commit('loadConfigSaasDependenciesComponent', this.configData.saasDependenciesComponent);
      store.commit('loadDisplayedMetrics', this.configData.displayedMetrics);
      store.commit('loadDisplayedMetricsDescription', this.configData.displayedMetricsDescription);
      store.commit('loadBackendCollectorComponent', this.configData.backendCollectorComponent);
    }
  }
};
</script>
<style lang="scss">
@media screen and (min-width: 1000px) {
  .el-dialog {
    /* stylelint-disable-next-line declaration-no-important */
    width: 522px !important;
  }
}

/* 全局dialog样式 */
.el-dialog {
  /* stylelint-disable-next-line declaration-no-important */
  width: 40% !important;
  height: 335px;
  overflow-x: hidden;
  overflow-y: auto;
}

.el-dialog .el-dialog__title {
  font-size: 16px;
  font-weight: normal;
  font-stretch: normal;
  line-height: 24px;
  color: #333;
  letter-spacing: 0px;
}

.el-dialog__body {
  max-height: 345px;

  /* stylelint-disable-next-line declaration-no-important */
  padding: 10px 20px !important;
  font-size: 14px;
  color: #606266;
}
</style>
