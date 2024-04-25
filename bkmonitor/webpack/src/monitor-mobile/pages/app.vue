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
  <van-pull-refresh
    :value="refresh"
    @change="handleRefreshChange"
    @refresh="handleRefresh"
  >
    <div style="min-height: 100vh">
      <keep-alive>
        <router-view :route-key="routeKey" />
      </keep-alive>
      <router-view
        key="noCache"
        name="noCache"
      />
      <drag-label
        v-if="['alarm-info', 'alarm-detail', 'quick-alarm-shield'].includes($route.name)"
        :alarm-num="alarmNum"
        @click="handleGoToEventCenter"
      />
      <van-overlay
        :show="loading"
        z-index="9999"
      >
        <div class="loading-wrap">
          <van-loading />
        </div>
      </van-overlay>
    </div>
  </van-pull-refresh>
</template>
<script lang="ts">
import { Component, Vue } from 'vue-property-decorator';

import { random } from 'monitor-common/utils/utils';
import { Loading, Overlay, PullRefresh } from 'vant';

import DragLabel from '../components/drag-label/drag-label.vue';

@Component({
  name: 'App',
  components: {
    [Loading.name]: Loading,
    [Overlay.name]: Overlay,
    DragLabel,
    [PullRefresh.name]: PullRefresh,
  },
})
export default class App extends Vue {
  routeKey: string = random(10);
  get loading() {
    return this.$store.state.app.loading;
  }

  get alarmNum() {
    return this.$store.getters['app/alarmCount'];
  }

  get refresh() {
    return this.$store.state.app.refresh;
  }

  created() {
    this.$store.commit('app/setPageLoading', true);
  }

  // 跳转至事件中心
  handleGoToEventCenter() {
    this.$router.push({
      name: 'event-center',
      query: {
        title: this.$store.state.app.bkBizName + this.$tc('事件中心'),
      },
    });
  }

  handleRefreshChange(v) {
    this.$store.commit('app/setRefresh', v);
  }

  handleRefresh() {
    this.handleRefreshChange(true);
    this.routeKey = random(100);
    // setTimeout(() => {
    //     this.$router.push({
    //         path: this.$route.path + '/' + random(10)
    //     })
    //     this.handleRefreshChange(false)
    // }, 1000)
  }
}
</script>
<style lang="scss" scoped>
.loading-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}
</style>
