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
  <!-- 功能开关列表 -->
  <div
    class="function-switch-wrapper"
    v-monitor-loading="{ isLoading: loading }"
  >
    <!-- 功能item -->
    <template v-if="!isAbnormal">
      <function-item
        class="func-item"
        v-for="(item, index) in dataList"
        :key="index"
        :data="item"
        :enable.sync="item.isEnable"
      />
    </template>
    <!-- 列表数据异常 -->
    <div
      v-else
      class="abnormal-data"
    >
      <img
        alt=''
        class="abnormal-img"
        src="../../static/images/svg/Abnormal-data.svg"
      >
      <div class="abnormal-text">
        {{ $t('拉取用户配置数据失败') }}
      </div>
      <bk-button
        theme="primary"
        @click="getFunctionList"
      >{{ $t('重新获取') }}</bk-button>
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Mixins, Provide, ProvideReactive } from 'vue-property-decorator';

import { listFunction } from '../../../monitor-api/modules/function_switch.js';
import { transformDataKey } from '../../../monitor-common/utils/utils';
import authorityMixinCreate from '../../mixins/authorityMixin';

import * as funcAuth from './authority-map';
import FunctionItem from './function-item.vue';

@Component({
  name: 'function-switch',
  components: { FunctionItem }
} as any)
export default class FunctionSwitch extends Mixins(authorityMixinCreate(funcAuth)) {
  // 功能列表数据
  dataList: any = [];
  loading = false;
  // 数据异常
  isAbnormal = false;
  @ProvideReactive('authority') authority: Record<string, boolean> = {};
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  created() {
    // 初始化数据
    this.getFunctionList();
  }

  // 获取功能列表数据
  getFunctionList() {
    this.loading = true;
    listFunction()
      .then((data) => {
        this.dataList = transformDataKey(data);
        this.isAbnormal = false;
      })
      .catch(() => {
        this.isAbnormal = true;
      })
      .finally(() => (this.loading = false));
  }
}
</script>

<style lang="scss" scoped>
@import '../../theme/index.scss';

.function-switch-wrapper {
  padding-bottom: 20px;

  .func-item {
    &:not(:last-child) {
      margin-bottom: 10px;
    }
  }

  .abnormal-data {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 22px;

    .abnormal-img {
      display: inline-block;
      width: 480px;
      height: 240px;
    }

    .abnormal-text {
      margin-bottom: 24px;
      font-size: 24px;
      line-height: 31px;
      color: $defaultFontColor;
    }
  }
}
</style>
