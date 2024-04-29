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
  <section
    v-bkloading="{ isLoading: basicLoading }"
    :class="['access-wrapper', itsmTicketIsApplying && 'iframe-container']"
  >
    <auth-container-page
      v-if="authPageInfo"
      :info="authPageInfo"
    ></auth-container-page>
    <div
      v-else-if="!basicLoading && !isCleaning"
      class="access-container"
    >
      <section class="access-step-wrapper">
        <div
          class="fixed-steps"
          :style="{ height: `${getShowStepsConfHeightNum}px` }"
        >
          <bk-steps
            theme="primary"
            direction="vertical"
            :controllable="isFinishCreateStep"
            :cur-step.sync="curStep"
            :steps="getShowStepsConf"
            :before-change="stepChangeBeforeFn"
          >
          </bk-steps>
          <div
            class="step-arrow"
            :style="{ top: `${getCurStepArrowTopNum}px` }"
          ></div>
        </div>
      </section>
      <section
        v-if="operateType"
        v-bkloading="{ isLoading: containerLoading, zIndex: 10 }"
        class="access-step-container"
      >
        <component
          :is="getCurrentComponent"
          ref="currentRef"
          :operate-type="operateType"
          :is-physics.sync="isPhysics"
          :is-update.sync="isUpdate"
          :is-switch="isSwitch"
          :index-set-id="indexSetId"
          :apply-data="applyData"
          :is-container-step="isContainerStep"
          :is-finish-create-step="isFinishCreateStep"
          :container-loading.sync="containerLoading"
          :force-show-component.sync="forceShowComponent"
          @setAssessmentItem="v => (applyData = v)"
          @changeIndexSetId="v => (indexSetId = v)"
          @changeSubmit="v => (isSubmit = v)"
          @changeClean="isCleaning = true"
          @stepChange="stepChange"
        ></component>
      </section>
    </div>
    <advance-clean-land
      v-else-if="!basicLoading && isCleaning"
      back-router="collection-item"
    />
  </section>
</template>

<script>
import { mapState, mapGetters } from 'vuex';
import AuthContainerPage from '@/components/common/auth-container-page';
import stepAdd from './step-add';
import stepIssued from './step-issued';
import stepField from './step-field';
import stepStorage from './step-storage.vue';
import stepResult from './step-result';
import stepMasking from './step-masking.tsx';
import advanceCleanLand from '@/components/collection-access/advance-clean-land';
import * as authorityMap from '../../common/authority-map';
/** 左侧侧边栏一个步骤元素的高度 */
const ONE_STEP_HEIGHT = 76;

export default {
  name: 'AccessSteps',
  components: {
    AuthContainerPage,
    stepAdd,
    stepIssued,
    stepField,
    stepStorage,
    stepResult,
    stepMasking,
    advanceCleanLand
  },
  data() {
    return {
      authPageInfo: null,
      basicLoading: true,
      isCleaning: false,
      isSubmit: false,
      isUpdate: false, // 判断第一步是否是处于编辑状态
      isItsm: window.FEATURE_TOGGLE.collect_itsm === 'on',
      operateType: '',
      curStep: 1, // 组件步骤
      isPhysics: true, // 采集配置是否是物理环境
      indexSetId: '',
      globals: {},
      itsmTicketIsApplying: false,
      applyData: {},
      containerLoading: false, // 容器日志提交loading
      /** 是否是容器步骤 */
      isContainerStep: false,
      /** 是否完成过一次创建步骤 */
      isFinishCreateStep: false,
      /** 强制渲染的组件 */
      forceShowComponent: '',
      /** 步骤所对应的组件 */
      // componentStepObj: {
      //   1: 'stepAdd',
      //   2: 'stepIssued',
      //   3: 'stepField',
      //   4: 'stepStorage',
      //   5: 'stepMasking',
      //   6: 'stepResult'
      // },
      /** 侧边栏所有的步骤 */
      stepsConf: [
        { title: this.$t('采集配置'), icon: 1, stepStr: 'stepAdd' },
        { title: this.$t('采集下发'), icon: 2, stepStr: 'stepIssued' },
        { title: this.$t('字段清洗'), icon: 3, stepStr: 'stepField' },
        { title: this.$t('存储'), icon: 4, stepStr: 'stepStorage' },
        { title: this.$t('日志脱敏'), icon: 5, stepStr: 'stepMasking' },
        { title: this.$t('完成'), icon: 6, stepStr: 'stepResult' }
      ]
    };
  },
  computed: {
    ...mapState({
      showRouterLeaveTip: state => state.showRouterLeaveTip
    }),
    ...mapGetters('collect', ['curCollect']),
    ...mapGetters(['bkBizId']),
    ...mapGetters(['spaceUid']),
    ...mapGetters(['isShowMaskingTemplate']),
    /** 是否是启停状态 */
    isSwitch() {
      return ['start', 'stop'].some(item => item === this.operateType);
    },
    isItsmAndNotStartOrStop() {
      return this.isItsm && this.operateType !== 'start' && this.operateType !== 'stop';
    },
    /** 左侧展示的步骤 */
    showStepsConf() {
      let finishShowConf = this.stepsConf;
      // 启停情况下只有采集下发和完成两个步骤
      if (this.isSwitch) {
        finishShowConf = finishShowConf.filter(item => ['stepIssued', 'stepResult'].includes(item.stepStr));
      }
      // 容器日志没有下发步骤
      if (this.isContainerStep) {
        finishShowConf = finishShowConf.filter(item => item.stepStr !== 'stepIssued');
      }
      // 判断当前业务是否展示脱敏 若不展示 隐藏脱敏步骤
      if (!this.isShowMaskingTemplate) {
        finishShowConf = finishShowConf.filter(item => item.stepStr !== 'stepMasking');
      }
      // 判断是否以及完成过一次步骤 有table_id的情况视为完成过一次完整的步骤  隐藏下发和完成两个步骤
      if (this.isFinishCreateStep && !this.isSwitch) {
        finishShowConf = finishShowConf.filter(item => !['stepIssued', 'stepResult'].includes(item.stepStr));
      }
      return finishShowConf;
    },
    /** 左侧展示的步骤更新icon的number */
    getShowStepsConf() {
      return this.showStepsConf.map((step, index) => ({
        ...step,
        icon: index + 1
      }));
    },
    /** 左侧展示的步骤总高度 */
    getShowStepsConfHeightNum() {
      return this.getShowStepsConf.length * ONE_STEP_HEIGHT;
    },
    /** 箭头样式的top */
    getCurStepArrowTopNum() {
      return this.curStep * ONE_STEP_HEIGHT - 38;
    },
    /** 当前展示的组件 */
    getCurrentComponent() {
      // 强制展示组件
      if (this.forceShowComponent) return this.forceShowComponent;
      const showComponent = {};
      // 根据展示的组件重置步骤 让curStep与组件对应
      this.getShowStepsConf.forEach(item => {
        showComponent[item.icon] = item.stepStr;
      });
      return showComponent[this.curStep];
    }
  },
  watch: {
    curStep() {
      this.setSteps();
    }
  },
  created() {
    this.initPage();
  },
  // eslint-disable-next-line no-unused-vars
  beforeRouteLeave(to, from, next) {
    if (!this.isSubmit && !this.isSwitch && !this.showRouterLeaveTip) {
      this.$bkInfo({
        title: this.$t('是否放弃本次操作？'),
        confirmFn: () => {
          next();
        }
      });
      return;
    }
    next();
  },
  methods: {
    // 先校验页面权限再初始化
    async initPage() {
      try {
        const paramData =
          this.$route.name === 'collectAdd'
            ? {
                action_ids: [authorityMap.CREATE_COLLECTION_AUTH],
                resources: [
                  {
                    type: 'space',
                    id: this.spaceUid
                  }
                ]
              }
            : {
                action_ids: [authorityMap.MANAGE_COLLECTION_AUTH],
                resources: [
                  {
                    type: 'collection',
                    id: this.$route.params.collectorId
                  }
                ]
              };
        const res = await this.$store.dispatch('checkAndGetData', paramData);
        if (res.isAllowed === false) {
          this.authPageInfo = res.data;
          this.basicLoading = false;
          return;
        }
      } catch (err) {
        console.warn(err);
        this.basicLoading = false;
        return;
      }

      const routeType = this.$route.name.toLowerCase().replace('collect', '');
      const {
        query: { type },
        name: routeName
      } = this.$route;
      this.isUpdate = routeName !== 'collectAdd'; // 判断是否是更新
      if ((routeType !== 'add' && !this.$route.params.notAdd) || type === 'clone') {
        // 克隆时 请求初始数据
        try {
          const detailRes = await this.getDetail();
          // 是否完成过一次完整的步骤
          this.isFinishCreateStep = !!detailRes.table_id;
          this.operateType = routeType;
        } catch (e) {
          console.warn(e);
          this.operateType = routeType;
        }
        try {
          const statusRes = await this.$http.request('collect/getCollectStatus', {
            query: {
              collector_id_list: this.$route.params.collectorId
            }
          });
          if (statusRes.data[0].status === 'PREPARE') {
            // 准备中编辑时跳到第一步，所以不用修改步骤
          } else {
            // 容器环境  非启用停用 非克隆状态则展示容器日志步骤
            if (!this.isPhysics && !this.isSwitch && type !== 'clone') this.isContainerStep = true;
            const finishPag = this.getShowStepsConf.slice(-1).icon;
            let jumpComponentStr = 'stepAdd';
            switch (this.operateType) {
              case 'edit': // 完成或者未完成编辑都从第一步走
                jumpComponentStr = 'stepAdd';
                break;
              case 'field':
                jumpComponentStr = 'stepField';
                break;
              case 'storage':
                jumpComponentStr = 'stepStorage';
                break;
              case 'masking':
                jumpComponentStr = 'stepMasking';
                break;
              default:
                break;
            }
            const jumpPage = this.getShowStepsConf.find(item => item.stepStr === jumpComponentStr).icon;
            // 审批通过后编辑直接进入第三步字段提取，否则进入第二步容量评估
            this.curStep = this.isItsm && this.applyData.itsm_ticket_status === 'applying' ? finishPag : jumpPage;
          }
        } catch (e) {
          console.warn(e);
        }
      } else {
        this.operateType = routeType;
      }
      this.basicLoading = false;
    },
    setSteps() {
      // 新增  并且为容器环境则步骤变为容器步骤 步骤为第一步时不判断
      if (this.operateType === 'add' && !this.isPhysics && this.curStep !== 1) this.isContainerStep = true;
    },
    stepChange(num) {
      if (num === 'back') {
        this.$router.push({
          name: 'log-collection',
          query: {
            spaceUid: this.$store.state.spaceUid
          }
        });
        return;
      }
      this.curStep = num || this.curStep + 1;
    },
    // 获取详情
    getDetail() {
      return new Promise((resolve, reject) => {
        this.$http
          .request('collect/details', {
            // manualSchema: true,
            params: {
              collector_config_id: this.$route.params.collectorId
            }
          })
          .then(async res => {
            if (res.data) {
              const collect = res.data;
              this.isPhysics = collect.environment !== 'container';
              if (collect.collector_scenario_id !== 'wineventlog' && this.isPhysics && collect?.params.paths) {
                collect.params.paths = collect.params.paths.map(item => ({ value: item }));
              }
              // 如果当前页面采集流程未完成 则展示流程服务页面
              const applyDataItem = {
                iframe_ticket_url: collect.ticket_url,
                itsm_ticket_status: collect.itsm_ticket_status
              };
              this.applyData = collect.itsm_ticket_status === 'applying' ? applyDataItem : {};
              this.itsmTicketIsApplying = false;
              this.$store.commit('collect/setCurCollect', collect);
              resolve(res.data);
            }
          })
          .catch(err => {
            reject(err);
          });
      });
    },
    // 获取状态
    getCollectStatus(idStr) {
      return this.$http.request('collect/getCollectStatus', {
        query: {
          collector_id_list: idStr
        }
      });
    },
    /** 步骤切换时触发该函数 */
    stepChangeBeforeFn() {
      /** 编辑状态切换步骤时 判断下是否修改过当前的值 */
      const isUpdateSubmitValue = this.$refs.currentRef?.getIsUpdateSubmitValue?.() || false;
      if (!isUpdateSubmitValue) {
        this.forceShowComponent = '';
        return true;
      }
      return new Promise(resolve => {
        this.$bkInfo({
          title: this.$t('是否放弃本次操作？'),
          confirmFn: () => {
            this.forceShowComponent = '';
            resolve(true);
          }
        });
      });
    }
  }
};
</script>

<style lang="scss">
@import '@/scss/mixins/clearfix';
@import '@/scss/conf';

.access-wrapper {
  padding: 20px 24px;
}

.iframe-container {
  padding: 0;
}

.access-container {
  position: relative;
  display: flex;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border: 1px solid $borderWeightColor;
}

.access-step-wrapper {
  width: 200px;
  padding-left: 30px;
  background: $bgHoverColor;
  border-right: 1px solid $borderWeightColor;

  .fixed-steps {
    position: relative;
    max-height: 100%;
    margin-top: 40px;

    .bk-steps {
      :last-child {
        &::after {
          display: none;
        }
      }
    }

    .bk-step {
      display: flex;
      height: 70px;
      color: #7a7c85;
      white-space: normal;

      &::after {
        left: 14px;
        width: 1px;
        background: none;
        border-left: 1px dashed #e5e6ec;
      }

      .bk-step-number {
        display: inline-block;
        width: 28px;
        height: 28px;
        margin-right: 10px;
        font-size: 12px;
        line-height: 28px;
        color: #858790;
        text-align: center;
        border: 1px solid #c4c6cc;
        border-radius: 50%;
        box-shadow: 0px 2px 4px 0px rgba(0, 130, 255, 0.15);
      }

      .bk-step-content {
        display: inline-block;
        width: 78%;
        overflow: hidden;
        hyphens: auto;
      }

      .bk-step-title {
        display: inline;
        color: #6e7079;
      }

      .bk-step-indicator {
        width: 28px;
        height: 28px;
        line-height: 26px;
      }
    }

    .current {
      .bk-step-number {
        color: #fff;
        background: #3a84ff;
        border: 1px solid #3a84ff;
        box-shadow: 0px 2px 4px 0px rgba(0, 130, 255, 0.15);
      }

      .bk-step-title {
        color: #448fff;
      }
    }

    .done {
      .bk-step-icon {
        color: #fff;
        border: 1px solid #dcdee5;
      }

      .bk-step-number {
        position: relative;
        color: #fafbfd;
        background: #fafbfd;
        box-shadow: 0px 2px 4px 0px rgba(0, 130, 255, 0.15);

        &::before {
          position: absolute;
          top: 50%;
          left: 50%;
          width: 16px;
          height: 16px;
          background-color: #fafbfd;
          background-image: url('../../images/icons/finish.svg');
          background-size: 100% 100%;
          border-radius: 50%;
          content: '';
          transform: translate(-50%, -50%);
        }
      }

      // .bk-step-indicator {
      //   background-color: #dcdee5;
      // }

      .bk-step-title {
        color: #63656e;
      }
    }
  }

  .step-arrow {
    position: absolute;
    right: 1px;
    width: 10px;
    height: 10px;
    background: #fff;
    border-top: 1px solid $borderWeightColor;
    border-right: 1px solid $borderWeightColor;
    border-left: 1px solid transparent;
    transform: rotate(-135deg);
    transform-origin: 62% 0;
  }
}

.access-step-container {
  flex: 1;
  width: calc(100% - 200px);
  background: #fff;
}
</style>
