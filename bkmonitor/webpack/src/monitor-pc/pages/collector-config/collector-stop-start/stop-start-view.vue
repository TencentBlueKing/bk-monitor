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
    class="stop-start-wrapper"
  >
    <div class="stop-start">
      <div class="stop-start-steps">
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
        v-if="initDone"
        ref="pluginContaner"
        class="stop-start-contaner"
      >
        <keep-alive>
          <component
            :is="curStep.component"
            :step.sync="left.step"
            :type.sync="type"
            :hosts.sync="hosts"
            :data="data"
            :open-detail="openDetail"
            :diff-data.sync="diffData"
            :upgrade-params="upgradeParams"
            @refresh="handleRefresh"
          />
        </keep-alive>
      </div>
    </div>
  </div>
</template>

<script>
import introduce from '../../../common/introduce';
import GuidePage from '../../../components/guide-page/guide-page';
import AddDelDone from '../collector-target-add-del/add-del-done/add-del-done';
import AddDel from '../collector-target-add-del/target-table/target-table';
import StopDone from './stop-done/stop-done';
import StopStart from './stop-start-host/stop-start-host';

export default {
  name: 'StopStartView',
  components: {
    StopStart,
    StopDone,
    AddDel,
    AddDelDone,
    GuidePage,
  },
  // props: {
  //     data: {
  //         type: Object,
  //         default: () => {}
  //     },
  //     stopStart: {
  //         type: Object,
  //         default: () => ({})
  //     }
  // },
  data() {
    return {
      hosts: {},
      configInfo: {},
      type: '',
      isRefreshConfigList: false,
      operationType: 'START',
      openDetail: false,
      upgradeParams: {},
      left: {
        stepsMap: [
          {
            name: this.$t('采集下发'),
            done: true,
            component: 'stop-start',
          },
          {
            name: this.$t('完成'),
            done: false,
            component: 'stop-done',
          },
        ],
        step: 0,
      },
      diffData: {},
      initDone: false,
      version: '',
      pageLoading: true,
    };
  },
  computed: {
    curStep() {
      return this.left.stepsMap[this.left.step];
    },
    data() {
      return this.$route.params.data;
    },
    stopStart() {
      return this.$route.params.stopStart;
    },
    curIntroduceData() {
      return introduce.data['collect-config'].introduce;
    },
    // 是否显示引导页
    showGuidePage() {
      return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
    },
  },
  beforeDestroy() {
    if (this.operationCount) {
      this.$parent.handleGetListData();
    }
  },
  async created() {
    this.pageLoading = true;
    this.$store.commit(
      'app/SET_NAV_TITLE',
      `${this.$route.params.title} - #${this.$route.params.data.id} ${this.$route.params.data.name}`
    );
    this.configInfo = this.data;
    this.type = this.stopStart.type;
    this.upgradeParams = this.stopStart.params;
    this.initDone = true;
  },
  methods: {
    handleNextStep() {
      this.left.stepsMap[this.left.step].done = true;
      this.left.step += 1;
    },
    handleRefresh() {
      this.pageLoading = false;
    },
    handleShowMsg(msg) {
      this.message = msg;
    },
    handleForward() {
      this.left.step -= 1;
    },
    handleSetStep(index) {
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
    // getUpOperation(id) {
    //   return configOperationInfo({ id })
    // },
    // addProp(obj) {
    //   const status = {
    //     START: 'STOPPED',
    //     STOP: 'STARTED'
    //   }
    //   this.data.id = obj.id
    //   this.data.name = obj.name
    //   this.data.updateParams = {}
    //   this.data.updateParams.configVersion = obj.config_version
    //   this.data.updateParams.infoVersion = obj.info_version
    //   this.data.objectTypeEn = obj.target_object_type
    //   this.data.status = obj.status
    //   this.data.nodeType = obj.target_node_type
    //   this.data.allowRollback = obj.allow_rollback
    //   this.type = status[obj.last_operation] || obj.last_operation
    //   this.operationType = obj.last_operation
    // }
    // getDiffData() {
    //   return deploymentConfigDiff({ id: this.data.id })
    // },
    // getAutoDeploy() {
    //   autoCollectStatus({ id: this.data.id }).then((data) => {
    //     this.diffData = data.diff_node
    //   })
    // }
    // handleUpgrade () {
    //     this.$parent.handleCloseUpdate(true)
    // }
  },
};
</script>

<style scoped lang="scss">
@import '../../home/common/mixins';

.stop-start-wrapper {
  .stop-start {
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
            width: 28px;
            height: 28px;
            line-height: 28px;
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
          border-left: 1px dashed $primaryFontColor;

          @include hover();

          &:last-child {
            border-left: 0;
          }

          &:before {
            /* stylelint-disable-next-line declaration-no-important */
            font-family: 'icon-monitor' !important;

            /* stylelint-disable-next-line declaration-no-important */
            font-size: 18px !important;
            color: #fff;

            /* stylelint-disable-next-line declaration-no-important */
            content: '\e6b7' !important;
            background: #dcdee5;
            border: 1px solid #c4c6cc;
          }
        }

        .is-current {
          color: $primaryFontColor;

          @include hover();

          &:before {
            color: #fff;
            background: $primaryFontColor;

            @include border-1px($primaryFontColor);
          }

          &-arrow {
            &:after {
              position: absolute;
              top: 3px;
              right: -6px;
              width: 10px;
              height: 10px;
              content: '';
              background: #fff;
              border-top: 1px solid $defaultBorderColor;
              border-left: 1px solid $defaultBorderColor;
              transform: rotate(-45deg);
            }
          }
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
