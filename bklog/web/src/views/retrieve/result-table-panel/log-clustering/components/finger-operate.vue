<!--
  - Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
  - Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
  - BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
  -
  - License for BK-LOG 蓝鲸日志平台:
  - -------------------------------------------------------------------
  -
  - Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  - documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  - the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
  - and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  - The above copyright notice and this permission notice shall be included in all copies or substantial
  - portions of the Software.
  -
  - THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
  - LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
  - NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
  - WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
  - SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
  -->
<template>
  <div class="fingerprint-setting fl-sb">

    <div class="is-near24">
      <bk-checkbox
        v-model="isNear24"
        data-test-id="fingerTable_checkBox_selectCustomSize"
        :true-value="true"
        :false-value="false"
        :disabled="!fingerOperateData.signatureSwitch"
        @change="handleShowNearPattern">
      </bk-checkbox>
      <span
        @mouseenter="handleShowAlarmPopover"
        @click="handleChangeTrigger">{{$t('近24H新增')}}</span>
      <div v-show="false">
        <div
          ref="alarmPopover"
          slot="content"
          class="alarm-content">
          <span @click.stop="updateNewClsStrategy">{{!alarmSwitch ? $t('开启告警') : $t('关闭告警')}}</span>
          <span
            v-if="alarmSwitch"
            class="right-alarm"
            @click="handleEmitEditAlarm">
            {{$t('编辑告警')}}</span>
        </div>
      </div>
    </div>

    <div class="pattern fl-sb" style="width: 200px">
      <span>Pattern</span>
      <div class="pattern-slider-box fl-sb">
        <span>{{$t('少')}}</span>
        <bk-slider
          class="pattern-slider"
          v-model="patternSize"
          data-test-id="fingerTable_slider_patterSize"
          :show-tip="false"
          :disable="!fingerOperateData.signatureSwitch"
          :max-value="fingerOperateData.sliderMaxVal"
          @change="handleChangepatternSize"></bk-slider>
        <span>{{$t('多')}}</span>
      </div>
    </div>

    <div class="fl-sb">
      <bk-dropdown-menu ref="refOfSubscriptionDropdown" align="right" trigger="click">
        <i
          v-if="isCurrentIndexSetIdCreateSubscription"
          class="bk-icon icon-email btn-subscription" :class="{
            selected: isCurrentIndexSetIdCreateSubscription
          }"
          v-bk-tooltips.bottom-end="$t('已订阅当前页面')"
          slot="dropdown-trigger" />
        <ul class="bk-dropdown-list" slot="dropdown-content">
          <li><a href="javascript:;" @click="isShowQuickCreateSubscriptionDrawer = true">{{$t('新建订阅')}}</a></li>
          <li><a href="javascript:;" @click="goToMySubscription">{{$t('我的订阅')}}</a></li>
        </ul>
      </bk-dropdown-menu>
      <i
        v-if="!isCurrentIndexSetIdCreateSubscription"
        class="bk-icon icon-email btn-subscription"
        @click="isShowQuickCreateSubscriptionDrawer = true"
        v-bk-tooltips.bottom-end="$t('邮件订阅')"
      />
    </div>

    <quick-create-subscription
      v-model="isShowQuickCreateSubscriptionDrawer"
      scenario="clustering"
      :index-set-id="$route.params.indexId"
    />

    <bk-popover
      ext-cls="popover-content"
      placement="bottom-start"
      width="400"
      ref="groupPopover"
      :disabled="!fingerOperateData.signatureSwitch"
      :tippy-options="tippyOptions"
      :on-show="handleShowMorePopover">
      <div
        v-bk-tooltips="$t('更多')"
        :class="{ 'operation-icon': true, 'disabled-icon': !fingerOperateData.signatureSwitch }"
        @click="handleClickGroupPopover">
        <span class="bk-icon icon-more"></span>
      </div>
      <div
        class="group-popover"
        slot="content">
        <div class="piece">
          <span>
            <span class="title">{{ $t('维度') }}</span>
            <i class="notice log-icon icon-help" v-bk-tooltips.top="$t('修改字段会影响当前聚类结果，请勿随意修改')"></i>
          </span>
          <bk-select
            v-model="dimension"
            searchable
            multiple
            display-tag
            ext-popover-cls="selected-ext"
            :scroll-height="140">
            <bk-option
              v-for="option in dimensionList"
              :key="option.id"
              :id="option.id"
              :name="option.name">
              <bk-checkbox
                ext-cls="ext-box"
                :title="option.name"
                :checked="dimension.includes(option.id)">
                {{ option.name }}
              </bk-checkbox>
            </bk-option>
          </bk-select>
          <div class="group-alert">
            <i class="bk-icon icon-info"></i>
            <span>{{ $t('如需根据某些维度拆分聚类结果，可将字段设置为维度。') }}</span>
          </div>
        </div>
        <div class="piece">
          <span class="title">{{ $t('分组') }}</span>
          <bk-select
            v-model="group"
            searchable
            multiple
            display-tag
            ext-popover-cls="selected-ext"
            :scroll-height="140">
            <bk-option
              v-for="option in groupList"
              :key="option.id"
              :id="option.id"
              :name="option.name">
              <bk-checkbox
                ext-cls="ext-box"
                :title="option.name"
                :checked="group.includes(option.id)">
                {{ option.name }}
              </bk-checkbox>
            </bk-option>
          </bk-select>
        </div>
        <div class="piece">
          <span class="title">{{ $t('同比') }}</span>
          <div class="year-on-year">
            <bk-switcher
              theme="primary"
              v-model="yearSwitch">
            </bk-switcher>
            <bk-select
              v-model="yearOnYearHour"
              ext-cls="compared-select"
              ext-popover-cls="compared-select-option"
              :clearable="false"
              :disabled="!yearSwitch"
              @toggle="toggleYearSelect">
              <bk-option
                v-for="option in fingerOperateData.comparedList"
                :key="option.id"
                :id="option.id"
                :name="option.name">
              </bk-option>
              <div slot="" class="compared-customize">
                <div
                  v-if="fingerOperateData.isShowCustomize"
                  class="customize-option"
                  @click="changeCustomizeState(false)">
                  <span>{{$t('自定义')}}</span>
                </div>
                <div style="margin-top: 8px;" v-else>
                  <bk-input
                    :placeholder="$t('输入自定义同比，按 Enter 确认')"
                    @enter="handleEnterCompared">
                  </bk-input>
                  <div class="compared-select-icon">
                    <span v-bk-tooltips="$t('自定义输入格式: 如 1h 代表一小时 h小时')" class="top-end">
                      <i class="log-icon icon-help"></i>
                    </span>
                  </div>
                </div>
              </div>
            </bk-select>
          </div>
        </div>
        <div class="popover-button">
          <bk-button
            style="margin-right: 8px;"
            theme="primary"
            size="small"
            @click="submitPopover">
            {{$t('保存')}}
          </bk-button>
          <bk-button
            theme="default"
            size="small"
            @click="cancelPopover">
            {{$t('取消')}}
          </bk-button>
        </div>
      </div>
    </bk-popover>
  </div>
</template>

<script>
import { debounce } from 'throttle-debounce';
import QuickCreateSubscription from './quick-create-subscription-drawer/quick-create-subscription.tsx';
export default {
  components: {
    QuickCreateSubscription,
  },
  props: {
    fingerOperateData: {
      type: Object,
      require: true,
    },
    requestData: {
      type: Object,
      require: true,
    },
    totalFields: {
      type: Array,
      require: true,
    },
  },
  data() {
    return {
      interactType: false, // false 为hover true 为click
      alarmSwitch: false,
      dimension: [], // 当前维度字段的值
      group: [], // 当前分组选中的值
      isToggle: false, // 当前是否显示分组下拉框
      patternSize: 0,
      yearOnYearHour: 1,
      isNear24: false,
      isRequestAlarm: false,
      popoverInstance: null,
      isShowPopoverInstance: false,
      yearSwitch: false,
      tippyOptions: {
        theme: 'light',
        trigger: 'manual',
        hideOnClick: false,
        offset: '16',
        interactive: true,
      },
      isCurrentIndexSetIdCreateSubscription: false,
      isShowQuickCreateSubscriptionDrawer: false,
    };
  },
  computed: {
    bkBizId() {
      return this.$store.state.bkBizId;
    },
    dimensionList() {
      return this.fingerOperateData.groupList.filter(item => !this.group.includes(item.id));
    },
    groupList() {
      return this.fingerOperateData.groupList.filter(item => !this.dimension.includes(item.id));
    },
  },
  watch: {
    group: {
      deep: true,
      handler(list) {
        // 分组列表未展开时数组变化则发送请求
        if (!this.isToggle) {
          this.$emit('handleFingerOperate', 'group', list);
        }
      },
    },
  },
  created() {
    this.checkReportIsExistedDebounce = debounce(1000, this.checkReportIsExisted);
  },
  mounted() {
    this.handleShowMorePopover();
    this.checkReportIsExistedDebounce();
    this.handlePopoverShow();
  },
  beforeDestroy() {
    this.popoverInstance = null;
  },
  methods: {
    /**
     * @desc: 同比自定义输入
     * @param { String } val
     */
    handleEnterCompared(val) {
      const matchVal = val.match(/^(\d+)h$/);
      if (!matchVal) {
        this.$bkMessage({
          theme: 'warning',
          message: this.$t('请按照提示输入'),
        });
        return;
      }
      this.changeCustomizeState(true);
      const { comparedList: propComparedList } = this.fingerOperateData;
      const isRepeat = propComparedList.some(el => el.id === Number(matchVal[1]));
      if (isRepeat) {
        this.yearOnYearHour = Number(matchVal[1]);
        return;
      }
      propComparedList.push({
        id: Number(matchVal[1]),
        name: this.$t('{n} 小时前', { n: matchVal[1] }),
      });
      this.$emit('handleFingerOperate', 'fingerOperateData', {
        comparedList: propComparedList,
      });
      this.yearOnYearHour = Number(matchVal[1]);
    },
    handleShowNearPattern(state) {
      this.$emit('handleFingerOperate', 'requestData', { show_new_pattern: state }, true);
    },
    handleChangepatternSize(val) {
      this.$emit('handleFingerOperate', 'requestData', { pattern_level: this.fingerOperateData.patternList[val] }, true);
    },
    changeCustomizeState(val) {
      this.$emit('handleFingerOperate', 'fingerOperateData', { isShowCustomize: val });
    },
    handleClickGroupPopover() {
      !this.isShowPopoverInstance ? this.$refs.groupPopover.instance.show() : this.$refs.groupPopover.instance.hide();
      this.isShowPopoverInstance = !this.isShowPopoverInstance;
    },
    handleEmitEditAlarm() {
      this.$emit('handleFingerOperate', 'editAlarm');
    },
    handlePopoverShow() {
      if (JSON.stringify(this.fingerOperateData.alarmObj) === '{}') {
        this.initNewClsStrategy();
      }
    },
    /**
     * @desc: 改变近24H新增的交互类型
     */
    handleChangeTrigger() {
      if (!this.interactType) {
        this.popoverInstance?.set({
          trigger: 'click',
          hideOnClick: true,
        });
      }
      this.interactType = true;
    },
    handleShowAlarmPopover(e) {
      if (this.popoverInstance || !this.fingerOperateData.signatureSwitch) return;
      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.$refs.alarmPopover,
        trigger: 'mouseenter',
        placement: 'top',
        arrow: true,
        theme: 'light',
        interactive: true,
        hideOnClick: false,
      });
      this.popoverInstance && this.popoverInstance.show();
    },
    /**
     * @desc: 查询新类告警
     */
    initNewClsStrategy() {
      this.$http.request('/logClustering/getNewClsStrategy', {
        params: {
          index_set_id: this.$route.params.indexId,
        },
      }).then((res) => {
        this.$emit('handleFingerOperate', 'fingerOperateData', {
          alarmObj: res.data,
        });
        this.alarmSwitch = res.data.is_active;
      });
    },
    /**
     * @desc: 更新新类告警
     */
    updateNewClsStrategy() {
      const action = this.alarmSwitch ? 'delete' : 'create';
      const strategyID = this.fingerOperateData.alarmObj?.strategy_id;
      const queryObj = {
        bk_biz_id: this.bkBizId,
        strategy_id: strategyID,
        action,
      };
      // 开启新类告警时需删除strategy_id字段
      !this.alarmSwitch && delete queryObj.strategy_id;
      this.isRequestAlarm = true,
      this.$http.request('/logClustering/updateNewClsStrategy', {
        params: {
          index_set_id: this.$route.params.indexId,
        },
        data: { ...queryObj },
      }).then((res) => {
        if (res.result) {
          this.popoverInstance.hide();
          this.$emit('handleFingerOperate', 'fingerOperateData', {
            alarmObj: {
              strategy_id: res.data,
              is_active: !this.alarmSwitch,
            },
          });
          this.$bkMessage({
            theme: 'success',
            message: this.$t('操作成功'),
            ellipsisLine: 0,
          });
          setTimeout(() => {
            this.alarmSwitch = !this.alarmSwitch;
          }, 200);
        }
      })
        .finally(() => {
          this.isRequestAlarm = false;
        });
    },
    async submitPopover() {
      await this.updateInitGroup();
      this.$emit('handleFingerOperate', 'fingerOperateData', {
        dimensionList: this.dimension,
        selectGroupList: this.group,
        yearSwitch: this.yearSwitch,
      });
      this.$emit('handleFingerOperate', 'requestData', {
        group_by: [...this.group, ...this.dimension],
        year_on_year_hour: this.yearSwitch ? this.yearOnYearHour : 0,
      }, true);
      this.cancelPopover();
    },
    /**
     * @desc: 是否默认展示分组接口
     */
    async updateInitGroup() {
      await this.$http.request('/logClustering/updateInitGroup', {
        params: {
          index_set_id: this.$route.params.indexId,
        },
        data: {
          group_fields: this.dimension,
        },
      });
    },
    cancelPopover() {
      this.isShowPopoverInstance = false;
      this.$refs.groupPopover.instance.hide();
    },
    toggleYearSelect(val) {
      !val && this.changeCustomizeState(true);
    },
    handleShowMorePopover() {
      const finger = this.fingerOperateData;
      this.isNear24 = this.requestData.show_new_pattern;
      this.patternSize = finger.patternSize;
      this.alarmSwitch = finger.alarmObj?.is_active;
      this.dimension = finger.dimensionList;
      this.group = finger.selectGroupList;
      this.yearSwitch = finger.yearSwitch;
      this.yearOnYearHour = finger.yearOnYearHour;
    },
    /**
     * 检查当前 索引集 是否创建过订阅。
     */
    checkReportIsExisted() {
      this.$http.request('newReport/getExistReports/', {
        query: {
          scenario: 'clustering',
          bk_biz_id: this.$route.query.bizId,
          index_set_id: this.$route.params.indexId,
        },
      }).then((response) => {
        console.log(response, !!(response.data.length));
        this.isCurrentIndexSetIdCreateSubscription = !!(response.data.length);
      })
        .catch(console.log);
    },
    /**
     * 空方法 checkReportIsExisted 的 debounce 版。
     */
    checkReportIsExistedDebounce() {},
    /**
     * 跳转到 监控下的 我的订阅
     */
    goToMySubscription() {
      const query = this.$route.query.bizId ? `?bizId=${this.$route.query.bizId}` : '';
      // window.open(`${window.MONITOR_URL}/${query}#/my-report`, '_blank');
      // 20231225 暂不需要
      window.open(`${window.MONITOR_URL}/${query}#/trace/report?isShowMyReport=true`, '_blank');
    },
  },
};
</script>
<style lang="scss" scoped>
@import '@/scss/mixins/flex.scss';

.fingerprint-setting {
  height: 32px;
  line-height: 24px;
  font-size: 12px;
  flex-shrink: 0;

  > div {
    margin-left: 20px;
  }

  .is-near24 {
    @include flex-center;

    > span {
      border-bottom: 1px dashed #979ba5;
      margin-left: 4px;
      line-height: 16px;
      cursor: pointer;
    }
  }

  .pattern {
    width: 200px;

    .pattern-slider-box {
      width: 154px;
    }

    .pattern-slider {
      width: 114px;
    }
  }
}

.compared-select-option {
  .compared-customize {
    position: relative;
    margin-bottom: 8px;
    top: -3px;
  }

  .compared-select-icon {
    font-size: 14px;
    position: absolute;
    top: 0;
    right: 22px;
  }

  .customize-option {
    padding: 0 16px;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
      background: #eaf3ff;
    }
  }

  .bk-form-control {
    width: 90%;
    margin: 0 auto;
  }

  .bk-form-input {
    /* stylelint-disable-next-line declaration-no-important */
    padding: 0 18px 0 10px !important;
  }
}

.alarm-content {
  color: #3a84ff;
  font-size: 12px;
  cursor: pointer;

  .right-alarm {
    margin-left: 6px;

    &:before {
      content: '|';
      margin-right: 6px;
      color: #dcdee5;
    }
  }
}

.selected-ext {
  .bk-option.is-selected {
    /* stylelint-disable-next-line declaration-no-important */
    background: none !important;
  }

  .bk-option:hover {
    background: #f4f6fa;
  }
}

.popover-content {
  .group-popover {
    padding-top: 8px;

    .piece {
      margin-bottom: 13px;
    }

    .title {
      display: inline-block;
      margin-bottom: 6px;
      color: #63656e;
    }

    .notice {
      color: #979ba5;
      font-size: 14px;
      cursor: pointer;
    }

    .group-alert {
      position: relative;
      margin: 6px 0 14px 0;
      padding: 6px 30px;
      line-height: 20px;
      color: #63656e;
      background: #f0f1f5;
      border-radius: 2px;

      .icon-info {
        color: #979ba5;
        font-size: 16px;
        position: absolute;
        top: 8px;
        left: 8px;
      }
    }

    .year-on-year {
      @include flex-center();
    }

    .compared-select {
      margin-left: 20px;
      flex: 1;
    }

    .popover-button {
      padding: 12px 0;

      @include flex-justify(end);
    }
  }
}

.ext-box {
  height: 32px;

  /* stylelint-disable-next-line declaration-no-important */
  display: flex !important;

  @include flex-center();

  :deep(.bk-checkbox-text) {
    /* stylelint-disable-next-line declaration-no-important */
    font-size: 12px !important;
    width: calc(100% - 20px);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.disabled-icon {
  background-color: #fff;
  border-color: #dcdee5;
  cursor: not-allowed;

  &:hover,
  .log-icon {
    border-color: #dcdee5;
    color: #c4c6cc;
  }
}

.operation-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 26px;
  height: 26px;
  margin-left: 10px;
  cursor: pointer;
  border: 1px solid #c4c6cc;
  transition: boder-color .2s;
  border-radius: 2px;
  outline: none;

  &:hover {
    border-color: #979ba5;
    transition: boder-color .2s;
  }

  &:active {
    border-color: #3a84ff;
    transition: boder-color .2s;
  }

  .icon-more {
    width: 16px;
    font-size: 16px;
    color: #979ba5;
  }
}

.fl-sb {
  align-items: center;

  @include flex-justify(space-between);
}

.btn-subscription {
  border-radius: 2px;
  padding: 8px;
  color: #63656E;
  cursor: pointer;
  font-size: 14px;

  &.selected {
    color: #3A84FF;
  }

  &:hover {
    background: #F0F1F5;
  }

  &:active {
    background-color: #E1ECFF;
  }
}
</style>
