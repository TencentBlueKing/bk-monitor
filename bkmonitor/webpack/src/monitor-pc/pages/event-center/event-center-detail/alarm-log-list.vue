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
  <ul class="log-list">
    <li
      class="log-list-item"
      v-for="(item, index) in list"
      :key="item.logId"
      v-show="item.show"
    >
      <div class="item-title">
        <span
          class="item-title-set icon-monitor"
          :class="[item.expand ? 'icon-mc-minus-plus' : 'icon-mc-plus-fill']"
          @click="beforeCollapseChange(item, index)"
          v-if="item.collapse"
        />
        <span class="item-title-icon"><i
          class="icon-monitor"
          :class="item.logIcon"
        /></span>
        <span class="item-title-date">{{ item.expand ? item.time : item.expandTime }}</span>
      </div>
      <div class="item-content">
        <div class="item-content-desc">
          {{ operateMap[item.operate] }}
          <span v-if="item.contents.length === 1">
            <span
              v-bk-tooltips.top="{
                content: item.sourceTime ? `${$t('数据时间:')}${item.sourceTime}` : ``,
                disabled: !item.sourceTime
              }"
              :class="{ 'tip-dashed': item.operate === 'CREATE' || item.operate === 'CONVERGE' }"
            >
              {{
                item.count > 1 ? `${$t('当前事件流水过多，收敛{count}条。',{ count: item.count })}` : item.contents[0] || '--'
              }}
            </span>
            <span
              v-if="item.operate === 'ANOMALY_NOTICE' && item.shieldType === 'saas_config'"
              class="can-click"
              @click="handleGotoShieldStrategy(item.shieldSnapshotId)"
            >
              {{ $t('查看屏蔽策略') }}
            </span>
          </span>
          <template v-else-if="item.operate === 'ANOMALY_NOTICE'">
            {{ item.contents[0] }}
            <span
              class="notice-group"
              v-for="text in item.contents[1]"
              :key="text"
            >{{ text }}</span>
            {{ item.contents[2] }}
            <span class="notice-status">{{ alertStatusMap[item.contents[3]] }}</span>
            {{ item.contents.length > 4 ? item.contents[4] : '' }}
            <span
              class="can-click"
              @click="handleNoticeDetail(item.actionId)"
            > {{ $t('点击查看明细') }} </span>
          </template>
          <template v-else-if="item.operate === 'ACK'">
            {{ item.contents[0] }}<span class="alarm-ack">{{ item.contents[1] }}</span>
          </template>
          <template v-else-if="item.contents.length > 1 && (item.operate === 'CREATE' || item.operate === 'CONVERGE')">
            <span
              v-for="(content, i) in item.contents"
              :key="i"
              v-bk-tooltips.top="
                i === item.index && item.sourceTime && (item.operate === 'CREATE' || item.operate === 'CONVERGE')
                  ? `${$t('数据时间:')}${item.sourceTime}`
                  : ''
              "
              :class="{
                'tip-dashed':
                  i === item.index && item.sourceTime && (item.operate === 'CREATE' || item.operate === 'CONVERGE')
              }"
            >
              {{ content || '--' }}
            </span>
          </template>
        </div>
        <div
          class="item-border"
          :style="{ borderColor: item.border ? '#979BA5' : '#DCDEE5' }"
        />
      </div>
    </li>
    <li
      class="log-list-loading"
      v-show="loading"
    >
      <img
        alt=''
        class="loading-img"
        src="../../../static/images/svg/spinner.svg"
      > {{ $t('正加载更多内容…') }}
    </li>
  </ul>
</template>
<script>
import { addListener, removeListener } from '@blueking/fork-resize-detector';

export default {
  name: 'AlarmLogList',
  props: {
    list: {
      type: Array,
      required: true
    },
    loading: Boolean,
    defaultClickCollapseIndex: {
      type: Number,
      deafult() {
        return -1;
      }
    }
  },
  data() {
    return {
      operateMap: {
        ACK: this.$t('# 告警确认 # '),
        ANOMALY_NOTICE: this.$t('# 告警通知 # '),
        CREATE: this.$t('# 告警触发 # '),
        CONVERGE: this.$t('# 告警收敛 # '),
        RECOVER: this.$t('# 告警恢复 # '),
        CLOSE: this.$t('# 告警关闭 # ')
      },
      alertStatusMap: {
        SUCCESS: this.$t('成功'),
        FAILED: this.$t('失败'),
        SHIELDED: this.$t('已屏蔽'),
        PARTIAL_SUCCESS: this.$t('部分失败')
      },
      disabledClick: false
    };
  },
  watch: {
    defaultClickCollapseIndex: {
      handler(index) {
        if (index !== -1 && this.list[index]) {
          this.disabledClick = false;
          this.handleCollapseChange(this.list[index], index);
        }
      }
    }
  },
  mounted() {
    addListener(this.$el, this.listenLogListResize);
    this.$emit('log-resize');
  },
  beforeDestroy() {
    removeListener(this.$el, this.listenLogListResize);
  },
  methods: {
    beforeCollapseChange(item, index) {
      if (!this.disabledClick && item.operate === 'CONVERGE' && item.isMultiple && !item.next) {
        this.$emit('change-list', item, index);
        this.disabledClick = true;
      } else {
        this.handleCollapseChange(item, index);
      }
    },
    async handleCollapseChange(item, index) {
      item.expand = !item.expand;
      const preItem = this.list[index - 1];
      const nextItem = this.list[item.next];
      if (preItem) {
        const preNextItem = this.list.slice(0, index).find(set => set.next === index - 1);
        if (preNextItem) {
          preItem.border = !!preNextItem.expand;
          preNextItem.border = !preNextItem.expand && item.expand;
        } else {
          preItem.border = item.expand;
        }
      }
      if (nextItem) {
        // const hasNextPre = index > 2 && this.list[item.next + 1].collapse && this.list[item.next + 1].expand
        const nextPreItem = this.list[item.next + 1];
        if (nextPreItem?.collapse) {
          nextItem.border = nextPreItem.expand || item.expand;
        } else {
          nextItem.border = item.expand;
        }
      }
      for (let i = index + 1; i <= item.next; i++) {
        this.list[i].show = item.expand;
      }
      item.border = nextItem?.border && !nextItem.show;
    },
    listenLogListResize() {
      this.$emit('log-resize');
    },
    handleNoticeDetail(actionId = -1) {
      this.$emit('notice-detail', true, actionId);
    },
    handleGotoShieldStrategy(shieldId) {
      this.$emit('goto-strategy', shieldId);
    }
  }
};
</script>
<style lang="scss" scoped>
.log-list {
  display: flex;
  flex-direction: column;
  padding: 20px 20px 10px 55px;
  font-size: 12px;
  color: #63656e;
  background-color: #fff;

  &-item {
    position: relative;
    display: flex;
    flex-direction: column;
    min-height: 70px;
    margin-bottom: 2px;

    .item-title {
      display: flex;
      flex: 0 0 30px;
      align-items: center;
      margin-left: -14px;

      &-set {
        position: absolute;
        left: -36px;
        font-size: 16px;
        color: #98999f;

        &:hover {
          color: #707279;
          cursor: pointer;
        }
      }

      &-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        margin-right: 10px;
        font-size: 16px;
        color: #fff;
        background-color: #c4c6cc;
        border-radius: 50%;
      }
    }

    .item-content {
      position: relative;
      flex: 1 0 40px;
      padding-left: 24px;
      margin-top: 2px;
      border-left: 2px solid #dcdee5;

      &-desc {
        margin-bottom: 16px;

        .tip-dashed {
          padding-bottom: 2px;
          cursor: pointer;
          border-color: #c4c6cc;
          border-bottom: 1px dashed;
        }

        .notice-group {
          display: inline-block;
          height: 20px;
          padding-right: 9px;
          padding-left: 9px;
          margin-left: 4px;
          line-height: 20px;
          color: #313238;
          text-align: center;
          background-color: #f1f1f1;
          border-radius: 2px;
        }

        .notice-status {
          display: inline-block;
          margin-left: 4px;
          color: #878787;
        }

        .alarm-ack {
          display: inline-block;
          margin-left: 2px;
          color: #313238;
        }

        .can-click {
          margin-left: 4px;
          color: #3a84ff;
          cursor: pointer;
        }
      }

      .item-border {
        position: absolute;
        right: 20px;
        bottom: 7px;
        left: 24px;
        height: 0;
        border: 1px dashed #dcdee5;
      }
    }
  }

  &-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 160px;
    height: 32px;
    margin: auto;
    margin-top: 16px;
    color: #979ba5;
    background-color: #ebedf0;
    border-radius: 2px;

    .loading-img {
      width: 16px;
      margin-right: 5px;
    }
  }
}
</style>
