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
  <div class="alarm-shield-event">
    <div
      v-if="bizList.length"
      class="event-item"
    >
      <div class="event-item-label">
        {{ $t('所属') }}
      </div>
      <div class="event-item-content">
        <bk-select
          v-model="bizId"
          style="width: 413px"
          readonly
        >
          <bk-option
            v-for="(option, index) in bizList"
            :id="option.id"
            :key="index"
            :name="option.text"
          />
        </bk-select>
      </div>
    </div>
    <div
      v-if="shieldData.dimension_config"
      class="event-detail"
    >
      <div class="event-detail-label">
        {{ $t('告警内容') }}
      </div>
      <div class="event-detail-content">
        <!-- <div class="column-item">
                    <div class="item-label"> {{ $t('告警级别：') }} </div><div class="item-content">{{shieldData.dimension_config.level}}</div>
                </div> -->
        <div class="column-item">
          <div class="item-label">{{ $t('维度信息') }} :</div>
          <div class="item-content">
            {{ shieldData.dimension_config.dimensions }}
          </div>
        </div>
        <div
          class="column-item"
          style="margin-bottom: 18px"
        >
          <div class="item-label">{{ $t('检测算法') }} :</div>
          <div class="item-content">
            {{ shieldData.dimension_config.event_message }}
          </div>
        </div>
      </div>
    </div>
    <shield-date-config ref="noticeDate" />
    <div class="event-desc">
      <div class="event-desc-label">
        {{ $t('屏蔽原因') }}
      </div>
      <div class="event-desc-content">
        <bk-input
          v-model="desc"
          class="content-desc"
          type="textarea"
          :maxlength="100"
        />
      </div>
    </div>
    <alarm-shield-notice
      ref="notice"
      @change-show="handleChangeShow"
    />
    <div class="event-btn">
      <bk-button
        class="button"
        :theme="'primary'"
        @click="handleSubmit"
      >
        {{ $t('提交') }}
      </bk-button>
      <bk-button
        class="button"
        :theme="'default'"
        @click="$router.push({ name: 'alarm-shield' })"
      >
        {{ $t('取消') }}
      </bk-button>
    </div>
  </div>
</template>

<script>
import { editShield } from 'monitor-api/modules/shield';

import { alarmShieldMixin } from '../../../common/mixins';
import ShieldDateConfig from '../alarm-shield-components/alarm-shield-date';
import AlarmShieldNotice from '../alarm-shield-components/alarm-shield-notice';

export default {
  name: 'AlarmShieldEvent',
  components: {
    ShieldDateConfig,
    AlarmShieldNotice,
  },
  mixins: [alarmShieldMixin],
  props: {
    shieldData: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      bizId: null,
      bizList: [],
      eventList: [],
      eventId: 0,
      eventInfo: {},
      isShowDetail: false,
      noticeShow: false,
      desc: '',
    };
  },
  watch: {
    shieldData: {
      handler() {
        this.handleSetEventData();
      },
    },
  },
  methods: {
    handleSetEventData() {
      const data = this.shieldData;
      this.bizList = this.$store.getters.bizList;
      this.bizId = data.bk_biz_id;
      const cycleConfig = data.cycle_config;
      const cycleMap = { 1: 'single', 2: 'day', 3: 'week', 4: 'month' }; // 1 单次 2 每天 3 每周 4 每月
      const type = cycleMap[cycleConfig.type];
      const isSingle = cycleConfig.type === 1;
      const shieldDate = {};
      this.noticeShow = data.shield_notice;
      if (data.shield_notice) {
        const shieldNoticeData = {
          notificationMethod: data.notice_config.notice_way,
          noticeNumber: data.notice_config.notice_time,
          member: {
            value: data.notice_config.notice_receiver.map(item => item.id),
          },
        };
        this.$refs.notice.setNoticeData(shieldNoticeData);
      }
      shieldDate.typeEn = type;
      shieldDate[type] = {
        list: [...cycleConfig.day_list, ...cycleConfig.week_list],
        range: isSingle ? [data.begin_time, data.end_time] : [cycleConfig.begin_time, cycleConfig.end_time],
      };
      shieldDate.dateRange = isSingle ? [] : [data.begin_time, data.end_time];
      this.$refs.noticeDate.setDate(shieldDate);
      this.desc = data.description;
    },
    handleSubmit() {
      const date = this.$refs.noticeDate.getDateData();
      const notice = this.$refs.notice.getNoticeConfig();
      if (!date || !notice) {
        return;
      }
      const cycle = this.getDateConfig(date);
      const params = {
        bk_biz_id: this.shieldData.bk_biz_id,
        id: this.shieldData.id,
        category: 'event',
        dimension_config: {
          id: this.eventId,
        },
        description: this.desc,
        shield_notice: this.noticeShow,
        cycle_config: cycle.cycle_config,
        begin_time: cycle.begin_time,
        end_time: cycle.end_time,
      };
      if (this.noticeShow) {
        params.notice_config = notice;
      }
      this.$emit('update:loading', true);
      editShield(params)
        .then(() => {
          this.$bkMessage({ theme: 'success', message: this.$t('修改成功') });
          this.$router.push({ name: 'alarm-shield', params: { refresh: true } });
        })
        .finally(() => {
          this.$emit('update:loading', false);
        });
    },
    handleChangeShow(v) {
      this.noticeShow = v;
    },
  },
};
</script>

<style lang="scss" scoped>
.alarm-shield-event {
  min-height: calc(100vh - 145px);
  padding: 40px 0 36px 30px;
  font-size: 14px;
  color: #63656e;

  .event-item {
    display: flex;
    align-items: center;
    height: 32px;
    margin-bottom: 20px;

    &-label {
      position: relative;
      min-width: 56px;
      margin-right: 24px;
      text-align: right;

      &::before {
        position: absolute;
        top: 2px;
        right: -9px;
        color: #ea3636;
        content: '*';
      }
    }

    &-content {
      flex-grow: 1;

      .checkbox-group {
        margin-right: 32px;
      }
    }
  }

  .event-detail {
    display: flex;
    align-items: flex-start;
    margin-bottom: 20px;

    &-label {
      position: relative;
      min-width: 56px;
      padding-top: 6px;
      margin-right: 24px;
      text-align: right;

      &::before {
        position: absolute;
        top: 8px;
        right: -9px;
        color: #ea3636;
        content: '*';
      }
    }

    &-content {
      display: flex;
      flex-direction: column;
      width: calc(100vw - 306px);
      min-width: 836px;
      padding: 18px 21px 0 21px;
      background: #fafbfd;
      border: 1px solid #dcdee5;
      border-radius: 2px;

      .column-item {
        display: flex;
        align-items: flex-start;
        margin-bottom: 20px;
      }

      .item-label {
        min-width: 70px;
        margin-right: 6px;
      }

      .item-content {
        word-break: break-all;
        word-wrap: break-word;
      }
    }
  }

  .event-desc {
    display: flex;
    align-items: flex-start;
    height: 78px;
    margin-bottom: 26px;

    &-label {
      min-width: 56px;
      padding-top: 6px;
      margin-right: 24px;
      text-align: right;
    }

    &-content {
      .content-desc {
        width: 836px;
      }

      :deep(.bk-textarea-wrapper .bk-form-textarea.textarea-maxlength) {
        margin-bottom: 0px;
      }

      :deep(.bk-form-textarea) {
        min-height: 60px;
      }
    }
  }

  .event-btn {
    margin-left: 80px;

    .button {
      width: 68px;
      margin-right: 8px;
    }
  }

  :deep(.date-notice-component .set-shield-config-item .item-label) {
    min-width: 56px;
    text-align: left;
  }

  :deep(.alarm-shield-notice .notice-btn) {
    margin: 0 0 18px 80px;
  }

  :deep(.alarm-shield-notice .notice-config) {
    .notice-item {
      &-label {
        /* stylelint-disable-next-line declaration-no-important */
        min-width: 56px !important;
      }
    }
  }
}
</style>
