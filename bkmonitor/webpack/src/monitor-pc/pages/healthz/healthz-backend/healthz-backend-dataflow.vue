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
  <div class="main-component-content">
    <p>{{ $t('后台服务') }}</p>
    <div
      v-for="(item, index) in backendDataFlowComponent"
      style="display: inline-block"
      :key="index"
    >
      <!--只有数据流的组件才显示连接线，最后一个组件不显示连接线-->
      <mo-healthz-component-tooltip-view
        :component-name="item"
        :index="index"
        :show-line="'yes'"
        :is-last="index === backendDataFlowComponent.length - 1"
      />
    </div>
  </div>
</template>
<script>
// import { mapState } from 'vuex'
import MoHealthzComponentTooltipView from '../common/healthz-component-tooltip';
import store from '../store/healthz/store';

export default {
  name: 'MoHealthzBackendDataflowView',
  components: {
    MoHealthzComponentTooltipView
  },
  computed: {
    backendDataFlowComponent() {
      return store.state.backendDataFlowComponent;
    }
    // ...mapState([
    //     'backendDataFlowComponent'
    // ])
  }
};
</script>
<style lang="scss" scoped>
@import '../style/healthz';
</style>
