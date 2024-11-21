<!-- eslint-disable vue/no-deprecated-slot-attribute -->
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
  <div
    class="field-table-container"
    v-bkloading="{ isLoading: isExtracting }"
  >
    <div
      v-if="!isPreviewMode"
      class="field-method-head"
    >
      <!-- <span class="field-method-link fr mr10" @click.stop="isReset = true">{{ 重置 }}</span> -->
      <div :class="{ 'table-setting': true, 'disabled-setting': isSettingDisable || isSetDisabled }">
        <div class="fr form-item-flex bk-form-item">
          <!-- <label class="bk-label has-desc" v-bk-tooltips="$t('确认保留原始日志,会存储在log字段. 其他字段提取内容会进行追加')">
            <span>{{ $t('保留原始日志') }}</span>
          </label> -->
          <div class="bk-form-content">
            <bk-checkbox
              v-if="!isPreviewMode && selectEtlConfig === 'bk_log_json' && retainExtraJsonIsOpen"
              v-model="retainExtraText"
              :checked="false"
              :false-value="false"
              :true-value="true"
              @change="handleKeepField"
            >
              <span
                style="margin-right: 20px; line-height: 30px"
                class="bk-label"
                >{{ $t('保留未定义字段') }}</span
              >
            </bk-checkbox>
            <!-- <bk-switcher size="small" theme="primary" v-model="retainOriginalText"></bk-switcher> -->
          </div>
        </div>
        <!-- <bk-switcher
          size="small"
          theme="primary"
          class="visible-deleted-btn"
          v-model="deletedVisible"
          @change="visibleHandle">
        </bk-switcher> -->
        <span
          :class="`bk-icon toggle-icon icon-${deletedVisible ? 'eye-slash' : 'eye'}`"
          data-test-id="fieldExtractionBox_span_hideItem"
          @click="visibleHandle"
        >
        </span>
        <span class="visible-deleted-text">
          {{ $t('已隐藏 {n} 项', { n: deletedNum }) }}
        </span>
      </div>
    </div>

    <div class="preview-panel-left">
      <bk-form
        ref="fieldsForm"
        :label-width="0"
        :model="formData"
      >
        <bk-table
          class="field-table"
          :class="!isPreviewMode ? 'add-field-table' : ''"
          :data="changeTableList"
          :empty-text="$t('暂无内容')"
          row-key="field_index"
          size="small"
          col-border
        >
          <template>
            <bk-table-column
              v-if="!isPreviewMode && extractMethod === 'bk_log_delimiter'"
              width="40"
              :resizable="false"
              align="center"
              label=""
            >
              <template #default="props">
                <span>{{ props.row.field_index }}</span>
              </template>
            </bk-table-column>
            <!-- 字段名 -->
            <bk-table-column
              :label="$t('字段名')"
              :render-header="$renderHeader"
              :resizable="false"
              min-width="100"
            >
              <template #default="props">
                <div
                  v-if="isPreviewMode"
                  class="overflow-tips"
                  v-bk-overflow-tips
                >
                  <span>{{ props.row.field_name }}</span>
                </div>
                <bk-form-item
                  v-else
                  :class="{ 'is-required is-error': props.row.fieldErr }"
                >
                  <bk-input
                    class="participle-disabled-input"
                    v-model.trim="props.row.field_name"
                    :disabled="getFieldEditDisabled(props.row)"
                    @blur="checkFieldNameItem(props.row)"
                  ></bk-input>
                  <template v-if="props.row.fieldErr">
                    <i
                      style="right: 8px"
                      class="bk-icon icon-exclamation-circle-shape tooltips-icon"
                      v-bk-tooltips.top="props.row.fieldErr"
                    >
                    </i>
                  </template>
                </bk-form-item>
              </template>
            </bk-table-column>
            <!-- 重命名 -->
            <bk-table-column
              :render-header="renderHeaderAliasName"
              :resizable="false"
              min-width="100"
            >
              <template #default="props">
                <div
                  v-if="isPreviewMode"
                  class="overflow-tips"
                  v-bk-overflow-tips
                >
                  <span>{{ props.row.alias_name }}</span>
                </div>
                <bk-form-item
                  v-else
                  :class="{ 'is-required is-error': props.row.aliasErr }"
                >
                  <bk-input
                    v-model.trim="props.row.alias_name"
                    :disabled="props.row.is_delete || isSetDisabled"
                    @blur="checkAliasNameItem(props.row)"
                  >
                  </bk-input>
                  <template v-if="props.row.aliasErr">
                    <i
                      style="right: 8px"
                      class="bk-icon icon-exclamation-circle-shape tooltips-icon"
                      v-bk-tooltips.top="props.row.aliasErr"
                    ></i>
                  </template>
                </bk-form-item>
              </template>
            </bk-table-column>
            <!-- 字段说明 -->
            <!-- <bk-table-column
              :render-header="renderHeaderDescription"
              :resizable="false"
              min-width="100"
            >
              <template #default="props">
                <div
                  v-if="isPreviewMode"
                  class="overflow-tips"
                  v-bk-overflow-tips
                >
                  <span>{{ props.row.description }}</span>
                </div>
                <bk-input
                  v-else
                  v-model.trim="props.row.description"
                  :disabled="props.row.is_delete || isSetDisabled"
                ></bk-input>
              </template>
            </bk-table-column> -->
            <!-- 类型 -->
            <bk-table-column
              :label="$t('类型')"
              :render-header="$renderHeader"
              :resizable="false"
              min-width="100"
            >
              <template #default="props">
                <div
                  v-if="isPreviewMode"
                  class="overflow-tips"
                  v-bk-overflow-tips
                >
                  <span>{{ props.row.field_type }}</span>
                </div>
                <!-- <bk-form-item v-else
                  :required="true"
                  :rules="props.row.is_delete ? notCheck : rules.field_type"
                  :property="'tableList.' + props.$index + '.field_type'">
                  <bk-select
                    :clearable="false"
                    :disabled="props.row.is_delete"
                    v-model="props.row.field_type"
                    @selected="(value) => {
                      fieldTypeSelect(value, props.row, props.$index)
                    }">
                    <bk-option v-for="option in globalsData.field_data_type"
                      :key="option.id"
                      :id="option.id"
                      :name="option.name">
                    </bk-option>
                  </bk-select>
                </bk-form-item> -->
                <!-- 替代方案 -->
                <!-- <bk-form-item v-else
                :class="{ 'is-required is-error': props.row.typeErr }"
                 :rules="props.row.is_delete ? notCheck : rules.field_type"
                 :property="'tableList.' + props.$index + '.field_type'"> -->
                <bk-form-item
                  v-else
                  :class="{ 'is-required is-error': props.row.typeErr }"
                >
                  <bk-select
                    v-model="props.row.field_type"
                    :clearable="false"
                    :disabled="props.row.is_delete || isSetDisabled"
                    @selected="
                      value => {
                        fieldTypeSelect(value, props.row, props.$index);
                      }
                    "
                  >
                    <bk-option
                      v-for="option in globalsData.field_data_type"
                      :disabled="isTypeDisabled(props.row, option)"
                      :id="option.id"
                      :key="option.id"
                      :name="option.name"
                    >
                    </bk-option>
                  </bk-select>
                  <template v-if="props.row.typeErr">
                    <i
                      style="right: 8px"
                      class="bk-icon icon-exclamation-circle-shape tooltips-icon"
                      v-bk-tooltips.top="$t('必填项')"
                    ></i>
                  </template>
                </bk-form-item>
              </template>
            </bk-table-column>
            <!--<bk-table-column :label="聚合" align="center" :resizable="false" width="50">
              <template slot-scope="props">
                <bk-popover v-if="props.row.is_time" :content="$t('时间字段默认设置可以聚合')">
                  <bk-checkbox
                    disabled
                    v-model="props.row.is_dimension">
                  </bk-checkbox>
                </bk-popover>
                <bk-checkbox v-else
                  :disabled="isPreviewMode || props.row.is_delete || props.row.is_analyzed"
                  v-model="props.row.is_dimension">
                </bk-checkbox>
              </template>
            </bk-table-column>-->
            <!-- 字符串类型下才能设置分词， 分词和维度只能选其中一个，且分词和时间不能同时存在, 选定时间后就同时勾选维度-->
            <!-- 分词 -->
            <!-- <bk-table-column
              :render-header="renderHeaderParticipleName"
              :resizable="false"
              :width="getParticipleWidth"
              align="center"
            >
              <template #default="props">
                <bk-checkbox
                  v-model="props.row.is_analyzed"
                  :disabled="getCustomizeDisabled(props.row, 'analyzed')"
                  @change="() => handelChangeAnalyzed(props.row.is_analyzed, props.$index)"
                >
                </bk-checkbox>
              </template>
            </bk-table-column> -->
            <!-- 分词符 -->
            <bk-table-column
              :render-header="renderHeaderParticipleName"
              :resizable="false"
              align="left"
              min-width="200"
            >
              <template #default="props">
                <!-- 预览模式-->
                <template v-if="isPreviewMode">
                  <template v-if="props.row.is_analyzed">
                    <div>
                      {{ props.row.participleState === 'custom' ? props.row.tokenize_on_chars : '自然语言分词' }}；
                      {{ $t('大小写敏感') }}: {{ props.row.is_case_sensitive ? '是' : '否' }}
                    </div>
                  </template>
                  <div v-else>{{ $t('不分词') }}</div>
                </template>
                <template v-else>
                  <div v-if="props.row.field_type === 'string'">
                    <bk-popconfirm
                      class="participle-popconfirm"
                      :is-show="isShowParticiple"
                      trigger="click"
                      @confirm="handleConfirmParticiple(props.row, props.$index)"
                    >
                      <div slot="content">
                        <div>
                          <bk-form
                            class="participle-form"
                            :label-width="95"
                            :model="formData"
                          >
                            <bk-form-item
                              :label="$t('分词')"
                              :property="'source_name'"
                            >
                              <bk-switcher
                                v-model="currentIsAnalyzed"
                                :disabled="getCustomizeDisabled(props.row, 'analyzed')"
                                theme="primary"
                                @change="() => handelChangeAnalyzed()"
                              ></bk-switcher>
                            </bk-form-item>
                            <bk-form-item
                              :label="$t('分词符')"
                              :property="'participle'"
                            >
                              <div class="bk-button-group">
                                <bk-button
                                  v-for="option in participleList"
                                  class="participle-btn"
                                  :class="currentParticipleState === option.id ? 'is-selected' : ''"
                                  :data-test-id="`fieldExtractionBox_button_filterMethod${option.id}`"
                                  :disabled="getCustomizeDisabled(props.row)"
                                  :key="option.id"
                                  @click="handleChangeParticipleState(option.id, props.$index)"
                                >
                                  {{ option.name }}
                                </bk-button>
                              </div>
                              <bk-input
                                v-if="currentParticipleState === 'custom'"
                                style="margin-top: 10px"
                                v-model="currentTokenizeOnChars"
                                :disabled="getCustomizeDisabled(props.row)"
                              >
                              </bk-input>
                            </bk-form-item>
                            <bk-form-item
                              :label="$t('大小写敏感')"
                              :property="'is_case_sensitive'"
                            >
                              <bk-switcher
                                v-model="currentIsCaseSensitive"
                                :disabled="getCustomizeDisabled(props.row)"
                                theme="primary"
                              ></bk-switcher>
                            </bk-form-item>
                          </bk-form>
                        </div>
                      </div>
                      <div
                        class="participle-cell-wrap"
                        @click="handlePopover(props.row, props.$index)"
                      >
                        <div
                          v-if="props.row.is_analyzed"
                          style="width: 85%"
                        >
                          <div>
                            {{ props.row.participleState === 'custom' ? props.row.tokenize_on_chars : '自然语言分词' }}
                          </div>
                          <div style="margin-top: -10px">
                            {{ $t('大小写敏感') }}: {{ props.row.is_case_sensitive ? '是' : '否' }}
                          </div>
                        </div>
                        <div
                          v-else
                          style="width: 85%"
                        >
                          {{ $t('不分词') }}
                        </div>
                        <div class="participle-select-icon bk-icon icon-angle-down"></div>
                      </div>
                    </bk-popconfirm>
                  </div>
                  <div v-else>
                    <bk-input
                      class="participle-disabled-input"
                      :placeholder="$t('无需设置')"
                      disabled
                    >
                    </bk-input>
                  </div>
                </template>
              </template>
            </bk-table-column>
            <!-- 操作 -->
            <bk-table-column
              v-if="getOperatorDisabled && !isPreviewMode"
              width="60"
              :label="$t('操作')"
              :render-header="$renderHeader"
              :resizable="false"
              align="center"
              prop="plugin_version"
            >
              <template #default="props">
                <span
                  :style="`color:${isSetDisabled ? '#dcdee5' : '#3a84ff'};`"
                  class="table-link"
                  @click="isDisableOperate(props.row)"
                >
                  {{ props.row.is_delete ? $t('复原') : $t('隐藏') }}
                </span>
              </template>
            </bk-table-column>
            <div
              class="empty-text"
              slot="empty"
            >
              {{ $t('请先选择字段提取模式') }}
            </div>
          </template>
        </bk-table>
      </bk-form>
    </div>

    <div class="preview-panel-right">
      <div class="preview-title preview-item">
        {{ $t('预览（值）') }}
      </div>
      <template v-if="deletedVisible">
        <div
          v-for="(row, index) in hideDeletedTable"
          :style="!isPreviewMode ? { height: '51px', 'line-height': '51px' } : ''"
          class="preview-item"
          :key="index"
          :title="row.value"
        >
          {{ row.value }}
        </div>
      </template>
      <template v-else>
        <div
          v-for="(row, index) in tableList"
          :style="!isPreviewMode ? { height: '51px', 'line-height': '51px' } : ''"
          class="preview-item"
          :key="index"
          :title="row.value"
        >
          {{ row.value }}
        </div>
      </template>
    </div>

    <bk-dialog
      v-model="isReset"
      :title="$t('重置确认')"
      theme="primary"
      @confirm="resetField"
    >
      {{ $t('重置将丢失当前的配置信息，重置为上一次保存的配置内容。确认请继续。') }}
    </bk-dialog>
  </div>
</template>

<script>
  import { mapGetters } from 'vuex';

  export default {
    name: 'FieldTable',
    props: {
      isEditJson: {
        type: Boolean,
        default: undefined,
      },
      tableType: {
        type: String,
        default: 'edit',
      },
      extractMethod: {
        type: String,
        default: 'bk_log_json',
      },
      deletedVisible: {
        type: Boolean,
        default: true,
      },
      // jsonText: {
      //     type: Array
      // },
      fields: {
        type: Array,
        default: () => [],
      },
      isTempField: {
        type: Boolean,
        default: false,
      },
      isExtracting: {
        type: Boolean,
        default: false,
      },
      originalTextTokenizeOnChars: {
        type: String,
        default: '',
      },
      retainExtraJson: {
        type: Boolean,
        default: false,
      },
      selectEtlConfig: {
        type: String,
        default: 'bk_log_json',
      },
      isSetDisabled: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        isReset: false,
        dialogDate: false,
        curRow: {},
        formData: {
          tableList: [],
        },
        isShowParticiple: false,
        // timeCheckResult: false,
        checkLoading: false,
        retainOriginalText: true, // 保留原始日志
        retainExtraText: false,
        currentIsAnalyzed: false,
        currentParticipleState: '',
        currentTokenizeOnChars: '',
        currentIsCaseSensitive: false,
        participleList: [
          {
            id: 'default',
            name: this.$t('自然语言分词'),
            placeholder: this.$t('自然语言分词，按照日常语法习惯进行分词'),
          },
          {
            id: 'custom',
            name: this.$t('自定义'),
            placeholder: this.$t('支持自定义分词符，可按需自行配置符号进行分词'),
          },
        ],
        rules: {
          field_name: [
            // 存在bug，暂时启用
            // {
            //     required: true,
            //     trigger: 'blur'
            // },
            // {
            //     validator: this.checkFieldNameFormat,
            //     trigger: 'blur'
            // },
            // {
            //     validator: this.checkFieldName,
            //     trigger: 'blur'
            // }
          ],
          alias_name: [
            // 目前组件不能拿到其他字段的值，不能通过validator进行验证
            // {
            //     validator: this.checkAliasName,
            //     trigger: 'blur'
            // }
            {
              max: 50,
              trigger: 'blur',
            },
            {
              regex: /^[A-Za-z0-9_]+$/,
              trigger: 'blur',
            },
          ],
          field_type: [
            // {
            //     required: true,
            //     trigger: 'change'
            // }
          ],
          notCheck: [
            {
              validator() {
                return true;
              },
              trigger: 'change',
            },
          ],
        },
      };
    },
    computed: {
      ...mapGetters({
        bkBizId: 'bkBizId',
      }),
      ...mapGetters('collect', ['curCollect']),
      ...mapGetters('globals', ['globalsData']),
      isSettingDisable() {
        return !this.fields.length;
      },
      deletedNum() {
        return this.formData.tableList.filter(item => item.is_delete).length;
      },
      isPreviewMode() {
        return this.tableType === 'preview';
      },
      tableList() {
        return this.formData.tableList;
      },
      hideDeletedTable() {
        return this.formData.tableList.filter(item => !item.is_delete);
      },
      changeTableList() {
        return this.deletedVisible ? this.hideDeletedTable : this.tableList;
      },
      getParticipleWidth() {
        return this.$store.getters.isEnLanguage ? '65' : '50';
      },
      retainExtraJsonIsOpen() {
        return this.globalsData?.retain_extra_json ?? false;
      },
      getOperatorDisabled() {
        if (this.selectEtlConfig === 'bk_log_json') return true;
        return !this.isPreviewMode && this.extractMethod !== 'bk_log_regexp';
      },
    },
    watch: {
      fields: {
        deep: true,
        handler() {
          this.reset();
        },
      },
      retainExtraJson(newVal) {
        this.retainExtraText = newVal;
      },
    },
    async mounted() {
      this.retainExtraText = this.retainExtraJson;
      this.reset();
      this.$emit('handle-table-data', this.changeTableList);
    },
    methods: {
      reset() {
        let arr = [];
        const copyFields = JSON.parse(JSON.stringify(this.fields)); // option指向地址bug
        const errTemp = {
          fieldErr: '',
          typeErr: false,
          aliasErr: '',
        };
        if (this.extractMethod !== 'bk_log_json') {
          errTemp.aliasErr = false;
        }
        copyFields.reduce((list, item) => {
          list.push(Object.assign({}, errTemp, item));
          return list;
        }, arr);
        arr.forEach(item => (item.previous_type = item.field_type));

        if (!this.isPreviewMode) {
          arr = arr.filter(item => !item.is_built_in);
        }

        if (this.isEditJson === false && !this.isTempField) {
          // 新建JSON时，类型如果不是数字，则默认为字符串
          arr.forEach(item => {
            if (typeof item.value !== 'number') {
              item.field_type = 'string';
              item.previous_type = 'string';
            }
          });
        }

        // 根据预览值 value 判断不是数字，则默认为字符串
        arr.forEach(item => {
          const { value, field_type } = item;
          item.participleState = item.tokenize_on_chars ? 'custom' : 'default';

          if (field_type === '' && value !== '' && this.judgeNumber(value)) {
            item.field_type = 'string';
            item.previous_type = 'string';
          }
        });
        this.formData.tableList.splice(0, this.formData.tableList.length, ...arr);
      },
      resetField() {
        this.$emit('reset');
      },
      // 当前字段类型是否禁用
      isTypeDisabled(row, option) {
        if (row.verdict) {
          // 不是数值，相关数值类型选项被禁用
          return ['int', 'long', 'double', 'float'].includes(option.id);
        }
        // 是数值，如果值大于 2147483647 即 2^31 - 1，int 选项被禁用
        return option.id === 'int' && row.value > 2147483647;
      },
      fieldTypeSelect(val, $row, $index) {
        const fieldName = $row.field_name;
        const fieldType = $row.field_type;
        const previousType = $row.previous_type;
        const isAnalyzed = $row.is_analyzed;
        const isCaseSensitive = $row.is_case_sensitive;
        const participleState = $row.participleState;
        const tokenizeOnChars = $row.tokenize_on_chars;
        if (val !== 'string') {
          const assignObj = {
            is_analyzed: false,
            participleState: 'default',
            tokenize_on_chars: '',
            is_case_sensitive: false,
          };
          Object.assign(this.changeTableList[$index], assignObj);
        }
        if (fieldType && this.curCollect.table_id) {
          const row = this.fields.find(item => item.field_name === fieldName);
          if (row?.field_type && row.field_type !== val) {
            const h = this.$createElement;
            this.$bkInfo({
              // title: '修改',
              // subTitle: '修改类型后，会影响到之前采集的数据',
              subHeader: h(
                'p',
                {
                  style: {
                    whiteSpace: 'normal',
                  },
                },
                this.$t('更改字段类型后在同时检索新老数据时可能会出现异常，确认请继续'),
              ),
              type: 'warning',
              confirmFn: () => {
                this.changeTableList[$index].field_type = val;
                this.changeTableList[$index].previousType = val;
                this.checkTypeItem($row);
              },
              cancelFn: () => {
                const assignObj = {
                  field_type: previousType,
                  is_analyzed: isAnalyzed,
                  participleState,
                  tokenize_on_chars: tokenizeOnChars,
                  is_case_sensitive: isCaseSensitive,
                };
                Object.assign(this.changeTableList[$index], assignObj);
                this.checkTypeItem($row);
              },
            });
            return false;
          }
        } else {
          this.changeTableList[$index].field_type = val;
        }
        this.checkTypeItem($row);
      },
      handlePopover(row) {
        this.currentParticipleState = row.participleState;
        this.currentIsCaseSensitive = row.is_case_sensitive;
        this.currentTokenizeOnChars = row.tokenize_on_chars;
        this.currentIsAnalyzed = row.is_analyzed;
      },
      handleConfirmParticiple(row) {
        this.$set(row, 'is_analyzed', this.currentIsAnalyzed);
        this.$set(row, 'is_case_sensitive', this.currentIsCaseSensitive);
        this.$set(row, 'tokenize_on_chars', this.currentTokenizeOnChars);
        this.$set(row, 'participleState', this.currentParticipleState);
      },
      handelChangeAnalyzed() {
        if (!this.currentIsAnalyzed) {
          this.currentIsCaseSensitive = false;
          this.currentTokenizeOnChars = '';
          this.currentParticipleState = 'default';
        }
      },
      handleChangeParticipleState(state) {
        this.currentParticipleState = state;
        this.currentTokenizeOnChars = state === 'custom' ? this.originalTextTokenizeOnChars : '';
      },
      // formatChange(val) {
      //   this.timeCheckResult = false;
      //   this.dialogField.time_format = val;
      // },
      // viewStandard() {
      //   if (this.isSettingDisable) return;

      //   this.$emit('standard');
      // },
      judgeNumber(value) {
        if (value === 0) return false;

        return value && value !== ' ' ? isNaN(value) : true;
      },
      getData() {
        // const data = JSON.parse(JSON.stringify(this.formData.tableList.filter(row => !row.is_delete)))
        const data = JSON.parse(JSON.stringify(this.formData.tableList));
        data.forEach(item => {
          if (item.hasOwnProperty('fieldErr')) {
            delete item.fieldErr;
          }

          if (item.hasOwnProperty('aliasErr')) {
            delete item.aliasErr;
          }

          if (item.hasOwnProperty('typeErr')) {
            delete item.typeErr;
          }
        });
        return data;
      },
      // checkFieldNameFormat (val) {
      //     return /^(?!_)(?!.*?_$)^[A-Za-z0-9_]+$/ig.test(val)
      // },
      // checkFieldName (val) {
      //     return this.extractMethod === 'bk_log_json' ?
      //             true : !this.globalsData.field_built_in.find(item => item.id === val.toLocaleLowerCase())
      // },
      checkTypeItem(row) {
        row.typeErr = row.is_delete ? false : !row.field_type;
        return !row.typeErr;
      },
      checkType() {
        return new Promise((resolve, reject) => {
          try {
            let result = true;
            this.formData.tableList.forEach(row => {
              if (!this.checkTypeItem(row)) {
                result = false;
              }
            });
            if (result) {
              resolve();
            } else {
              console.warn('Type校验错误');
              reject(result);
            }
          } catch (err) {
            console.warn('Type校验错误');
            reject(err);
          }
        });
      },
      checkFieldNameItem(row) {
        const { field_name, is_delete, field_index } = row;
        let result = '';

        if (!is_delete) {
          if (!field_name) {
            result = this.$t('必填项');
          } else if (this.extractMethod !== 'bk_log_json' && !/^(?!_)(?!.*?_$)^[A-Za-z0-9_]+$/gi.test(field_name)) {
            result = this.$t('只能包含a-z、A-Z、0-9和_，且不能以_开头和结尾');
          } else if (
            this.extractMethod !== 'bk_log_json' &&
            this.globalsData.field_built_in.find(item => item.id === field_name.toLocaleLowerCase())
          ) {
            result =
              this.extractMethod === 'bk_log_regexp'
                ? this.$t('字段名与系统字段重复，必须修改正则表达式')
                : this.$t('字段名与系统内置字段重复');
          } else if (this.extractMethod === 'bk_log_delimiter' || this.selectEtlConfig === 'bk_log_json') {
            result = this.filedNameIsConflict(field_index, field_name) ? this.$t('字段名称冲突, 请调整') : '';
          } else {
            result = '';
          }
        } else {
          result = '';
        }
        row.fieldErr = result;
        this.$emit('handle-table-data', this.changeTableList);

        return result;
      },
      checkFieldName() {
        return new Promise((resolve, reject) => {
          try {
            let result = true;
            this.formData.tableList.forEach(row => {
              if (this.checkFieldNameItem(row)) {
                // 返回 true 的时候未通过
                result = false;
              }
            });
            if (result) {
              resolve();
            } else {
              console.warn('FieldName校验错误');
              reject(result);
            }
          } catch (err) {
            console.warn('FieldName校验错误');
            reject(err);
          }
        });
      },
      checkAliasNameItem(row) {
        const { field_name: fieldName, alias_name: aliasName, is_delete: isDelete } = row;
        if (isDelete) {
          return true;
        }

        if (aliasName) {
          // 设置了别名
          if (!/^(?!^\d)[\w]+$/gi.test(aliasName)) {
            // 别名只支持【英文、数字、下划线】，并且不能以数字开头
            row.aliasErr = this.$t('别名只支持【英文、数字、下划线】，并且不能以数字开头');
            return false;
          }
          if (this.globalsData.field_built_in.find(item => item.id === aliasName.toLocaleLowerCase())) {
            // 别名不能与内置字段名相同
            row.aliasErr = this.$t('别名不能与内置字段名相同');
            return false;
          }
        } else if (this.globalsData.field_built_in.find(item => item.id === fieldName.toLocaleLowerCase())) {
          // 字段名与内置字段冲突，必须设置别名
          row.aliasErr = this.$t('字段名与内置字段冲突，必须设置别名');
          return false;
        }

        row.aliasErr = '';
        return true;
      },
      checkAliasName() {
        return new Promise((resolve, reject) => {
          try {
            let result = true;
            this.formData.tableList.forEach(row => {
              if (!this.checkAliasNameItem(row)) {
                result = false;
              }
            });
            if (result) {
              resolve();
            } else {
              console.warn('AliasName校验错误');
              reject(result);
            }
          } catch (err) {
            console.warn('AliasName校验错误');
            reject(err);
          }
        });
      },
      validateFieldTable() {
        const promises = [];
        promises.push(this.checkFieldName());
        promises.push(this.checkAliasName());
        promises.push(this.checkType());
        return promises;
      },
      visibleHandle() {
        if (this.isSettingDisable) return;

        this.$emit('delete-visible', !this.deletedVisible);
      },
      handleKeepLog(value) {
        this.$emit('handle-keep-log', value);
      },
      handleKeepField(value) {
        this.$emit('handle-keep-field', value);
      },
      renderHeaderAliasName(h) {
        return h(
          'div',
          {
            class: 'render-header',
          },
          [
            h('span', { directives: [{ name: 'bk-overflow-tips' }], class: 'title-overflow' }, [this.$t('重命名')]),
            h('span', this.$t('(选填)')),
            h('span', {
              class: 'icon bklog-icon bklog-info-fill',
              directives: [
                {
                  name: 'bk-tooltips',
                  value: this.$t('非必填字段，填写后将会替代字段名；字段名与内置字段重复时，必须重新命名。'),
                },
              ],
            }),
          ],
        );
      },
      renderHeaderDescription(h) {
        return h(
          'div',
          {
            class: 'render-header',
          },
          [
            h('span', { directives: [{ name: 'bk-overflow-tips' }], class: 'title-overflow' }, [this.$t('字段说明')]),
            h('span', this.$t('(选填)')),
          ],
        );
      },
      renderHeaderParticipleName(h) {
        return h(
          'span',
          {
            directives: [
              {
                name: 'bk-tooltips',
                value: this.$t('选中分词,适用于分词检索,不能用于指标和维度'),
              },
            ],
          },
          [
            h(
              'span',
              {
                class: 'render-Participle title-overflow',
                directives: [{ name: 'bk-overflow-tips' }],
              },
              [this.$t('分词符')],
            ),
          ],
        );
      },
      isDisableOperate(row) {
        if (this.isSetDisabled) return;
        row.is_delete = !row.is_delete;
        this.$emit('handle-table-data', this.changeTableList);
      },
      filedNameIsConflict(fieldIndex, fieldName) {
        const otherFieldNameList = this.formData.tableList.filter(item => item.field_index !== fieldIndex);
        return otherFieldNameList.some(item => item.field_name === fieldName);
      },
      /** 当前字段是否禁用 */
      getFieldEditDisabled(row) {
        if (row?.is_delete) return true;
        if (this.selectEtlConfig === 'bk_log_json') return false;
        return this.extractMethod !== 'bk_log_delimiter' || this.isSetDisabled;
      },
      /**
       * @desc: 判断当前分词符或者分词符有关的子项是否禁用
       * @param {Any} row 字段信息
       * @param {String} type 是分词还是分词有关的子项
       * @returns {Boolean}
       */
      getCustomizeDisabled(row, type = 'analyzed-item') {
        const { is_delete: isDelete, field_type: fieldType } = row;
        let atLastAnalyzed = this.currentIsAnalyzed;
        if (type === 'analyzed') atLastAnalyzed = true;
        return this.isPreviewMode || isDelete || fieldType !== 'string' || !atLastAnalyzed || this.isSetDisabled;
      },
      // isShowFieldDateIcon(row) {
      //   return ['string', 'int', 'long'].includes(row.field_type);
      // },
    },
  };
</script>

<style lang="scss" scoped>
  @import '@/scss/mixins/clearfix';
  @import '@/scss/mixins/overflow-tips.scss';

  /* stylelint-disable no-descending-specificity */
  .field-table-container {
    position: relative;
    display: flex;

    .field-method-head {
      position: absolute;
      top: -30px;
      right: 0;
    }

    :deep(.field-table.add-field-table) {
      .bk-table-body {
        .cell {
          display: contents;
          height: 100%;

          /* stylelint-disable-next-line declaration-no-important */
          padding: 0 !important;

          .tooltips-icon {
            top: 16px;
          }
        }
      }

      .bk-form-input {
        height: 50px;
        border: 1px solid transparent;
      }

      .participle-disabled-input {
        .bk-form-input[disabled] {
          /* stylelint-disable-next-line declaration-no-important */
          border-color: transparent !important;
        }
      }

      .bk-select {
        height: 50px;
        border: 1px solid transparent;

        .bk-select-name {
          height: 50px;
          padding: 7px 38px 0 13px;
        }

        .bk-select-angle {
          top: 12px;
        }

        &.is-default-trigger.is-unselected:before {
          top: 8px;
        }
      }

      .participle-select-icon {
        font-size: 20px;
        font-weight: 500;
        color: #979ba5;
      }
    }

    .field-table {
      .bk-table-body {
        .cell {
          padding-right: 5px;
          padding-left: 5px;
        }
      }

      .bk-label {
        display: none;
      }

      .render-header {
        display: flex;
        align-items: center;
        height: 100%;

        span:nth-child(2) {
          color: #979ba5;
        }

        .render-Participle {
          display: inline-block;
          width: 100%;
          text-align: center;
        }

        span:nth-child(3) {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 14px;
          height: 14px;
          margin-top: 2px;
          font-size: 14px;
          outline: none;
        }
      }

      .bk-table-empty-text {
        padding: 12px 0;
      }

      .bk-table-empty-block {
        min-height: 32px;
      }

      .empty-text {
        color: #979ba5;
      }

      .participle-popconfirm {
        width: 100%;

        .bk-tooltip-ref {
          width: 100%;
        }

        .participle-cell-wrap {
          display: flex;
          align-items: center;
          margin-left: 10px;
        }
      }
    }

    .preview-panel-left {
      flex: 1;
    }

    .preview-panel-right {
      width: 335px;
      font-size: 12px;
      color: #c4c6cc;
      background: #63656e;
      border-bottom: 1px solid #72757d;
      border-radius: 0 2px 2px 0;

      .preview-item {
        height: 43px;
        padding: 0 10px;
        overflow: hidden;
        line-height: 43px;
        text-overflow: ellipsis;
        white-space: nowrap;
        border-top: 1px solid #72757d;

        &:first-child {
          height: 43px;
          border-top: 1px solid transparent;
        }
      }

      .preview-title {
        color: #fff;
      }
    }

    .bk-table .table-link {
      cursor: pointer;
    }

    .field-date {
      display: inline-block;
      padding: 0 10px;
      font-size: 14px;
      outline: none;

      &:hover {
        color: #3a84ff;
        cursor: pointer;
      }

      &.field-date-active {
        color: #3a84ff;

        .icon-date-picker {
          color: #3a84ff;
        }
      }

      &.field-date-disable {
        color: #dcdee5;
        cursor: not-allowed;
      }
    }

    .icon-date-picker {
      color: #979ba5;

      &.active {
        color: #3a84ff;
      }
    }
  }

  .field-date-dialog {
    .prompt {
      padding: 6px 7px;
      margin-bottom: 20px;
      font-size: 12px;
      color: #63656e;
      background: #f6f6f6;

      span {
        font-weight: 600;
        color: #313238;
      }
    }

    .bk-label {
      text-align: left;
    }
  }

  .field-dropdown-list {
    padding: 7px 0;
    margin: -7px -14px;

    .dropdown-item {
      padding: 0 10px;
      font-size: 12px;
      line-height: 32px;
      color: #63656e;
      cursor: pointer;

      &:hover {
        color: #3a84ff;
        background: #e1ecff;
      }
    }
  }

  .header {
    /* stylelint-disable-next-line declaration-no-important */
    white-space: normal !important;
  }

  .participle-form {
    margin-right: 10px;

    .bk-form-control {
      width: 200px;
    }

    .bk-form-item {
      margin-top: 5px;

      .bk-label {
        padding: 0 13px 0 0;
      }
    }

    .participle-btn {
      padding: 0 8px;
      font-size: 12px;
    }
  }
</style>
