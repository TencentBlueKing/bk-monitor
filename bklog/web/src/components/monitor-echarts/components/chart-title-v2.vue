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
  <div class="title-wrapper-new">
    <div
      ref="chartTitle"
      class="chart-title"
      tabindex="0"
    >
      <div class="main-title">
        <div
          class="title-click"
          @click.stop="handleShowMenu"
        >
          <span
            class="bk-icon icon-down-shape"
            :class="{ 'is-flip': isFold }"
          ></span>
          <div class="title-name">{{ title }}</div>
          <i18n
            class="time-result"
            path="（找到 {0} 条结果，用时 {1} 毫秒) {2}"
          >
            <span class="total-count">{{ getShowTotalNum(totalCount) }}</span>
            <span>{{ tookTime }}</span>
          </i18n>
        </div>
        <div
          v-if="!isFold"
          class="converge-cycle"
          @click.stop
        >
          <span>{{ $t('汇聚周期') + ':' }}</span>
          <bk-select
            ext-cls="select-custom"
            v-model="chartInterval"
            :clearable="false"
            behavior="simplicity"
            data-test-id="generalTrendEcharts_div_selectCycle"
            size="small"
            @change="handleIntervalChange"
          >
            <bk-option
              v-for="option in intervalArr"
              :id="option.id"
              :key="option.id"
              :name="option.name"
            >
            </bk-option>
          </bk-select>

          <span
            class="bklog-icon bklog-shezhi"
            @click="handleSettingClick"
          ></span>
          <div style="display: none">
            <div
              ref="refSettingContext"
              class="bklog-v3-grade-setting"
            >
              <div class="grade-title">{{ $t('分级设置') }}</div>
              <div class="grade-row">
                <div class="grade-label required">{{ $t('字段设置') }}</div>
                <div class="grade-field-setting">
                  <bk-select
                    v-model="gradeValue"
                    style="width: 240px"
                    searchable
                    :readonly="true"
                  >
                    <bk-option
                      v-for="option in gradeCategory"
                      :key="option.id"
                      :id="option.id"
                      :name="option.name"
                    >
                    </bk-option>
                  </bk-select>
                  <template v-if="gradeValue === 'custom'">
                    <bk-select
                      v-model="gradeFieldValue"
                      style="width: 320px; margin-left: 10px"
                      searchable
                    >
                      <bk-option
                        v-for="option in fieldList"
                        :key="option.field_name"
                        :id="option.field_name"
                        :name="`${option.field_name}(${option.field_alias || option.field_name})`"
                      >
                      </bk-option>
                    </bk-select>
                  </template>
                </div>
              </div>
              <div class="grade-row">
                <div class="grade-label">{{ $t('字段列表') }}</div>
                <div class="grade-table">
                  <div class="grade-table-header">
                    <div
                      class="grade-table-col"
                      style="width: 64px"
                    >
                      颜色
                    </div>
                    <div
                      class="grade-table-col"
                      style="width: 177px"
                    >
                      字段定义
                    </div>
                    <div
                      class="grade-table-col"
                      style="width: 330px"
                    >
                      正则表达式
                    </div>
                  </div>
                  <div class="grade-table-body">
                    <template v-for="item in gradeSettingList">
                      <div
                        :class="['grade-table-row', { readonly: item.id === 'others' }]"
                        :key="item.id"
                      >
                        <div
                          class="grade-table-col"
                          style="width: 64px"
                        >
                          <span
                            :style="{
                              width: '16px',
                              height: '16px',
                              background: item.color,
                              borderRadius: '1px',
                            }"
                          ></span>
                          <template v-if="item.id !== 'others' && false">
                            <bk-select
                              v-model="item.color"
                              style="width: 32px"
                              size="small"
                              behavior="simplicity"
                              class="bklog-v3-grade-color-select"
                              ext-popover-cls="bklog-v3-grade-color-list"
                              :clearable="false"
                            >
                              <bk-option
                                v-for="option in colorList"
                                :key="option.id"
                                :id="option.name"
                                :name="option.name"
                              >
                                <div
                                  :style="{
                                    width: '100%',
                                    height: '16px',
                                    background: option.name,
                                  }"
                                ></div>
                              </bk-option>
                            </bk-select>
                          </template>
                        </div>
                        <div
                          class="grade-table-col"
                          style="width: 177px"
                        >
                          {{ item.name }}
                        </div>
                        <div
                          class="grade-table-col"
                          style="width: 330px"
                        >
                          {{ item.regExp }}
                        </div>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
              <div class="grade-row grade-footer">
                <bk-button
                  theme="primary"
                  style="width: 64px; height: 32px; margin-right: 8px"
                  @click="handleSaveGradeSettingClick"
                >
                  {{ $t('确定') }}
                </bk-button>
                <bk-button
                  theme="default"
                  style="width: 64px; height: 32px"
                  @click="handleSaveGradeSettingClick"
                >
                  {{ $t('取消') }}
                </bk-button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div
        v-if="subtitle"
        class="sub-title"
      >
        {{ subtitle }}
      </div>
    </div>
    <bk-spin
      v-if="loading && !isFold"
      class="chart-spin"
    ></bk-spin>
  </div>
</template>

<script lang="ts">
  import { Component, Vue, Prop, Ref, Watch } from 'vue-property-decorator';
  import { formatNumberWithRegex } from '@/common/util';
  import PopInstanceUtil from '../../../global/pop-instance-util';
  import ChartMenu from './chart-menu.vue';

  @Component({
    name: 'chart-title-v2',
    components: {
      ChartMenu,
    },
  })
  export default class ChartTitle extends Vue {
    @Prop({ default: '' }) title: string;
    @Prop({ default: '' }) subtitle: string;
    @Prop({ default: () => [] }) menuList: string[];
    @Prop({ default: localStorage.getItem('chartIsFold') === 'true' }) isFold: boolean;
    @Prop({ default: true }) loading: boolean;
    @Prop({ default: true }) isEmptyChart: boolean;
    @Prop({ required: true }) totalCount: number;
    @Ref('chartTitle') chartTitleRef: HTMLDivElement;

    chartInterval = 'auto';
    intervalArr = [
      { id: 'auto', name: 'auto' },
      { id: '1m', name: '1 min' },
      { id: '5m', name: '5 min' },
      { id: '1h', name: '1 h' },
      { id: '1d', name: '1d' },
    ];

    /**
     * 分级类别
     */
    gradeCategory = [
      {
        id: 'normal',
        name: '默认配置',
      },
      {
        id: 'custom',
        name: '自定义',
      },
    ];

    colorList = [
      { id: 'error', name: '#F59789' },
      { id: 'warn', name: '#F5C78E' },
      { id: 'info', name: '#6FC5BF' },
      { id: 'debug', name: '#92D4F1' },
      { id: 'trace', name: '#DCDEE5' },
    ];

    gradeValue = 'normal';

    /**
     * 分级字段
     */
    gradeFieldValue = null;

    settingInstance = new PopInstanceUtil({
      refContent: () => this.$refs.refSettingContext as HTMLElement,
      tippyOptions: {
        appendTo: document.body,
        hideOnClick: true,
      },
    });

    gradeSettingList = [
      {
        id: 'error',
        color: '#F59789',
        name: 'error',
        regExp: 'err*',
      },
      {
        id: 'warn',
        color: '#F5C78E',
        name: 'warn',
        regExp: 'warn*',
      },
      {
        id: 'info',
        color: '#6FC5BF',
        name: 'info',
        regExp: 'info*',
      },
      {
        id: 'debug',
        color: '#92D4F1',
        name: 'debug',
        regExp: 'debug*',
      },
      {
        id: 'trace',
        color: '#DCDEE5',
        name: 'trace',
        regExp: 'trace*',
      },
      {
        id: 'others',
        color: '#DCDEE5',
        name: 'others',
        regExp: '--',
      },
    ];

    get retrieveParams() {
      return this.$store.getters.retrieveParams;
    }

    get tookTime() {
      return Number.parseFloat(this.$store.state.tookTime).toFixed(0);
    }

    get fieldList() {
      return this.$store.state.indexFieldInfo.fields ?? [];
    }

    @Watch('retrieveParams.interval')
    watchChangeChartInterval(newVal) {
      this.chartInterval = newVal;
    }

    handleShowMenu(e: MouseEvent) {
      this.$emit('toggle-expand', !this.isFold);

      // this.showMenu = !this.showMenu
      // const rect = this.chartTitleRef.getBoundingClientRect()
      // this.menuLeft = rect.width  - 185 < e.layerX ? rect.width  - 185 : e.layerX
    }
    getShowTotalNum(num) {
      return formatNumberWithRegex(num);
    }
    handleMenuClick(item) {
      this.$emit('menu-click', item);
    }
    // 汇聚周期改变
    handleIntervalChange() {
      this.$emit('interval-change', this.chartInterval);
    }

    handleSettingClick(e) {
      this.settingInstance?.show(e.target);
    }

    handleSaveGradeSettingClick() {
      this.settingInstance?.hide();
    }

    handleGradeColorChange(item, args) {
      console.log(item, args);
    }
  }
</script>
<style lang="scss" scoped>
  .title-wrapper-new {
    position: relative;
    z-index: 999;
    flex: 1;
    width: 100%;

    .converge-cycle {
      display: flex;
      align-items: center;
      margin-left: 14px;
      font-size: 12px;
      font-weight: normal;
      color: #4d4f56;

      .select-custom {
        display: inline-block;
        margin-left: 5px;
        vertical-align: middle;
        border: none;
        color: #313238;
        :deep(.bk-select-name) {
          padding: 0 26px 0 16px;
        }
      }

      .bklog-icon {
        cursor: pointer;
        font-size: 14px;
        padding: 1px;
      }
    }

    .chart-title {
      padding: 0 10px;
      margin-left: -10px;
      font-size: 12px;
      color: #4d4f56;
      border-radius: 2px;

      .title-click {
        display: flex;
        flex-wrap: nowrap;
        align-items: center;
        cursor: pointer;
      }

      .main-title {
        display: flex;
        flex-wrap: nowrap;
        align-items: center;
        justify-content: space-between;
        height: 24px;

        .title-name {
          height: 20px;
          overflow: hidden;
          font-weight: 700;
          line-height: 20px;
          text-overflow: ellipsis;
          white-space: nowrap;
          color: #313238;
          font-family: MicrosoftYaHei-Bold;
        }

        .time-result {
          .total-count {
            color: #f00;
          }
        }

        .icon-down-shape {
          margin-right: 8px;
          transition: transform 0.3s;

          &.is-flip {
            transition: transform 0.3s;
            transform: rotate(-90deg);
          }
        }

        // &::after {
        //   /* stylelint-disable-next-line declaration-no-important */
        //   font-family: 'icon-monitor' !important;
        //   content: '\e61c';
        //   font-size: 20px;
        //   width: 24px;
        //   height: 16px;
        //   align-items: center;
        //   justify-content: center;
        //   color: #979ba5;
        //   margin-right: auto;
        //   display: none;
        // }
      }

      .sub-title {
        height: 16px;
        overflow: hidden;
        line-height: 16px;
        color: #979ba5;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .menu-list {
      position: absolute;
      top: 0;
      right: 36px;

      .bklog-icon {
        font-size: 14px;
        color: #979ba5;
        cursor: pointer;
      }
    }

    .chart-spin {
      position: absolute;
      top: 27px;
      right: 36px;
    }
  }
</style>
<style lang="scss">
  .bklog-v3-grade-setting {
    width: 736px;
    background: #ffffff;
    border: 1px solid #dcdee5;
    box-shadow: 0 2px 6px 0 #0000001a;
    border-radius: 2px;
    padding: 16px 0 0 0;

    .grade-title {
      height: 24px;
      font-size: 16px;
      color: #313238;
      line-height: 24px;
      padding: 0 24px;
    }

    .grade-row {
      padding: 0 24px;
      display: flex;
      align-items: flex-start;
      margin-top: 16px;

      .grade-label {
        padding-right: 8px;
        font-size: 12px;
        color: #4d4f56;
        text-align: left;
        line-height: 20px;
        margin-right: 8px;
        height: 32px;
        display: flex;
        align-items: center;

        &.required {
          position: relative;

          &::after {
            content: '*';
            color: #ea3636;
            position: absolute;
            right: 0px;
            top: 8px;
          }
        }
      }

      .grade-field-setting {
        display: flex;
      }

      .grade-table {
        border-top: 1px solid #dcdee5;
        border-left: 1px solid #dcdee5;

        .grade-table-header {
          background: #f0f1f5;
          display: flex;
        }

        .grade-table-col {
          height: 42px;
          border-right: 1px solid #dcdee5;
          border-bottom: 1px solid #dcdee5;
          padding: 8px;
          display: flex;
          align-items: center;
        }

        .grade-table-row {
          display: flex;

          &.readonly {
            background: #fafbfd;

            .grade-table-col {
              color: #979ba5;
              cursor: not-allowed;
            }
          }
        }
      }

      &.grade-footer {
        height: 48px;
        background: #fafbfd;
        box-shadow: 0 -1px 0 0 #dcdee5;
        padding: 8px 24px;
        display: flex;
        justify-content: flex-end;
      }
    }
  }

  .bklog-v3-grade-color-select {
    border: none;
    .bk-select-name {
      visibility: hidden;
    }
  }

  .bklog-v3-grade-color-list {
    .bk-options-wrapper {
      .bk-options {
        &.bk-options-single {
          .bk-option {
            .bk-option-content {
              padding: 2px;
            }
          }
        }
      }
    }
  }
</style>
