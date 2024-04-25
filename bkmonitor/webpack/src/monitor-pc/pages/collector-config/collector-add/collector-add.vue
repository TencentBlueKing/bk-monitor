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
  <div class="collector-add">
    <div class="add-step">
      <ul class="step-list">
        <li
          v-for="(item, index) in stepConf.list"
          :key="index"
          class="step-list-item"
          :class="[
            `step-list-item-${index + 1}`,
            {
              'is-active': stepConf.active === index,
              'is-done': item.done,
            },
          ]"
        >
          <div
            :class="[
              'list-item-content',
              {
                'is-active-arrow': stepConf.active === index,
              },
            ]"
          >
            {{ item.name }}
          </div>
        </li>
      </ul>
    </div>
    <div class="add-container">
      <component
        :is="currentView"
        :hosts.sync="hosts"
        :is-clone="isClone"
        :config.sync="config"
        :password-input-change-set="passwordInputChangeSet"
        :type.sync="componentType"
        @target="target"
        @previous="handlePrevious"
        @next="handleNext"
        @passwordInputName="handlePasswordInputName"
      />
    </div>
  </div>
</template>

<script>
import { createNamespacedHelpers } from 'vuex';

import authorityMixinCreate from '../../../mixins/authorityMixin';
import { SET_INFO_DATA } from '../../../store/modules/collector-config';
import * as collectAuth from '../authority-map';
import ConfigDelivery from './config-delivery/config-delivery';
import ConfigDone from './config-done/config-done';
import ConfigSelect from './config-select/config-select';
import ConfigSet from './config-set/config-set';

const { mapGetters, mapMutations } = createNamespacedHelpers('collector-config');
export default {
  name: 'CollectorAdd',
  components: {
    ConfigSet,
    ConfigSelect,
    ConfigDelivery,
    ConfigDone,
  },
  mixins: [authorityMixinCreate(collectAuth)],
  provide() {
    return {
      authority: this.authority,
      handleShowAuthorityDetail: this.handleShowAuthorityDetail,
      collectAuth,
    };
  },
  beforeRouteLeave(to, from, next) {
    // 清除新建配置info缓存
    to.name !== 'plugin-add' && this[SET_INFO_DATA](null);
    next();
  },
  data() {
    return {
      componentType: 'ADD',
      currentView: 'config-set',
      hosts: {},
      stepConf: {
        active: 0,
        list: [
          {
            name: this.$t('配置'),
            done: false,
            component: 'config-set',
          },
          {
            name: this.$t('选择目标'),
            done: false,
            component: 'config-select',
          },
          {
            name: this.$t('采集下发'),
            done: false,
            component: 'config-delivery',
          },
          {
            name: this.$t('完成'),
            done: false,
            component: 'config-done',
          },
        ],
      },
      config: {
        mode: 'add',
        data: {},
        set: {},
        select: {},
        delivery: {},
        done: {},
        target: {},
      },
      passwordInputChangeSet: new Set(), // 父组件维护一个用于判断密码框有无发生变更的set，用于判断提交表单时是否需要将该密码表单pop出去
    };
  },
  computed: {
    ...mapGetters(['addParams']),
    /** 是否为克隆采集 */
    isClone() {
      return this.$route.name === 'collect-config-clone';
    },
  },
  created() {
    const { params } = this.$route;
    if (typeof params.pluginId !== 'undefined') {
      this.config = {
        ...this.addParams,
        data: {
          updateParams: {
            pluginId: params.pluginId,
          },
        },
        mode: 'add',
        set: {},
        select: {},
        delivery: {},
        done: {},
        target: {},
      };
      this.componentType = 'ADD';
      if (typeof params.id !== 'undefined') {
        this.config.data.id = params.id;
        if (!this.isClone) {
          this.componentType = 'EDIT';
          this.config.mode = 'edit';
        }
      }
    }
    this.$store.commit(
      'app/SET_NAV_TITLE',
      params.id && !this.isClone
        ? `${this.$t('route-' + '编辑配置').replace('route-', '')} - #${this.$route.params.id} ${
            this.$route.params.title
          }`
        : this.$t('新建配置')
    );
  },
  methods: {
    ...mapMutations([SET_INFO_DATA]),
    changeView(index) {
      const { stepConf } = this;
      this.$set(stepConf, 'active', index);
      this.currentView = stepConf.list[index].component;
    },
    handlePrevious() {
      const { stepConf } = this;
      const { active } = stepConf;
      this.changeView(active - 1);
      stepConf.list[active - 1].done = false;
    },
    handleNext() {
      const { stepConf } = this;
      const { active } = stepConf;
      this.changeView(active + 1);
      stepConf.list[active].done = true;
    },
    target(v) {
      this.config.target = v;
    },
    handlePasswordInputName(val) {
      this.passwordInputChangeSet.add(val);
    },
  },
};
</script>

<style lang="scss" scoped>
@import '../../home/common/mixins';

.collector-add {
  min-height: calc(100vh - 110px);
  background: #fff;
  display: flex;
  border-radius: 2px;
  border: 1px solid #dcdee5;
  border-right: 0;
  margin: 20px;

  .add-step {
    flex: 0 0 202px;
    background: $defaultBgColor;
    border-radius: 2px 0px 0px 0px;
    border-right: 1px solid $defaultBorderColor;

    .step-list {
      margin-left: 45px;
      padding: 40px 0 0 0;

      @for $i from 1 through 4 {
        &-item-#{$i} {
          &:before {
            content: '#{$i}';
          }
        }
      }

      .is-active {
        @include is-active;
      }

      .step-list-item {
        position: relative;
        border-left: 1px dashed $defaultBorderColor;
        height: 70px;
        padding-left: 25px;
        color: $defaultFontColor;

        &:before {
          width: 26px;
          height: 26px;
          line-height: 26px;
          display: inline-block;
          position: absolute;
          border-radius: 50%;
          left: -15px;
          top: -5px;
          text-align: center;
          background: #fff;
          color: $defaultFontColor;

          @include border-1px(#c4c6cc);
        }

        &:last-child {
          border-left: 0;
        }

        .list-item-content {
          position: relative;
          font-size: 14px;
          line-height: 19px;
        }
      }

      .is-done {
        border-left: 1px dashed #dcdee5;

        @include hover();

        &:last-child {
          border-left: 0;
        }

        &:before {
          /* stylelint-disable-next-line declaration-no-important */
          font-size: 28px !important;

          /* stylelint-disable-next-line declaration-no-important */
          content: '\e6b7' !important;

          /* stylelint-disable-next-line */
          font-family: 'icon-monitor' !important;
          background: #dcdee5;
          color: #fff;
          border: 1px solid #dcdee5;
        }

        .list-item-content {
          color: #63656e;
        }
      }
    }
  }

  .add-container {
    flex: 1;
    overflow: auto;
  }
}
</style>
