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
  <div class="event-item">
    <div
      :class="['event-item-title', { 'event-item-show': showTarget }]"
      @click="handleShowTarget"
    >
      <span :class="['text', 'color-' + itemData.level]">
        <span class="ellipsis">{{ itemData.target ? itemData.target : itemData.name }}</span>
        <i :class="['icon-monitor', 'icon-arrow-down', { 'icon-show': showTarget }]"></i>
      </span>
    </div>
    <transition name="count-fade">
      <div
        v-show="showCount"
        :class="['event-item-count']"
      >
        {{ $t('异常事件: ', { num: itemData.events.length }) }}
      </div>
    </transition>
    <ul
      ref="event-list"
      :class="['event-item-target']"
      :data-show="showTarget"
    >
      <li
        v-for="(item, index) in itemData.events"
        class="target-item"
        :key="item.eventId + '-' + index"
        @click="goToDetail(item)"
      >
        <template v-if="!itemData.target">
          <div class="text-row">
            <span class="row-label">{{ $t('目标2') }}</span
            ><span class="ellipsis">{{ item.target }}</span>
          </div>
          <div class="text-row">
            <span class="row-label">{{ $t('时长2') }}</span
            ><span class="ellipsis">{{ item.duration }}</span>
          </div>
        </template>
        <template v-else>
          <div class="msg-item">
            <span :class="['level-text', 'level-color-' + item.level]">
              {{ '[' + tipsMsgMap[item.level - 1] + ']' }}
            </span>
            <span class="msg ellipsis">
              {{ item.strategyName }}
            </span>
          </div>
        </template>
      </li>
    </ul>
  </div>
</template>
<script lang="ts">
import { Vue, Component, Prop, Ref } from 'vue-property-decorator';

import type { IListItem } from './event-center.vue';

@Component({
  name: 'event-item',
})
export default class EventListItem extends Vue {
  // 类型配置
  @Prop({ default: () => null, required: true }) readonly itemData: IListItem;

  @Ref('event-list') readonly eventList: HTMLUListElement;

  // 显示目标信息
  showTarget = false;
  // 显示异常事件个数
  showCount = true;

  get tipsMsgMap(): string[] {
    return [String(this.$tc('致命')), String(this.$tc('预警')), String(this.$tc('提醒'))];
  }

  // 展开目标
  handleShowTarget() {
    if (this.itemData.events.length) {
      if (this.eventList.style.maxHeight) {
        this.eventList.style.maxHeight = null;
      } else {
        this.eventList.style.maxHeight = `${this.eventList.scrollHeight}px`;
        this.eventList.addEventListener('webkitTransitionEnd', this.targetAfterLeave);
      }
      this.showTarget = !this.showTarget;
      this.showCount && (this.showCount = false);
    }
  }

  // 进入详情
  goToDetail({ eventId }) {
    this.$router.push({
      name: 'alarm-detail',
      params: {
        id: eventId,
      },
    });
  }

  targetAfterLeave(e) {
    const { show } = e.target.dataset;
    !show && (this.showCount = true);
  }
}
</script>
<style lang="scss" scoped>
@import '../../static/scss/variate.scss';
@import '../../static/scss/mixin.scss';

.event-item {
  min-height: 66px;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0px 1px 0px 0px rgba(99, 101, 110, 0.05);

  &:not(:last-child) {
    margin-bottom: 10px;
  }

  .ellipsis {
    @include ellipsis;
  }

  &-title {
    padding: 11px 16px 4px 16px;
    border-bottom: 1px solid #fff;
    transition: all 0.3s ease-in-out;

    .text {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 16px;
      line-height: 22px;

      &::before {
        position: absolute;
        top: 50%;
        left: -16px;
        width: 4px;
        height: 16px;
        content: '';
        transform: translate(0, -50%);
      }

      .icon-arrow-down {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        overflow: hidden;
        font-size: 28px;
        color: #dcdee5;
        transition: transform 0.3s ease-in-out;
        transform: rotate(0);
        transform-origin: 50% 50%;
      }

      .icon-show {
        transform: rotate(-180deg);
      }
    }

    .color-1 {
      &::before {
        background-color: $deadlyColor;
      }
    }

    .color-2 {
      &::before {
        background-color: #ff9c01;
      }
    }

    .color-3 {
      &::before {
        background-color: #ffd000;
      }
    }
  }

  &-show {
    padding-bottom: 11px;
    border-bottom: 1px solid #eaebef;
  }

  &-count {
    padding: 0px 16px 0 16px;
    overflow: hidden;
    font-size: 14px;
    color: #979ba5;
  }
  // count-fade
  .count-fade-enter {
    opacity: 0;
  }

  .count-fade-leave-to {
    height: 0;
  }

  .count-fade-leave {
    height: 20px;
  }

  .count-fade-enter-to {
    opacity: 1;
  }

  .count-fade-enter-active,
  .count-fade-leave-active {
    transition: all 0.2s ease-in-out;
  }

  &-target {
    max-height: 0;
    padding: 0 16px;
    overflow: hidden;
    transition: max-height 0.5s ease-in-out;
    will-change: max-height;

    .target-item {
      padding: 16px 0 17px 0;
      font-size: 14px;
      color: $defaultFontColor;

      &:not(:last-child) {
        margin-bottom: 2px;
        border-bottom: 1px solid #eaebef;
      }

      .text-row {
        display: flex;
        align-items: center;
        line-height: 20px;

        .row-label {
          display: inline-block;
          flex-shrink: 0;
          width: 42px;
        }
      }

      .text-row:not(:last-child) {
        margin-bottom: 2px;
      }

      .msg-item {
        display: flex;
        align-items: center;
        font-size: 14px;
        font-weight: 400;
        line-height: 20px;

        .level-text {
          flex-shrink: 0;
          margin-right: 4px;
        }

        .msg {
          color: #63656e;
        }

        .level-color-1 {
          color: #ea3636;
        }

        .level-color-2 {
          color: #ffd000;
        }

        .level-color-3 {
          color: #ff9c01;
        }
      }
    }
  }
}
</style>
