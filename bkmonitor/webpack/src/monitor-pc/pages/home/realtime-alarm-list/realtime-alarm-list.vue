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
  <panel-card
    class="real-time-alarm"
    :title="$t('实时告警事件')"
  >
    <a
      slot="title"
      class="title-setting"
      :class="{ 'title-disable': !list.length }"
      href="javascript:void(0)"
      @click="gotoPageHandle"
    >
      {{ $t('查看更多') }}
    </a>
    <div class="list">
      <ul>
        <li
          v-for="item in list"
          :key="item.id"
          class="item"
          @click="item.id && gotoDetailHandle(item.id)"
        >
          <span :class="`icon-${item.level}`">{{ item.level === 1 ? 'C' : item.level === 2 ? 'N' : 'S' }}</span>
          <div
            class="content"
            :title="item.title"
          >
            <div class="content-content">{{ item.targetKey }} {{ item.title }}</div>
            <svg-icon
              v-if="item.isRecovered"
              icon-name="check"
              class="checked-icon"
            />
          </div>
          <span class="end">{{ getTimeFromNow(item.beginTime) || '--' }}</span>
        </li>
      </ul>
    </div>
  </panel-card>
</template>

<script>
import dayjs from 'dayjs';

import { gotoPageMixin } from '../../../common/mixins';
import SvgIcon from '../../../components/svg-icon/svg-icon';
import PanelCard from '../components/panel-card/panel-card';

export default {
  name: 'RealTimeAlarmList',
  components: {
    PanelCard,
    SvgIcon,
  },
  mixins: [gotoPageMixin],
  props: {
    list: {
      type: Array,
      required: true,
    },
  },
  methods: {
    getTimeFromNow(t) {
      return dayjs(dayjs(t * 1000).format('YYYYMMDDHHmmss'), 'YYYYMMDDHHmmss').fromNow();
    },
    gotoPageHandle() {
      this.$router.push({
        name: 'event-center',
        query: {
          activeFilterId: 'NOT_SHIELDED_ABNORMAL',
          from: 'now-7d',
          to: 'now',
        },
      });
    },
    gotoDetailHandle(id) {
      this.$router.push({
        name: 'event-center-detail',
        params: {
          id,
        },
      });
    },
  },
};
</script>

<style scoped lang="scss">
@import '../common/mixins';

.real-time-alarm {
  .title-setting {
    float: right;
    height: 19px;
    font-size: $fontSmSize;
    line-height: 19px;
    color: #3a84ff;
  }

  .title-disable {
    color: #979ba5;
    cursor: not-allowed;
  }

  .list {
    ul {
      padding: 0;

      .item {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        padding: 15px 0;
        list-style: none;
        border-bottom: 1px solid #f0f1f5;

        &:hover {
          cursor: pointer;
          background: #fafbfd;
        }

        .icon,
        %icon {
          flex: 0 0 24px;
          width: 24px;
          height: 24px;
          font-weight: 900;
          line-height: 24px;
          text-align: center;
          border-radius: 100%;
        }

        .icon-1 {
          color: $deadlyAlarmColor;
          background: #fdd;

          @extend %icon;
        }

        .icon-3 {
          color: $warningAlarmColor;
          background: #ffe8c3;

          @extend %icon;
        }

        .icon-2 {
          color: $remindAlarmColor;
          background: #fff9de;

          @extend %icon;
        }

        .content {
          flex: 1;
          height: 19px;
          margin: 0 10px;
          overflow: hidden;
          font-size: $fontSmSize;
          line-height: 19px;
          color: $defaultFontColor;

          &-content {
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;

            &:hover {
              color: $normalFontColor;
            }
          }

          .checked-icon {
            font-size: 18px;
            color: #85cfb7;
          }
        }

        .end {
          min-width: 50px;
          height: 19px;
          font-size: $fontSmSize;
          line-height: 19px;
          color: #979ba5;
        }

        &:last-child {
          padding-bottom: 10px;
          border-bottom: 0;
        }
      }
    }
  }
}
</style>
