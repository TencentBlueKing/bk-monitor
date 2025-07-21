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
  <div>
    <!-- 聚类规则 -->
    <div class="container-item table-container flbc">
      <div class="flbc">
        <p>{{ $t('聚类规则') }}</p>
        <div class="bk-button-group template-check-content">
          <bk-button
            :class="{ 'is-selected': ruleType === 'template' }"
            size="small"
            @click="handleClickTemplateBtn('template')"
          >
            {{ $t('模板') }}
          </bk-button>
          <bk-button
            :class="{ 'is-selected': ruleType === 'customize' }"
            size="small"
            @click="handleClickTemplateBtn('customize')"
          >
            {{ $t('自定义') }}
          </bk-button>
        </div>
        <bk-select
          v-if="ruleType === 'template'"
          ref="templateListRef"
          ext-cls="template-select"
          v-model="templateRule"
          behavior="simplicity"
          searchable
          :style="'margin-left: 10px'"
          :clearable="false"
          @selected="handleSelectTemplate"
        >
          <bk-option
            v-for="option in templateList"
            :id="option.id"
            :key="option.id"
            :name="option.name"
          >
            <TemplateOption
              :config-item="option"
              :template-list="templateList"
              @operate-change="operateChange"
            />
          </bk-option>
          <template #extension>
            <FromAddInput
              :btn-str="$t('新建模板')"
              :template-list="templateList"
              :placeholder="$t('请输入模板名称')"
              @created="createTemplate"
            />
          </template>
        </bk-select>
      </div>
      <div class="table-operate">
        <bk-dropdown-menu>
          <template slot="dropdown-trigger">
            <bk-button
              style="min-width: 48px"
              class="btn-hover"
              data-test-id="LogCluster_button_addNewRules"
              size="small"
            >
              {{ $t('导入') }}
            </bk-button>
          </template>
          <ul
            class="bk-dropdown-list"
            slot="dropdown-content"
          >
            <li>
              <a
                href="javascript:;"
                @click="handleFastAddRule"
              >
                {{ $t('本地导入') }}
              </a>
            </li>
            <li>
              <a
                href="javascript:;"
                @click="handleAddRuleToIndex"
              >
                {{ $t('其他索引集导入') }}
              </a>
            </li>
          </ul>
        </bk-dropdown-menu>
        <bk-button
          style="min-width: 48px"
          class="btn-hover"
          size="small"
          @click="() => handleExportRule()"
        >
          {{ $t('导出') }}
        </bk-button>
        <bk-button
          style="min-width: 72px"
          class="btn-hover"
          data-test-id="LogCluster_button_reductionRules"
          size="small"
          @click="reductionRule"
        >
          {{ $t('恢复默认') }}
        </bk-button>
      </div>
    </div>
    <!-- 添加规则dialog -->
    <bk-dialog
      width="640"
      ext-cls="add-rule"
      v-model="isShowAddRule"
      :mask-close="false"
      :title="isEditRules ? $t('编辑规则') : $t('添加规则')"
      header-position="left"
      @after-leave="cancelAddRuleContent"
    >
      <bk-form
        ref="addRulesRef"
        :label-width="200"
        :model="addRulesData"
        form-type="vertical"
      >
        <bk-form-item
          :label="$t('正则表达式')"
          :property="'regular'"
          :rules="rules.regular"
          required
        >
          <bk-input
            style="width: 560px"
            v-model="addRulesData.regular"
          ></bk-input>
          <span>{{ $t('样例') }}：\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}</span>
        </bk-form-item>
        <bk-form-item
          :label="$t('占位符')"
          :property="'placeholder'"
          :rules="rules.placeholder"
          required
        >
          <bk-input
            style="width: 560px"
            v-model="addRulesData.placeholder"
          ></bk-input>
          <span>{{ $t('样例') }}：IP</span>
        </bk-form-item>
      </bk-form>
      <template #footer>
        <div class="flbc">
          <div class="inspection-status">
            <div
              v-if="isClickSubmit"
              class="inspection-status"
            >
              <div>
                <bk-spin
                  v-if="isDetection"
                  class="spin"
                  size="mini"
                ></bk-spin>
                <span
                  v-else
                  :style="`color:${isRuleCorrect ? '#45E35F' : '#FE5376'}`"
                  :class="['bk-icon spin', isRuleCorrect ? 'icon-check-circle-shape' : 'icon-close-circle-shape']"
                ></span>
              </div>
              <span style="margin-left: 24px">{{ detectionStr }}</span>
            </div>
          </div>

          <div>
            <bk-button
              :disabled="isDetection"
              theme="primary"
              @click="handleRuleSubmit"
            >
              {{ isRuleCorrect ? $t('保存') : $t('检测语法') }}</bk-button
            >
            <bk-button @click="isShowAddRule = false">{{ $t('取消') }}</bk-button>
          </div>
        </div>
      </template>
    </bk-dialog>
    <!-- 其他索引集导入弹窗 -->
    <bk-dialog
      width="640"
      ext-cls="add-rule"
      v-model="isShowOtherExport"
      header-position="left"
      :mask-close="false"
      :title="$t('其他索引集导入')"
      :auto-close="false"
      :loading="confirmLoading"
      @after-leave="cancelOtherExport"
      @value-change="otherExportChange"
      @confirm="otherExportConfirm"
    >
      <bk-form
        ref="exportRef"
        :label-width="90"
        :model="indexSetData"
      >
        <bk-form-item
          :label="$t('选择索引集')"
          :property="'index_set_id'"
          :rules="indexSetRules.index_set_id"
          required
        >
          <bk-select
            v-model="indexSetData.index_set_id"
            v-bkloading="{ isLoading: indexSetLoading, size: 'small' }"
            :clearable="false"
            searchable
          >
            <bk-option
              v-for="option in indexSetList"
              :id="option.id"
              :key="option.id"
              :name="option.name"
            >
            </bk-option>
          </bk-select>
        </bk-form-item>
        <bk-form-item
          :label="$t('导入模式')"
          :property="'export_type'"
          :rules="indexSetRules.export_type"
          required
        >
          <bk-radio-group v-model="indexSetData.export_type">
            <bk-radio value="replace"> {{ $t('替换') }} </bk-radio>
            <bk-radio value="assign"> {{ $t('补齐') }} </bk-radio>
          </bk-radio-group>
        </bk-form-item>
      </bk-form>
    </bk-dialog>
  </div>
</template>

<script>
import { base64Decode } from '@/common/util';
import * as authorityMap from '@/common/authority-map';
import FromAddInput from './from-input';
import TemplateOption from './template-option';
import dayjs from 'dayjs';
export default {
  components: {
    FromAddInput,
    TemplateOption,
  },
  model: {
    prop: 'value', // 对应 props msg
    event: 'change',
  },
  props: {
    value: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      isRuleCorrect: false, // 检测语法是否通过
      isClickSubmit: false, // 是否点击添加
      isDetection: false, // 是否正在检测中
      /** 检测中的文字 */
      detectionStr: '',
      /** 是否展示添加规则弹窗 */
      isShowAddRule: false,
      /** 是否展示导入其他规则弹窗 */
      isShowOtherExport: false,
      indexSetLoading: false,
      /** 是否是编辑规则 */
      isEditRules: false,
      confirmLoading: false,
      editRulesIndex: -1,
      addRulesIndex: -1,
      indexSetList: [],
      indexSetData: {
        index_set_id: '',
        export_type: 'replace',
      },
      indexSetRules: {
        index_set_id: [
          {
            required: true,
            trigger: 'blur',
          },
        ],
        export_type: [
          {
            required: true,
            trigger: 'blur',
          },
        ],
      },
      addRulesData: {
        regular: '', // 添加聚类规则正则
        placeholder: '', // 添加聚类规则占位符
        scope: 'alone',
      },
      rules: {
        regular: [
          {
            validator: this.checkRegular,
            required: true,
            trigger: 'blur',
          },
        ],
        placeholder: [
          {
            regex: /^(?!.*:)\S+/,
            required: true,
            trigger: 'blur',
          },
        ],
      },
      /** 快速导入的dom */
      inputDocument: null,
      templateRule: '',
      templateList: [],
      ruleType: 'template',
      initTemplateID: -1,
    };
  },
  computed: {
    rulesList: {
      get() {
        return this.value;
      },
      set(v) {
        this.$emit('change', v);
      },
    },
    spaceUid() {
      return this.$store.state.spaceUid;
    },
  },
  watch: {
    addRulesData: {
      deep: true,
      handler() {
        this.resetDetection();
      },
    },
  },
  mounted() {
    this.initInputType();
    this.initTemplateList();
  },
  methods: {
    /**
     * @desc: 关闭添加规则弹窗重置参数
     */
    cancelAddRuleContent() {
      this.isRuleCorrect = false;
      this.isEditRules = false;
      this.isClickSubmit = false;
      this.addRulesIndex = -1;
      this.editRulesIndex = -1;
      Object.assign(this.addRulesData, { regular: '', placeholder: '' });
      this.$refs.addRulesRef.clearError();
    },
    otherExportChange(v) {
      if (v) {
        this.requestIndexSetList();
      } else {
        this.indexSetList = [];
      }
    },
    otherExportConfirm() {
      this.$refs.exportRef
        .validate()
        .then(async () => {
          this.confirmLoading = true;
          const { index_set_id, export_type } = this.indexSetData;
          const res = await this.getClusterConfig(index_set_id);
          const importRuleArr = this.base64ToRuleArr(res.data.predefined_varibles);
          this.rulesList =
            export_type === 'replace' ? importRuleArr : this.mergeAndDeduplicate(importRuleArr, this.rulesList);
          this.isShowOtherExport = false;
          this.$emit('show-table-loading');
        })
        .finally(() => {
          this.confirmLoading = false;
        });
    },
    getClusterConfig(indexSetID) {
      try {
        const params = { index_set_id: indexSetID };
        const data = { collector_config_id: this.configID };
        return this.$http.request('/logClustering/getConfig', { params, data });
      } catch (e) {
        console.warn(e);
      }
    },
    mergeAndDeduplicate(arr1, arr2) {
      // 合并两个数组
      const combinedArray = [...arr1, ...arr2];
      // 创建一个集合用于去重
      const uniqueSet = new Set();
      // 结果数组
      const resultArray = [];
      combinedArray.forEach(item => {
        // 将对象转换为字符串进行比较，忽略 __Index__
        const key = Object.entries(item)
          .filter(([k, _]) => k !== '__Index__')
          .map(([k, v]) => `${k}:${v}`)
          .sort()
          .join('|');

        // 如果集合中没有该字符串，则添加到结果数组和集合中
        if (!uniqueSet.has(key)) {
          uniqueSet.add(key);
          resultArray.push(item);
        }
      });
      return resultArray;
    },
    async checkRegular(val) {
      const result = await this.checkRegularRequest(val);
      return result;
    },
    // 检测数据名是否可用
    async checkRegularRequest(val) {
      try {
        const res = await this.$http.request('logClustering/checkRegexp', {
          data: { regexp: val },
        });
        if (res.data) {
          return res.data;
        }
      } catch (error) {
        return false;
      }
    },
    reductionRule() {
      const ruleArr = this.base64ToRuleArr(this.tableStr);
      if (ruleArr.length > 0) {
        this.rulesList = ruleArr;
        this.$emit('show-table-loading');
      }
    },
    base64ToRuleArr(str) {
      if (!str) return [];
      try {
        const ruleList = JSON.parse(base64Decode(str));
        const ruleNewList = ruleList.reduce((pre, cur, index) => {
          const itemObj = {};
          const matchVal = cur.match(/:(.*)/);
          const key = cur.substring(0, matchVal.index);
          itemObj[key] = matchVal[1];
          itemObj.__Index__ = index;
          pre.push(itemObj);
          return pre;
        }, []);
        return ruleNewList;
      } catch (e) {
        return [];
      }
    },
    inputFileEvent() {
      // 检查文件是否选择:
      if (!this.inputDocument.value) return;
      const file = this.inputDocument.files[0];
      // 读取文件:
      const reader = new FileReader();
      reader.onload = e => {
        try {
          const list = Object.values(JSON.parse(e.target.result)).map((item, index) => {
            if (!item.placeholder || !String(item.rule)) throw new Error('无效的json');
            return {
              [item.placeholder]: String([item.rule]),
              __Index__: index,
            };
          });
          this.rulesList = list;
        } catch (err) {
          this.$bkMessage({
            theme: 'error',
            message: this.$t('不是有效的json文件'),
          });
        }
      };
      // 以Text的形式读取文件:
      reader.readAsText(file);
    },
    /** 导出规则 */
    handleExportRule(filename = '') {
      if (!this.rulesList.length) {
        this.$bkMessage({
          theme: 'error',
          message: this.$t('聚类规则为空，无法导出规则'),
        });
        return;
      }
      const eleLink = document.createElement('a');
      const time = `${dayjs().format('YYYYMMDDHHmmss')}`;
      eleLink.download = filename || `bk_log_search_download_${time}.json`;
      eleLink.style.display = 'none';
      const jsonStr = this.rulesList.reduce((pre, cur, index) => {
        const entriesArr = Object.entries(cur);
        pre[index] = {
          placeholder: entriesArr[0][0],
          rule: entriesArr[0][1],
        };
        return pre;
      }, {});
      // 字符内容转变成blob地址
      const blob = new Blob([JSON.stringify(jsonStr, null, 4)]);
      eleLink.href = URL.createObjectURL(blob);
      // 触发点击
      document.body.appendChild(eleLink);
      eleLink.click();
      document.body.removeChild(eleLink);
    },
    /**
     * @desc: 添加规则dialog
     */
    handleRuleSubmit() {
      if (this.isRuleCorrect) {
        this.$emit('show-table-loading');
        const newRuleObj = {};
        const { regular, placeholder } = this.addRulesData;
        newRuleObj[placeholder] = regular;
        // 添加渲染列表时不重复的key值
        newRuleObj.__Index__ = new Date().getTime();
        if (this.isEditRules) {
          // 编辑规则替换编辑对象
          this.rulesList.splice(this.editRulesIndex, 1, newRuleObj);
        } else {
          // 检测正则和占位符是否都重复 重复则不添加
          const isRepeat = this.isRulesRepeat(newRuleObj);
          if (!isRepeat) {
            if (this.addRulesIndex >= 0) {
              this.rulesList.splice(this.addRulesIndex + 1, 0, newRuleObj);
            } else {
              this.rulesList.push(newRuleObj);
            }
          }
        }
        this.isShowAddRule = false;
      } else {
        // 第一次点击检查时显示文案变化
        this.isDetection = true;
        this.isClickSubmit = true;
        this.detectionStr = this.$t('检验中');
        setTimeout(() => {
          this.$refs.addRulesRef.validate().then(
            () => {
              this.isRuleCorrect = true;
              this.isDetection = false;
              this.detectionStr = this.$t('检验成功');
            },
            () => {
              this.isRuleCorrect = false;
              this.isDetection = false;
              this.detectionStr = this.$t('检测失败');
            }
          );
        }, 1000);
      }
    },
    /**
     * @desc: 检测规则和占位符是否重复
     * @param { Object } newRules 检测对象
     * @returns { Boolean }
     */
    isRulesRepeat(newRules = {}) {
      return this.rulesList.some(listItem => {
        const [regexKey, regexVal] = Object.entries(newRules)[0];
        const [listKey, listVal] = Object.entries(listItem)[0];
        return regexKey === listKey && regexVal === listVal;
      });
    },
    initInputType() {
      const inputDocument = document.createElement('input');
      inputDocument.type = 'file';
      inputDocument.style.display = 'none';
      inputDocument.addEventListener('change', this.inputFileEvent);
      this.inputDocument = inputDocument;
    },
    /** 初始化模板列表 */
    async initTemplateList() {
      try {
        const res = await this.$http.request('logClustering/ruleTemplate', {
          params: {
            space_uid: this.spaceUid,
          },
        });
        this.templateList = res.data.map((item, index) => ({
          ...item,
          isShowEdit: false,
          name: item.template_name,
          editStr: item.template_name,
          index,
        }));
        return Promise.resolve(res);
      } catch (err) {
        console.error(err);
        return Promise.reject(err);
      }
    },
    /** 创建模板 */
    createTemplate(name) {
      this.$http
        .request('logClustering/createTemplate', {
          data: {
            space_uid: this.spaceUid,
            template_name: name,
          },
        })
        .then(res => {
          if (res.code === 0) {
            this.initTemplateList();
          }
        })
        .catch(err => {
          console.error(err);
        });
    },
    /** 快速添加规则 */
    handleFastAddRule() {
      this.inputDocument.click(); // 本地文件回填
    },
    handleAddRuleToIndex() {
      this.isShowOtherExport = true;
    },
    resetDetection() {
      this.isDetection = false;
      this.isClickSubmit = false;
      this.isRuleCorrect = false;
    },
    clusterEdit(index) {
      const [key, val] = Object.entries(this.rulesList[index])[0];
      Object.assign(this.addRulesData, { regular: val, placeholder: key });
      this.editRulesIndex = index;
      this.isEditRules = true;
      this.isShowAddRule = true;
    },
    clusterAddRule(index) {
      Object.assign(this.addRulesData, { regular: '', placeholder: '' });
      this.addRulesIndex = index;
      this.isEditRules = false;
      this.isShowAddRule = true;
    },
    requestIndexSetList() {
      this.indexSetLoading = true;
      this.$http
        .request('retrieve/getIndexSetList', {
          query: {
            space_uid: this.spaceUid,
          },
        })
        .then(res => {
          if (res.data.length) {
            const indexSetList = [];
            for (const item of res.data) {
              if (item.permission?.[authorityMap.SEARCH_LOG_AUTH] && item.tags.map(item => item.tag_id).includes(8)) {
                indexSetList.push({
                  name: item.index_set_name,
                  id: item.index_set_id,
                });
              }
            }
            this.indexSetList = indexSetList;
          }
        })
        .catch(e => {
          console.warn(e);
        })
        .finally(() => {
          this.indexSetLoading = false;
        });
    },
    cancelOtherExport() {
      this.indexSetData.index_set_id = '';
      this.indexSetData.export_type = 'replace';
    },
    operateChange(type, configItem) {
      switch (type) {
        case 'delete':
          this.handleDeleteTemplate(configItem);
          break;
        case 'update':
          this.handleUpdateTemplateName(configItem);
        case 'edit':
          this.handleEditTemplateName(configItem.index);
          break;
        case 'cancel':
          this.handleCancelEditTemplate(configItem.index);
          break;
      }
    },
    handleSelectTemplate(value) {
      this.templateRule = value;
      const selectTemplateStr = this.templateList.find(item => item.id === value).predefined_varibles;
      this.rulesList = this.base64ToRuleArr(selectTemplateStr);
      this.$emit('show-table-loading');
    },
    handleEditTemplateName(index) {
      this.templateList.forEach(item => (item.isShowEdit = false));
      this.templateList[index].isShowEdit = true;
    },
    /** 编辑配置 */
    handleUpdateTemplateName(configItem) {
      this.$http
        .request('logClustering/updateTemplateName', {
          params: {
            regex_template_id: configItem.id,
          },
          data: {
            template_name: configItem.editStr,
          },
        })
        .then(res => {
          if (res.code === 0) {
            this.templateList[configItem.index].name = configItem.editStr;
            this.templateList[configItem.index].isShowEdit = false;
            this.$bkMessage({
              theme: 'success',
              message: this.$t('操作成功'),
            });
          }
        })
        .catch(err => {
          console.error(err);
        });
    },
    handleCancelEditTemplate(index) {
      this.templateList[index].editStr = this.templateList[index].name;
      this.templateList[index].isShowEdit = false;
    },
    handleDeleteTemplate(configItem) {
      this.$http
        .request('logClustering/deleteTemplate', {
          params: {
            regex_template_id: configItem.id,
          },
        })
        .then(res => {
          if (res.code === 0) {
            this.initTemplateList().then(() => {
              this.$refs.templateListRef.show();
              this.$bkMessage({
                theme: 'success',
                message: this.$t('操作成功'),
              });
            });
          }
        })
        .catch(err => {
          console.error(err);
        });
    },
    handleClickTemplateBtn(val) {
      this.ruleType = val;
      const btnShowID = this.initTemplateID === 0 ? this.templateList[0].id : this.initTemplateID;
      this.templateRule = val === 'customize' ? 0 : btnShowID;
      if (val !== 'customize') this.handleSelectTemplate(btnShowID);
    },
    initTemplateSelect(v) {
      this.templateRule = v.regex_template_id;
      this.ruleType = v.regex_rule_type;
      this.initTemplateID = v.regex_template_id;
    },
  },
  beforeDestroy() {
    this.inputDocument.removeEventListener('change', this.inputFileEvent);
    this.inputDocument = null;
  },
};
</script>
<style lang="scss" scoped>
  /* stylelint-disable no-descending-specificity */
  .container-item {
    margin-bottom: 10px;

    .add-box {
      min-width: 48px;

      .bk-icon {
        left: -3px;
        width: 10px;
      }
    }

    &.table-container {
      position: relative;
      height: 32px;

      p {
        font-size: 12px;
      }

      .table-operate {
        position: absolute;
        top: 0;
        right: 0;

        .bk-button {
          margin-left: 2px;
          border-radius: 3px;
        }

        .btn-hover {
          &:hover {
            color: #3a84ff;
            border: 1px solid #3a84ff;
          }
        }
      }
    }

    .template-check-content {
      margin-left: 20px;
    }

    .cluster-table {
      border: 1px solid #dcdee5;
      border-bottom: none;
      border-radius: 2px;
    }
  }

  .template-select {
    min-width: 200px;
  }

  .add-rule {
    .bk-form {
      width: 560px;
      padding-top: 8px;
      font-size: 12px;

      .bk-label {
        text-align: left;
      }
    }

    .bk-form-control {
      display: flex;
      align-items: center;
      height: 32px;

      .bk-form-radio {
        margin-right: 20px;
      }
    }
  }

  .flbc {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .inspection-status {
    position: relative;
    display: flex;
    font-size: 14px;

    .bk-icon {
      font-size: 18px;
    }

    .spin {
      position: absolute;
      top: 2px;
    }
  }
</style>
