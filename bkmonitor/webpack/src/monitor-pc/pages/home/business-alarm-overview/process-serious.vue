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
  <section class="mainframe-serious">
    <div class="mainframe-serious-title">
      <span class="serious-title">{{ $t('共产生{count}个高危告警', { count: alarm.warning_count }) }} </span>
      <a
        v-if="alarm.has_more"
        href="javascript:void(0)"
        class="check-more"
        @click="gotoEventCenter"
      >
        {{ $t('查看更多') }}
      </a>
    </div>
    <ul class="mainframe-serious-list">
      <li
        v-for="item in alarm.abnormal_events"
        :key="item.event_id"
        class="item"
      >
        <svg-icon
          :icon-name="`${item.type === 'serious' ? 'warning' : 'hint'}`"
          :class="`item-icon item-icon-${item.type}`"
        />
        <span @click="gotoDetailHandle(item.event_id)">{{ item.content }}</span>
      </li>
    </ul>
  </section>
</template>

<script>
import { gotoPageMixin } from '../../../common/mixins';
import SvgIcon from '../../../components/svg-icon/svg-icon';

export default {
  name: 'ProcessSerious',
  components: {
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
    homeDays: {
      type: Number,
      default() {
        return 7;
      },
    },
  },
  methods: {
    gotoDetailHandle(id) {
      const query = `?queryString=id : ${id}&from=now-${this.homeDays || 7}d&to=now`;
      const url = `${location.origin}${location.pathname}?bizId=${this.homeItemBizId}#/event-center${query}`;
      window.open(url);
    },
    gotoEventCenter() {
      const query = `activeFilterId=NOT_SHIELDED_ABNORMAL&from=now-${this.homeDays || 7}d&to=now`;
      const url = `${location.origin}${location.pathname}?bizId=${this.homeItemBizId}#/event-center?${query}`;
      location.href = url;
    },
  },
};
</script>

<style scoped lang="scss">
@import '../common/mixins';

.mainframe-serious {
  &-title {
    border-bottom: 1px solid $defaultBorderColor;
    font-size: $fontSmSize;
    min-width: 450px;
    padding-bottom: 8px;
    margin-right: 40px;
    color: $defaultFontColor;
  }

  .check-more {
    float: right;
    font-size: 14px;
    color: #3a84ff;
  }

  .serious-title {
    font-weight: bold;
  }

  .slight-title {
    font-weight: bold;
  }

  &-list {
    padding: 0 20px 0 0;
    max-height: 280px;
    overflow: auto;

    .item {
      margin: 15px 0;
      font-size: 12px;
      color: $defaultFontColor;

      &:hover {
        cursor: pointer;
        color: #3a84ff;
      }

      &-icon {
        margin-right: 6px;
        margin-bottom: 1px;
        width: 16px;
        height: 16px;
      }

      &-icon-serious {
        color: $deadlyAlarmColor;
      }

      &-icon-normal {
        color: $warningAlarmColor;
      }

      &-icon-unset,
      &-icon-default {
        color: $remindAlarmColor;
      }
    }
  }
}
</style>
