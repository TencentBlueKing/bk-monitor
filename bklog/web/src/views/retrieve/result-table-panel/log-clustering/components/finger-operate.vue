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
  <div class="fingerprint-setting fl-sb">
    <div
      v-if="!isExternal"
      class="is-near24"
      v-bk-tooltips="{ content: $t('请先新建新类告警策略'), disabled: strategyHaveSubmit }"
    >
      <bk-checkbox
        v-model="isNear24"
        :disabled="!clusterSwitch || !strategyHaveSubmit"
        :false-value="false"
        :true-value="true"
        data-test-id="fingerTable_checkBox_selectCustomSize"
        @change="handleShowNearPattern"
      >
        <span>{{ $t('仅查看新类') }}</span>
      </bk-checkbox>
    </div>

    <!-- <div
      style="width: 200px"
      class="pattern fl-sb"
    >
      <span>Pattern</span>
      <div class="pattern-slider-box fl-sb">
        <span>{{ $t('少') }}</span>
        <bk-slider
          class="pattern-slider"
          v-model="patternSize"
          :max-value="fingerOperateData.sliderMaxVal"
          :show-tip="false"
          data-test-id="fingerTable_slider_patterSize"
          @change="handleChangepatternSize"
        ></bk-slider>
        <span>{{ $t('多') }}</span>
      </div>
    </div> -->

    <div
      class="fl-sb"
      v-if="!isExternal"
    >
      <bk-dropdown-menu
        ref="refOfSubscriptionDropdown"
        align="right"
        trigger="click"
      >
        <template #dropdown-trigger>
          <i
            v-if="isCurrentIndexSetIdCreateSubscription"
            class="bk-icon icon-email btn-subscription"
            v-bk-tooltips.bottom-end="$t('已订阅当前页面')"
            :class="{
              selected: isCurrentIndexSetIdCreateSubscription,
            }"
          />
        </template>
        <template #dropdown-content>
          <ul class="bk-dropdown-list">
            <li>
              <a
                href="javascript:;"
                @click="isShowQuickCreateSubscriptionDrawer = true"
                >{{ $t('新建订阅') }}</a
              >
            </li>
            <li>
              <a
                href="javascript:;"
                @click="goToMySubscription"
                >{{ $t('我的订阅') }}</a
              >
            </li>
          </ul>
        </template>
      </bk-dropdown-menu>
      <i
        v-if="!isCurrentIndexSetIdCreateSubscription"
        class="bk-icon icon-email btn-subscription"
        v-bk-tooltips.bottom-end="$t('邮件订阅')"
        @click="isShowQuickCreateSubscriptionDrawer = true"
      />
    </div>

    <quick-create-subscription
      v-model="isShowQuickCreateSubscriptionDrawer"
      :index-set-id="$route.params.indexId"
      scenario="clustering"
    />

    <bk-popover
      ref="groupPopover"
      width="400"
      ext-cls="popover-content"
      :disabled="!clusterSwitch"
      :on-show="handleShowMorePopover"
      :tippy-options="tippyOptions"
      placement="bottom-start"
    >
      <div
        v-bk-tooltips="$t('更多')"
        :class="{ 'operation-icon': true, 'disabled-icon': !clusterSwitch }"
        @click="handleClickGroupPopover"
      >
        <span class="bk-icon icon-more"></span>
      </div>
      <template #content>
        <div class="group-popover">
          <div
            v-if="!isExternal"
            class="piece"
          >
            <span>
              <span class="title">{{ $t('维度') }}</span>
              <i
                class="notice bklog-icon bklog-help"
                v-bk-tooltips.top="$t('修改字段会影响当前聚类结果，请勿随意修改')"
              ></i>
            </span>
            <bk-select
              v-model="dimension"
              :scroll-height="140"
              ext-popover-cls="selected-ext"
              display-tag
              multiple
              searchable
            >
              <bk-option
                v-for="option in dimensionList"
                :id="option.id"
                :key="option.id"
                :name="option.name"
              >
                <bk-checkbox
                  ext-cls="ext-box"
                  :checked="dimension.includes(option.id)"
                  :title="option.name"
                >
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
              :scroll-height="140"
              ext-popover-cls="selected-ext"
              display-tag
              multiple
              searchable
            >
              <bk-option
                v-for="option in groupList"
                :id="option.id"
                :key="option.id"
                :name="option.name"
              >
                <bk-checkbox
                  ext-cls="ext-box"
                  :checked="group.includes(option.id)"
                  :title="option.name"
                >
                  {{ option.name }}
                </bk-checkbox>
              </bk-option>
            </bk-select>
          </div>
          <div class="piece">
            <span class="title">{{ $t('同比') }}</span>
            <div class="year-on-year">
              <bk-switcher
                v-model="yearSwitch"
                theme="primary"
              >
              </bk-switcher>
              <bk-select
                ext-cls="compared-select"
                v-model="yearOnYearHour"
                :clearable="false"
                :disabled="!yearSwitch"
                ext-popover-cls="compared-select-option"
                @toggle="toggleYearSelect"
              >
                <bk-option
                  v-for="option in fingerOperateData.comparedList"
                  :id="option.id"
                  :key="option.id"
                  :name="option.name"
                >
                </bk-option>
                <template #extension>
                  <div class="compared-customize">
                    <div
                      v-if="fingerOperateData.isShowCustomize"
                      class="customize-option"
                      @click="changeCustomizeState(false)"
                    >
                      <span>{{ $t('自定义') }}</span>
                    </div>
                    <div v-else>
                      <bk-input
                        :placeholder="$t('输入自定义同比，按 Enter 确认')"
                        @enter="handleEnterCompared"
                      >
                      </bk-input>
                      <div class="compared-select-icon">
                        <span
                          class="top-end"
                          v-bk-tooltips="$t('自定义输入格式: 如 1h 代表一小时 h小时')"
                        >
                          <i class="bklog-icon bklog-help"></i>
                        </span>
                      </div>
                    </div>
                  </div>
                </template>
              </bk-select>
            </div>
          </div>
          <div class="popover-button">
            <bk-button
              style="margin-right: 8px"
              size="small"
              theme="primary"
              @click="submitPopover"
            >
              {{ $t('保存') }}
            </bk-button>
            <bk-button
              size="small"
              theme="default"
              @click="cancelPopover"
            >
              {{ $t('取消') }}
            </bk-button>
          </div>
        </div>
      </template>
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
      clusterSwitch: {
        type: Boolean,
        default: false,
      },
      strategyHaveSubmit: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        interactType: false, // false 为hover true 为click
        dimension: [], // 当前维度字段的值
        group: [], // 当前分组选中的值
        isToggle: false, // 当前是否显示分组下拉框
        patternSize: 0,
        yearOnYearHour: 1,
        isNear24: false,
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
        /** 打开设置弹窗时的维度 */
        catchDimension: [],
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
      isExternal() {
        return this.$store.state.isExternal;
      },
    },
    watch: {
      group: {
        deep: true,
        handler(list) {
          // 分组列表未展开时数组变化则发送请求
          if (!this.isToggle) {
            this.$emit('handle-finger-operate', 'group', list);
          }
        },
      },
    },
    created() {
      this.checkReportIsExistedDebounce = debounce(1000, this.checkReportIsExisted);
    },
    mounted() {
      this.handleShowMorePopover();
      !this.isExternal && this.checkReportIsExistedDebounce();
    },
    beforeUnmount() {
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
        this.$emit('handle-finger-operate', 'fingerOperateData', {
          comparedList: propComparedList,
        });
        this.yearOnYearHour = Number(matchVal[1]);
      },
      handleShowNearPattern(state) {
        this.$emit('handle-finger-operate', 'requestData', { show_new_pattern: state }, true);
      },
      handleChangepatternSize(val) {
        this.$emit(
          'handle-finger-operate',
          'requestData',
          { pattern_level: this.fingerOperateData.patternList[val] },
          true,
        );
      },
      changeCustomizeState(val) {
        this.$emit('handle-finger-operate', 'fingerOperateData', { isShowCustomize: val });
      },
      handleClickGroupPopover() {
        !this.isShowPopoverInstance ? this.$refs.groupPopover.instance.show() : this.$refs.groupPopover.instance.hide();
        this.isShowPopoverInstance = !this.isShowPopoverInstance;
      },
      async submitPopover() {
        // 设置过维度 进行二次确认弹窗判断
        if (this.catchDimension.length) {
          const dimensionSortStr = this.dimension.sort().join(',');
          const catchDimensionSortStr = this.catchDimension.sort().join(',');
          const isShowInfo = dimensionSortStr !== catchDimensionSortStr;
          if (isShowInfo && !this.isExternal) { // 外部版不能改维度
            this.$bkInfo({
              type: 'warning',
              title: this.$t('修改维度字段会影响已有备注、告警配置，如无必要，请勿随意变动。请确定是否修改？'),
              confirmFn: async () => {
                await this.updateInitGroup();
                this.finishEmit();
              },
            });
          } else {
            // 不请求更新维度接口 直接提交
            this.finishEmit();
          }
        } else {
          // 没设置过维度 直接提交
          if (this.dimension.length) await this.updateInitGroup();
          this.finishEmit();
        }
      },
      finishEmit() {
        this.$emit('handle-finger-operate', 'fingerOperateData', {
          dimensionList: this.dimension,
          selectGroupList: this.group,
          yearSwitch: this.yearSwitch,
          yearOnYearHour: this.yearOnYearHour,
        });
        this.$emit(
          'handle-finger-operate',
          'requestData',
          {
            group_by: [...this.group, ...this.dimension],
            year_on_year_hour: this.yearSwitch ? this.yearOnYearHour : 0,
          },
          true,
        );
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
        this.dimension = finger.dimensionList;
        this.catchDimension = finger.dimensionList;
        this.group = finger.selectGroupList;
        this.yearSwitch = finger.yearSwitch;
        this.yearOnYearHour = finger.yearOnYearHour;
      },
      /**
       * 检查当前 索引集 是否创建过订阅。
       */
      checkReportIsExisted() {
        this.$http
          .request('newReport/getExistReports/', {
            query: {
              scenario: 'clustering',
              bk_biz_id: this.$route.query.bizId,
              index_set_id: this.$route.params.indexId,
            },
          })
          .then(response => {
            this.isCurrentIndexSetIdCreateSubscription = !!response.data.length;
          })
          .catch(console.log);
      },
      /**
       * 空方法 checkReportIsExisted 的 debounce 版。
       */
      checkReportIsExistedDebounce() {},
      /**
       * 打开 我的订阅 全局弹窗
       */
      goToMySubscription() {
        window.bus.$emit('showGlobalDialog');
      },
    },
  };
</script>
<style lang="scss" scoped>
  @import '@/scss/mixins/flex.scss';

  .fingerprint-setting {
    flex-shrink: 0;
    height: 32px;
    font-size: 12px;
    line-height: 24px;

    .is-near24 {
      margin-right: 20px;
      @include flex-center;

      > span {
        margin-left: 4px;
        line-height: 16px;
        cursor: pointer;
      }
    }

    .pattern {
      width: 200px;
      margin-right: 20px;

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
      padding: 4px 0;
    }

    .compared-select-icon {
      position: absolute;
      top: 3px;
      right: 22px;
      font-size: 14px;
    }

    .customize-option {
      padding: 0 16px;
      cursor: pointer;
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
        font-size: 14px;
        color: #979ba5;
        cursor: pointer;
      }

      .group-alert {
        position: relative;
        padding: 6px 30px;
        margin: 6px 0 14px 0;
        line-height: 20px;
        color: #63656e;
        background: #f0f1f5;
        border-radius: 2px;

        .icon-info {
          position: absolute;
          top: 8px;
          left: 8px;
          font-size: 16px;
          color: #979ba5;
        }
      }

      .year-on-year {
        @include flex-center();
      }

      .compared-select {
        flex: 1;
        margin-left: 20px;
      }

      .popover-button {
        padding: 12px 0;

        @include flex-justify(flex-end);
      }
    }
  }

  .ext-box {
    /* stylelint-disable-next-line declaration-no-important */
    display: flex !important;
    height: 32px;

    @include flex-center();

    :deep(.bk-checkbox-text) {
      width: calc(100% - 20px);
      overflow: hidden;

      /* stylelint-disable-next-line declaration-no-important */
      font-size: 12px !important;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .disabled-icon {
    cursor: not-allowed;
    background-color: #fff;
    border-color: #dcdee5;

    &:hover,
    .bklog-icon {
      color: #c4c6cc;
      border-color: #dcdee5;
    }
  }

  .operation-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    cursor: pointer;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    outline: none;
    transition: boder-color 0.2s;

    &:hover {
      border-color: #979ba5;
      transition: boder-color 0.2s;
    }

    &:active {
      border-color: #3a84ff;
      transition: boder-color 0.2s;
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
    margin-right: 20px;
    font-size: 14px;
    color: #63656e;
    cursor: pointer;
    border-radius: 2px;

    &.selected {
      color: #3a84ff;
    }

    &:hover {
      background: #f0f1f5;
    }

    &:active {
      background-color: #e1ecff;
    }
  }
</style>
./quick-create-subscription-drawer/quick-create-subscription.jsx
