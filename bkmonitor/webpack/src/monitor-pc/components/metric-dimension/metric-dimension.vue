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
  <div class="dimension-table-wrapper">
    <div class="operation-upload-download">
      <div class="upload">
        <input
          ref="uploadMetricFile"
          type="file"
          multiple
          accept=".json"
          style="display: none"
          @change="getFileInfo"
        />
        {{ $t('在下方自定义添加或') }}
        <span
          class="uploadt-btn"
          @click="handleUpload"
        >
          {{ $t('点击上传文件') }}
        </span>
      </div>
      <div class="download">
        <span v-if="isEdit"
          ><span class="bk-icon icon-exclamation-circle risk" /> {{ $t('编辑指标/维度有风险') }}
        </span>
        <a
          class="download-example"
          href="javascript:void(0);"
          @click="handleDownloadMetricJson"
        >
          {{ $t('下载样例') }}
        </a>
      </div>
    </div>
    <div
      v-for="(table, index) in tables"
      :key="index"
      style="margin-bottom: 10px"
    >
      <div class="table-title">
        <div class="name">
          <span>{{ table.name }}</span
          ><span v-if="table.alias">({{ table.alias }})</span>
        </div>
        <span class="operator">
          <svg @click="editTableName(index, table)">
            <g>
              <line
                x1="0"
                y1="20"
                x2="16"
                y2="20"
                stroke-width="2px"
                stroke="#63656E"
              />
              <line
                x1="3"
                y1="17"
                x2="14"
                y2="10"
                stroke-width="2px"
                stroke="#63656E"
              />
              <line
                x1="15"
                y1="9"
                x2="17"
                y2="8"
                stroke-width="2px"
                stroke="#63656E"
              />
            </g>
          </svg>
          <span
            v-if="tables.length > 1"
            class="bk-icon icon-close"
            @click="handelRemoveTable(index)"
          />
        </span>
      </div>
      <bk-table :data="table.data">
        <bk-table-column
          :label="$t('指标/维度')"
          prop="dimension"
        >
          <template slot-scope="props">
            <div class="row-header">
              {{ props.row.rowHeader }}
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          label-class-name="require"
          class-name="small-padding"
          :label="$t('英文名')"
          prop="englishName"
        >
          <template slot-scope="props">
            <div class="name">
              <verify-input
                position="right"
                :validator="{ content: props.row.nameErrorMsg }"
                :show-validate.sync="props.row.nameError"
              >
                <bk-input
                  v-model.trim="props.row.name"
                  :disabled="Boolean(props.row.sourceName)"
                  :maxlength="256"
                  :placeholder="$t('英文')"
                  @blur="checkInput(props.row, ['name', 'alias'])"
                  @change="checkInput(props.row, ['name', 'alias'])"
                />
              </verify-input>
              <bk-popover
                v-if="!(props.row.name.length || Boolean(props.row.sourceName))"
                class="change-name"
                placemnet="top-end"
                trigger="mouseenter"
              >
                <span
                  v-show="props.row.isReservedWord"
                  class="icon-monitor icon-change"
                  @click="rename(props.row)"
                />
                <div slot="content">
                  <p style="margin-bottom: 0; font-size: 12px">
                    {{ $t('冲突： 点击进行转换') }}
                  </p>
                </div>
              </bk-popover>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          class-name="small-padding"
          :label="$t('别名')"
          prop="alias"
        >
          <template slot-scope="props">
            <verify-input
              position="right"
              :validator="{ content: props.row.aliasErrorMsg }"
              :show-validate.sync="props.row.aliasError"
            >
              <bk-input
                v-model.trim="props.row.alias"
                :maxlength="128"
                :placeholder="$t('别名')"
                @blur="checkInput(props.row, ['name', 'alias'])"
                @change="checkInput(props.row, ['name', 'alias'])"
              />
            </verify-input>
          </template>
        </bk-table-column>
        <bk-table-column
          class-name="small-padding"
          :label="$t('类型')"
          prop="type"
        >
          <template slot-scope="props">
            <verify-input
              v-if="props.row.monitorType === 'metric'"
              class="error-icon-right"
              position="right"
              :show-validate.sync="props.row.typeError"
            >
              <bk-select
                v-model="props.row.type.value"
                :clearable="false"
              >
                <bk-option
                  v-for="(dataType, typeIndex) in props.row.type.list"
                  :id="dataType.id"
                  :key="typeIndex"
                  :name="dataType.name"
                />
              </bk-select>
            </verify-input>
            <bk-select
              v-else
              v-model="props.row.type.value"
              :clearable="false"
              :disabled="props.row.monitorType === 'dimension'"
            >
              <bk-option
                v-for="(dataType, typeIndex) in props.row.type.list"
                :id="dataType.id"
                :key="typeIndex"
                :name="dataType.name"
              />
            </bk-select>
          </template>
        </bk-table-column>
        <bk-table-column
          class-name="small-padding"
          :label="$t('单位')"
          prop="unit"
        >
          <template slot-scope="props">
            <bk-input
              v-if="props.row.monitorType === 'metric'"
              v-model="props.row.unit"
            />
            <div
              v-else
              style="text-align: center"
            >
              <span>--</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column :label="$t('启/停')">
          <template slot-scope="props">
            <bk-switcher
              v-if="props.row.monitorType === 'metric'"
              v-model="props.row.switch"
              size="small"
            />
            <div
              v-else
              style="text-align: center"
            >
              <span>--</span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column :label="$t('增/删')">
          <template slot-scope="props">
            <span
              class="bk-icon icon-plus-circle"
              @click.stop="handleAdd(props.row.monitorType, table.data, props.$index)"
            />

            <span
              class="bk-icon icon-minus-circle"
              @click.stop="handleDel(table.data, props.$index, index)"
            />
          </template>
        </bk-table-column>
      </bk-table>
    </div>
    <div
      class="add-category"
      @click="create"
    >
      <span class="bk-icon icon-plus" /><span> {{ $t('增加指标分类') }} </span>
    </div>
    <bk-dialog
      v-model="isShow"
      :theme="'primary'"
      :mask-close="false"
      header-position="left"
      :show-footer="false"
      :width="480"
      :title="metricForm.isEdit ? $t('编辑指标分类') : $t('增加指标分类')"
      @after-leave="afterLeave"
      @confirm="handleConfirm"
    >
      <div class="metric-name">
        <div class="hint">
          <svg viewBox="0 0 64 64">
            <g>
              <path
                d="M32,4C16.5,4,4,16.5,4,32s12.5,28,28,28s28-12.5,28-28S47.5,4,32,4z M32,56C18.7,56,8,45.3,8,32S18.7,8,32,8s24,10.7,24,24S45.3,56,32,56z"
              />
              <path
                d="M30.9,25.2c-1.8,0.4-3.5,1.3-4.8,2.6c-1.5,1.4,0.1,2.8,1,1.7c0.6-0.8,1.5-1.4,2.5-1.8c0.7-0.1,1.1,0.1,1.2,0.6c0.1,0.9,0,1.7-0.3,2.6c-0.3,1.2-0.9,3.2-1.6,5.9c-1.4,4.8-2.1,7.8-1.9,8.8c0.2,1.1,0.8,2,1.8,2.6c1.1,0.5,2.4,0.6,3.6,0.3c1.9-0.4,3.6-1.4,5-2.8c1.6-1.6-0.2-2.7-1.1-1.8c-0.6,0.8-1.5,1.4-2.5,1.6c-0.9,0.2-1.4-0.2-1.6-1c-0.1-0.9,0.1-1.8,0.4-2.6c2.5-8.5,3.6-13.3,3.3-14.5c-0.2-0.9-0.8-1.7-1.6-2.1C33.3,24.9,32,24.9,30.9,25.2z"
              />
              <circle
                cx="35"
                cy="19"
                r="3"
              />
            </g>
          </svg>
          <span>
            {{ $t('指标分类的定义影响指标检索的时候,如试图查看，仪表盘添加视图和添加监控策略时选择指标的分类。') }}
          </span>
        </div>
        <verify-input
          :validator="{ content: $t('输入指标名,以字母开头,允许包含下划线和数字') }"
          :show-validate.sync="metricForm.isNameEmpty"
        >
          <bk-input
            v-model.trim="metricForm.name"
            :placeholder="$t('英文名')"
            @blur="metricForm.isNameEmpty = !regx.test(metricForm.name)"
          />
        </verify-input>
        <verify-input>
          <bk-input
            v-model="metricForm.alias"
            :placeholder="$t('别名')"
          />
        </verify-input>
      </div>
      <div class="footer">
        <bk-button
          class="confirm-btn"
          theme="primary"
          @click="handleConfirm"
          @keyup.enter="handleConfirm"
        >
          {{ $t('确认') }} </bk-button
        ><bk-button @click="isShow = false">
          {{ $t('取消') }}
        </bk-button>
      </div>
    </bk-dialog>
  </div>
</template>
<script>
/**
 * @description: 指标纬度选择器
 * valiDateTables  验证指标选择器参数
 * getMetricParams 获取指标纬度选择器参数
 */
import VerifyInput from '../../components/verify-input/verify-input.vue';

export default {
  name: 'DimensionTable',
  components: {
    VerifyInput,
  },
  props: {
    rows: {
      type: Array,
      default: () => [],
    },
    isImport: {
      type: Boolean,
      default: false,
    },
    isEdit: {
      type: Boolean,
      default: false,
    },
    reservedWords: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      regx: /^[_|a-zA-Z][a-zA-Z0-9_]*$/,
      regxTwo: /^[a-zA-Z][a-zA-Z0-9_]*$/,
      templateRows: [
        {
          rowHeader: '指标(Metric)',
          name: '',
          sourceName: '',
          alias: '',
          type: {
            list: [
              {
                id: 'int',
                name: 'int',
              },
              {
                id: 'double',
                name: 'double',
              },
              {
                id: 'diff',
                name: 'diff',
              },
            ],
            value: 'double',
          },
          typeError: false,
          isReservedWord: false,
          nameError: false,
          aliasError: false,
          typeErrorMsg: '',
          nameErrorMsg: '',
          aliasErrorMsg: '',
          unit: '',
          monitorType: 'metric',
          switch: true,
          disabled: true,
        },
        {
          rowHeader: this.$t('维度(Dimension)'),
          name: '',
          sourceName: '',
          alias: '',
          type: {
            list: [
              {
                id: 'string',
                name: 'string',
              },
            ],
            value: 'string',
          },
          isReservedWord: false,
          nameError: false,
          aliasError: false,
          nameErrorMsg: '',
          aliasErrorMsg: '',
          unit: '',
          monitorType: 'dimension',
          switch: true,
          disabled: true,
        },
      ],
      isUpload: false,
      tables: [],
      tableIndex: 0,
      metricForm: {
        name: '',
        alias: '',
        isEdit: false,
        isNameEmpty: false,
      },
      isExistReservedWord: false,
      isShow: false,
      rowUnwatch: null,
    };
  },
  computed: {
    import() {
      return this.isUpload || this.isImport;
    },
    metricJson() {
      return [
        {
          fields: [
            {
              monitor_type: 'metric',
              type: 'long',
              name: 'zk_znode_count',
              unit: '',
              description: this.$t('节点数'),
            },
            {
              monitor_type: 'metric',
              type: 'long',
              name: 'zk_packets_sent',
              unit: '',
              description: this.$t('包发送量'),
            },
            {
              monitor_type: 'metric',
              type: 'long',
              name: 'zk_packets_received',
              unit: '',
              description: this.$t('包接收量'),
            },
            {
              monitor_type: 'metric',
              type: 'long',
              name: 'zk_open_file_descriptor_count',
              unit: '',
              description: this.$t('文件描述符数量'),
            },
            {
              monitor_type: 'dimension',
              type: 'string',
              name: 'server',
              unit: '',
              description: this.$t('服务地址'),
            },
          ],
          table_name: 'overview',
          table_desc: this.$t('总览'),
        },
      ];
    },
  },
  watch: {
    rows: {
      handler(val) {
        this.handleChangeRows(val);
      },
      deep: true,
    },
  },
  created() {
    if (!this.isEdit && !this.rows.length) {
      this.tables = [
        {
          name: 'base',
          data: JSON.parse(JSON.stringify(this.templateRows)),
          alias: this.$t('默认分类'),
        },
      ];
    }
  },
  methods: {
    handleUpload() {
      this.$refs.uploadMetricFile.click();
    },
    /**
     * @description: 处理表格数据的新增和回填
     * @param {val} Array
     * @return: void
     */
    handleChangeRows(val) {
      if (val.length) {
        if (this.import) {
          this.tables = [];
        }
        val.forEach(item => {
          if (!this.reservedWords.find(text => text === item.name.toLocaleUpperCase())) {
            const data = [];
            item.fields.forEach((field, i) => {
              const index = field.monitor_type === 'metric' ? 0 : 1;
              const isMetric = field.monitor_type === 'metric';
              const obj = JSON.parse(JSON.stringify(this.templateRows[index]));
              obj.rowHeader = isMetric ? this.$t('指标(Metric)') : this.$t('维度(Dimension)');
              obj.name = field.name || '';
              obj.sourceName = field.source_name || '';
              obj.alias = field.description || '';
              obj.unit = field.unit || '';
              obj.switch = typeof field.is_active !== 'undefined' ? field.is_active : true;
              obj.disabled = i < 2;
              if (isMetric) {
                if (obj.type.list.find(t => t.name === field.type)) {
                  obj.type.value = field.type;
                } else {
                  obj.type.value = 'double';
                }
                if (typeof field.is_diff_metric !== 'undefined' && field.is_diff_metric) {
                  obj.type.value = 'diff';
                }
              } else {
                obj.type.value = 'string';
              }
              data.push(obj);
            });
            // 没有维度字段，则自动添加一个维度
            if (!data.find(row => row.rowHeader === this.$t('维度(Dimension)'))) {
              data.push(JSON.parse(JSON.stringify(this.templateRows[1])));
            }
            const tableIndex = this.tables.findIndex(table => table.name === item.name);
            const tableObj = {
              name: this.regx.test(item.name) ? item.name : '',
              alias: item.alias || '',
              data,
            };
            this.insertTableData(tableIndex, tableObj);
          } else {
            this.$bkMessage({ theme: 'error', message: `${item.name}${this.$t('是保留字')}` });
          }
        });
        if (this.import) {
          this.valiDateTables();
          this.isUpload = false;
          this.$emit('update:isImport', false);
        }
      }
      this.checkDuplicateMetricName();
    },
    handleDownloadMetricJson() {
      const downlondEl = document.createElement('a');
      const blob = new Blob([JSON.stringify(this.metricJson, null, 4)]);
      const fileUrl = URL.createObjectURL(blob);
      downlondEl.href = fileUrl;
      downlondEl.download = 'metric.json';
      downlondEl.style.display = 'none';
      document.body.appendChild(downlondEl);
      downlondEl.click();
      document.body.removeChild(downlondEl);
    },
    create() {
      this.isShow = true;
      this.isNameEmpty = false;
    },
    editTableName(index, table) {
      this.metricForm.isEdit = true;
      this.isShow = true;
      this.tableIndex = index;
      this.metricForm.name = table.name;
      this.metricForm.alias = table.alias;
    },
    handleAdd(type, table, index) {
      const row = this.templateRows.find(item => item.monitorType === type);
      if (row) {
        const newRow = JSON.parse(JSON.stringify(row));
        newRow.disabled = false;
        table.splice(index + 1, 0, newRow);
      }
    },
    async getFileInfo(e) {
      const files = Array.from(e.target.files);
      this.isUpload = true;
      const tables = await new Promise(resolve => {
        let count = 0;
        const result = [];
        files.forEach(file => {
          const reader = new FileReader();
          reader.onload = e => {
            const contents = JSON.parse(e.target.result);
            if (!Array.isArray(contents)) {
              this.$bkMessage('error', this.$t('文件内容不符合规范'));
            } else {
              contents.forEach(item => {
                result.push({
                  fields: Array.isArray(item.fields) ? item.fields : [],
                  name: item.table_name || '',
                  alias: item.table_desc || '',
                });
              });
            }
            count += 1;
            if (count === files.length) {
              resolve(result);
            }
          };
          reader.readAsText(file, 'UTF-8');
        });
      });
      this.$bkMessage({ theme: 'success', message: this.$t('文件上传成功') });
      this.handleChangeRows(tables);
      e.target.value = '';
    },
    insertTableData(tableIndex, tableObj) {
      // 如果是导入且有重名，则直接替换对应表格
      if (this.import) {
        if (tableIndex > -1) {
          this.tables.splice(tableIndex, 1, tableObj);
        } else {
          this.tables.push(tableObj);
        }
      } else {
        if (tableIndex > -1) {
          this.$bkMessage({ theme: 'error', message: this.$t('注意: 名字冲突') });
        } else {
          this.tables.push(tableObj);
        }
      }
    },
    handleConfirm() {
      if (this.regx.test(this.metricForm.name) && !this.metricForm.isEdit) {
        if (
          !this.tables.find(item => item.name === this.metricForm.name) &&
          !this.reservedWords.find(item => item === this.metricForm.name.toLocaleUpperCase())
        ) {
          this.tables.push({
            name: this.metricForm.name,
            alias: this.metricForm.alias || this.metricForm.name,
            data: JSON.parse(JSON.stringify(this.templateRows)),
          });
          this.isShow = false;
        } else {
          this.$bkMessage({ theme: 'error', message: `${this.$t('指标分类不能同名且不能为')}${this.metricForm.name}` });
        }
      } else if (this.metricForm.isEdit && this.regx.test(this.metricForm.name)) {
        this.tables[this.tableIndex].name = this.metricForm.name;
        this.tables[this.tableIndex].alias = this.metricForm.alias || this.metricForm.name;
        this.isShow = false;
        this.metricForm.isEdit = false;
      }
    },
    afterLeave() {
      this.metricForm.name = '';
      this.metricForm.alias = '';
      this.metricForm.isNameEmpty = false;
    },
    handelRemoveTable(index) {
      this.tables.splice(index, 1);
    },
    handleDel(table, rowIndex) {
      if (!table[rowIndex].disabled) {
        table.splice(rowIndex, 1);
      } else {
        table[rowIndex].name = '';
        table[rowIndex].sourceName = '';
        table[rowIndex].alias = '';
      }
    },
    getMetricParams() {
      const metricJson = [];
      this.tables.forEach(table => {
        const fields = [];
        table.data.forEach(row => {
          if (row.name) {
            const obj = {
              type: row.type.value,
              monitor_type: row.monitorType,
              unit: row.unit,
              name: row.name,
              source_name: row.sourceName,
              description: row.alias,
            };
            if (row.monitorType === 'metric') {
              obj.is_active = row.switch;
              if (obj.type === 'diff') {
                obj.is_diff_metric = true;
                obj.type = 'double';
              } else {
                obj.is_diff_metric = false;
              }
            }
            fields.push(obj);
          }
        });
        metricJson.push({
          fields,
          table_name: table.name,
          table_desc: table.alias,
        });
      });
      return metricJson;
    },
    rename(row) {
      const rows = [];
      let prefix = '_';
      this.tables.forEach(table => {
        rows.push(...table.data);
      });
      if (row.name.toLowerCase() === 'name' || row.name.toLowerCase() === 'field') {
        prefix = '__';
      }
      if (rows.find(item => item.name === `${prefix}${row.name}`)) {
        this.$bkMessage({ theme: 'error', message: this.$t('注意: 名字冲突') });
      } else {
        row.sourceName = row.name;
        row.name = `${prefix}${row.name}`;
        row.isReservedWord = false;
      }
    },
    checkInput(obj, keys) {
      const pass = this.validateRequired(obj, keys);
      if (!pass) {
        this.checkDuplicateMetricName();
      }
    },
    /**
     * @desc 检查是否有重复的metric
     */
    checkDuplicateMetricName() {
      const rows = [];
      this.tables.forEach(table => {
        const data = table.data.map(item => {
          item.tableName = table.name;
          return item;
        });
        rows.push(...data);
      });
      const hasDuplicateName = this.validateDuplicateName(rows, 'nameError', 'nameErrorMsg');
      return hasDuplicateName;
    },
    validateDuplicateName(rows, key1, key2) {
      let hasDuplicateName = false;
      for (let i = rows.length - 1; i > -1; i--) {
        const copyRows = [...rows];
        const tableNameOne = rows[i].tableName;
        for (let k = 0; k < copyRows.length; k++) {
          const tableNameTwo = copyRows[k].tableName;
          if (i !== k && rows[i].name && rows[i].name === copyRows[k].name) {
            if (
              (rows[i].monitorType === 'metric' && copyRows[k].monitorType === 'metric') ||
              tableNameOne === tableNameTwo
            ) {
              hasDuplicateName = true;
              rows[i][key1] = true;
              rows[i][key2] = this.$t('注意: 名字冲突');
              copyRows[k][key1] = true;
              copyRows[k][key2] = this.$t('注意: 名字冲突');
            }
          }
        }
      }
      return !hasDuplicateName;
    },
    /**
     * @desc 维度字段非必填，当维度字段有name和alias的值时，必须同时校验两者。
     */
    validateRequired(obj, keys) {
      const rules = {
        name: val => {
          val = val.toUpperCase();
          obj.nameError = false;
          obj.nameErrorMsg = '';
          if (obj.monitorType === 'metric' || obj.alias || (obj.monitorType === 'dimension' && val)) {
            const regx = obj.sourceName ? this.regx : this.regxTwo;
            if (!regx.test(val)) {
              obj.nameError = true;
              obj.nameErrorMsg = this.$t('输入名称，以字母开头，仅支持字母、下划线和数字');
            } else if (val.length > 100) {
              obj.nameError = true;
              obj.nameErrorMsg = this.$t('注意：最大值为100个字符');
            }
          }
          obj.isReservedWord = this.reservedWords.find(item => item === val);
          if (obj.isReservedWord) {
            this.isExistReservedWord = true;
          }
          return obj.nameError || Boolean(obj.isReservedWord);
        },
        alias: val => {
          if (val.length > 100) {
            obj.aliasError = true;
            obj.aliasErrorMsg = this.$t('注意：最大值为100个字符');
          } else {
            obj.aliasError = false;
            obj.aliasErrorMsg = '';
          }
          return obj.aliasError;
        },
        type: val => {
          if (!val) {
            obj.typeError = true;
            obj.typeErrorMsg = true;
          } else {
            obj.typeError = false;
            obj.typeErrorMsg = '';
          }
          return obj.typeError;
        },
      };
      const validateResult = [];
      keys.forEach(key => {
        if (key !== 'type' || obj.monitorType !== 'dimension') {
          const fn = rules[key];
          const val = key === 'type' ? obj.type.value : obj[key];
          const result = fn(val);
          validateResult.push(result);
        }
      });
      return validateResult.includes(true);
    },
    /**
     * @description: 验证表格中所有参数, 验证通过返回true，否则返回false
     * @return: Boolean
     */
    valiDateTables() {
      let validateResult = true;
      this.isExistReservedWord = false;
      this.tables.forEach(item => {
        item.data.forEach(row => {
          const result = this.validateRequired(row, ['name', 'alias', 'type']);
          if (result) {
            validateResult = false;
          }
        });
      });
      if (this.isExistReservedWord) {
        this.$bkMessage({ theme: 'error', message: this.$t('注意: 名字冲突') });
      }
      return validateResult && this.checkDuplicateMetricName();
    },
  },
};
</script>
<style lang="scss" scoped>
.dimension-table-wrapper {
  .operation-upload-download {
    display: flex;
    justify-content: space-between;
    font-size: #6c656e;
    font-size: 14px;

    .uploadt-btn {
      color: #3a84ff;
      cursor: pointer;
    }

    .download-example {
      color: #3a84ff;
    }
  }

  .name {
    position: relative;

    .change-name {
      position: absolute;
      top: 0;
      right: 10px;
      font-size: 24px;
      color: #ff9c01;

      .icon-change {
        cursor: pointer;
      }
    }
  }

  .table-title {
    display: flex;
    height: 42px;
    padding: 0 21px;
    line-height: 42px;
    color: #313238;
    background-color: #dcdee5;

    .name {
      flex: 1;
    }

    .operator {
      padding-top: 8px;
    }
  }

  .row-header {
    height: 32px;
    padding-left: 10px;
    overflow: hidden;
    font-size: 12px;
    line-height: 32px;
    text-overflow: ellipsis;
    white-space: nowrap;
    background-color: #fafbfd;
    border: 1px solid #dcdee5;
  }

  .row-unit {
    height: 32px;
    padding-left: 10px;
    font-size: 12px;
    line-height: 32px;
    background-color: #fff;
    border: 1px solid #dcdee5;
  }

  :deep(.bk-table-row) {
    .step-verify-input .tooltips-icon {
      top: 8px;
      right: 4px;
    }

    .step-verify-input.error-icon-right {
      :deep(.tooltips-icon) {
        right: 30px;
      }
    }
  }

  :deep(.small-padding) {
    .cell {
      padding: 0 0 0 10px;

      &.require {
        &::after {
          position: relative;
          left: 5px;
          font-size: 12px;
          color: red;
          content: '*';
        }
      }
    }
  }

  .add-category {
    height: 42px;
    line-height: 42px;
    text-align: center;
    cursor: pointer;
    border: 1px dashed #dcdee5;

    span {
      margin-right: 6px;
    }
  }

  .metric-name {
    .bk-form-control:first-child {
      margin-bottom: 20px;
    }

    .hint {
      margin-bottom: 19px;
      font-size: 12px;
      color: #63656e;
      fill: #c4c6cc;

      svg {
        position: relative;
        top: 2px;
        width: 14px;
        height: 14px;
      }
    }

    /* stylelint-disable-next-line no-descending-specificity */
    :deep(.tooltips-icon) {
      top: 8px;
      right: 4px;
    }
  }

  :deep(.bk-switcher.is-checked) {
    background-color: #3a84ff;
  }

  .footer {
    position: relative;
    top: 32px;
    right: 24px;
    width: 480px;
    height: 50px;
    padding-right: 24px;
    line-height: 50px;
    text-align: right;
    background-color: #fafbfd;
    border-top: 1px solid #dcdee5;

    .confirm-btn {
      margin-right: 10px;
    }
  }

  /* stylelint-disable-next-line no-descending-specificity */
  svg {
    width: 20px;
    height: 30px;
    cursor: pointer;
  }

  .bk-icon {
    cursor: pointer;
  }

  .icon-plus-circle {
    font-size: 21px;
  }

  .icon-minus-circle {
    font-size: 21px;
  }

  .disabled {
    color: #dcdee5;
    cursor: not-allowed;
  }

  .icon-close {
    position: relative;
    bottom: 8px;
    font-size: 16px;
    font-weight: 600;
    color: #63656e;
    cursor: pointer;
  }

  :deep(.bk-dialog-body) {
    position: relative;
    padding-bottom: 20px;
    margin-top: 6px;
  }
}
</style>
