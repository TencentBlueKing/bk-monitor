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
  <div class="alarm-shield-target">
    <!-- 编辑时不能修改屏蔽目标 -->
    <template v-if="!isEdit">
      <!-- 不同选择器btn -->
      <div class="bk-button-group">
        <bk-button
          v-for="(item, index) in buttonList"
          :key="index"
          class="btn-width"
          :class="{ 'is-selected': targetType === item.id }"
          @click.stop="handleBtnChange(item.id)"
        >
          {{ item.name }}
        </bk-button>
      </div>
      <!-- 各种选择器的提示 -->
      <div class="tips-text"><i class="icon-monitor icon-tips item-icon" />{{ tips[targetType] }}</div>
      <!-- 3种选择器  实例  IP  节点 -->
      <div class="target-selector">
        <alarm-shield-ipv6
          v-if="initialized"
          :show-dialog="showIpv6Dialog"
          :shield-dimension="targetType"
          :checked-value="ipv6Value"
          :origin-checked-value="originIpv6Value"
          :show-view-diff="isClone"
          @change="handleValueChange"
          @closeDialog="handleIpv6DialogChange"
        />
        <div
          v-if="targetError"
          class="target-selector-error"
        >
          {{ $t('选择屏蔽目标') }}
        </div>
      </div>
    </template>
    <!-- 编辑勾选展示 -->
    <bk-table
      v-else-if="targetType !== 'biz' && isEdit"
      class="static-table"
      :data="targetData"
      :max-height="450"
    >
      <bk-table-column
        class="fix-same-code"
        :label="labelMap[type]"
        prop="name"
      />
    </bk-table>
  </div>
</template>

<script lang="ts">
import { Component, Prop, Vue } from 'vue-property-decorator';

import { deepClone } from 'monitor-common/utils';

import { transformMonitorToValue, transformValueToMonitor } from '../../../components/monitor-ip-selector/utils';
import AlarmShieldIpv6, {
  Ipv6FieldMap,
  ShieldDetailTargetFieldMap,
  ShieldDimension2NodeType,
} from '../alarm-shield-set/alarm-shield-scope/alarm-shield-ipv6';

import type { TranslateResult } from 'vue-i18n/types/index';

@Component({
  components: {
    AlarmShieldIpv6,
  },
})
export default class AlarmShieldTarget extends Vue {
  targetError = false; //  未勾选提示
  targetType = 'ip'; //  当前选择器类型

  //  选择器类型btn
  btnList: { id: string; name: TranslateResult }[] = [];
  //  不同选择器提示语
  tips: { instance: TranslateResult; ip: TranslateResult; node: TranslateResult };
  //  不同类型的展示标签
  labelMap: { instance: TranslateResult; ip: TranslateResult; node: TranslateResult };
  initialized = true;
  showIpv6Dialog = false;
  ipv6Value = {};
  originIpv6Value = {};
  // 是否为克隆
  @Prop({ default: false })
  isClone: boolean;
  //  是否编辑
  @Prop({ default: false })
  isEdit: boolean;

  //  targetData回填数据
  @Prop({ default: () => [] })
  targetData: [];

  //  targetType
  @Prop()
  type: string;

  @Prop({ default: () => [] })
  dataTarget: string[];

  // 回填数据
  @Prop({ default: () => ({}) })
  shieldData: any;

  // 是否需要校验
  @Prop({ default: true })
  needVerify: boolean;

  get buttonList() {
    const res = [{ name: this.$t('button-拓扑节点'), id: 'node', order: 2 }];
    if (this.dataTarget.find(item => item === 'HOST')) {
      res.push({ name: this.$t('button-主机'), id: 'ip', order: 1 });
    }
    if (this.dataTarget.find(item => item === 'SERVICE')) {
      res.push({ name: this.$t('button-服务实例'), id: 'instance', order: 0 });
    }
    return res.sort((a, b) => a.order - b.order);
  }

  created() {
    this.tips = {
      instance: this.$t('服务实例屏蔽: 屏蔽告警中包含该实例的通知'),
      ip: this.$t('主机屏蔽: 屏蔽告警中包含该IP通知,包含对应的实例'),
      node: this.$t('节点屏蔽: 屏蔽告警中包含该节点下的所有IP和实例的通知'),
    };
    this.labelMap = {
      ip: this.$t('主机'),
      instance: this.$t('服务实例'),
      node: this.$t('节点名称'),
    };

    if (this.isClone) {
      this.initialized = false;
      this.targetType = this.type;
      this.cloneDefaultData();
      this.$nextTick(() => (this.initialized = true));
    }
  }

  // 克隆节点回写数据
  cloneDefaultData() {
    const { scope_type, dimension_config } = this.shieldData;
    const targetList = dimension_config?.[ShieldDetailTargetFieldMap[scope_type]] || [];
    this.ipv6Value =
      scope_type === 'instance'
        ? {
            [Ipv6FieldMap[scope_type]]: targetList.map(id => ({ service_instance_id: id })),
          }
        : transformMonitorToValue(targetList, ShieldDimension2NodeType[scope_type]);
    this.originIpv6Value = deepClone(this.ipv6Value);
  }

  //  选择器切换
  handleBtnChange(id: string): void {
    this.targetType = id;
    this.showIpv6Dialog = true;
    this.targetError = false;
  }

  //  提交数据，拿到类型和目标数据方便父组件提交
  getTargetData(): { scope_type: string; target: any[] } {
    const data = this.ipv6Value?.[Ipv6FieldMap?.[this.targetType]];
    if (!data?.length && this.needVerify) {
      this.targetError = true;
      return;
    }
    if (!data?.length) {
      return {
        scope_type: this.targetType,
        target: [],
      };
    }
    return {
      scope_type: this.targetType,
      target: transformValueToMonitor(this.ipv6Value, ShieldDimension2NodeType[this.targetType]),
    };
  }

  handleIpv6DialogChange() {
    this.targetError = false;
    this.showIpv6Dialog = false;
  }
  handleValueChange({ value }) {
    this.ipv6Value = { ...this.ipv6Value, ...value };
  }
}
</script>

<style lang="scss" scoped>
.alarm-shield-target {
  position: relative;

  &.out-line {
    outline: 1px solid #dcdee5;
  }

  .btn-width {
    width: 168px;
  }

  .tips-text {
    display: flex;
    align-items: center;
    margin: 10px 0;
    font-size: 12px;

    .item-icon {
      margin-right: 6px;
      font-size: 14px;
      line-height: 1;
      color: #979ba5;
    }
  }

  .target-selector {
    display: block;
    width: 80%;

    &-error {
      font-size: 12px;
      color: #ea3636;
    }
  }

  .static-table {
    width: 836px;

    :deep(.cell) {
      padding-left: 30px;
    }

    &:before {
      height: 1px;
    }
  }
}
</style>
