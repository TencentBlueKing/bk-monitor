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

<script setup lang="ts">
import { ref, computed } from 'vue';
import { Popup as TPopup } from 'tdesign-vue-next';
import FieldSelectConfig from './field-list.vue';
import FieldAlias from './field-alias.vue';
import useStore from '@/shared/composables/use-store';

const store = useStore();

const visible = ref(false);
const fieldSelectConfigRef = ref<{ isPopoverInstance: () => boolean }>();

const isUnionSearch = computed(() => store.getters.isUnionSearch);
const isExternal = computed(() => store.state.isExternal);
const isSceneMode = computed(() => store.getters.isSceneMode);

// 联合查询、外部环境和场景化检索不展示
const isFieldSettingShow = computed(() => {
  return !store.getters.isUnionSearch && !isExternal.value && !isSceneMode.value;
});

const handleVisibleChange = (next: boolean) => {
  if (!next && fieldSelectConfigRef.value?.isPopoverInstance()) return;
  visible.value = next;
};
const handlePopoverHide = () => {
  visible.value = false;
};
</script>
<template>
  <div v-show="!isUnionSearch" class="field-seeting">
    <TPopup
      :visible="visible"
      trigger="click"
      placement="bottom-left"
      overlay-class-name="bklog-v3-popover-tag field-setting-popover"
      @visible-change="handleVisibleChange"
    >
      <span class="bklog-icon bklog-shezhi" />
      <template #content>
        <ul class="dropdown-list">
          <li><FieldSelectConfig ref="fieldSelectConfigRef" @handle-popover-hide="handlePopoverHide" /></li>
          <li v-if="isFieldSettingShow"><FieldAlias @handle-popover-hide="handlePopoverHide" /></li>
        </ul>
      </template>
    </TPopup>
  </div>
</template>
<style lang="scss">
.field-seeting {
  position: absolute;
  right: 20px;

  .bklog-shezhi {
    font-size: 15px;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
    }
  }
}

.field-setting-popover {
  .tippy-tooltip {
    padding: 7px 0;
  }

  .dropdown-list {
    width: 130px;
    li {
      height: 32px;
      padding: 0 6px 0px 12px;
      line-height: 32px;
      color: #4d4f56;
      cursor: pointer;

      &:hover {
        background: #f5f7fa;
      }
    }
  }
}
</style>
