<!-- eslint-disable vue/no-deprecated-slot-attribute -->
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
          :style="{ height: `${getShowStepsConfHeightNum}px` }"
          class="fixed-steps"
        >
          <bk-steps
            :before-change="stepChangeBeforeFn"
            :controllable="isFinishCreateStep"
            :cur-step.sync="curStep"
            :steps="getShowStepsConf"
            direction="vertical"
            theme="primary"
          >
          </bk-steps>
          <div class="step-arrow"></div>
        </div>
      </section>
      <section
        v-if="operateType"
        class="access-step-container"
        v-bkloading="{ isLoading: containerLoading, zIndex: 10 }"
      >
        <component
          ref="currentRef"
          :apply-data="applyData"
          :container-loading.sync="containerLoading"
          :cur-step="curStep"
          :force-show-component.sync="forceShowComponent"
          :index-set-id="indexSetId"
          :is="getCurrentComponent"
          :is-container-step="isContainerStep"
          :is-finish-create-step="isFinishCreateStep"
          :is-physics.sync="isPhysics"
          :is-switch="isSwitch"
          :is-update.sync="isUpdate"
          :operate-type="operateType"
          @change-clean="isCleaning = true"
          @change-index-set-id="v => (indexSetId = v)"
          @change-submit="v => (isSubmit = v)"
          @reset-cur-collect-val="() => getDetail()"
          @set-assessment-item="v => (applyData = v)"
          @step-change="stepChange"
        ></component>
      </section>
      <issuedSlider
        v-if="getCurrentComponent !== 'stepResult' && getCurrentComponent !== 'stepAdd'"
        :is-finish-create-step="isFinishCreateStep"
        :is-switch="isSwitch"
        :operate-type="operateType"
      ></issuedSlider>
    </div>
    <advance-clean-land
      v-else-if="!basicLoading && isCleaning"
      back-router="collection-item"
    />
  </section>
</template>

<script>
  import advanceCleanLand from '@/components/collection-access/advance-clean-land';
  import AuthContainerPage from '@/components/common/auth-container-page';
  import { mapState, mapGetters } from 'vuex';

  import * as authorityMap from '../../common/authority-map';
  import stepAdd from './step-add';
  import stepField from './step-field';
  import stepMasking from './step-masking.tsx';
  import stepResult from './step-result';
  import stepStorage from './step-storage.vue';
  import issuedSlider from './issued-slider.vue';

  /** 左侧侧边栏一个步骤元素的高度 */
  const ONE_STEP_HEIGHT = 76;

  export default {
    name: 'AccessSteps',
    components: {
      AuthContainerPage,
      stepAdd,
      stepField,
      stepStorage,
      stepResult,
      stepMasking,
      advanceCleanLand,
      issuedSlider,
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
        /** 编辑时切换步骤 */
        isChangeStepLoading: false,
        /** 步骤所对应的组件 */
        // componentStepObj: {
        //   1: 'stepAdd',
        //   2: 'stepField',
        //   3: 'stepStorage',
        //   4: 'stepMasking',
        //   5: 'stepResult'
        // },
        /** 侧边栏所有的步骤 */
        stepsConf: [
          { title: this.$t('采集配置'), icon: 1, stepStr: 'stepAdd' },
          { title: this.$t('字段清洗'), icon: 2, stepStr: 'stepField' },
          { title: this.$t('存储'), icon: 3, stepStr: 'stepStorage' },
          { title: this.$t('日志脱敏'), icon: 4, stepStr: 'stepMasking' },
          { title: this.$t('完成'), icon: 5, stepStr: 'stepResult' },
        ],
      };
    },
    computed: {
      ...mapState({
        showRouterLeaveTip: state => state.showRouterLeaveTip,
      }),
      ...mapGetters('collect', ['curCollect']),
      ...mapGetters(['bkBizId']),
      ...mapGetters(['spaceUid']),
      ...mapGetters(['isShowMaskingTemplate']),
      /** 是否是启停状态 */
      isSwitch() {
        return ['start', 'stop'].some(item => item === this.operateType);
      },
      /** 左侧展示的步骤 */
      showStepsConf() {
        let finishShowConf = this.stepsConf;
        // 判断当前业务是否展示脱敏 若不展示 隐藏脱敏步骤
        if (!this.isShowMaskingTemplate) {
          finishShowConf = finishShowConf.filter(item => item.stepStr !== 'stepMasking');
        }
        // 判断是否以及完成过一次步骤 有table_id的情况视为完成过一次完整的步骤  隐藏完成步骤
        if (this.isFinishCreateStep && !this.isSwitch) {
          finishShowConf = finishShowConf.filter(item => !['stepResult'].includes(item.stepStr));
        }
        return finishShowConf;
      },
      /** 左侧展示的步骤更新icon的number */
      getShowStepsConf() {
        return this.showStepsConf.map((step, index) => ({
          ...step,
          icon: index + 1,
        }));
      },
      /** 左侧展示的步骤总高度 */
      getShowStepsConfHeightNum() {
        return this.getShowStepsConf.length * ONE_STEP_HEIGHT;
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
      },
    },
    watch: {
      curStep() {
        this.setSteps();
      },
    },
    created() {
      this.initPage();
    },

    beforeRouteLeave(to, from, next) {
      if (!this.isSubmit && !this.isSwitch && !this.showRouterLeaveTip) {
        this.$bkInfo({
          title: this.$t('是否放弃本次操作？'),
          confirmFn: () => {
            next();
          },
        });
        return;
      }
      // 离开路由时清空采集配置导入数据
      this.$store.commit('collect/updateExportCollectObj', {
        collectID: null,
        syncType: [],
        collect: {},
      });
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
                      id: this.spaceUid,
                    },
                  ],
                }
              : {
                  action_ids: [authorityMap.MANAGE_COLLECTION_AUTH],
                  resources: [
                    {
                      type: 'collection',
                      id: this.$route.params.collectorId,
                    },
                  ],
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
          name: routeName,
        } = this.$route;
        this.isUpdate = routeName !== 'collectAdd'; // 判断是否是更新
        if ((routeType !== 'add' && !this.$route.params.notAdd) || type === 'clone') {
          // 克隆时 请求初始数据
          try {
            const detailRes = await this.getDetail();
            // 是否完成过一次完整的步骤
            this.isFinishCreateStep = !!detailRes.table_id && type !== 'clone';
            this.operateType = routeType;
          } catch (e) {
            console.warn(e);
            this.operateType = routeType;
          }
          try {
            const statusRes = await this.$http.request('collect/getCollectStatus', {
              query: {
                collector_id_list: this.$route.params.collectorId,
              },
            });
            if (statusRes.data[0].status === 'PREPARE') {
              // 准备中编辑时跳到第一步，所以不用修改步骤
            } else {
              // 容器环境  非启用停用 非克隆状态则展示容器日志步骤
              if (!this.isPhysics && !this.isSwitch && type !== 'clone') this.isContainerStep = true;
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
              this.curStep = this.getShowStepsConf.find(item => item.stepStr === jumpComponentStr).icon;
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
              spaceUid: this.$store.state.spaceUid,
            },
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
                collector_config_id: this.$route.params.collectorId,
              },
            })
            .then(async res => {
              if (res.data) {
                const collect = res.data;
                this.isPhysics = collect.environment !== 'container';
                if (collect.collector_scenario_id !== 'wineventlog' && this.isPhysics && collect?.params.paths) {
                  collect.params.paths = collect.params.paths.map(item => ({ value: item }));
                }
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
            collector_id_list: idStr,
          },
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
            title: this.$t('是否保存本次操作？'),
            confirmLoading: true,
            confirmFn: async () => {
              await new Promise(infoResolve => {
                if (this.$refs.currentRef?.stepSubmitFun) {
                  if (this.isChangeStepLoading) return;
                  // 正在请求中
                  this.isChangeStepLoading = true;
                  this.$refs.currentRef.stepSubmitFun(isCanChangeStep => {
                    resolve(isCanChangeStep);
                    infoResolve(isCanChangeStep);
                    this.isChangeStepLoading = false;
                    if (isCanChangeStep) this.forceShowComponent = '';
                  });
                  return;
                }
                infoResolve(false);
                resolve(false);
              });
            },
            cancelFn: () => {
              this.forceShowComponent = '';
              resolve(true);
            },
          });
        });
      },
    },
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
            content: '';
            background-color: #fafbfd;
            background-image: url('../../images/icons/finish.svg');
            background-size: 100% 100%;
            border-radius: 50%;
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
      top: 38px;
      right: -1px;
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
