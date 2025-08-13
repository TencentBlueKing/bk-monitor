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
    :value="isShow"
    :title="$t('添加条件')"
    :before-close="handleBackStep"
    @on-confirm="handleSubmit"
    @on-cancel="handleBackStep"
  >
    <bk-checkbox-group v-model="aaa">
      <bk-checkbox
        v-for="item in dimensionsList"
        :key="item.id"
        class="dialog-checkbox"
        :value="item.id"
        :disabled="item.disabled"
      >
        {{ item.name }}
      </bk-checkbox>
    </bk-checkbox-group>
  </monitor-dialog>
</template>

<script lang="ts">
import { Component, Prop, Vue } from 'vue-property-decorator';

import MonitorDialog from 'monitor-ui/monitor-dialog/monitor-dialog.vue';

@Component({
  name: 'add-dimesion-dialog',
  components: {
    MonitorDialog,
  },
})
export default class AddDimesionDialog extends Vue {
  @Prop({ default: false })
  isShow: boolean;
  @Prop({ default: () => [] })
  dimensionsList: any[];
  @Prop({ default: () => [] })
  checkedDimensions: [];

  aaa = [];
  created() {
    this.aaa = this.checkedDimensions;
  }
  handleSubmit() {
    const changeList = this.dimensionsList.filter(item => this.aaa.indexOf(item.id) > -1);
    this.$emit('add-dimension', changeList);
    this.$emit('close-dialog', false);
  }

  handleBackStep() {
    this.$emit('close-dialog', false);
  }
}
</script>

<style lang="scss" scoped>
.dialog-checkbox {
  padding-right: 16px;
  margin-top: 8px;
}
</style>
