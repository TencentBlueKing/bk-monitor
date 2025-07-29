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
  <guide-page
    v-if="showGuidePage"
    :guide-data="curIntroduceData"
  />
  <div
    v-else
    v-bkloading="{ isLoading: pageLoading }"
    class="add-del-wrapper"
  >
    <div class="add-del">
      <div class="add-del-steps">
        <ul class="step-list">
          <li
            v-for="(item, index) in left.stepsMap"
            :key="index"
            class="step-list-item"
            :class="['step-list-item-' + (index + 1), { 'is-current': left.step === index, 'is-ok': item.done }]"
            @click="item.done && handleSetStep(index)"
          >
            <div
              class="step-list-item-content"
              :class="{ 'is-current-arrow': left.step === index }"
            >
              {{ item.name }}
            </div>
          </li>
        </ul>
      </div>
      <div
        ref="pluginContaner"
        class="add-del-contaner"
      >
        <keep-alive>
          <component
            :is="curStep.component"
            :data="data"
            :page-loading.sync="pageLoading"
            :hosts.sync="hosts"
            :step.sync="left.step"
            :type.sync="componentType"
            :need-rollback.sync="needRollback"
            :config="config"
            :diff-data.sync="diffData"
            :target="target"
            @refresh="handleRefresh"
            @step-change="handleStepChange"
            @target="targetUpdata"
          />
        </keep-alive>
      </div>
    </div>
  </div>
</template>

<script>
import { collectConfigDetail } from 'monitor-api/modules/collecting';

import introduce from '../../../common/introduce';
import GuidePage from '../../../components/guide-page/guide-page';
import { SET_NAV_ROUTE_LIST } from '../../../store/modules/app';
import Done from './add-del-done/add-del-done';
import BkHost from './bk-host/bk-host';
import TargetTable from './target-table/target-table';

export default {
  name: 'AddAndDel',
  components: {
    BkHost,
    TargetTable,
    Done,
    GuidePage,
  },
  data() {
    return {
      componentName: 'add-and-del',
      config: {
        params: {},
        set: {
          data: {},
          others: {},
        },
      },
      hosts: {},
      diffData: {},
      left: {
        stepsMap: [
          {
            name: this.$t('选择目标'),
            done: false,
            component: 'bk-host',
          },
          {
            name: this.$t('采集下发'),
            done: false,
            component: 'TargetTable',
          },
          {
            name: this.$t('完成'),
            done: false,
            component: 'done',
          },
        ],
        step: 0,
      },
      pageLoading: true,
      ipLoading: true,
      componentType: 'ADD_DEL',
      needRollback: true,
      target: {},
      id: '',
      data: {},
    };
  },
  computed: {
    curStep() {
      return this.left.stepsMap[this.left.step];
    },
    curIntroduceData() {
      return introduce.data['collect-config'].introduce;
    },
    // 是否显示引导页
    showGuidePage() {
      return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
    },
  },
  created() {
    this.id = this.$route.params.id;
    this.$store.commit('app/SET_NAV_TITLE', this.$t('加载中...'));
    this.updateNav();
  },
  mounted() {
    this.getCollectorConfigDetail();
    this.left.step = 0;
  },
  methods: {
    updateNav(name = '') {
      const routeList = [];
      routeList.push({
        name: `${this.$t('增删目标')} ${name}`,
        id: 'collect-config',
      });
      this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
    },
    handleStepChange(v, index) {
      this.left.stepsMap[index].done = v;
    },
    handleNextStep() {
      this.left.stepsMap[this.left.step].done = true;
      this.left.step += 1;
    },
    handleShowMsg(msg) {
      this.message = msg;
    },
    handleRefresh() {
      this.pageLoading = false;
    },
    handleForward() {
      this.left.step -= 1;
    },
    handleSetStep(index) {
      if (this.left.stepsMap[index].done) {
        return;
      }
      this.left.step = index;
    },
    handleStepOk(v) {
      this.curStep.done = v;
    },
    handleScroll() {
      if (this.$refs.pluginContaner) {
        this.$refs.pluginContaner.scrollTop = 0;
      }
    },
    getConfigParams(data) {
      this.data = data;
      this.config.id = data.id;
      this.config.mode = 'edit';
      this.config.set.data.objectType = data.target_object_type;
      this.config.set.others.targetNodeType = data.target_node_type;
      this.config.set.others.targetNodes =
        data.collect_type === 'SNMP' ? data.target_nodes : data.target || data.target_nodes;
      this.config.set.others.remoteCollectingHost = data.remote_collecting_host;
      this.config.supportRemote = data.plugin_info.is_support_remote;
      this.config.params = {
        name: data.name,
        collect_type: data.collect_type,
        target_object_type: data.target_object_type,
        target_node_type: data.target_node_type,
        plugin_id: data.plugin_info.plugin_id,
        target_nodes: data.target || data.target_nodes,
        params: data.params,
        label: data.label,
        remote_collecting_host: data.remote_collecting_host,
      };
      this.config.config_json = data.plugin_info.config_json;
      this.$store.commit(
        'app/SET_NAV_TITLE',
        `${this.$t('route-' + '增删目标').replace('route-', '')} - #${data.id} ${data.name}`
      );
      this.config.target = {};
    },
    getCollectorConfigDetail() {
      this.pageLoading = true;
      collectConfigDetail({ id: this.id }).then(data => {
        this.updateNav(data.name);
        this.getConfigParams(data);
      });
    },
    targetUpdata(v) {
      this.target = v;
    },
  },
};
</script>

<style scoped lang="scss">
@import '../../home/common/mixins';
// stylelint-disable declaration-no-important
.add-del-wrapper {
  .add-del {
    display: flex;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0px 2px 4px 0px rgba(25, 25, 41, 0.05);

    @include border-1px();

    &-steps {
      width: 202px;
      height: calc(100vh - 110px);
      background: $defaultBgColor;
      border-right: 1px solid $defaultBorderColor;
      border-radius: 2px 0px 0px 0px;

      .step-list {
        padding: 40px 0 0 0;
        margin-left: 45px;

        @for $i from 1 through 7 {
          &-item-#{$i} {
            &:before {
              content: '#{$i}';
            }
          }
        }

        &-item {
          position: relative;
          height: 70px;
          padding-left: 25px;
          color: $defaultFontColor;
          border-left: 1px dashed $defaultBorderColor;

          &:before {
            position: absolute;
            top: -5px;
            left: -15px;
            display: inline-block;
            width: 26px;
            height: 26px;
            line-height: 26px;
            // box-shadow: 0px 2px 4px 0px rgba(0, 130, 255, 0.15);
            color: $defaultFontColor;
            text-align: center;
            background: #fff;
            border-radius: 50%;

            @include border-1px(#c4c6cc);
          }

          &:last-child {
            border-left: 0;
          }

          &-content {
            position: relative;
            font-size: 14px;
            line-height: 19px;
          }
        }

        .is-ok {
          border-left: 1px dashed #dcdee5;

          @include hover();

          &:last-child {
            border-left: 0;
          }

          &:before {
            /* stylelint-disable-next-line font-family-no-missing-generic-family-keyword */
            font-family: 'icon-monitor' !important;
            font-size: 18px !important;
            color: #fff;
            content: '\e6b7' !important;
            background: #dcdee5;
            border: 1px solid #dcdee5;
          }
        }

        .is-current {
          @include is-active;
        }
      }
    }

    &-contaner {
      position: relative;
      flex: 1;
      max-height: calc(100vh - 110px);
      overflow: auto;

      &::-webkit-scrollbar {
        width: 2px;
        height: 2px;
      }
    }
  }
}
</style>
