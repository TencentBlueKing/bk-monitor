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
  <div class="quick-alarm-shield">
    <!-- 屏蔽类型 -->
    <section class="shield-section">
      <div class="shield-section-title">
        {{ $t('屏蔽类型') }}
      </div>
      <div class="shield-section-content">
        <van-radio-group v-model="shieldType">
          <van-radio
            v-for="item in radioList.type"
            class="content-radio"
            :key="item.value"
            :name="item.value"
          >
            {{ item.name }}
          </van-radio>
        </van-radio-group>
      </div>
    </section>
    <!-- 屏蔽内容 -->
    <section class="shield-section">
      <div class="shield-section-title">
        {{ $t('屏蔽内容') }}
      </div>
      <div class="shield-section-detail">
        <div
          v-for="(item, index) in shieldContent"
          :class="['detail-item', { 'is-dimension': item.name === $t('维度') }]"
          :key="index"
        >
          <template v-if="item.type === shieldType">
            <span>
              {{ `${item.name}:` }}
            </span>
            <!-- 维度信息需要可复选 -->
            <van-checkbox-group
              v-if="item.name === $t('维度') && Array.isArray(item.value)"
              class="detail-item-span"
              v-model="selectedDimension"
              icon-size="16px"
            >
              <van-checkbox
                v-for="dimension in item.value"
                :key="dimension.displayValue"
                :name="dimension.key"
                shape="square"
              >
                {{ dimension.displayValue }}
              </van-checkbox>
            </van-checkbox-group>
            <span
              v-else
              class="detail-item-span"
            >
              {{ item.value }}
            </span>
          </template>
        </div>
      </div>
    </section>
    <!-- 屏蔽时长 -->
    <section class="shield-section">
      <div class="shield-section-title">
        {{ $t('屏蔽时长') }}
      </div>
      <div class="shield-section-date">
        <van-grid :column-num="3">
          <van-grid-item
            v-for="item in dataPickerList"
            :class="active === item.id ? 'active' : ''"
            :key="item.id"
            :text="item.name"
            @click="handleShowDatePicker(item.id, item.value)"
          />
        </van-grid>
      </div>
    </section>
    <!-- 原因 -->
    <section class="shield-section">
      <div class="shield-section-title">
        {{ $t('原因') }}
      </div>
      <div class="shield-section-content">
        <van-radio-group v-model="reason">
          <van-radio
            v-for="item in radioList.reason"
            class="content-radio"
            :key="item.value"
            :name="item.value"
          >
            {{ item.name }}
          </van-radio>
        </van-radio-group>
      </div>
    </section>
    <datetime-picker
      :min-date="minDate"
      :show.sync="isShowDatePicker"
      @confirm="handleDateTimeConfirm"
    />
    <footer-button
      v-show="!isShowDatePicker"
      :loading="loading"
      @click="handleSubmit"
    >
      {{ $t('提交') }}
    </footer-button>
  </div>
</template>

<script lang="ts">
import { Component, Prop, Vue, Watch } from 'vue-property-decorator';

import { Checkbox, CheckboxGroup, Grid, GridItem, Popup, Radio, RadioGroup, Toast } from 'vant';

import { quickShield } from '../../../monitor-api/modules/mobile_event';
import DatetimePicker, { type ITimeObj } from '../../components/datetime-picker/datetime-picker.vue';
import FooterButton from '../../components/footer-button/footer-button.vue';
import AlarmModule from '../../store/modules/alarm-info';
import EventModule from '../../store/modules/event-detail';

interface IRadioList {
  name: string;
  value: string;
}
interface IDimensionItem {
  displayValue: string;
  displayKey: string;
  value: string;
  key: string;
}
interface IDataPickerList {
  id: number;
  name: string;
  value: number;
}
interface IShieldItem {
  type: string;
  name: string;
  value: IDimensionItem[] | string;
}
interface IEentDetail {
  dimensions: IDimensionItem[];
  dimensionMessage: string;
  strategyName: string;
  targetMessage: string;
  anomalyMessage: string;
  levelName: string;
}
enum TimeSemantics {
  TenMinutes = 1,
  ThirtyMinutes = 2,
  TwelveHour = 3,
  OneDays = 4,
  SevenDays = 5,
  Custom = 6,
}

@Component({
  name: 'quick-alarm-shield',
  components: {
    [RadioGroup.name]: RadioGroup,
    [Radio.name]: Radio,
    [CheckboxGroup.name]: CheckboxGroup,
    [Checkbox.name]: Checkbox,
    DatetimePicker,
    [Popup.name]: Popup,
    [Grid.name]: Grid,
    [GridItem.name]: GridItem,
    FooterButton,
  },
})
export default class AlarmDetail extends Vue {
  @Prop({ default: 0 }) readonly eventId!: number | string;
  @Prop() readonly routeKey: string;
  private active = TimeSemantics.TenMinutes; // 屏蔽时间当前项
  private shieldType = 'event'; // 屏蔽类型 value
  private reason = '变更中'; // 屏蔽原因 value
  private customTime = ''; // 自定义时间
  private radioList: { type: IRadioList[]; reason: IRadioList[] }; // type: 屏蔽类型列表 reason: 屏蔽原因列表
  private isShowDatePicker = false; // 是否展示时间选择器
  private dataPickerList: IDataPickerList[] = []; // 时间选择列表
  private loading = false;
  private minDate: Date = new Date(); // 可选的最小时间
  private shieldContent: IShieldItem[] = []; // 屏蔽内容
  private selectedDimension: string[] = []; // 选择的维度信息
  private endTime = ''; // 截止时间
  private eventDetail: IEentDetail = {
    // 事件详情
    dimensions: [],
    dimensionMessage: '',
    strategyName: '',
    targetMessage: '',
    anomalyMessage: '',
    levelName: '',
  };

  @Watch('routeKey')
  onRouteKeyChange() {
    this.initData();
  }

  created() {
    this.radioList = {
      type: [{ name: this.$tc('事件屏蔽'), value: 'event' }],
      reason: [
        { name: this.$tc('变更中'), value: '变更中' },
        { name: this.$tc('无关紧要'), value: '无关紧要' },
        { name: this.$tc('已知问题'), value: '已知问题' },
        { name: this.$tc('其他'), value: '其他' },
      ],
    };
    this.customTime = this.$tc('自定义');
    this.dataPickerList = [
      { id: 1, name: String(this.$t('分钟', { num: 10 })), value: 60000 * 10 },
      { id: 2, name: String(this.$t('分钟', { num: 30 })), value: 60000 * 30 },
      { id: 3, name: String(this.$t('小时', { num: 12 })), value: 60000 * 60 * 12 },
      { id: 4, name: String(this.$t('天', { num: 1 })), value: 60000 * 60 * 24 },
      { id: 5, name: String(this.$t('天', { num: 7 })), value: 60000 * 60 * 24 * 7 },
      { id: 6, name: this.$tc('自定义'), value: 0 },
    ];
  }

  activated() {
    this.initData();
  }

  initData() {
    if (this.eventId) {
      this.endTime = this.handleEndTime(new Date(new Date().getTime() + 600000));
      this.getEventDetail();
    }
  }

  //  获取事件详情数据
  async getEventDetail() {
    this.$store.commit('app/setPageLoading', true);
    const [eventDetail] = await Promise.all([
      EventModule.getEventDetail({ id: this.eventId }),
      AlarmModule.getEventNum(),
    ]);
    this.eventDetail = eventDetail;
    this.selectedDimension = this.eventDetail.dimensions?.map(item => item.key) || []; // 默认选中所有维度信息
    this.handleSetRadioList();
    this.shieldContent = [
      // {
      //   type: 'event',
      //   name: this.$tc('级别'),
      //   value: this.eventDetail.levelName,
      // },
      {
        type: 'event',
        name: this.$tc('维度'),
        value: this.eventDetail.dimensions,
      },
      {
        type: 'strategy',
        name: this.$tc('策略名称'),
        value: this.eventDetail.strategyName,
      },
      {
        type: 'scope',
        name: this.$tc('IP/实例'),
        value: this.eventDetail.targetMessage,
      },
      {
        type: 'event',
        name: this.$tc('条件'),
        value: this.eventDetail.anomalyMessage,
      },
    ];
    this.$store.commit('app/setPageLoading', false);
  }

  async handleSetRadioList() {
    const index = this.radioList.type.findIndex(item => item.value === 'scope');
    // targetMessage不为空时才有实例屏蔽选项
    if (this.eventDetail.targetMessage) {
      // keep-alive钩子的影响，添加过无需再添加
      if (index === -1) {
        this.radioList.type.push({ name: this.$tc('IP/实例屏蔽'), value: 'scope' });
      }
    } else if (index > -1) {
      // 去除存在的实例屏蔽选项
      this.radioList.type.splice(index, 1);
    }
  }

  //  屏蔽时间选择
  handleShowDatePicker(id, value) {
    this.active = id;
    //  弹出自定义时间框
    if (this.active === TimeSemantics.Custom) {
      this.isShowDatePicker = true;
      return;
    }
    const endTime = new Date(new Date().getTime() + value);
    this.endTime = this.handleEndTime(endTime);
  }

  //  确认事件
  handleDateTimeConfirm(timeObj: ITimeObj) {
    const data = this.dataPickerList.find(item => item.id === TimeSemantics.Custom);
    const date = timeObj.dateObj;
    data.name = this.handleEndTime(date);
    this.endTime = data.name;
  }

  //  拼接自定义截止时间
  handleEndTime(date) {
    const Y = `${date.getFullYear()}-`;
    const M = `${date.getMonth() + 1 < 10 ? `0${date.getMonth() + 1}` : date.getMonth() + 1}-`;
    const D = `${date.getDate()} `;
    const h = `${date.getHours() < 10 ? `0${date.getHours()}` : date.getHours()}:`;
    const m = `${date.getMinutes() < 10 ? `0${date.getMinutes()}` : date.getMinutes()}:`;
    const s = date.getSeconds() < 10 ? `0${date.getSeconds()}` : date.getSeconds();
    return Y + M + D + h + m + s;
  }

  //  提交快捷屏蔽
  handleSubmit() {
    if (this.active === TimeSemantics.Custom && this.dataPickerList[5].name === '自定义') {
      this.$notify('选择自定义时间');
      return;
    }
    this.loading = true;
    const params: Record<string, any> = {
      event_id: this.eventId,
      type: this.shieldType,
      end_time: this.endTime,
      desc: this.reason,
    };
    if (this.shieldType === 'event') {
      params.dimension_keys = this.selectedDimension;
    }
    quickShield(params)
      .then(() => {
        Toast({
          message: this.$tc('操作成功'),
          duration: 2000,
          position: 'bottom',
        });
        this.$router.back();
      })
      .catch(e => {
        Toast({
          message: e?.message || this.$tc('操作失败'),
          duration: 2000,
          position: 'bottom',
        });
      })
      .finally(() => {
        this.loading = false;
      });
  }
}
</script>

<style lang="scss" scoped>
@import '../../static/scss/variate.scss';

.quick-alarm-shield {
  padding: 13px 16px;
  padding-bottom: 50px;
  font-size: 14px;
  color: $defaultFontColor;

  .shield-section {
    margin-bottom: 13px;

    &-title {
      margin-bottom: 13px;
      font-weight: 500;
      color: #313238;
    }

    &-content {
      padding: 0 20px;
      background: #fff;
      border-radius: 4px;
      box-shadow: 0 1px 0 0 rgba(99, 101, 110, 0.05);

      .content-radio {
        position: relative;
        height: 32px;
        padding: 8px 0;

        :deep(.van-radio__label) {
          color: $defaultFontColor;
        }

        &:after {
          position: absolute;
          right: 0;
          bottom: 0;
          width: 315px;
          height: 1px;
          content: '';
          background: $borderColor;
          opacity: 0.6;
        }

        &:nth-last-child(1)::after {
          display: none;
        }
      }
    }

    &-detail {
      padding: 16px 20px;
      background: #fff;

      .detail-item {
        line-height: 20px;

        &-span {
          word-break: break-all;
        }
      }

      .is-dimension {
        display: flex;
        align-items: flex-start;
        justify-content: flex-start;

        span {
          flex-shrink: 0;
        }

        .detail-item-span {
          width: 100%;
          padding-bottom: 5px;
          margin-left: 4px;
          overflow: hidden;
        }

        .van-checkbox {
          padding-bottom: 5px;
          border-bottom: 1px solid #ebecf1;

          & + .van-checkbox {
            margin-top: 5px;
          }
        }

        :deep(.van-checkbox__label) {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }

    &-date {
      :deep(.van-grid-item) {
        height: 50px;

        .van-hairline {
          span {
            word-break: break-all;

            &:last-child {
              text-align: center;
              word-break: normal;
            }
          }

          &::after {
            border-color: #eaebef;
          }
        }

        &.active {
          .van-hairline {
            background: #e1ecff;
            border: 1px solid #3a84ff;

            .van-grid-item__text {
              color: #3a84ff;
              text-align: center;
              word-break: normal;
            }
          }
        }
      }
    }
  }
}
</style>
