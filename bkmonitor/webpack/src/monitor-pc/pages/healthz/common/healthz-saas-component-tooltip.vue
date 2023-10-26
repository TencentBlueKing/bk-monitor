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
  <!--cmdb,job,bk_data的tooltip-->
  <div>
    <el-tooltip
      popper-class="healthz-component-tooltip"
      effect="light"
      :placement="'bottom'"
    >
      <div slot="content">
        <div class="content-tooltips-overflow">
          <div
            class="content-tooltip-h5"
            v-for="(tip, _index) in filteredNodeData"
            :key="_index"
            @click="showPopupDialog"
          >
            <el-tooltip
              popper-class="healthz-component-tooltip"
              placement="top"
              :open-delay="500"
              effect="light"
            >
              <div slot="content">
                {{ tip.description }} {{ tip.value }}
              </div>
              <h5
                :class="{
                  'class-normal': status === -1,
                  'class-success': status === 0,
                  'class-warning': status === 1,
                  'class-error': status > 1
                }"
              >
                {{ tip.server_ip }} {{ tip.description }} {{ tip.value }}
                <i
                  class="reload-agent"
                  v-show="tip.status > 1"
                />
                <i
                  class="warning-agent"
                  v-show="tip.status === 1"
                />
              </h5>
            </el-tooltip>
          </div>
        </div>
        <div class="tooltip-footer">
          <div class="tooltip-success" />
          <span class="tooltip-text"> {{ $t('正常') }} </span>
          <div class="tooltip-warning" />
          <span class="tooltip-text"> {{ $t('关注') }} </span>
          <div class="tooltip-error" />
          <span class="tooltip-text"> {{ $t('异常') }} </span>
        </div>
      </div>
      <el-button
        class="btn-class-space"
        :class="{
          'class-success': color === 'green',
          'class-warning': color === 'yellow',
          'class-error': color === 'red',
          'class-normal': color === ''
        }"
      >
        {{ componentName }}
      </el-button>
    </el-tooltip>
    <!--弹窗-->
    <!-- 对 cmdb, job, bk_data 增加自动测试的功能 -->
    <mo-healthz-saas-popup-window-view
      :component-name="componentName"
      @changestatus="changeStatus"
      :is-visible.sync="isShowDialog"
      ref="popup"
    />
    <div
      :class="status === 0 ? 'dash-border' : 'dotted-line'"
      :style="{ visibility: showLine }"
      v-if="!isLast"
    />
  </div>
</template>
<script>
import { Button, Tooltip } from 'element-ui';

import store from '../store/healthz/store';

import MoHealthzSaasPopupWindowView from './healthz-saas-popup-window';

export default {
  name: 'MoHealthzSaasComponentTooltipView',
  components: {
    ElTooltip: Tooltip,
    ElButton: Button,
    MoHealthzSaasPopupWindowView
  },
  props: {
    // 当前组件名称
    componentName: {
      type: String
    },
    // 是否展示连接线
    showLine: {
      type: String,
      default: 'hidden'
    },
    // 当前组件的位置，第一个组件不显示线
    index: {
      type: Number
    },
    // 当前组件是否是最后一个
    isLast: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      colors: ['green', 'yellow', 'red'], // 组件的颜色列表
      status: -1, // 当前组件状态，-1表示初始状态，还未测试，0表示正常，1表示关注，2表示错误
      isShowDialog: false, // 是否显示弹窗
      tips: {} // 弹窗上的数据
    };
  },
  computed: {
    saasComponentNeedToTest() {
      return store.state.saasComponentNeedToTest;
    },
    selectedIPs() {
      return store.state.selectedIPs;
    },
    globalData() {
      return store.state.globalData;
    },
    // ...mapState([
    //     'saasComponentNeedToTest',
    //     'selectedIPs',
    //     'globalData'
    // ]),
    // 通过全局数据得到的本地数据
    nodeData() {
      const returnData = [];
      const tmpGlobal = this.globalData;
      for (let i = 0; i < tmpGlobal.length; i++) {
        if (this.componentName === tmpGlobal[i].node_name) {
          const tips = {};
          tips.server_ip = tmpGlobal[i].server_ip;
          tips.description = tmpGlobal[i].description;
          tips.value = tmpGlobal[i].result.value;
          tips.name = tmpGlobal[i].node_name;
          tips.message = tmpGlobal[i].result.message;
          tips.status = tmpGlobal[i].result.status;
          tips.solution = tmpGlobal[i].solution;
          // 检查 result 中是否存在 api_list 存在的话，就放入tips
          if (Object.prototype.hasOwnProperty.call(tmpGlobal[i].result, 'api_list')) {
            tips.api_list = tmpGlobal[i].result.api_list;
          }
          returnData.push(tips);
        }
      }
      return returnData;
    },
    // 根据前端显示的选中的ip列表过滤本地数据
    filteredNodeData() {
      // 如果当前组件为saas依赖周边，则直接返回数据
      if (store.state.saasDependenciesComponent.indexOf(this.componentName) > -1) return this.nodeData;
      const resultData = [];
      for (let i = 0; i < this.nodeData.length; i++) {
        if (this.selectedIPs.indexOf(this.nodeData[i].server_ip) > -1) {
          resultData.push(this.nodeData[i]);
        }
      }
      return resultData;
    },
    // 当前节点所有数据的状态列表
    statusList() {
      const statusList = [];
      const tmpGlobal = this.filteredNodeData;
      for (let i = 0; i < tmpGlobal.length; i++) {
        if (this.componentName === tmpGlobal[i].name) {
          statusList.push(tmpGlobal[i].status);
        }
      }
      return statusList;
    },
    // 由当前数据状态列表计算而来的颜色
    color() {
      // 根据状态改变颜色
      if (this.status === -1) return '';
      return this.colors[this.status];
    }
  },
  watch: {
    filteredNodeData(newValue, oldValue) {
      // 只有在旧数据为空，且新数据只有一条的情况下才执行，相当于watch once
      if (oldValue.length === 0 && newValue.length === 1) {
        this.$refs.popup.tips = newValue[0];
        this.$refs.popup.loadSaasDataToTest();
        this.$refs.popup.runTest();
      }
    }
  },
  methods: {
    // 显示当前弹窗，根据当前组件的不同，显示不同组件
    showPopupDialog() {
      // 设置弹窗上的数据
      this.isShowDialog = true;
    },
    // 根据子组件传过来的状态更新当前状态
    changeStatus(status, componentName) {
      if (componentName === this.componentName) {
        this.status = status;
      }
    }
  }
};
</script>
<style lang="scss" scoped>
@import '../style/healthz';
</style>
