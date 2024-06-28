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
  <div class="alarm-shield-detail-scope">
    <div class="scope-item">
      <div class="item-label">
        {{ $t('屏蔽范围') }}
      </div>
      <div class="item-content">
        <div class="item-content-target">
          {{ target }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AlarmShieldDetailScope',
  props: {
    dimension: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      target: '',
    };
  },
  watch: {
    dimension: {
      handler: 'handleDimension',
      immediate: true,
      deep: true,
    },
  },
  methods: {
    // 目前的解决方案是把数组转化成字符串，缺点是展示条数过多会现得密密麻麻，看不清楚 （展示待更改）
    handleDimension(v) {
      if (Object.keys(v).length) {
        this.target = v.target.join(',');
      }
    },
  },
};
</script>

<style lang="scss" scoped>
.alarm-shield-detail-scope {
  font-size: 14px;
  color: #63656e;

  .scope-item {
    display: flex;
    align-items: flex-start;
    margin-bottom: 20px;

    .item-label {
      min-width: 90px;
      margin-right: 24px;
      color: #979ba5;
      text-align: right;
    }

    .item-content {
      min-height: 16px;

      &-target {
        max-width: calc(100vw - 306px);
        word-break: break-all;
      }
    }
  }
}
</style>
