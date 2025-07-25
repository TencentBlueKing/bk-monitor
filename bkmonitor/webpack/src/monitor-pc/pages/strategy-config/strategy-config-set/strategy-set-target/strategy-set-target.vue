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
  <monitor-dialog
    :value.sync="show"
    :title="title || $t('监控目标')"
    width="1100"
    :need-footer="false"
    :z-index="2000"
    @on-confirm="handleConfirm"
    @change="handleValueChange"
  >
    <strategy-config-target
      v-if="isShowTarget"
      :can-save-empty="canSaveEmpty"
      :tab-disabled="tabDisabled"
      :target-list="targetList"
      :set-config="strategySetConfig"
      :hidden-template="hiddenTemplate"
      @target-change="handleTargetChange"
      @message-change="handleTargetDesChange"
      @target-type-change="handleTargetTypeChange"
      @cancel="handleValueChange"
      @save-change="handleSaveChange"
    />
  </monitor-dialog>
</template>
<script lang="ts">
import { Component, Prop, Vue, Watch } from 'vue-property-decorator';

import MonitorDialog from 'monitor-ui/monitor-dialog/monitor-dialog.vue';

import StrategyConfigTarget from '../../strategy-config-target/strategy-config-target.vue';

@Component({
  components: {
    MonitorDialog,
    StrategyConfigTarget,
  },
})
export default class StrategySetTarget extends Vue {
  show = false;
  // 是否展示
  @Prop({
    type: Boolean,
    default: false,
  })
  dialogShow: boolean;

  // 业务id
  @Prop()
  bizId: number | string;

  // 监控对象类型
  @Prop()
  objectType: string;

  // 默认选择的目标
  @Prop()
  targetList: Array<any>;

  // 目标类型
  @Prop()
  targetType: string;

  // 策略id
  @Prop()
  strategyId: number | string;

  // tab的disabled状态控制, 0: 静态disabled; 1: 动态disabled; -1: 都不disabled
  @Prop({ default: null, type: [Number, null] })
  tabDisabled: -1 | 0 | 1 | null;

  // 是否允许保存空的目标
  @Prop({ default: false, type: Boolean })
  canSaveEmpty: {
    default: false;
    type: boolean;
  };

  @Prop({ default: false, type: Boolean }) hiddenTemplate: boolean;
  @Prop({ default: '', type: String }) title: string;

  isShowTarget = false;

  @Watch('dialogShow', {
    immediate: true,
  })
  onDialogShowChange(v) {
    this.show = v;
    if (!v) {
      setTimeout(() => {
        this.isShowTarget = false;
      }, 300);
    } else {
      this.isShowTarget = true;
    }
  }

  get zIndex() {
    if (window.__bk_zIndex_manager?.nextZIndex) {
      return window.__bk_zIndex_manager.nextZIndex();
    }
    return 2000;
  }

  get strategySetConfig() {
    return {
      targetType: this.targetType,
      objectType: this.objectType,
      bizId: this.bizId,
      strategyId: this.strategyId || 0,
    };
  }

  // 是否显示触发
  handleValueChange(v) {
    this.$emit('update:dialogShow', v);
    this.$emit('show-change', v);
  }

  // 点击保存触发
  handleConfirm() {
    this.show = false;
    this.$emit('update:dialogShow', false);
  }

  // 选中目标改变触发
  handleTargetChange(targets: Array<any>) {
    this.$emit('targets-change', targets);
    this.handleConfirm();
  }

  // 目标类型改变触发
  handleTargetTypeChange(v) {
    this.$emit('target-type-change', v);
  }

  // 目标描述改变触发
  handleTargetDesChange(message) {
    this.$emit('message-change', message);
  }

  // 单条策略监控目标保存成功
  handleSaveChange() {
    this.$emit('save-change', true);
  }
}
</script>
