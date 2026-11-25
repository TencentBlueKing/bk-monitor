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
  <div class="empty-status-container">
    <!-- TEmpty caches description in a computed; slot presence itself is not reactive. -->
    <TEmpty :key="slots.default ? 'custom-content' : 'default-content'" class="empty-status-body" :class="{ 'is-part': scene === 'part' }">
      <template #image>
        <img v-if="imageSource" :src="imageSource" class="exception-image" alt="" />
      </template>
      <template #title><span /></template>
      <template #description>
        <div class="empty-text-content">
          <p v-if="showText" class="empty-text">{{ description ?? typeText }}</p>
          <template v-if="slots.default">
            <div class="empty-text"><slot /></div>
          </template>
          <template v-else-if="showOperation">
            <SourceTranslation v-if="emptyType === 'search-empty'" class="operation-text" path="可以尝试{0}或{1}">
              <span style="margin: 0 3px">{{ t('调整关键词') }}</span>
              <button type="button" class="operation-btn exception-clear" @click="handleOperation('clear-filter')">
                {{ t('清空筛选条件') }}
              </button>
            </SourceTranslation>
            <button v-if="emptyType === '500'" type="button" class="operation-btn exception-refresh" @click="handleOperation('refresh')">
              {{ t('刷新') }}
            </button>
          </template>
        </div>
      </template>
    </TEmpty>
  </div>
</template>

<script setup lang="ts">
import {computed, useSlots} from 'vue';
import {Empty as TEmpty} from 'tdesign-vue-next';
import useLocale from '@/shared/composables/use-locale';
import SourceTranslation from '@/platform/i18n/translation';
import type {EmptyStatusOperation} from './types';
import forbidden from '@/shared/assets/exception/403.svg';
import notFound from '@/shared/assets/exception/404.svg';
import serverError from '@/shared/assets/exception/500.svg';
import building from '@/shared/assets/exception/building.svg';
import empty from '@/shared/assets/exception/empty.svg';
import searchEmpty from '@/shared/assets/exception/search-empty.svg';
import login from '@/shared/assets/exception/login.svg';

const props = withDefaults(defineProps<{
  emptyType?: string;
  description?: string;
  scene?: string;
  showOperation?: boolean;
  showText?: boolean;
}>(), {emptyType: 'empty', scene: 'part', showOperation: true, showText: true});
const emit = defineEmits<{(event: 'operation', operation: EmptyStatusOperation): void}>();
const {t} = useLocale();
const slots = useSlots();
const images: Record<string, string> = {'403': forbidden, '404': notFound, '500': serverError, building, empty, 'search-empty': searchEmpty, login};
const defaultTextMap: Record<string, string> = {
  empty: t('暂无数据'),
  'search-empty': t('搜索结果为空'),
  '500': t('数据获取异常'),
  '403': t('无业务权限'),
};
const imageSource = computed(() => images[props.emptyType]);
const typeText = computed(() => defaultTextMap[props.emptyType]);
const handleOperation = (operation: EmptyStatusOperation) => emit('operation', operation);
</script>

<style lang="scss">
  .empty-status-container {
    min-width: 0;
    max-width: 100%;
    padding: var(--bklog-space-20) 0;

    .empty-status-body {
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 100%;
      text-align: center;

      .t-empty__image {
        width: 100%;
      }

      .t-empty__title {
        display: none;
      }

      .t-empty__description {
        max-width: 100%;
        margin: 0;
        overflow-wrap: anywhere;
      }

      &.is-part {
        .exception-image {
          width: var(--bklog-exception-image-part-width);
          height: var(--bklog-exception-image-part-height);
        }

        .empty-text-content {
          margin-top: var(--bklog-space-8);
        }

        .empty-text {
          font-size: var(--bklog-font-action);
          line-height: var(--bklog-line-height-action);
        }

        .operation-text,
        .exception-refresh,
        .empty-text + .empty-text {
          font-size: var(--bklog-font-body);
          line-height: var(--bklog-line-height-body);
        }
      }
    }

    .exception-image {
      width: var(--bklog-exception-image-width);
      max-width: 100%;
      height: var(--bklog-exception-image-height);
      object-fit: contain;
      user-select: none;
    }

    .empty-text-content {
      margin-top: var(--bklog-space-16);
    }

    .empty-text {
      margin: 0;
      color: var(--td-text-color-primary);
      font-size: var(--bklog-space-20);
      line-height: calc(var(--bklog-space-24) + var(--bklog-space-4));
    }

    .operation-text,
    .exception-refresh,
    .empty-text + .empty-text {
      color: var(--td-text-color-secondary);
      font-size: var(--bklog-font-action);
      line-height: var(--bklog-line-height-action);
    }

    .empty-text + :is(.operation-text, .exception-refresh, .empty-text) {
      margin-top: var(--bklog-space-8);
    }

    :is(.operation-text, .exception-refresh) {
      display: inline-block;
    }

    .operation-btn {
      max-width: 100%;
      padding: 0;
      white-space: normal;
      overflow-wrap: anywhere;
      color: var(--td-text-color-link);
      background: transparent;
      border: 0;
      font-family: inherit;
      cursor: pointer;

      &:hover {
        color: var(--td-brand-color-hover);
      }

      &:focus-visible {
        outline: var(--bklog-border-width) solid currentColor;
        outline-offset: var(--bklog-space-2);
      }
    }

    .exception-clear {
      margin-inline-start: var(--bklog-space-4);
      font-size: inherit;
      line-height: inherit;
    }
  }
</style>
