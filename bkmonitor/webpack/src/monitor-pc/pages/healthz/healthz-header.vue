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
  <div
    class="pattern"
    style="margin-bottom: 15px"
  >
    <!-- <a
      @click="$emit('update:msg', 0)"
      :class="msg === 0 ? 'list' : 'error-btn'"
    > {{ $t('服务状态') }} </a> -->
    <a
      v-if="isAdmin"
      @click="$emit('update:msg', 1)"
      :class="msg === 1 ? 'list' : 'error-btn'"
    >
      {{ $t('异常告警') }}
    </a>
  </div>
</template>
<script>
export default {
  name: 'MoHealthzHeaderView',
  props: {
    msg: {
      type: Number
    }
  },
  data() {
    return {
      isAdmin: process.env.NODE_ENV === 'development' ? window.is_superuser : window.is_superuser
    };
  },
  methods: {}
};
</script>
<style scoped>
.pattern {
  width: 100%;
  height: 48px;
  padding-top: 4px;
  font-size: 0;
  background: #e8eaec;
}

.list {
  display: inline-block;
  width: 120px;
  height: 40px;
  font-size: 14px;
  line-height: 40px;
  color: #fff;
  text-align: center;
  background: #86b1ff;
  border-radius: 2px;
}

.error-btn {
  display: inline-block;
  width: 120px;
  height: 40px;
  font-size: 14px;
  line-height: 40px;
  color: #666;
  text-align: center;
  background: #fff;
  border-radius: 2px;
}
</style>
