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
    :style="{ left: annotation.x + 'px', top: annotation.y + 'px' }"
    class="echart-annotation"
    v-show="annotation.show"
  >
    <div class="echart-annotation-title">{{ annotation.title }}</div>
    <div class="echart-annotation-name">
      <span
        :style="{ backgroundColor: annotation.color }"
        class="name-mark"
      ></span
      >{{ annotation.name }}
    </div>
    <ul class="echart-annotation-list">
      <template v-for="item in annotation.list">
        <li
          v-if="item.show"
          class="list-item"
          :key="item.id"
          @click="handleGotoDetail(item)"
        >
          <span
            class="icon-monitor item-icon"
            :class="`icon-mc-${item.id}`"
          ></span>
          <span>
            {{ toolBarMap[item.id] }}
            <span
              v-if="item.id === 'ip'"
              style="color: #c4c6cc"
            >
              {{ `(${item.value.split('-').reverse().join(':')})` }}
            </span>
          </span>
          <i class="icon-monitor icon-mc-link list-item-link"></i>
        </li>
      </template>
    </ul>
  </div>
</template>

<script lang="ts">
import { Component, Vue, Prop } from 'vue-property-decorator';

import { IAnnotation, IAnnotationListItem } from '../options/type-interface';

@Component({ name: 'ChartAnnotation' })
export default class ChartAnnotation extends Vue {
  @Prop({ required: true }) annotation: IAnnotation;
  get toolBarMap() {
    return {
      ip: this.$t('相关主机详情'),
      process: this.$t('相关进程信息'),
      strategy: this.$t('相关策略'),
    };
  }
  handleGotoDetail(item: IAnnotationListItem) {
    switch (item.id) {
      case 'ip':
        window.open(location.href.replace(location.hash, `#/performance/detail/${item.value}`));
        break;
      case 'process':
        window.open(
          location.href.replace(location.hash, `#/performance/detail-new/${item.value.id}/${item.value.processId}`)
        );
        break;
      case 'strategy':
        window.open(location.href.replace(location.hash, `#/strategy-config?metricId=${item.value}`));
        break;
    }
  }
}
</script>

<style lang="scss" scoped>
  .echart-annotation {
    position: absolute;
    z-index: 99;
    width: 220px;
    min-height: 84px;
    font-size: 12px;
    color: #63656e;
    background: white;
    border-radius: 2px;
    box-shadow: 0px 4px 12px 0px rgba(0, 0, 0, 0.2);

    &-title {
      margin: 6px 0 0 16px;
      line-height: 20px;
    }

    &-name {
      display: flex;
      align-items: center;
      max-width: 90%;
      height: 20px;
      padding-left: 18px;
      margin-top: 2px;
      overflow: hidden;
      font-weight: 700;
      text-overflow: ellipsis;
      white-space: nowrap;
      border-bottom: 1px solid #f0f1f5;

      .name-mark {
        flex: 0 0 12px;
        height: 4px;
        margin-right: 10px;
      }
    }

    &-list {
      display: flex;
      flex-direction: column;

      .list-item {
        display: flex;
        flex: 0 0 30px;
        align-items: center;
        padding-left: 16px;

        .item-icon {
          width: 16px;
          height: 16px;
          margin-right: 10px;
          font-size: 16px;
        }

        &-link {
          margin-right: 6px;
          margin-left: auto;
          font-size: 12px;
        }

        &:hover {
          color: #3a84ff;
          cursor: pointer;
          background-color: #e1ecff;
        }
      }
    }
  }
</style>
