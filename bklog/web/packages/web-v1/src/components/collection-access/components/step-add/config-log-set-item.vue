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
  <div v-if="scenarioId !== 'wineventlog'">
    <bk-form
      ref="validateForm"
      :form-type="showType"
      :label-width="labelWidth"
      :model="subFormData"
    >
      <div>
        <!-- 段日志正则调试 -->
        <div
          v-if="hasMultilineReg"
          class="multiline-log-container mt"
        >
          <div class="row-container">
            <bk-form-item
              :label="$t('行首正则')"
              :rules="rules.notEmptyForm"
              property="params.multiline_pattern"
              required
            >
              <div class="flex-ac">
                <bk-input
                  style="width: 320px"
                  v-model.trim="subFormData.params.multiline_pattern"
                  data-test-id="sourceLogBox_input_beginningRegular"
                ></bk-input>
                <bk-button
                  class="king-button"
                  data-test-id="sourceLogBox_button_debugging"
                  size="small"
                  text
                  @click="showRegDialog = true"
                >
                  {{ $t('调试') }}
                </bk-button>
              </div>
            </bk-form-item>
          </div>
          <div :class="['row-container', 'second', showType === 'horizontal' && 'ml115']">
            <i18n
              class="i18n-style"
              path="最多匹配{0}行，最大耗时{1}秒"
            >
              <bk-form-item
                :rules="rules.maxLine"
                property="params.multiline_max_lines"
              >
                <bk-input
                  v-model="subFormData.params.multiline_max_lines"
                  :precision="0"
                  :show-controls="false"
                  data-test-id="sourceLogBox_input_mostMatches"
                  type="number"
                >
                </bk-input>
              </bk-form-item>
              <bk-form-item
                :rules="rules.maxTimeout"
                property="params.multiline_timeout"
              >
                <bk-input
                  v-model="subFormData.params.multiline_timeout"
                  :precision="0"
                  :show-controls="false"
                  data-test-id="sourceLogBox_input_maximumTimeConsuming"
                  type="number"
                >
                </bk-input>
              </bk-form-item>
            </i18n>
          </div>
          <multiline-reg-dialog
            :old-pattern.sync="subFormData.params.multiline_pattern"
            :show-dialog.sync="showRegDialog"
          >
          </multiline-reg-dialog>
        </div>
        <template v-if="!isStandardOutput">
          <!-- 日志路径 -->
          <div
            v-for="(log, index) in logPaths"
            class="form-div mt log-paths"
            :key="index"
          >
            <bk-form-item
              :label="index === 0 ? $t('日志路径') : ''"
              :property="'params.paths.' + index + '.value'"
              :rules="rules.paths"
              required
            >
              <div class="log-path flex-ac">
                <bk-input
                  v-model="log.value"
                  data-test-id="sourceLogBox_input_addLogPath"
                />
                <div class="ml9">
                  <i
                    class="bk-icon icon-plus-circle-shape icons"
                    data-test-id="sourceLogBox_i_newAddLogPath"
                    @click="addLog('paths')"
                  />
                  <i
                    :class="['bk-icon icon-minus-circle-shape icons ml9', { disable: logPaths.length === 1 }]"
                    data-test-id="sourceLogBox_i_deleteAddLogPath"
                    @click="delLog(index, 'paths')"
                  />
                </div>
              </div>
              <div
                v-if="index === 0"
                :class="['tips', showType !== 'horizontal' && 'log-tips']"
              >
                <i18n path="日志文件的绝对路径，可使用 {0}">
                  <span class="font-gray">{{ $t('通配符') }}</span>
                </i18n>
              </div>
            </bk-form-item>
          </div>
          <!-- 路径黑名单 -->
          <div
            v-en-class="'en-span'"
            :class="['filter-content black-content', showType !== 'horizontal' && 'black-hori-title']"
          >
            <div class="black-list-title">
              <div
                class="list-title-btn"
                @click="isShowBlackList = !isShowBlackList"
              >
                <i :class="['bk-icon icon-play-shape', isShowBlackList && 'icon-rotate']"></i>
                <span>{{ $t('路径黑名单') }}</span>
              </div>
              <div class="black-title-tips">
                <i class="bk-icon icon-info-circle"></i>
                <span>
                  {{ $t('可通过正则语法排除符合条件的匹配项') }}   
                  <!-- <a
                    href="javascript:;"
                    @click.stop="()=>{}"
                  >
                    {{ $t('正则语法说明') }}
                  </a> -->
                  {{ $t('。如：匹配任意字符：.*')}}</span>
              </div>
            </div>
            <template v-if="isShowBlackList">
              <div
                v-for="(log, index) in blackLogListPaths"
                :class="['form-div log-paths', !!index && 'mt']"
                :key="index"
              >
                <bk-form-item
                  :property="'params.exclude_files.' + index + '.value'"
                  label=""
                  required
                >
                  <div class="log-path flex-ac">
                    <bk-input
                      v-model="log.value"
                      data-test-id="sourceLogBox_input_addLogPath"
                    ></bk-input>
                    <div class="ml9">
                      <i
                        class="bk-icon icon-plus-circle-shape icons"
                        data-test-id="sourceLogBox_i_newAddLogPath"
                        @click="addLog('exclude_files')"
                      ></i>
                      <i
                        :class="[
                          'bk-icon icon-minus-circle-shape icons ml9',
                          { disable: blackLogListPaths.length === 1 },
                        ]"
                        data-test-id="sourceLogBox_i_deleteAddLogPath"
                        @click="delLog(index, 'exclude_files')"
                      ></i>
                    </div>
                  </div>
                </bk-form-item>
              </div>
            </template>
          </div>
          <!-- 日志字符集 -->
          <bk-form-item
            class="mt"
            :label="$t('字符集')"
            required
          >
            <bk-select
              style="width: 320px"
              v-model="subFormData.data_encoding"
              :clearable="false"
              data-test-id="sourceLogBox_div_changeLogCharacterTet"
              searchable
            >
              <bk-option
                v-for="(option, ind) in globalsData.data_encoding"
                :id="option.id"
                :key="ind"
                :name="option.name"
              >
              </bk-option>
            </bk-select>
          </bk-form-item>
        </template>
        <!-- 日志过滤 -->
        <bk-form-item
          class="mt"
          :label="$t('日志过滤')"
          required
        >
          <log-filter
            ref="logFilterRef"
            :conditions="subFormData.params.conditions"
            :conditions-change.sync="subFormData.params.conditions"
            :is-clone-or-update="isCloneOrUpdate"
          />
        </bk-form-item>
        <bk-form-item
          v-if="currentEnvironment == 'linux' || currentEnvironment == 'windows'"
          class="mt"
          :label="$t('设备元数据')"
          required
        >
          <device-metadata
            ref="deviceMetadataRef"
            :metadata="configData.extra_labels"
            @extra-labels-change="extraLabelsChange"
          >
          </device-metadata>
        </bk-form-item>
      </div>
    </bk-form>
  </div>
  <!-- win event日志类型 -->
  <div v-else>
    <!-- 日志种类 -->
    <bk-form
      ref="validateForm"
      class="mt"
      :form-type="showType"
      :label-width="labelWidth"
      :model="subFormData"
    >
      <bk-form-item
        :label="$t('日志种类')"
        data-test-id="sourceLogBox_div_logSpecies"
        required
      >
        <bk-checkbox-group
          v-model="selectLogSpeciesList"
          @change="otherBlurRules"
        >
          <div class="species-item">
            <bk-checkbox
              v-for="(item, index) in logSpeciesList"
              :disabled="selectLogSpeciesList.length === 1 && selectLogSpeciesList[0] === item.id"
              :key="index"
              :value="item.id"
            >
              {{ item.name }}
            </bk-checkbox>
            <bk-tag-input
              v-model="otherSpeciesList"
              :allow-auto-match="true"
              :allow-create="true"
              :class="otherRules ? 'tagRulesColor' : ''"
              :has-delete-icon="true"
              free-paste
              @blur="otherBlurRules"
              @remove="otherBlurRules"
            >
            </bk-tag-input>
          </div>
        </bk-checkbox-group>
      </bk-form-item>
    </bk-form>
    <!-- win-过滤内容 -->
    <div
      v-en-class="'en-span'"
      :class="['config-item', 'mt', showType === 'horizontal' && 'win-content']"
    >
      <span v-bk-tooltips="$t('为减少传输和存储成本，可以过滤掉部分内容,更复杂的可在“清洗”功能中完成')">
        <span class="filter-title">{{ $t('过滤内容') }}</span>
      </span>
      <div
        v-for="(item, index) in eventSettingList"
        class="form-div win-filter"
        :key="index"
      >
        <bk-select
          class="select-div"
          v-model="item.type"
          :clearable="false"
          @selected="tagBlurRules(item, index)"
        >
          <bk-option
            v-for="option in selectEventList"
            :disabled="option.isSelect"
            :id="option.id"
            :key="option.id"
            :name="option.name"
          >
          </bk-option>
        </bk-select>
        <bk-tag-input
          v-model="item.list"
          :class="{
            'tag-input': true,
            tagRulesColor: !item.isCorrect,
          }"
          :paste-fn="v => pasteFn(v, index)"
          allow-auto-match
          allow-create
          has-delete-icon
          @blur="tagBlurRules(item, index)"
          @remove="tagBlurRules(item, index)"
        >
        </bk-tag-input>
        <div class="ml9">
          <i
            :class="[
              'bk-icon icon-plus-circle-shape icons',
              {
                disable: eventSettingList.length === selectEventList.length,
              },
            ]"
            @click="addWinEvent"
          ></i>
          <i
            :class="['bk-icon icon-minus-circle-shape icons ml9', { disable: eventSettingList.length === 1 }]"
            @click="delWinEvent(index)"
          ></i>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
  import { mapGetters } from 'vuex';

  import LogFilter from '../log-filter';
  import MultilineRegDialog from './multiline-reg-dialog';
  import DeviceMetadata from './device-metadata.vue';
  export default {
    components: {
      MultilineRegDialog,
      LogFilter,
      DeviceMetadata,
    },
    props: {
      showType: {
        type: String,
        default: 'horizontal',
      },
      configData: {
        type: Object,
        required: true,
      },
      scenarioId: {
        type: String,
        required: true,
      },
      currentEnvironment: {
        type: String,
        require: true,
      },
      configLength: {
        type: Number,
        default: 0,
      },
      configChangeLength: {
        type: Number,
        require: true,
      },
      isCloneOrUpdate: {
        type: Boolean,
        require: true,
      },
      enLabelWidth: {
        type: Number,
        default: 180,
      },
    },
    data() {
      return {
        rules: {
          paths: [
            // 日志路径
            {
              required: true,
              trigger: 'change',
            },
          ],
          notEmptyForm: [
            // 不能为空的表单
            {
              required: true,
              trigger: 'blur',
            },
          ],
          maxLine: [
            // 最多匹配行数
            {
              validator: val => {
                if (val > 5000) {
                  this.formData.params.multiline_max_lines = '5000';
                } else if (val < 1) {
                  this.formData.params.multiline_max_lines = '1';
                }
                return true;
              },
              trigger: 'blur',
            },
          ],
          maxTimeout: [
            // 最大耗时
            {
              validator: val => {
                if (val > 10) {
                  this.formData.params.multiline_timeout = '10';
                } else if (val < 1) {
                  this.formData.params.multiline_timeout = '1';
                }
                return true;
              },
              trigger: 'blur',
            },
          ],
        },
        subFormData: {
          data_encoding: 'UTF-8', // 日志字符集
          params: {
            multiline_pattern: '', // 行首正则, char
            multiline_max_lines: '50', // 最多匹配行数, int
            multiline_timeout: '2', // 最大耗时, int
            paths: [
              // 日志路径
              { value: '' },
            ],
            exclude_files: [
              // 日志黑名单路径
              { value: '' },
            ],
            conditions: {
              type: 'none', // 过滤方式类型
              match_type: 'include', // 过滤方式 可选字段 include, exclude
              match_content: '',
              separator: '|',
              separator_filters: [
                // 分隔符过滤条件
                { fieldindex: '', word: '', op: '=', logic_op: 'and' },
              ],
            },
            winlog_name: [], // windows事件名称
            winlog_level: [], // windows事件等级
            winlog_event_id: [], // windows事件id
            extra_labels: [], // 补充元数据
          },
        },
        type: 'and',
        showRegDialog: false, // 显示段日志调试弹窗
        otherRules: false, // 是否有其他规则
        logSpeciesList: [
          {
            id: 'Application',
            name: this.$t('应用程序(Application)'),
          },
          {
            id: 'Security',
            name: this.$t('安全(Security)'),
          },
          {
            id: 'System',
            name: this.$t('系统(System)'),
          },
          {
            id: 'Other',
            name: this.$t('其他'),
          },
        ],
        selectLogSpeciesList: ['Application', 'Security', 'System', 'Other'],
        otherSpeciesList: [],
        selectEventList: [
          {
            id: 'winlog_event_id',
            name: this.$t('事件ID'),
            isSelect: false,
          },
          {
            id: 'winlog_level',
            name: this.$t('级别'),
            isSelect: false,
          },
          {
            id: 'winlog_source',
            name: this.$t('事件来源'),
            isSelect: false,
          },
          {
            id: 'winlog_content',
            name: this.$t('事件内容'),
            isSelect: false,
          },
        ],
        eventSettingList: [{ type: 'winlog_event_id', list: [], isCorrect: true }],
        isShowBlackList: false,
      };
    },
    computed: {
      ...mapGetters('globals', ['globalsData']),
      // 是否打开行首正则功能
      hasMultilineReg() {
        return this.scenarioId === 'section';
      },
      // 日志路径
      logPaths() {
        return this.subFormData.params.paths || [];
      },
      blackLogListPaths() {
        return this.subFormData.params?.exclude_files || [];
      },
      labelWidth() {
        return this.$store.state.isEnLanguage ? this.enLabelWidth : 115;
      },
      // 是否是标准输出
      isStandardOutput() {
        return this.currentEnvironment === 'std_log_config';
      },
      // win日志类型是否有报错
      winCannotPass() {
        return this.eventSettingList.some(el => el.isCorrect === false) || this.otherRules;
      },
      getWinParamsData() {
        // wineventlog日志类型时进行params属性修改
        const winParams = {};
        const { selectLogSpeciesList, otherSpeciesList, eventSettingList } = this;
        const cloneSpeciesList = structuredClone(selectLogSpeciesList);
        if (cloneSpeciesList.includes('Other')) {
          cloneSpeciesList.splice(cloneSpeciesList.indexOf('Other'), 1);
        }
        winParams.winlog_name = cloneSpeciesList.concat(otherSpeciesList);
        eventSettingList.forEach(el => {
          winParams[el.type] = el.list;
        });
        return winParams;
      },
    },
    watch: {
      subFormData: {
        deep: true,
        handler(val) {
          const { data_encoding, params } = val;
          this.$emit('config-change', { data_encoding, params });
        },
      },
      configLength() {
        this.assignSubData(this.configData);
      },
      configChangeLength() {
        this.initConfigLogSet();
      },
    },
    mounted() {
      (this.isCloneOrUpdate || this.configChangeLength > 0) && this.initConfigLogSet();
    },
    methods: {
      initPathList(params, type = 'paths') {
        if (params[type]?.length > 0) {
          params[type] =
            typeof params[type][0] === 'string' ? params[type].map(item => ({ value: item })) : params[type];
        } else {
          // 兼容原日志路径为空列表
          params[type] = [{ value: '' }];
        }
      },
      addLog(type = 'paths') {
        this.subFormData.params[type].push({ value: '' });
      },
      delLog(index, type = 'paths') {
        if (this.subFormData.params[type].length > 1) {
          this.subFormData.params[type].splice(
            this.subFormData.params[type].findIndex((item, ind) => ind === index),
            1,
          );
        }
      },
      addWinEvent() {
        const eventType = this.eventSettingList.map(el => el.type);
        const selectType = this.selectEventList.map(el => el.id);
        if (eventType.length !== selectType.length) {
          const selectFilter = selectType.filter(v => eventType.indexOf(v) === -1);
          this.eventSettingList.push({ type: selectFilter[0], list: [], isCorrect: true });
          this.selectDisabledChange(true);
        }
      },
      delWinEvent(index) {
        if (this.eventSettingList.length > 1) {
          this.eventSettingList.splice(
            this.eventSettingList.findIndex((el, ind) => index === ind),
            1,
          );
          this.selectDisabledChange(false);
        }
      },
      selectDisabledChange(state = true) {
        if (this.eventSettingList.length === 1) {
          this.selectEventList.forEach(el => (el.isSelect = false));
        }
        if (this.eventSettingList.length === this.selectEventList.length) {
          this.selectEventList.forEach(el => (el.isSelect = true));
        }
        for (const eItem of this.eventSettingList) {
          for (const sItem of this.selectEventList) {
            if (eItem.type === sItem.id) {
              sItem.isSelect = state;
            }
          }
        }
      },
      otherBlurRules(input, tags) {
        if (!tags) return;
        this.otherRules = !tags.every(Boolean);
        tags.length === 0 && (this.otherRules = false);
        const slist = this.selectLogSpeciesList;
        if (slist.length === 1 && slist[0] === 'Other' && !this.otherSpeciesList.length) {
          this.otherRules = true;
        }
      },
      tagBlurRules(item, index) {
        switch (item.type) {
          case 'winlog_event_id':
            this.eventSettingList[index].isCorrect = item.list.every(el => /^[\d]+$/.test(el));
            break;
          case 'winlog_level':
            this.eventSettingList[index].isCorrect = item.list.every(Boolean);
            break;
          default:
            this.eventSettingList[index].isCorrect = true;
            break;
        }
      },
      pasteFn(v, index) {
        const oldEventList = this.eventSettingList[index].list;
        const matchList = v.split(/\n/g); // 根据换行符进行切割
        this.eventSettingList[index].list = oldEventList.concat(matchList);
      },
      assignSubData(assignObj = {}) {
        Object.assign(this.subFormData, assignObj);
      },
      async logFilterValidate() {
        try {
          await this.$refs.validateForm?.validate();
          await this.$refs.logFilterRef?.inputValidate();
          return true;
        } catch (error) {
          return false;
        }
      },
      initConfigLogSet() {
        this.assignSubData(this.configData);
        const { params } = this.subFormData;
        if (this.scenarioId === 'wineventlog') {
          const otherList = params.winlog_name.filter(v => ['Application', 'Security', 'System'].indexOf(v) === -1);
          if (otherList.length > 0) {
            this.otherSpeciesList = otherList;
            this.selectLogSpeciesList = params.winlog_name.filter(v =>
              ['Application', 'Security', 'System'].includes(v),
            );
            this.selectLogSpeciesList.push('Other');
          } else {
            this.selectLogSpeciesList = params.winlog_name;
          }

          delete params.ignore_older;
          delete params.max_bytes;
          delete params.tail_files;

          const newEventSettingList = [];
          const selectStrList = this.selectEventList.map(item => item.id);
          for (const [key, val] of Object.entries(params)) {
            if (selectStrList.includes(key) && val[0] !== '') {
              newEventSettingList.push({
                type: key,
                list: val,
                isCorrect: true,
              });
            }
          }
          if (newEventSettingList.length !== 0) {
            this.eventSettingList = newEventSettingList;
          }
          this.selectDisabledChange();
        }
        this.initPathList(params, 'paths');
        this.initPathList(params, 'exclude_files');
        this.isShowBlackList = params.exclude_files.some(item => !!item.value);
        this.$nextTick(() => {
          this.$refs.logFilterRef?.initContainerData();
        });
      },
      extraLabelsChange(val) {
        this.$set(this.subFormData.params, 'extra_labels', val);
      },
      // 自定义标签表单验证
      async extraLabelsValidate() {
        try {
          await this.$refs.deviceMetadataRef?.extraLabelsValidate();
          return true;
        } catch (error) {
          return false;
        }
      }
    },
  };
</script>
<style lang="scss" scoped>
  @import '@/scss/mixins/flex.scss';

  .filter-content {
    position: relative;
    left: 115px;
    max-width: 80%;
    padding: 20px 0;

    &.en-span {
      left: 180px;

      > span {
        left: -110px;
      }
    }

    .black-list-title {
      margin-bottom: 6px;
      font-size: 12px;

      @include flex-align;

      .list-title-btn {
        color: #3a84ff;
        cursor: pointer;

        @include flex-align;

        i {
          display: inline-block;
          margin-right: 6px;
        }

        .icon-info-circle {
          display: inline-block;
        }

        .icon-rotate {
          transform: rotateZ(90deg);
        }
      }

      .black-title-tips {
        margin-left: 14px;
        color: #63656e;

        .icon-info-circle {
          font-size: 16px;
          color: #979ba5;
        }
      }
    }

    .bk-form-radio {
      font-size: 12px;
    }

    :deep(.bk-form-content) {
      /* stylelint-disable-next-line declaration-no-important */
      margin-left: 0 !important;
    }

    &.black-content {
      padding: 10px 0 0 0;
    }

    &.black-hori-title {
      left: 0;
    }
  }

  .log-path {
    position: relative;

    .bk-form-control {
      width: 320px;
    }
  }

  .log-tips {
    position: absolute;
    top: -30px;
    left: 80px;
  }

  .i18n-style {
    display: flex;
    align-items: center;
  }
</style>
