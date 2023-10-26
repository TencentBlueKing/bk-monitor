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
  <div class="main-content-box">
    <div class="main-content-box-title">
      {{ $t('监控后台服务状态') }}
    </div>
    <!--后台服务器性能指标-->
    <mo-healthz-backend-metrics-view />
    <!--数据链路-->
    <mo-healthz-backend-collector-view v-if="isShowCollector" />
    <!--后台服务-->
    <mo-healthz-backend-dataflow-view />
    <!--依赖周边组件状态-->
    <mo-healthz-backend-component-view />
  </div>
</template>
<script>
import MoHealthzBackendCollectorView from './healthz-backend-collector';
import MoHealthzBackendComponentView from './healthz-backend-component';
import MoHealthzBackendDataflowView from './healthz-backend-dataflow';
import MoHealthzBackendMetricsView from './healthz-backend-metrics';

export default {
  name: 'MoHealthzBackendView',
  components: {
    MoHealthzBackendMetricsView,
    MoHealthzBackendCollectorView,
    MoHealthzBackendDataflowView,
    MoHealthzBackendComponentView
  },
  computed: {
    // 是否显示数据链路健康检查
    isShowCollector() {
      return this.$platform.ee || this.$platform.ce;
    }
  }
};
</script>
<style lang="scss" scoped>
@import '../style/healthz';
</style>
