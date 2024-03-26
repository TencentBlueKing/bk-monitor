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
  <div class="uptime-check">
    <div class="uptime-check-tab">
      <div
        v-for="item in tabList"
        class="tab-item"
        :class="{ 'tab-active': active === item.id }"
        :key="item.id"
        @click="handleTabChange(item.id)"
      >
        {{ item.name }}
      </div>
      <div class="uptime-check-content">
        <page-tips
          style="margin-bottom: 16px"
          :tips-text="
            $t(
              '服务拨测通过拨测节点向远程目标发送探测信息，来发现目标服务的状态情况。支持TCP HTTP(s) UDP ICMP。该功能依赖服务器安装bkmonitorbeat采集器。'
            )
          "
          :link-text="$t('采集器安装前往节点管理')"
          :link-url="`${$store.getters.bkNodemanHost}#/plugin-manager/list`"
          doc-link="quickStartDial"
        />
        <keep-alive v-if="active">
          <component
            :is="active"
            :from-route-name="fromRoueName"
            :node-name="nodeName"
            @node-name-change="nodeName = ''"
            @set-task="handleSetNodeName"
          />
        </keep-alive>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
import { TranslateResult } from 'vue-i18n';
import { Component, Mixins, Prop, Provide, ProvideReactive } from 'vue-property-decorator';

import pageTips from '../../components/pageTips/pageTips.vue';
import authorityMixinCreate from '../../mixins/authorityMixin';

import UptimeCheckNode from './uptime-check-nodes/uptime-check-nodes.vue';
import UptimeCheckTask from './uptime-check-task/uptime-check-task.vue';
import * as uptimeAuth from './authority-map';

enum UptimeCheckType {
  task = 'uptime-check-task',
  node = 'uptime-check-node'
}
interface ITabItem {
  id: UptimeCheckType;
  name: TranslateResult;
}
Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
@Component({
  name: 'uptime-check',
  components: {
    UptimeCheckTask,
    UptimeCheckNode,
    pageTips
  }
})
export default class UptimeCheck extends Mixins(authorityMixinCreate(uptimeAuth)) {
  @Prop() id;
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @ProvideReactive('uptimeAuth') uptimeAuth = uptimeAuth;
  private active = '';
  private tabList: ITabItem[] = [];
  private fromRoueName = '';
  private nodeName = '';
  beforeRouteEnter(to, from, next) {
    next((vm) => {
      vm.active = vm.id && UptimeCheckType.node === vm.id ? UptimeCheckType.node : UptimeCheckType.task;
      vm.fromRoueName = from.name || '';
    });
  }
  beforeRouteLeave(to, from, next) {
    this.nodeName = '';
    next();
  }
  created() {
    this.tabList = [
      {
        name: this.$t('拨测任务'),
        id: UptimeCheckType.task
      },
      {
        name: this.$t('拨测节点'),
        id: UptimeCheckType.node
      }
    ];
  }
  handleSetNodeName(name) {
    this.active = UptimeCheckType.task;
    this.nodeName = name || '';
  }
  handleTabChange(id) {
    this.active = id;
  }
}
</script>
<style lang="scss" scoped>
.uptime-check {
  height: calc(100vh - 52px - var(--notice-alert-height));
  margin: -20px -24px 0 -24px;
  overflow: hidden;

  &-tab {
    height: 32px;
    padding-top: 3px;
    padding-left: 24px;
    background: #fff;
    border-bottom: 1px solid #dcdee5;
    box-shadow: 0 3px 4px 0 rgba(64, 112, 203, .06);

    .tab-item {
      display: inline-block;
      height: 100%;
      margin-right: 30px;
      font-size: 14px;
      cursor: pointer;
    }

    .tab-active {
      color: #3a84ff;
      border-bottom: 2px solid #3a84ff;
    }
  }

  &-content {
    height: calc(100vh - 88px);
    padding: 20px 20px 0 0;
    overflow: auto;
  }
}
</style>
