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
  <div class="task-cards">
    <div
      v-if="taskList.length"
      class="task-cards-header"
    >
      <span
        :class="[!taskDetail.show ? 'header-name' : 'header-title']"
        @click="handleBackGroup"
      >
        {{ $t('拨测任务') }}
      </span>
      <span
        v-if="taskDetail.show"
        class="header-detail"
        >>
      </span>
      <span
        v-if="taskDetail.show"
        class="header-name"
        >{{ taskDetail.name }}</span
      >
    </div>
    <div class="task-cards-container">
      <div
        ref="cardList"
        class="card-list"
      >
        <div
          v-for="(item, index) in taskList"
          :ref="'card-' + index"
          :key="index"
          draggable
          :class="['card-list-item', { 'drag-active': drag.active === index, 'is-disabled': isDisabled(item) }]"
          @drag="handleDrag(index, $event)"
          @dragstart="handleDragStart(index, item, $event)"
          @dragend="handleDragEnd(index, $event)"
          @click.stop="handleItemClick(item)"
          @mouseenter="hoverActive = index"
          @mouseleave="handleTaskMouseLeave(item, index)"
        >
          <div class="item-title">
            <div class="item-title-name">
              {{ item.name
              }}<span
                v-if="isDisabled(item)"
                class="stoped-icon"
                >{{ $t('已停用') }}</span
              >
            </div>
            <div class="item-title-url">
              {{ item.url }}
            </div>
            <span
              v-if="hoverActive === index"
              :ref="'popover-' + index"
              v-authority="{ active: !authority.MANAGE_AUTH }"
              class="item-title-icon"
              :class="{ 'hover-active': popover.hover }"
              @click.stop="authority.MANAGE_AUTH ? handlePopoverShow(item, index, $event) : handleShowAuthorityDetail()"
              @mouseleave="handleTaskPopoverLeave"
              @mouseover="popover.hover = true"
            >
              <i class="bk-icon icon-more" />
            </span>
          </div>
          <div class="item-content">
            <div class="label-item">
              <div
                v-if="isDisabled(item)"
                class="disabled-label-item-name"
              >
                --
              </div>
              <div
                v-else
                class="label-item-name"
              >
                <span
                  class="label-num"
                  :style="{ color: filterAvailableAlarm(item.available, item.available_alarm) }"
                >
                  {{ item.available !== null ? item.available : '--' }} </span
                ><span style="color: #63656e">{{ item.available !== null ? '%' : '' }}</span>
              </div>
              <div class="label-item-title">
                {{ $t('可用率') }}
              </div>
            </div>
            <div class="label-item">
              <div
                v-if="isDisabled(item)"
                class="disabled-label-item-name"
              >
                --
              </div>
              <div
                v-else
                class="label-item-name"
              >
                <template v-if="item.task_duration !== null">
                  <span
                    class="label-num"
                    :style="{ color: filterTaskDurationAlarm(item.task_duration, item.task_duration_alarm) }"
                  >
                    {{ item.task_duration }} </span
                  ><span style="color: #63656e">{{ item.task_duration !== null ? 'ms' : '' }}</span>
                </template>
                <template v-else>
                  <span
                    class="label-num icon-monitor icon-remind"
                    style="color: #ea3636"
                  />
                </template>
              </div>
              <div class="label-item-title">
                {{ $t('平均响应时长') }}
              </div>
            </div>
          </div>
          <div
            v-if="drag.active === index"
            class="drag-active-item"
          />
        </div>
      </div>
      <div
        v-show="scroll.show"
        class="card-loading"
      >
        <span class="icon-monitor icon-loading" /> {{ $t('加载更多...') }}
      </div>
      <div v-show="false">
        <div
          ref="popoverContent"
          class="popover-desc"
        >
          <div
            class="popover-desc-btn"
            @click.stop="handleEditTask"
          >
            {{ $t('button-编辑') }}
          </div>
          <div
            class="popover-desc-btn"
            @click.stop="handleDeleteTask"
          >
            {{ $t('删除') }}
          </div>
          <div
            class="popover-desc-btn"
            @click.stop="handleCloneTask"
          >
            {{ $t('克隆') }}
          </div>
          <div
            class="popover-desc-btn"
            @click.stop="handleChangeStatus"
          >
            {{ taskList[hoverActive] && $t(taskList[hoverActive].switch ? '停用' : '启用') }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import { createNamespacedHelpers } from 'vuex';

import { uptimeCheckMixin } from '../../../../common/mixins';

const { mapGetters } = createNamespacedHelpers('uptime-check-task');
export default {
  name: 'TaskCards',
  mixins: [uptimeCheckMixin],
  inject: ['authority', 'handleShowAuthorityDetail'],
  props: {
    tasks: {
      type: Array,
      default() {
        return [];
      },
    },
    taskDetail: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      task: {
        list: [],
      },
      scroll: {
        show: false,
      },
      drag: {
        active: -1,
      },
      popover: {
        hover: false,
        instance: null,
        active: -1,
      },
      hoverActive: -1,
    };
  },
  computed: {
    ...mapGetters({ taskList: 'groupTaskList' }),
    hasTaskList() {
      return !!this.taskList.length;
    },
  },
  watch: {
    'taskList.length': {
      handler() {
        this.$nextTick().then(() => {
          this.handleWindowResize();
        });
      },
    },
  },
  beforeDestroy() {
    this.handlePopoverHide();
  },
  methods: {
    refreshItemWidth() {
      this.handleWindowResize();
    },
    handleWindowResize() {
      const len = this.taskList.length;
      const width = this.$refs['card-0']?.length ? this.$refs['card-0'][0].getBoundingClientRect().width : 400;
      if (len > 0) {
        let i = 0;
        while (i < len) {
          const ref = this.$refs[`card-${i}`][0];
          if (ref && ref.getBoundingClientRect().width !== width) {
            ref.style.maxWidth = `${width}px`;
          }
          i += 1;
        }
      }
    },
    handleWindowScroll() {
      const scrollHeight = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop;
      const clientHeight =
        window.innerHeight || Math.min(document.documentElement.clientHeight, document.body.clientHeight);
      if (clientHeight + scrollTop >= scrollHeight && !this.scroll.show) {
        this.scroll.show = true;
        setTimeout(() => {
          this.scroll.show = false;
          for (let i = 0; i < 50; i++) {
            this.taskList.push({ name: `${this.$t('新增')}-0${i}` });
          }
          this.$nextTick().then(() => {
            this.handleWindowResize();
          });
        }, 2000);
      }
    },
    getItemWidth() {
      return this.taskList.length ? this.$refs['card-0'][0].getBoundingClientRect().width : 0;
    },
    handleExpand() {
      this.expand = !this.expand;
    },
    handleBackGroup() {
      if (this.taskDetail.show) {
        this.$emit('update:taskDetail', {
          show: false,
          name: '',
          tasks: [],
          id: -1,
        });
      }
    },
    handleTaskMouseLeave() {
      this.hoverActive = -1;
      this.popover.hover = false;
    },
    handleTaskPopoverLeave() {
      this.popover.hover = this.popover.active >= 0;
      !this.popover.hover && this.handlePopoverHide();
    },
    handlePopoverShow(item, index, e) {
      this.popover.instance = this.$bkPopover(e.target, {
        content: this.$refs.popoverContent,
        arrow: false,
        trigger: 'click',
        placement: 'bottom',
        theme: 'light task-card',
        maxWidth: 520,
        duration: [200, 0],
        appendTo: () => this.$refs[`popover-${index}`][0],
        onHidden: () => {
          this.popover.hover = false;
        },
      });
      // .instances[0]
      this.popover.active = index;
      this.popover.instance?.show(100);
    },
    handlePopoverHide() {
      this.popover.instance?.hide(100);
      this.popover.instance?.destroy();
      this.popover.instance = null;
    },
    handleEditTask() {
      this.$emit('edit', this.taskList[this.hoverActive]);
    },
    handleDeleteTask() {
      this.$emit('delete-task', this.taskList[this.hoverActive]);
    },
    handleCloneTask() {
      this.$emit('clone-task', this.taskList[this.hoverActive]);
    },
    // 切换任务的启停状态
    handleChangeStatus() {
      const taskItem = this.taskList[this.hoverActive];
      this.$emit('change-status', taskItem);
    },
    handleItemClick(item) {
      this.$emit('detail-show', item);
    },
    handleDragStart(i, item, e) {
      const event = e;
      event.dataTransfer.setData('text/plain', item.id);
      event.dropEffect = 'move';
      this.handlePopoverHide();
      this.drag.active = i;
    },
    handleDragEnd(i, e) {
      e.preventDefault();
      this.drag.active = -1;
    },
    handleDeleteItem(i) {
      this.taskList.splice(i, 1);
    },
    handleDrag(i, e) {
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop;
      if (e.y < 180) {
        window.scrollTo(e.x, scrollTop - 9);
      }
    },
    // 任务停用状态
    isDisabled(item) {
      return !item?.switch;
    },
  },
};
</script>
<style lang="scss" scoped>
.task-cards {
  &-header {
    display: flex;
    align-items: center;
    font-size: 14px;
    margin-bottom: 14px;
    color: #979ba5;
    font-weight: bold;

    .header-title {
      cursor: pointer;
    }

    .header-name {
      color: #313238;
      cursor: default;
    }

    .header-detail {
      padding: 0 5px;
      font-weight: normal;
      cursor: default;
    }
  }

  &-container {
    @keyframes done-loading {
      0% {
        transform: rotate(0deg);
      }

      100% {
        transform: rotate(-360deg);
      }
    }

    .card-list {
      display: flex;
      margin-right: -20px;
      flex-wrap: wrap;
      position: relative;

      &-item {
        flex: 1;
        min-width: 300px;
        max-width: 400px;
        height: 194px;
        background: #fff;
        border-radius: 2px;
        border: 1px solid #dcdee5;
        margin-right: 20px;
        margin-bottom: 20px;
        position: relative;
        cursor: pointer;

        &:hover {
          box-shadow: 0px 3px 6px 0px rgba(0, 0, 0, 0.1);
        }

        &.is-disabled {
          .item-title-name,
          .item-title-url {
            color: #979ba5;
          }

          .item-title-name {
            .stoped-icon {
              display: inline-block;
              height: 22px;
              line-height: 22px;
              padding: 0 10px;
              margin-left: 8px;
              color: #63656e;
              font-weight: initial;
              font-size: 12px;
              background-color: #f0f1f5;
            }
          }
        }

        .item-title {
          display: flex;
          flex-direction: column;
          height: 60px;
          padding: 10px 24px 0;
          border-bottom: 1px solid #dcdee5;

          /* stylelint-disable-next-line no-descending-specificity */
          &-name {
            color: #313238;
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 2px;
            max-width: 350px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            line-height: 20px;
          }

          /* stylelint-disable-next-line no-descending-specificity */
          &-url {
            color: #979ba5;
            font-size: 12px;
            padding-right: 5px;
            text-align: left;
            direction: rtl;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            unicode-bidi: plaintext;
            margin-right: 30px;
            line-height: 16px;
          }

          &-icon {
            position: absolute;
            right: 14px;
            top: 14px;
            color: #63656e;
            font-size: 18px;
            width: 32px;
            height: 32px;
            display: flex;
            justify-content: center;
            align-items: center;
            border-radius: 50%;
            cursor: pointer;
            transition: background-color 0.2s ease-in-out;

            &.hover-active {
              background-color: #f0f1f5;
              border-radius: 50%;
              color: #3a84ff;
            }
          }
        }

        .item-content {
          flex: 1;
          height: 134px;
          display: flex;
          justify-content: center;
          padding-top: 29px;

          .label-item {
            font-size: 12px;
            color: #979ba5;

            &-name {
              text-align: center;

              .label-num {
                font-size: 36px;
                color: #313238;
                display: inline-flex;
                justify-content: flex-end;
                align-items: center;
                height: 50px;
              }
            }

            &-title {
              text-align: center;
            }

            &:first-child {
              margin-right: 60px;
            }

            .disabled-label-item-name {
              display: flex;
              align-items: center;
              justify-content: center;
              height: 50px;
              font-size: 30px;
              color: #979ba5;
            }
          }
        }
      }

      .drag-active {
        border: 1px dashed #c4c6cc;

        &-item {
          position: absolute;
          left: 0;
          right: 0;
          top: 0;
          bottom: 0;
          background: #fafbfd;
          opacity: 0.6;
        }
      }
    }

    .card-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;

      .icon-loading {
        font-size: 14px;
        color: #c4c6cc;
        margin-right: 5px;
        animation: done-loading 1s linear 0s infinite;
      }
    }

    .popover-desc {
      display: flex;
      flex-direction: column;
      color: #63656e;
      font-size: 12px;
      border-radius: 2px;
      border: 1px solid #dcdee5;
      min-width: 68px;
      padding: 6px 0;
      background: #fff;

      &-btn {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        padding-left: 10px;
        height: 32px;
        background: #fff;
        // &:first-child {
        //     border-bottom: 1px solid #DCDEE5;
        // }
        &:hover {
          background: #f0f1f5;
          color: #3a84ff;
          cursor: pointer;
        }
      }
    }
  }
}
</style>
