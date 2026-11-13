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

import { useApplicationStore } from '@/app/state/domains/application-store';
import { ref, computed } from 'vue';
import { Popup as TPopup } from 'tdesign-vue-next';
import FieldSelectConfig from './field-list.vue';
import FieldAlias from './field-alias.vue';


const store = useApplicationStore();

const visible = ref(false);
const fieldAliasRef = ref<{ handleOpenSidebar: () => void }>();
const handleAliasOpen = () => fieldAliasRef.value?.handleOpenSidebar();
const fieldSelectConfigRef = ref<{ isPopoverInstance: () => boolean }>();

const isUnionSearch = computed(() => store.isUnionSearch);
const isExternal = computed(() => store.isExternal);
const isSceneMode = computed(() => store.isSceneMode);

// 联合查询、外部环境和场景化检索不展示
const isFieldSettingShow = computed(() => {
  return !store.isUnionSearch && !isExternal.value && !isSceneMode.value;
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
          <li v-if="isFieldSettingShow">
            <div class="bklog-v3 field-alias-title" @click="handleAliasOpen">
              <span class="bklog-icon bklog-wholesale-editor" />{{ $t('批量编辑别名') }}
            </div>
          </li>
        </ul>
      </template>
    </TPopup>
    <!-- Keep the event listener and drawer mounted before Popup's lazy content opens. -->
    <FieldAlias
      v-if="isFieldSettingShow"
      ref="fieldAliasRef"
      :show-trigger="false"
      @handle-popover-hide="handlePopoverHide"
    />
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
  .t-popup__content {
    width: 130px;
    padding: 7px 0;
    border: 1px solid var(--bklog-border-muted, #dcdee5);
    border-radius: var(--bklog-radius-control, 2px);
    box-shadow: var(--bklog-shadow-small, 0 2px 6px 0 #0000001a);
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
