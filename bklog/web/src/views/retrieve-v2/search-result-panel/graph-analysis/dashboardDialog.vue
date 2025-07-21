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
<script setup>
import { ref, defineExpose } from 'vue';
import 'bk-magic-vue/lib/utils/svg-icon';
const isShow = ref(false);
const checkValue = ref(false);
const inputValue = ref('');
const collapseValue = ref([]);
const arrData = ref([
  {
    id: 1,
    name: 'General',
    children: [
      { id: 11, name: 'aaaa' },
      { id: 12, name: 'bbbb' },
      { id: 13, name: 'cccc' },
    ],
  },
  {
    id: 2,
    name: 'a 回到仓库',
    children: [
      { id: 21, name: 'aaaa' },
      { id: 22, name: 'bbbb' },
    ],
  },
  {
    id: 3,
    name: 'aaaa 会刷',
    children: [
      { id: 31, name: '33aaaa' },
      { id: 32, name: 'a333aaa' },
    ],
  },
]);
const handleShow = () => {
  isShow.value = true;
};

defineExpose({
  handleShow,
});
</script>
<template>
  <bk-dialog
    v-model:is-show="isShow"
    theme="primary"
    :width="480"
    header-position="left"
    :title="$t('收藏至仪表盘')"
  >
    <bk-checkbox v-model="checkValue" class="dialog_checkbox">{{
      $t("同名视图替换")
    }}</bk-checkbox>
    <bk-input v-model="inputValue" right-icon="icon-search"> </bk-input>
    <bk-collapse class="my-menu"  v-model="collapseValue">
      <bk-collapse-item
        :name="item.name"
        v-for="item in arrData"
        :key="item.id"
        :hide-arrow="true"
      >
        <i v-if="collapseValue.includes(item.name)" class="bk-icon icon-folder-open-shape"> </i>
        <i v-else class="bk-icon icon-folder-shape"> </i>
        <span>{{ item.name }}</span>
        <div slot="content">
          <ul class="list">
            <li class="list_li" v-for="childItem in item.children" :key="childItem.id">{{ childItem.name }}</li>
          </ul>
        </div>
      </bk-collapse-item>
    </bk-collapse>
  </bk-dialog>
</template>

<style lang="scss" scoped>
.dialog_checkbox {
  margin-bottom: 15px;
}

.icon-folder-open-shape {
  color: #a3c5fd;
}

.icon-folder-shape {
  color: #a3c5fd;
}

.list_li{
    height: 32px;
    padding: 0 12px;
    margin-bottom: 4px;
    line-height: 32px;
    background: #F5F7FA;
    border-radius: 2px;
}
</style>
