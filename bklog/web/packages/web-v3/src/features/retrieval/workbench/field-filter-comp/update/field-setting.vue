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
      :show-arrow="false"
      overlay-class-name="bklog-v3-popover-tag field-setting-popover"
      :overlay-inner-style="{ padding: 'var(--bklog-space-4) 0', width: 'max-content' }"
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
    width: max-content;
    padding: var(--bklog-space-4) 0;
    border: var(--bklog-border-width) solid var(--bklog-border-muted, var(--td-component-stroke));
    border-radius: var(--bklog-standard-control-radius);
    box-shadow: var(--bklog-dropdown-shadow, var(--td-shadow-2));
  }

  .dropdown-list {
    width: auto;
    margin: 0;

    li {
      display: flex;
      align-items: center;
      height: var(--bklog-control-size-medium);
      min-height: var(--bklog-control-size-medium);
      padding: 0;
      font-size: var(--bklog-font-body);
      line-height: var(--bklog-line-height-body);
      color: var(--td-text-color-secondary);
      cursor: pointer;

      &:hover {
        background: var(--bklog-option-surface-hover);
      }
    }
  }

  .field-select-config-v2,
  .field-alias-title {
    width: 100%;
  }

  .dropdown-trigger,
  .field-alias-title {
    display: flex;
    align-items: center;
    gap: var(--bklog-space-8);
    width: 100%;
    height: var(--bklog-control-size-medium);
    padding: 0 var(--bklog-space-12);
    font-size: var(--bklog-font-body);
    line-height: var(--bklog-line-height-body);
    white-space: nowrap;
  }

  .dropdown-trigger .bklog-icon,
  .field-alias-title .bklog-icon {
    flex: none;
    width: var(--bklog-space-16);
    margin: 0;
    font-size: var(--bklog-space-16);
    line-height: 1;
  }

  .field-select-config-v2 .icon-angle-right-line {
    position: static;
    flex: none;
    width: var(--bklog-space-12);
    margin: 0 0 0 auto;
    font-size: var(--bklog-space-12);
    line-height: 1;
  }
}
</style>
