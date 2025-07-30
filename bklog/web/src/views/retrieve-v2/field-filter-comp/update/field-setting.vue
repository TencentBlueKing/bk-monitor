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
import Vue, { ref, computed, onBeforeUnmount } from "vue";
import FieldSelectConfig from "./field-list.vue";
import FieldAlias from "./field-alias.vue";
import useStore from "@/hooks/use-store";

const { $bkPopover } = Vue.prototype;
const store = useStore();

let popoverInstance = null;
const fieldSelectConfigRef = ref();
const dropdownListRef = ref();

const isUnionSearch = computed(() => store.getters.isUnionSearch);
const isExternal = computed(() => store.state.isExternal);

// 联合查询和外部环境不展示
const isFieldSettingShow = computed(() => {
  return !store.getters.isUnionSearch && !isExternal.value;
});

const handleSetting = (e) => {
  if (popoverInstance) {
    return;
  }
  popoverInstance = $bkPopover(e.target, {
    content: dropdownListRef.value,
    trigger: "manual",
    arrow: false,
    width: "130px",
    theme: "light",
    sticky: true,
    interactive: true,
    placement: "bottom-start",
    boundary: "viewport",
    extCls: "field-setting-popover",
    onHide: () => {
      if (fieldSelectConfigRef.value.isPopoverInstance()) {
        return false;
      }
    },
    onHidden: () => {
      popoverInstance?.destroy?.();
      popoverInstance = null;
    },
  });
  popoverInstance.show();
};

/**
 * @description 关闭 popover
 *
 */
const handlePopoverHide = () => {
  popoverInstance?.hide?.();
};
onBeforeUnmount(() => {
  if (popoverInstance) {
    popoverInstance?.destroy?.();
    popoverInstance = null;
  }
});
</script>
<template>
  <div class="field-seeting" v-show="!isUnionSearch">
    <span>
      <span class="bklog-icon bklog-shezhi" @click.stop="handleSetting"> </span>
    </span>
    <div v-show="false">
      <ul ref="dropdownListRef" class="dropdown-list">
        <li>
          <FieldSelectConfig
            ref="fieldSelectConfigRef"
            @handle-popover-hide="handlePopoverHide"
          ></FieldSelectConfig>
        </li>
        <li v-if="isFieldSettingShow">
          <FieldAlias @handle-popover-hide="handlePopoverHide"></FieldAlias>
        </li>
      </ul>
    </div>
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
