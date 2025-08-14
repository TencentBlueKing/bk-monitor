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
    v-bkloading="{ isLoading: loading, extCls: 'bk-loading-fixed' }"
    class="metric-dimension"
  >
    <div class="dialog-hearder">
      <div
        v-if="!isFromHome"
        class="title"
      >
        {{ $t('设置指标&维度') }}
      </div>
      <!-- 顶部按钮 -->
      <div class="set-button">
        <bk-button
          v-authority="{
            active: !authority.MANAGE_AUTH,
          }"
          class="mc-btn-add add-btn btn"
          @click="authority.MANAGE_AUTH ? handleAddGroup() : handleShowAuthorityDetail()"
        >
          {{ $t('新建分组') }}
        </bk-button>
        <bk-dropdown-menu :disabled="!canMoveBtn">
          <bk-button
            slot="dropdown-trigger"
            type="primary"
            class="move"
          >
            <span>{{ $t('移动到...') }}</span>
            <i class="bk-icon icon-angle-down" />
          </bk-button>
          <ul
            slot="dropdown-content"
            v-authority="{
              active: !authority.MANAGE_AUTH,
            }"
            class="bk-dropdown-list"
            style="overflow: auto"
            @click="!authority.MANAGE_AUTH && handleShowAuthorityDetail()"
          >
            <li
              v-for="(name, index) in groupNameList"
              :key="index"
              class="move-btn"
              @click="authority.MANAGE_AUTH && handleMoveGroup(name)"
            >
              {{ name }}
            </li>
          </ul>
        </bk-dropdown-menu>
        <bk-popover
          placement="top-start"
          :tippy-options="tippyOptions"
          :delay="200"
        >
          <bk-button
            v-if="!isFromHome"
            class="mc-btn-add btn"
            style="margin-left: 8px"
            @click="handleRefreshData"
            >{{ $t('button-刷新') }}</bk-button
          >
          <div slot="content">
            <div>{{ $t('此刷新仅追加新获取的指标和维度') }}</div>
          </div>
        </bk-popover>
        <div class="set-right">
          <!-- <span class="mr-10">{{ $t('如需编辑可在下方自定义添加或') }}</span>
                    <span class="blue mr-14" @click="handleUploadMetric">{{ $t('上传文件') }}</span>
                    <input type="file" multiple accept=".json" ref="uploadMetricFile" @change="getFileInfo" style="display: none;">
                    <a class="blue mr-14" href="javascript:void(0);" @click="handleDownloadMetricJson"> {{ $t('下载样例') }} </a> -->
          <template v-if="!isFromHome">
            <monitor-import
              v-authority="{ active: !authority.MANAGE_AUTH }"
              style="margin-right: 10px; color: #3a84ff"
              :return-text="true"
              accept="application/json"
              @change="data => (authority.MANAGE_AUTH ? handleImportMetric(data) : handleShowAuthorityDetail())"
            />
            <span style="color: #dcdee5">|</span>
            <monitor-export
              v-authority="{ active: !authority.MANAGE_AUTH }"
              @click="cb => (authority.MANAGE_AUTH ? handleExportMetric(cb) : handleShowAuthorityDetail())"
            />
            <span>{{ $t('数据时间:') }}{{ dataTime }}</span>
            <span
              class="blue dataPreview"
              @click="handleShowData"
              >{{ $t('预览') }}</span
            >
            <bk-switcher
              v-model="dataPreview"
              size="small"
              theme="primary"
            />
          </template>
          <template v-else>
            <i class="bk-icon icon-exclamation-circle-shape risk-icon" />
            <span class="mr-10">{{ $t('编辑指标或维度存在风险') }}</span>
            <bk-popover
              class="change-name"
              placemnet="top-end"
            >
              <span class="blue mr-14">{{ $t('查看风险点') }}</span>
              <div slot="content">
                {{ $t('注意在仪表盘和策略中使用了修改前的指标将失效') }}
              </div>
            </bk-popover>
            <span style="color: #dcdee5">|</span>
            <monitor-import
              v-authority="{ active: !authority.MANAGE_AUTH }"
              style="margin: 0 10px; color: #3a84ff"
              :return-text="true"
              @change="data => (authority.MANAGE_AUTH ? handleImportMetric(data) : handleShowAuthorityDetail())"
            />
            <span style="color: #dcdee5">|</span>
            <monitor-export
              v-authority="{ active: !authority.MANAGE_AUTH }"
              @click="cb => (authority.MANAGE_AUTH ? handleExportMetric(cb) : handleShowAuthorityDetail())"
            />
            <span style="color: #dcdee5">|</span>
            <span
              class="blue dataPreview"
              @click="handleHideStop"
              >{{ $t('隐藏已停用') }}</span
            >
            <bk-switcher
              v-model="hideStop"
              size="small"
              theme="primary"
              @change="handleHideActive"
            />
          </template>
        </div>
      </div>
    </div>
    <!-- 指标/维度表格 -->
    <metric-group
      v-for="(group, index) in tableData"
      :key="index"
      :metric-data="group.fields"
      :group-name="`${group.table_name}(${group.table_desc})`"
      :group-index="index"
      :unit-list="unitList"
      :is-show-data="dataPreview"
      :os-type-list="osTypeList"
      :name-list="nameList"
      :desc-name-list="descNameList(group.fields)"
      :is-from-home="isFromHome"
      :stop-data="stopedData[index]"
      :hide-stop="hideStop"
      :type-list="typeList"
      @edit-group="handleEditGroup"
      @del-group="handleDelGroup"
      @add-row="handleAddRow"
      @del-row="handleDelRow"
      @add-first="handleAddFirstRow"
      @switch="handleMetricSwitch"
    />
    <div class="footer-btn mb10">
      <bk-button
        v-authority="{
          active: !authority.MANAGE_AUTH,
        }"
        class="mc-btn-add add-btn btn mr-r"
        theme="primary"
        :disabled="loading"
        @click="authority.MANAGE_AUTH ? handleSave() : handleShowAuthorityDetail()"
      >
        {{ $t('保存') }}
      </bk-button>
      <bk-button
        v-if="!isFromHome"
        class="mc-btn-add add-btn btn mr-r"
        theme="primary"
        @click="handleBackPlugin"
      >
        {{ $t('返回') }}
      </bk-button>
      <bk-button
        v-else-if="isFromHome || isShowCancel"
        class="mc-btn-add add-btn btn"
        @click="handleCancel"
      >
        {{ $t('取消') }}
      </bk-button>
    </div>
    <!-- 新建/编辑分组dialog -->
    <bk-dialog
      v-model="groupDialog.isShow"
      :mask-close="false"
      header-position="left"
      :show-footer="false"
      :width="480"
      :title="groupDialog.isEdit ? $t('编辑指标分类') : $t('增加指标分类')"
      @after-leave="afterLeave"
      @confirm="handleSetGroup"
    >
      <div class="metric-name">
        <div class="hint">
          <i class="icon-monitor icon-tips" />
          {{ $t('指标分类的定义影响指标检索的时候,如试图查看，仪表盘添加视图和添加监控策略时选择指标的分类。') }}
        </div>
        <span class="item required">{{ $t('英文名') }}</span>
        <verify-input
          class="verify-input"
          :validator="{ content: $t('输入指标名,以字母开头,允许包含下划线和数字') }"
          :show-validate.sync="rule.isNameEmpty"
        >
          <bk-input
            v-model.trim="groupDialog.name"
            :placeholder="$t('英文名')"
            @blur="rule.isNameEmpty = !regx.test(groupDialog.name)"
          />
        </verify-input>
        <span class="item"> {{ $t('别名') }} </span>
        <verify-input>
          <bk-input
            v-model="groupDialog.desc"
            :placeholder="$t('别名')"
          />
        </verify-input>
      </div>
      <div class="footer">
        <bk-button
          class="confirm-btn"
          theme="primary"
          @click="handleSetGroup"
        >
          {{ $t('确认') }}
        </bk-button>
        <bk-button @click="groupDialog.isShow = false">
          {{ $t('取消') }}
        </bk-button>
      </div>
    </bk-dialog>
  </div>
</template>

<script>
import dayjs from 'dayjs';
import { releaseCollectorPlugin } from 'monitor-api/modules/model';
import { saveMetric } from 'monitor-api/modules/plugin';
import { getUnitList } from 'monitor-api/modules/strategies';
import { random } from 'monitor-common/utils/utils';

import MonitorExport from '../../../../../components/monitor-export/monitor-export';
import MonitorImport from '../../../../../components/monitor-import/monitor-import';
import VerifyInput from '../../../../../components/verify-input/verify-input.vue';
import MetricGroup from './metric-group.vue';

const MAX_NUM_METRIC_DIM = 5000; /** 插件允许指标维度最大条数 */
const MAX_NUM_METRIC_DIM_SNMP = 500; /** snmp插件允许指标维度最大条数 */
export default {
  name: 'MetricDimensionDialog',
  components: {
    MetricGroup,
    VerifyInput,
    MonitorExport,
    MonitorImport,
  },
  inject: ['authority', 'handleShowAuthorityDetail'],
  props: {
    dataTime: {
      type: String,
    },
    osTypeList: {
      //  操作系统类型
      type: Array,
      default: () => [],
    },
    metricJson: {
      //  指标/维度数据
      type: Array,
      default: () => [],
    },
    pluginData: {
      //  保存指标/维度必要的插件数据
      type: Object,
      default: () => ({}),
    },
    isFromHome: {
      //  是否首页入口或者详情入口
      type: Boolean,
      default: false,
    },
    isToken: Boolean, //  是否发布
    pluginType: {
      // 插件类型
      type: String,
    },
  },
  data() {
    return {
      loading: false,
      dataPreview: false, //  数据预览开关
      hideStop: false,
      noActive: false,
      groupDialog: {
        //  新增/编辑分组dialog数据
        isEdit: false,
        isShow: false,
        name: '',
        desc: '',
        index: -1,
      },
      regx: /^[_|a-zA-Z][a-zA-Z0-9_]*$/, // 分组名字校验规则
      rule: {
        isNameEmpty: false,
      },
      tableData: [],
      stopedData: {},
      unitList: [],
      tippyOptions: {
        distance: 0,
      },
      isShowCancel: false,
    };
  },
  computed: {
    //  分组名称列表
    groupNameList() {
      return this.tableData.map(group => group.table_name);
    },
    /** 是否为snmp插件 */
    isSnmp() {
      return this.pluginType === 'SNMP';
    },
    //  英文名列表
    nameList() {
      let list = [];
      this.tableData.forEach(group => {
        const res = group.fields.map(item => item.name);
        list = list.concat(res);
      });
      return list;
    },
    //  是否有数据，并且至少有一个启用
    haveData() {
      const nameRes = this.tableData.some(group => group.fields.some(item => item.monitor_type === 'metric'));
      const activeRes = this.tableData.some(group => group.fields.some(item => item.is_active));
      return activeRes && nameRes;
    },
    //  能否保存
    canSave() {
      // 指标全局唯一
      let isMetricRepeat = false;
      const metricExisted = [];
      this.tableData.some(row =>
        row.fields
          .filter(item => item.monitor_type === 'metric')
          .some(item => {
            if (metricExisted.includes(item)) {
              isMetricRepeat = true;
              return true;
            }
            metricExisted.push(item);
            return false;
          })
      );
      // 维度组里唯一
      let isDimensionRepeat = false;
      this.tableData.some(row => {
        const existed = [];
        return row.fields
          .filter(item => item.monitor_type === 'dimension')
          .some(item => {
            if (existed.includes(item)) {
              isDimensionRepeat = true;
              return true;
            }
            existed.push(item);
          });
      });
      // 别名全局唯一
      let isDescRepeat = false;
      const descExisted = [];
      this.tableData.some(row =>
        row.fields
          .filter(item => item.description !== '')
          .some(item => {
            if (descExisted.includes(item)) {
              isDescRepeat = true;
              return true;
            }
            descExisted.push(item);
            return false;
          })
      );
      return !isMetricRepeat && !isDimensionRepeat && !isDescRepeat;
    },
    canMoveBtn() {
      //  能否启用移动
      const res = this.tableData.some(group => group.fields.some(item => item.isCheck));
      return res;
    },
    //  下载的样例模板
    metricJsonExample() {
      return []; // 功能关闭，待确认模板
    },
    typeList() {
      const list = [
        //  类别表
        { id: 'double', name: 'double' },
        { id: 'int', name: 'int' },
      ];
      if (this.pluginData && ['Script', 'JMX', 'Exporter', 'Pushgateway'].includes(this.pluginData.plugin_type)) {
        list.push({ id: 'diff', name: 'diff' });
      }
      return list;
    },
  },
  watch: {
    metricJson: {
      handler(newV) {
        this.tableData = JSON.parse(JSON.stringify(newV));
        this.handleTabelDataChange();
      },
      deep: true,
    },
  },
  created() {
    this.loading = true;
    this.getUnitListData();
    this.loading = false;
  },
  methods: {
    /**
     * 是否允许继续添加指标维度
     * @param tableData 指标维度数据
     * @param isImport 是否导入数据
     **/
    isAllowAddItem(tableData = this.tableData, isImport = false) {
      const num = tableData.reduce((total, group) => (total += group.fields.length), 0);
      const max = this.isSnmp ? MAX_NUM_METRIC_DIM_SNMP : MAX_NUM_METRIC_DIM;
      return isImport ? num <= max : num < max;
    },
    /** 新增、导入指标维度超过最大值提示 */
    handleMaxMetircDimMsg() {
      const message = this.$t(
        this.isSnmp ? 'SNMP设置指标数量超过{n}，请删减非必要指标' : '设置指标数量超过{n}，请删减非必要指标',
        { n: this.isSnmp ? MAX_NUM_METRIC_DIM_SNMP : MAX_NUM_METRIC_DIM }
      );
      this.$bkMessage({
        message,
        theme: 'error',
      });
    },
    //  别名列表
    descNameList(fields) {
      return fields.map(item => item.description);
    },
    handleTabelDataChange() {
      this.tableData.forEach((group, groupIndex) => {
        group.fields.forEach(item => {
          item.id = random(10);
          if (item.monitor_type === 'metric' && item.type === 'double' && item.is_diff_metric) {
            item.type = 'diff';
          }
          if (!item.is_active) {
            // 初始化停用数据
            this.handleMetricSwitch(groupIndex, item);
          }
        });
      });
      this.handleSortTableData();
    },
    //  获取动态单位数据
    async getUnitListData() {
      await getUnitList()
        .then(data => {
          this.unitList = data.map(item => ({
            ...item,
            children: item.formats,
            id: item.name,
          }));
        })
        .catch(() => {});
    },
    // 获取新行数据
    getNewRow(type, name, isDel) {
      const item = {
        monitor_type: type,
        name,
        description: '',
        source_name: '',
        value: {
          linux: null,
          windows: null,
          aix: null,
        },
        isFirst: false,
        is_active: true,
        is_diff_metric: false,
        isCheck: false,
        isDel,
        errValue: false,
        reValue: false,
        descReValue: false,
        showInput: false,
        id: random(10),
      };
      if (type === 'metric') {
        item.order = 1;
        item.dimensions = [];
        item.type = 'double';
        item.unit = 'none';
      } else {
        item.order = 3;
        item.type = 'string';
        item.unit = '--';
      }
      return item;
    },
    //  排序
    handleSortTableData() {
      this.tableData.forEach(item => {
        item.fields.sort((a, b) => a.order - b.order);
      });
    },
    //  新增分组
    handleAddGroup() {
      this.groupDialog.isShow = true;
    },
    //  数据预览开关
    handleShowData() {
      this.dataPreview = !this.dataPreview;
    },
    //  隐藏已停用
    handleHideStop() {
      this.tableData.forEach(item => {
        item.fields = item.fields.filter(row => row.is_active);
      });
      this.hideStop = true;
    },
    // 启用停用隐藏
    handleHideActive(status) {
      if (status) {
        this.handleHideStop();
      } else {
        this.tableData.forEach((item, index) => {
          const arr = this.stopedData[index] || [];
          arr.forEach(row => {
            item.fields.splice(row.index, 0, row.data);
          });
        });
      }
    },

    // 停用或启用指标时抛出的事件
    handleMetricSwitch(groupindex, data) {
      const index = this.tableData[groupindex]?.fields.findIndex(item => item.id === data.id);
      const arr = this.stopedData[groupindex];
      if (Array.isArray(arr)) {
        const elIndex = arr.findIndex(item => item.data.id === data.id);
        if (elIndex > -1) {
          this.stopedData[groupindex].splice(elIndex, 1);
        } else {
          this.stopedData[groupindex].push({ index, data });
        }
      } else {
        this.stopedData[groupindex] = [{ index, data }];
      }
    },
    //  保存分组校验
    handleSetGroup() {
      const group = this.groupDialog;
      // 校验分组名字是否符合命名规范
      const isTrueName = this.regx.test(group.name);
      this.rule.isNameEmpty = !isTrueName;
      if (!isTrueName) {
        return;
      }
      // 编辑情况下未变名字
      if (
        group.isEdit &&
        this.tableData[group.index].table_name === group.name &&
        this.tableData[group.index].table_desc === group.desc
      ) {
        group.isShow = false;
        return;
      }
      // 校验分组名字是否与关键字冲突
      const res = this.tableData.some(
        item => item.table_name === group.name && item.table_name !== this.tableData[group.index].table_name
      );
      if (res) {
        this.$bkMessage({ theme: 'error', message: `${this.$t('注意: 名字冲突')}` });
        return;
      }
      // 新增/编辑
      if (group.isEdit) {
        this.tableData[group.index].table_name = group.name;
        this.tableData[group.index].table_desc = group.desc || group.name;
        group.isEdit = false;
      } else {
        this.tableData.push({
          table_name: group.name,
          table_desc: group.desc || group.name,
          fields: [],
        });
      }
      group.isShow = false;
    },
    // 编辑分组回填
    handleEditGroup(index) {
      const group = this.groupDialog;
      group.isShow = true;
      group.isEdit = true;
      group.index = index;
      group.name = this.tableData[index].table_name;
      group.desc = this.tableData[index].table_desc;
    },
    //  删除分组
    handleDelGroup(index) {
      this.tableData.splice(index, 1);
    },
    //  关闭dialog回调
    afterLeave() {
      this.groupDialog.name = '';
      this.groupDialog.desc = '';
      this.groupDialog.isEdit = false;
      this.rule.isNameEmpty = false;
    },
    //  在当前行下新增一行
    handleAddRow(row, index, groupIndex) {
      if (!this.isAllowAddItem()) {
        /** 超出最大限制无法添加 */
        this.handleMaxMetircDimMsg();
        return;
      }
      const arr = this.tableData[groupIndex].fields;
      const item = this.getNewRow(row.monitor_type, '', true);
      const dataIndex = arr.findIndex(item => item.id === row.id);
      arr.splice(dataIndex + 1, 0, item);
    },
    //  删除行
    handleDelRow(row, index, groupIndex) {
      const arr = this.tableData[groupIndex].fields;
      const dataIndex = arr.findIndex(item => item.id === row.id);
      arr.splice(dataIndex, 1);
    },
    //  新增初始行
    handleAddFirstRow(index) {
      this.tableData[index].fields.push(this.getNewRow('metric', '', true));
      this.tableData[index].fields.push(this.getNewRow('dimension', '', true));
    },
    // 先移动所有可以移动的指标， 最后移动维度
    // 对于指标直接从原分组删除移动到目标分组，单个维度如果关联多个指标，则只进行copy
    handleMoveGroup(name) {
      let targetGroup = null;
      const result = [];
      this.tableData.forEach((group, index) => {
        if (group.table_name !== name) {
          const metrics = [];
          const dimensions = [];
          group.fields.forEach(item => {
            item.monitor_type === 'metric' ? metrics.push(item) : dimensions.push(item);
          });
          const stopedData = this.stopedData[index];
          // 处理被停用数据中可能需要移动的数据
          if (Array.isArray(stopedData)) {
            for (let i = stopedData.length - 1; i > -1; i--) {
              const row = stopedData[i].data;
              if (row.isCheck && row.monitor_type === 'metric') {
                row.isCheck = false;
                result.push(row);
                stopedData.splice(i, 1);
              }
              if (row.monitor_type === 'dimension') {
                dimensions.push(row);
              }
            }
          }
          [...metrics, ...dimensions].forEach(item => {
            if (item.isCheck) {
              if (item.monitor_type === 'metric') {
                const findIndex = group.fields.findIndex(row => row.name === item.name);
                group.fields.splice(findIndex, 1);
              } else {
                // 获取每一次循环新的metrics
                const curMetrics = group.fields.filter(row => row.monitor_type === 'metric');
                if (!this.checkDimensionRelevance(item, curMetrics)) {
                  let findIndex = group.fields.findIndex(row => row.name === item.name);
                  if (findIndex === -1 && Array.isArray(stopedData)) {
                    findIndex = stopedData.findIndex(
                      row => row.monitor_type === 'dimension' && row.data.name === item.name
                    );
                    stopedData.splice(findIndex, 1);
                  } else {
                    // 若但前分组维度还有关联的指标则不需要删除维度
                    if (metrics.filter(metric => metric.dimensions.includes(item.name)).length <= 1) {
                      group.fields.splice(findIndex, 1);
                    }
                  }
                }
              }
              item.isCheck = false;
              result.push(item);
            }
          });
        } else {
          targetGroup = group.fields;
          targetGroup.forEach(item => {
            item.isCheck = false;
          });
        }
      });
      // 移动目标到分组
      result.forEach(item => {
        const index = targetGroup.findIndex(row => row.name === item.name && row.monitor_type === item.monitor_type);
        const obj = item.monitor_type === 'metric' ? item : { ...item };
        if (index > -1) {
          targetGroup.splice(index, 1, obj);
        } else {
          targetGroup.push(obj);
        }
      });
      // 重新排序
      this.handleSortTableData();
    },
    // 检查单个维度是否关联了1个以上的指标
    checkDimensionRelevance(dimension, metrics) {
      return metrics.filter(metric => metric.dimensions.includes(dimension.name)).length > 1;
    },
    //  删除已勾选的指标/维度
    handleDelAllCheck(arr) {
      arr.forEach((item, index) => {
        if (item.isCheck) {
          arr.splice(index, 1);
        }
      });
      if (arr.find(item => item.isCheck)) this.handleDelAllCheck(arr);
    },
    //  保存指标/维度
    async handleSave() {
      const cacheData = JSON.parse(JSON.stringify(this.tableData));
      //  过滤新增但没填名字的指标/维度
      cacheData.forEach(group => {
        group.fields = group.fields.filter(item => item.name);
      });
      //  过度空的分组
      const tableData = cacheData.filter(group => group.fields.length !== 0);
      if (!this.haveData) {
        this.$bkMessage({ theme: 'error', message: this.$t('每个分组至少设置一个指标并且是启用状态') });
        return;
      }
      if (!this.canSave) {
        this.$bkMessage({
          theme: 'error',
          message: this.$t('所有的指标/维度的英文名和别名不能重名或为空'),
        });
        return;
      }
      // 前端业务逻辑字段，传给后端时删掉
      const frontEndParams = ['descReValue', 'errValue', 'isCheck', 'isDel', 'isFirst', 'id', 'reValue', 'showInput'];
      const params = {
        plugin_id: this.pluginData.plugin_id,
        plugin_type: this.pluginData.plugin_type,
        config_version: this.pluginData.config_version,
        info_version: this.pluginData.info_version,
        metric_json: (tableData || []).map(item => ({
          ...item,
          fields: item.fields.map(set => {
            const tmpSet = { ...set };
            if (set.monitor_type === 'metric' && set.type === 'diff') {
              tmpSet.type = 'double';
              tmpSet.is_diff_metric = true;
            }
            frontEndParams.forEach(filed => {
              delete tmpSet[filed];
            });
            return tmpSet;
          }),
        })),
      };
      if (this.isFromHome || !this.isToken) {
        params.need_upgrade = true;
      }
      if (this.loading) return;
      this.loading = true;
      const data = await saveMetric(params, { needMessage: false }).catch(err => {
        this.$bkMessage({ theme: 'error', message: err.message, ellipsisLine: 0 });
        return false;
      });
      if (data) {
        let result = true;
        if (data.token) {
          result = await releaseCollectorPlugin(this.pluginData.plugin_id, data)
            .then(() => true)
            .catch(() => false);
        }
        result && this.handleSucessSave(data);
      }
      this.loading = false;
    },
    handleSucessSave(data) {
      this.isShowCancel = true;
      this.$emit('change-version', data);
      this.handleCancel();
    },
    //  取消
    handleCancel() {
      if (this.isFromHome) {
        this.$router.back();
      } else {
        this.$emit('close-dialog');
      }
    },
    //  刷新指标数据
    handleRefreshData() {
      this.loading = true;
      setTimeout(() => {
        this.$emit('refresh-data', this.tableData);
        this.loading = false;
      }, 1000);
    },
    // //  上传文件
    // handleUploadMetric () {
    //     this.$refs.uploadMetricFile.click()
    // },
    //  获取上传文件的信息
    async getFileInfo(e) {
      const files = Array.from(e.target.files);
      this.isImport = true;
      const result = [];
      let len = 0;
      await new Promise(resolve => {
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
                  table_name: item.table_name || '',
                  table_desc: item.table_desc || '',
                });
              });
            }
            len += 1;
            if (len === files.length) {
              resolve(result);
            }
          };
          reader.readAsText(file, 'UTF-8');
        });
      });
      this.$bkMessage({ theme: 'success', message: this.$t('文件上传成功') });
      this.tableData = result;
      e.target.value = '';
    },
    //  下载Json文件
    handleDownloadMetricJson() {
      const downlondEl = document.createElement('a');
      const blob = new Blob([JSON.stringify(this.metricJsonExample, null, 4)]);
      const fileUrl = URL.createObjectURL(blob);
      downlondEl.href = fileUrl;
      downlondEl.download = 'metric.json';
      downlondEl.style.display = 'none';
      document.body.appendChild(downlondEl);
      downlondEl.click();
      document.body.removeChild(downlondEl);
    },
    handleBackPlugin() {
      this.$emit('close-dialog');
      this.$emit('back-plugin');
    },
    handleExportMetric(cb) {
      typeof cb === 'function' &&
        cb(
          this.tableData
            .filter(item => item.table_name)
            .map(item => ({
              ...item,
              fields: item?.fields
                ?.filter(item => item.name)
                .map(({ description, monitor_type, is_diff_metric, name, type, unit, is_active, dimensions = [] }) => {
                  if (monitor_type === 'metric') {
                    return {
                      description,
                      is_active,
                      is_diff_metric,
                      monitor_type,
                      name,
                      type,
                      unit,
                      dimensions,
                    };
                  }
                  return {
                    description,
                    monitor_type,
                    name,
                    type,
                    unit,
                    is_active,
                  };
                }),
            })),
          `${this.pluginData.plugin_id}-${dayjs.tz().format('YYYY-MM-DD HH-mm-ss')}.json`
        );
    },
    handleImportMetric(data) {
      let dataJson = null;
      try {
        dataJson = JSON.parse(data);
      } catch (error) {
        console.log(error);
      }
      const list = [];
      const errorList = [];
      const allMetricFieldList = [];
      if (dataJson?.length) {
        dataJson.forEach((item, index) => {
          if (item.table_name) {
            const tableItem = {
              table_name: item.table_name,
              table_desc: item.table_desc || item.table_name,
              fields: [],
            };
            const fieldList = [];
            const oldTableItem = this.tableData.find(set => set.table_name === item.table_name);
            item.fields.forEach((field, childIndex) => {
              if (!field.name) {
                errorList.push(
                  this.$t('分组：{tableName} 第{index}个字段未填写名称', {
                    tableName: item.table_name,
                    index: childIndex + 1,
                  })
                );
              }
              // else if (fieldList.some(set => set.name === field.name)) {
              //   errorList.push(this.$t(
              //     '分组：{tableName} 指标名：{fieldName}重复'
              //     , { tableName: item.table_name,  fieldName: field.name }
              //   ))
              // }
              if (fieldList.some(set => set.description !== '' && set.description === field.description)) {
                errorList.push(
                  this.$t('分组：{tableName} 别名：{fieldName}重复', {
                    tableName: item.table_name,
                    fieldName: field.description,
                  })
                );
              }
              if (field.monitor_type === 'metric') {
                if (allMetricFieldList.some(set => set.name === field.name)) {
                  errorList.push(
                    this.$t('分组：{tableName} 指标名：{fieldName}重复', {
                      tableName: item.table_name,
                      fieldName: field.name,
                    })
                  );
                }
                const metricItem = this.getDefaultMetric(field);
                const oldMetricItem = oldTableItem?.fields.find(
                  set => set.name === metricItem.name && set.monitor_type === metricItem.monitor_type
                );
                if (oldMetricItem?.value) {
                  metricItem.value = oldMetricItem.value;
                }
                fieldList.push(metricItem);
                allMetricFieldList.push(metricItem);
              } else if (field.monitor_type === 'dimension') {
                if (fieldList.some(set => set.name === field.name)) {
                  errorList.push(
                    this.$t('分组：{tableName} 指标名：{fieldName}重复', {
                      tableName: item.table_name,
                      fieldName: field.name,
                    })
                  );
                }
                const dimensionItem = this.getDefaultDimension(field);
                const oldDimensionItem = oldTableItem?.fields.find(
                  set => set.name === dimensionItem.name && set.monitor_type === dimensionItem.monitor_type
                );
                if (oldDimensionItem?.value) {
                  dimensionItem.value = oldDimensionItem.value;
                }
                fieldList.push(dimensionItem);
                allMetricFieldList.push(dimensionItem);
              } else {
                errorList.push(
                  this.$t('分组：{tableName} 字段：{fieldName}填写字段分类错误', {
                    tableName: item.table_name,
                    fieldName: field.name,
                  })
                );
              }
            });
            tableItem.fields = fieldList;
            list.push(tableItem);
          } else {
            errorList.push(this.$t('第{index}个分组未填写字段table_name', { index: index + 1 }));
          }
        });
      } else {
        this.$bkMessage({
          theme: 'error',
          message: this.$t('未检测到需要导入的指标和维度'),
        });
        return;
      }
      if (errorList.length) {
        this.$bkMessage({
          theme: 'error',
          message: this.$createElement(
            'ul',
            {},
            errorList.map(message => this.$createElement('li', {}, message))
          ),
          delay: 10000,
          ellipsisLine: 0,
        });
        return;
      }
      if (!this.isAllowAddItem(list, true)) {
        this.handleMaxMetircDimMsg();
        return;
      }
      this.tableData = JSON.parse(JSON.stringify(list));
      this.handleTabelDataChange();
    },
    getDefaultMetric({
      description = '',

      is_active = true,

      is_diff_metric = false,
      name,
      type = 'double',
      unit = 'none',
      dimensions = [],
    }) {
      return {
        dimensions,
        description,
        is_active,
        is_diff_metric,
        monitor_type: 'metric',
        name,
        type,
        unit,
        source_name: '',
        showInput: false,
        isCheck: false,
        isDel: true,
        value: {
          linux: null,
          windows: null,
          aix: null,
        },
        order: 1,
        id: random(10),
      };
    },
    getDefaultDimension({
      description = '',

      is_active = true,
      name,
    }) {
      return {
        description,
        is_active,
        is_diff_metric: false,
        monitor_type: 'dimension',
        name,
        type: 'string',
        unit: 'none',
        source_name: '',
        showInput: false,
        isCheck: false,
        isDel: true,
        value: {
          linux: null,
          windows: null,
          aix: null,
        },
        order: 3,
        id: random(10),
      };
    },
  },
};
</script>

<style lang="scss" scoped>
.metric-dimension {
  height: 100%;
  padding: 20px;
  padding-bottom: 30px;

  .btn {
    font-size: 12px;
  }

  .dialog-hearder {
    margin-bottom: 16px;

    .title {
      margin-bottom: 17px;
      font-size: 24px;
      color: #313238;
    }

    .set-button {
      display: flex;
      align-items: center;
      justify-content: space-between;

      .add-btn {
        margin-right: 8px;
      }

      .move {
        padding-right: 7px;
      }

      .move-btn {
        height: 32px;
        padding: 0 16px;
        line-height: 32px;

        &:hover {
          color: #3a84ff;
          cursor: pointer;
          background: #e1ecff;
        }
      }

      .set-right {
        display: flex;
        flex-grow: 1;
        align-items: center;
        justify-content: flex-end;

        .blue {
          color: #3a84ff;
          cursor: pointer;
        }

        .mr-10 {
          margin-right: 10px;
        }

        .mr-14 {
          margin-right: 14px;
        }

        .dataPreview {
          margin: 0 7px 0 14px;
        }

        .risk-icon {
          margin-right: 4px;
          font-size: 16px;
          color: #979ba5;
        }
      }
    }
  }
}

.footer-btn {
  padding-top: 8px;

  .mr-r {
    margin-right: 6px;
  }
}

.metric-name {
  .verify-input {
    margin-bottom: 20px;
  }

  .item {
    color: #63656e;

    &.required::after {
      position: relative;
      top: -1px;
      left: 3px;
      color: red;
      content: '*';
    }
  }

  .hint {
    margin-bottom: 15px;
    font-size: 12px;
    color: #63656e;

    .icon-monitor {
      margin-right: 6px;
      font-size: 14px;
      color: #979ba5;
    }
  }

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
</style>
