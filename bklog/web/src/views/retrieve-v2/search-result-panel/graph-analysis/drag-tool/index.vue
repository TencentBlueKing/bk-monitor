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
<script setup type="ts">
  import { computed, ref } from 'vue';

  const props = defineProps({
    direction: {
      type: String,
      default: 'horizional'
    }
  });

  const emit = defineEmits(['move-end']);

  const startPosition = ref({ x: 0, y: 0 });
  const endPosition = ref({ x: 0, y: 0 });
  const showMoveLine = ref(false);
  const oldUserSelect = ref(undefined);

  const moveStyle = computed(() => {
    if (showMoveLine.value) {
      return {
        '--line-offset-x': `${endPosition.value.x - startPosition.value.x}px`,
        '--line-offset-y': `${endPosition.value.y - startPosition.value.y}px`,
      };
    }

    return {};
  });


  const handleMousemove = (e) => {
    Object.assign(endPosition.value, { x: e.x, y: e.y });
  };

  const handleMouseup = () => {
    showMoveLine.value = false;

    if (oldUserSelect.value !== undefined) {
      document.body.style.setProperty('user-select', oldUserSelect.value);
      oldUserSelect.value = undefined;
    } else {
      document.body.style.removeProperty('user-select');
    }

    window.removeEventListener('mousemove', handleMousemove);
    window.removeEventListener('mouseup', handleMouseup);
    emit('move-end', {
      offsetX: endPosition.value.x - startPosition.value.x,
      offsetY: endPosition.value.y - startPosition.value.y,
    });
  };

  const handleMousedown = (e) => {
    oldUserSelect.value = document.body.style.getPropertyValue('user-select');
    document.body.style.setProperty('user-select', 'none');
    Object.assign(startPosition.value, { x: e.x, y: e.y });
    Object.assign(endPosition.value, { x: e.x, y: e.y });
    showMoveLine.value = true;
    window.addEventListener('mousemove', handleMousemove);
    window.addEventListener('mouseup', handleMouseup);
  };
</script>
<template>
  <div
    :style="moveStyle"
    :class="['graph-drag-tool', direction, { dragging: showMoveLine }]"
    @mousedown="handleMousedown"
  >
    <div class="drag-tool-point">
      <span></span>
      <span></span>
      <span></span>
      <span></span>
      <span></span>
    </div>
  </div>
</template>

<style lang="scss">
  .graph-drag-tool {
    display: flex;
    align-items: center;
    justify-content: center;

    .drag-tool-point {
      box-sizing: content-box;
      display: flex;
      justify-content: space-between;

      > span {
        display: block;
        width: 3px;
        height: 3px;
        background: #c4c6cc;
        border-radius: 50%;
      }
    }

    &.horizional {
      &.dragging {
        &::after {
          position: absolute;
          right: 0;
          bottom: 0;
          left: 0;
          z-index: 100;
          height: 1px;
          content: '';
          border-bottom: dashed 1px #3a84ff;
          transform: translate(0, var(--line-offset-y));
        }
      }

      .drag-tool-point {
        width: 27px;
        height: 3px;
        padding: 2px 0;
        cursor: s-resize;
        content: '';
      }
    }

    &.vertical {
      &.dragging {
        &::after {
          position: absolute;
          top: 0;
          bottom: 0;
          left: 0;
          z-index: 100;
          width: 1px;
          content: '';
          border-left: dashed 1px #3a84ff;
          transform: translate(var(--line-offset-x), 0);
        }
      }

      .drag-tool-point {
        flex-direction: column;
        width: 3px;
        height: 27px;
        padding: 0 2px;
        cursor: w-resize;
      }
    }
  }
</style>
