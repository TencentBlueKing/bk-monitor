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
  <section class="serious-content">
    <div class="serious-content-tab">
      <div class="tab-wrap">
        <span
          class="tab"
          :class="{ active: tabIndex === 0 }"
          @click="tabIndex = 0"
          ><span class="tab-name"> {{ $t('拨测任务') }} </span><span class="tab-num">{{ taskNum }}</span></span
        >
        <span
          class="tab"
          :class="{ active: tabIndex === 1 }"
          @click="tabIndex = 1"
          ><span class="tab-name"> {{ $t('拨测节点') }} </span><span class="tab-num">{{ nodeNum }}</span></span
        >
      </div>
    </div>
    <div
      v-show="tabIndex === 0"
      class="serious-content-wrap"
    >
      <div
        v-if="alarm.task && alarm.task.abnormal_events.length"
        class="serious-content-wrap-container"
      >
        <div
          v-for="item in alarm.task.abnormal_events"
          :key="item.task_id"
          class="chart-item"
        >
          <business-alarm-card
            :id="item.event_id"
            :title="item.title"
            :level="1"
            :alarm="item"
          />
        </div>
      </div>
      <div
        v-else
        class="no-alarm"
      >
        {{ $t('拨测任务很健康，无告警事件产生!') }}
      </div>
    </div>
    <div
      v-show="tabIndex === 1"
      class="serious-content-wrap"
    >
      <div
        v-if="alarm.node && alarm.node.abnormal_nodes.length"
        class="serious-content-wrap-container"
      >
        <ul class="list">
          <li
            v-for="item in alarm.node.abnormal_nodes"
            :key="item.id"
            class="item"
            @click="nodeAlarmClickHandle"
          >
            <svg-icon
              icon-name="warning"
              class="item-icon item-icon-serious"
            />
            <span>{{ item.isp ? `${item.isp}-` : '' }}{{ item.name }} {{ $t('节点出现异常，请及时排查！') }} </span>
          </li>
        </ul>
      </div>
      <div
        v-else
        class="no-alarm"
      >
        {{ $t('拨测节点很健康，无告警事件产生!') }}
      </div>
    </div>
  </section>
</template>

<script>
import { gotoPageMixin } from '../../../common/mixins';
import SvgIcon from '../../../components/svg-icon/svg-icon';
import BusinessAlarmCard from '../components/business-alarm-card/business-alarm-card';

export default {
  name: 'UptimecheckSerious',
  components: {
    BusinessAlarmCard,
    SvgIcon,
  },
  mixins: [gotoPageMixin],
  inject: ['homeItemBizId'],
  props: {
    alarm: {
      type: Object,
      default() {
        return {};
      },
    },
  },
  data() {
    return {
      tabIndex: 0,
    };
  },
  computed: {
    taskNum() {
      const { alarm } = this;
      if (alarm.task?.abnormal_events) {
        return alarm.task.abnormal_events.length > 99 ? '99+' : alarm.task.abnormal_events.length;
      }
      return 0;
    },
    nodeNum() {
      const { alarm } = this;
      if (alarm.node?.abnormal_nodes.length) {
        return alarm.node.abnormal_nodes.length > 99 ? '99+' : alarm.node.abnormal_nodes.length;
      }
      return 0;
    },
  },
  methods: {
    nodeAlarmClickHandle() {
      const url = `${location.origin}${location.pathname}?bizId=${this.homeItemBizId}#/uptime-check?dashboardId=uptime-check-node`;
      window.open(url);
    },
  },
};
</script>

<style scoped lang="scss">
@import '../common/mixins';

.serious-content {
  &-tab {
    font-size: 0;
    margin-bottom: 10px;

    .tab-wrap {
      margin-right: 40px;
      border-bottom: 1px solid $defaultBorderColor;

      .tab {
        display: inline-block;
        font-size: $fontSmSize;
        color: $defaultFontColor;
        padding-bottom: 7px;
        margin-bottom: -1px;

        &:nth-child(1) {
          margin-right: 20px;
        }

        &:hover {
          cursor: pointer;
        }

        &-name {
          vertical-align: middle;
        }

        &-num {
          display: inline-block;
          min-width: 16px;
          padding: 0 5px;
          height: 16px;
          background: #c4c6cc;
          color: #fff;
          opacity: 1;
          border-radius: 8px;
          text-align: center;
          line-height: 16px;
          margin-left: 6px;
          font-size: 12px;
        }
      }

      .active {
        color: #3a84ff;
        border-bottom: 2px solid #3a84ff;

        .tab-num {
          background: #3a84ff;
        }
      }
    }
  }

  &-wrap {
    text-align: center;

    &-container {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      flex-wrap: wrap;
      min-width: 460px;
      max-height: 260px;
      overflow: auto;

      @media only screen and (min-width: 1414px) {
        .chart-item:nth-child(2n + 1) {
          margin-right: 30px;
        }
      }

      @media only screen and (max-width: 1434px) {
        .chart-item {
          margin-right: 30px;
        }
      }

      .list {
        padding: 0;
        max-height: 280px;
        overflow: auto;

        .item {
          display: flex;
          text-align: center;
          margin: 5px 0;
          font-size: 12px;
          color: $defaultFontColor;

          &:hover {
            cursor: pointer;
            color: #3a84ff;
          }

          &-icon {
            margin-right: 6px;
            width: 16px;
            height: 16px;
          }

          &-icon-serious {
            color: $deadlyAlarmColor;
          }

          &-icon-slight {
            color: $warningAlarmColor;
          }

          &-icon-unset,
          &-icon-default {
            color: $remindAlarmColor;
          }
        }
      }
    }

    .no-alarm {
      margin: 5px 0;
      font-size: 12px;
      color: $defaultFontColor;
      text-align: left;
    }
  }
}
</style>
