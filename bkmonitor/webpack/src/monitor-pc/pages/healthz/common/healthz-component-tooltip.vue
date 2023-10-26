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
  <!--公共组件按钮加tooltip-->
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
            @click="showPopupDialog(tip)"
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
                  'class-success': tip.status === 0,
                  'class-warning': tip.status === 1,
                  'class-error': tip.status > 1
                }"
              >
                {{ tip.server_ip }} {{ tip.description }} {{ tip.value }}
                <i
                  class="reload-agent fix-same-code"
                  v-show="tip.status > 1"
                />
                <i
                  class="fix-same-code warning-agent"
                  v-show="tip.status === 1"
                />
              </h5>
            </el-tooltip>
          </div>
        </div>
        <div class="tooltip-footer">
          <div class="fix-same-code tooltip-success" />
          <span class="tooltip-text"> {{ $t('正常') }} </span>
          <div class="fix-same-code tooltip-warning" />
          <span class="tooltip-text"> {{ $t('关注') }} </span>
          <div class="fix-same-code tooltip-error" />
          <span class="tooltip-text"> {{ $t('异常') }} </span>
        </div>
      </div>
      <el-button
        class="btn-class-space fix-same-code"
        :class="{
          'class-error': color === 'red',
          'class-success': color === 'green',
          'class-warning': color === 'yellow',
          'class-normal': color === ''
        }"
      >
        {{ componentName }}
      </el-button>
    </el-tooltip>
    <mo-healthz-common-popup-window-view
      :is-visible.sync="isShowDialog"
      :tips="tips"
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

import MoHealthzCommonPopupWindowView from './healthz-common-popup-window';

export default {
  name: 'MoHealthzComponentTooltipView',
  components: {
    MoHealthzCommonPopupWindowView,
    ElTooltip: Tooltip,
    ElButton: Button
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
    // 是否是最后一个组件，用于控制是否渲染横线
    isLast: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      colors: ['green', 'yellow', 'red'], // 组件的颜色列表
      tips: {}, // 弹窗显示的数据
      isShowDialog: false // 是否显示当前弹窗
    };
  },
  computed: {
    selectedStoreIPs() {
      return store.state.selectedIPs;
    },
    storeGlobalData() {
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
      const tmpGlobal = this.storeGlobalData;
      // eslint-disable-next-line @typescript-eslint/prefer-for-of
      tmpGlobal.forEach((item) => {
        if (this.componentName === item.node_name) {
          const tips = {};
          tips.server_ip = item.server_ip;
          tips.description = item.description;
          tips.value = item.result.value;
          tips.name = item.node_name;
          tips.message = item.result.message;
          tips.status = item.result.status;
          tips.solution = item.solution;
          // 检查 result 中是否存在 api_list 存在的话，就放入tips
          if (Object.prototype.hasOwnProperty.call(item.result, 'api_list')) {
            tips.api_list = item.result.api_list;
          }
          returnData.push(tips);
        }
      });
      return returnData;
    },
    // 根据前端显示的选中的ip列表过滤本地数据
    filteredNodeData() {
      // 如果当前组件为saas依赖周边，则直接返回数据
      if (store.state.saasDependenciesComponent.indexOf(this.componentName) > -1) return this.nodeData;
      const resultData = [];
      this.nodeData.forEach((item) => {
        if (this.selectedStoreIPs.indexOf(item.server_ip) > -1) {
          resultData.push(item);
        }
      });
      resultData.sort(this.compare);
      return resultData;
    },
    // 当前节点所有数据的状态列表
    statusList() {
      const statusList = [];
      const tmpGlobal = this.filteredNodeData;
      tmpGlobal.forEach((item) => {
        if (this.componentName === item.name) {
          statusList.push(item.status);
        }
      });
      return statusList;
    },
    // 由当前数据状态列表计算而来的颜色
    color() {
      // 无数据，则无颜色
      if (this.statusList.length === 0) return '';
      let max = Math.max.apply(null, this.statusList);
      max = max > 1 ? 2 : max;
      return this.colors[max];
    },
    // 当前节点的状态，由所有数据的状态列表聚合而来，所有的状态都为0时才为0
    status() {
      // 如果没有数据，则认为出错
      if (this.statusList.length === 0) return 2;
      const max = Math.max.apply(null, this.statusList);
      return max > 1 ? 2 : max;
    }
  },
  methods: {
    // 显示当前弹窗，根据当前组件的不同，显示不同组件
    showPopupDialog(tips) {
      // 设置弹窗上的数据
      this.tips = tips;
      this.isShowDialog = true;
    },
    // 比较函数
    compare(obj1, obj2) {
      if (obj1.status > obj2.status) return -1;
      if (obj1.status < obj2.status) return 1;
      return 0;
    }
  }
};
</script>
<style lang="scss" scoped>
@import '../style/healthz';
</style>
<style>
/* healthz页面下的tooltip样式 */
.healthz-component-tooltip {
  /* stylelint-disable-next-line declaration-no-important */
  box-shadow: 0px 3px 4px 0px rgba(112, 115, 120, .1) !important;

  /* stylelint-disable-next-line declaration-no-important */
  border-radius: 2px !important;

  /* stylelint-disable-next-line declaration-no-important */
  border: solid 1px #e8eaec !important;
}
</style>
