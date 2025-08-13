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
  <div class="plugin-instance-wrapper">
    <div
      v-show="message && left.step === 0 && pluginInfo.type === 'edit'"
      class="plugin-message"
    >
      <span class="mo-icon-cc-attribute" />
      <div class="text">
        {{ message }}
      </div>
    </div>
    <div class="plugin-instance">
      <div class="plugin-instance-steps">
        <ul class="step-list">
          <li
            v-for="(item, index) in left.stepsMap"
            :key="index"
            class="step-list-item bk-icon"
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
        class="plugin-instance-contaner"
      >
        <keep-alive>
          <component
            :is="curStep.component"
            :show.sync="showView"
            :data.sync="pluginInfo"
            :from-route="fromRouteName"
          />
        </keep-alive>
      </div>
    </div>
  </div>
</template>

<script>
import { createNamespacedHelpers } from 'vuex';

import authorityMixinCreate from '../../../mixins/authorityMixin';
import { SET_PLUGIN_CONFIG } from '../../../store/modules/plugin-manager';
import * as pluginManageAuth from '../authority-map';
import StepSetDone from './set-steps/step-set-done.vue';
import StepSetPlugin from './set-steps/step-set-plugin.vue';
import StepSetTest from './set-steps/step-set-test.vue';

const { mapMutations } = createNamespacedHelpers('plugin-manager');

export default {
  name: 'PluginInstance',
  components: {
    StepSetDone,
    StepSetPlugin,
    StepSetTest,
  },
  provide() {
    return {
      authority: this.authority,
      handleShowAuthorityDetail: this.handleShowAuthorityDetail,
      pluginManageAuth,
    };
  },
  mixins: [authorityMixinCreate(pluginManageAuth)],
  beforeRouteEnter(_to, from, next) {
    next(vm => {
      // 缓存上一页过来的路由名字
      vm.fromRouteName = from.name;
    });
  },
  async beforeRouteLeave(to, _from, next) {
    if (
      to.name !== 'plugin-add' &&
      to.name !== 'plugin-edit' &&
      this.left.step < 2 &&
      this.$store.getters.bizIdChangePending !== to.name
    ) {
      const needNext = await this.handleCancel(false);
      next(needNext);
    } else {
      next();
    }
  },
  props: {
    show: {
      type: Boolean,
    },
  },
  data() {
    return {
      // 缓存上一个路由
      fromRouteName: '',
      pluginInfo: {},
      left: {
        stepsMap: [
          {
            name: this.$t('定义插件'),
            done: false,
            component: 'step-set-plugin',
          },
          {
            name: this.$t('插件调试'),
            done: false,
            component: 'step-set-test',
          },
          {
            name: this.$t('完成'),
            done: false,
            component: 'step-set-done',
          },
        ],
        step: 0,
      },
      message: '',
      showView: false,
      right: {},
    };
  },
  computed: {
    curStep() {
      return this.left.stepsMap[this.left.step];
    },
  },
  created() {
    const { pluginId } = this.$route.params;
    const { params } = this.$route;
    const id = params.pluginData ? params.pluginData.plugin_id : '';
    this.$store.commit(
      'app/SET_NAV_TITLE',
      this.$route.name === 'plugin-add'
        ? this.$t('route-' + '新建插件').replace('route-', '')
        : `${this.$t('route-' + '编辑插件').replace('route-', '')} - ${pluginId || id}`
    );
    this.pluginInfo = {
      isEdit: this.$route.name !== 'plugin-add',
      pluginId,
      type: this.$route.name === 'plugin-add' ? 'create' : 'edit',
      pluginData: params.pluginData,
    };
    if (this.pluginInfo.type === 'create' && (pluginId || this.pluginInfo.pluginData)) {
      this.pluginInfo.type = 'import';
    }
    this.showView = this.show;
    this.$bus.$on('forward', this.handleForward);
    this.$bus.$on('next', this.handleNextStep);
    this.$bus.$on('showmsg', this.handleShowMsg);
    this.$bus.$on('resetscroll', this.handleScroll);
  },
  beforeDestroy() {
    this.$bus.$off('forward', this.handleForward);
    this.$bus.$off('next', this.handleNextStep);
    this.$bus.$off('showmsg', this.handleShowMsg);
    this.$bus.$on('resetscroll', this.handleScroll);
    this[SET_PLUGIN_CONFIG](null);
  },
  methods: {
    ...mapMutations([SET_PLUGIN_CONFIG]),
    handleNextStep() {
      const step = this.left.stepsMap[this.left.step];
      if (step) {
        step.done = true;
      }
      this.left.step += 1;
    },
    // 点击取消
    handleCancel(needBack = true) {
      return new Promise(resolve => {
        this.$bkInfo({
          title: this.$t('是否放弃本次操作？'),
          confirmFn: () => {
            needBack && this.$router.back();
            resolve(true);
          },
          cancelFn: () => resolve(false),
        });
      });
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
  },
};
</script>

<style scoped lang="scss">
@import '../../home/common/mixins';

.plugin-instance-wrapper {
  padding: 20px;

  .plugin-message {
    height: 42px;
    padding: 0 16px;
    margin-bottom: 16px;
    line-height: 42px;
    background: #f0f8ff;
    border: 1px solid #a3c5fd;

    .mo-icon-cc-attribute {
      font-size: 18px;
      vertical-align: sub;
      color: #3a84ff;
    }

    .text {
      display: inline-block;
      font-size: 14px;
      color: #63656e;
    }
  }

  .plugin-instance {
    display: flex;
    min-height: calc(100vh - 100px);
    background: #fff;
    border-radius: 2px;
    box-shadow: 0px 2px 4px 0px rgba(25, 25, 41, 0.05);

    @include border-1px();

    &-steps {
      width: 202px;
      // min-height: calc(100vh - 150px);
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
            /* stylelint-disable-next-line declaration-no-important */
            border-left: 1px solid #fafbfd !important;
          }

          &-content {
            position: relative;
            font-size: 14px;
            line-height: 19px;
          }
        }

        .is-ok {
          @include hover();

          &:last-child {
            border-left: 0;
          }

          &:before {
            /* stylelint-disable-next-line declaration-no-important */
            font-family: 'icon-monitor' !important;

            /* stylelint-disable-next-line declaration-no-important */
            font-size: 28px !important;
            color: #fff;

            /* stylelint-disable-next-line declaration-no-important */
            content: '\e6b7' !important;
            background: #dcdee5;
            // @include border-1px($primaryFontColor);
            border-color: #dcdee5;
          }
        }

        .is-current {
          color: $primaryFontColor;
          border-left: 1px dashed $primaryFontColor;

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
      // height: calc(100vh - 102px);
      flex: 1;
      overflow: auto;

      &::-webkit-scrollbar {
        width: 4px;
        height: 4px;
      }
    }
  }
}
</style>
