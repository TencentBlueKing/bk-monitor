/*
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
 */
import { Component, Emit, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { releaseCollectorPlugin, retrieveCollectorPlugin } from '../../../../monitor-api/modules/model';
import { saveMetric } from '../../../../monitor-api/modules/plugin';
import { getUnitList } from '../../../../monitor-api/modules/strategies';
import { deepClone, random } from '../../../../monitor-common/utils';
import MonitorExport from '../../../components/monitor-export/monitor-export.vue';
import MonitorImport from '../../../components/monitor-import/monitor-import.vue';
import VerifyInput from '../../../components/verify-input/verify-input.vue';
import { matchRuleFn } from '../../custom-escalation/group-manage-dialog';
import MetricGroup from '../plugin-instance/set-steps/metric-dimension/metric-group.vue';

import './metric-dimension-dialog.scss';

const groupNameRegx = /^[_|a-zA-Z][a-zA-Z0-9_]*$/; /* 分组名字校验规则 */
const MAX_NUM_METRIC_DIM = 5000; /** 插件允许指标维度最大条数 */
const MAX_NUM_METRIC_DIM_SNMP = 500; /** snmp插件允许指标维度最大条数 */
const GROUP_DEFAULT_NAME = 'group_default'; /* 默认分组名 */

interface IProps {
  show?: boolean;
  dataTime?: string;
  osTypeList?: string[];
  metricJson?: any[];
  isRoutePage?: boolean;
  isToken?: boolean;
  pluginType?: string;
  onShowChange?: (v: boolean) => void;
  onBackDebug?: () => void;
  onRefreshData?: () => any;
  onChangeVersion?: () => any;
  onBackPlugin?: () => void;
}

@Component
export default class MetricDimensionDialog extends tsc<IProps> {
  @Prop({ default: false, type: Boolean }) show: boolean;
  /* 数据时间 */
  @Prop({ default: '', type: String }) dataTime: string;
  /* 操作系统类型 */
  @Prop({ default: () => [], type: Array }) osTypeList: string[];
  /* 指标维度数据  */
  @Prop({ default: () => [], type: Array }) metricJson: any[];
  /* 保存指标/维度必要的插件数据 */
  @Prop({ default: () => ({}), type: Object }) pluginData: any;
  /* 是否首页入口或者详情入口 */
  @Prop({ default: true, type: Boolean }) isRoutePage: boolean;
  /* 是否发布 */
  @Prop({ default: false, type: Boolean }) isToken: boolean;
  /* 插件类型 */
  @Prop({ default: '', type: String }) pluginType: string;

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  loading = false;
  // 数据预览开关
  dataPreview = false;
  hideStop = false;
  noActive: false;
  // 新增/编辑分组dialog数据
  groupDialog = {
    isEdit: false,
    isShow: false,
    rule_list: [],
    name: '',
    desc: '',
    index: -1
  };
  rule = {
    isNameEmpty: false
  };
  tableData = [];
  unitList = [];
  tippyOptions = {
    distance: 0
  };
  isShowCancel = false;
  isImport = false;
  localMetricData = [];
  localPluginData: any = {};
  /* 插件类型 */
  localPluginType = null;
  transFromAll = random(8);
  /** 自动采集新增指标是否开启 */
  isAutoCollect = false;
  /** 是否隐藏切换自动采集功能时的提示 */
  isHiddenTip = true;

  /* 分组名称列表 */
  get groupNameList() {
    return this.tableData.map(group => group.table_name);
  }
  /* 是否为snmp插件 */
  get isSnmp() {
    return this.localPluginType === 'SNMP';
  }
  /* 英文名列表 */
  get nameList() {
    let list = [];
    this.tableData.forEach(group => {
      const res = group.fields.map(item => item.name);
      list = list.concat(res);
    });
    return list;
  }
  /* 是否有数据，并且至少有一个启用 */
  get haveData() {
    const nameRes = this.tableData.every(
      group => group.table_name === GROUP_DEFAULT_NAME || group.fields.some(item => item.monitor_type === 'metric')
    );
    const activeRes = this.tableData.some(group => group.fields.some(item => item.is_active));
    return activeRes && nameRes;
  }
  /* 能否保存 */
  get canSave() {
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
  }
  /* 能否启用移动 */
  get canMoveBtn() {
    const res = this.tableData.some(group => group.fields.some(item => item.isCheck));
    return res;
  }
  /* 下载的样例模板 */
  get metricJsonExample() {
    return []; // 功能关闭，待确认模板
  }
  get typeList() {
    const list = [
      //  类别表
      { id: 'double', name: 'double' },
      { id: 'int', name: 'int' }
    ];
    if (
      this.localPluginData &&
      ['Script', 'JMX', 'Exporter', 'Pushgateway'].includes(this.localPluginData.plugin_type)
    ) {
      list.push({ id: 'diff', name: 'diff' });
    }
    return list;
  }
  /* 是否存在格式错误 */
  get hasWrongFormat() {
    let i = 0;
    const strs = [];
    let hasD = false;
    let hasM = false;
    this.tableData.forEach(group => {
      group.fields.forEach(f => {
        if (f.reValue) {
          i += 1;
          if (f.monitor_type === 'dimension') {
            if (!hasD) {
              hasD = true;
              strs.push(`[${this.$t('维度名称')}]`);
            }
          }
          if (f.monitor_type === 'metric') {
            if (!hasM) {
              hasM = true;
              strs.push(`[${this.$t('指标名称')}]`);
            }
          }
        }
      });
    });
    return i > 1 ? strs : [];
  }

  @Watch('show')
  async handleWatchShow(v: boolean) {
    if (v) {
      this.init();
    }
  }

  created() {
    if (this.isRoutePage) {
      this.init();
    }
  }

  async init() {
    this.loading = true;
    if (this.isRoutePage) {
      const detailData = await retrieveCollectorPlugin(this.$route.params.pluginId).catch(() => ({}));
      this.localMetricData = detailData.metric_json;
      this.localPluginType = detailData.plugin_type;
      this.isAutoCollect = detailData.enable_field_blacklist;
      this.isHiddenTip = detailData.is_split_measurement;
      this.localMetricData = this.localMetricData.map(group => ({
        ...group,
        rule_list: group.rule_list || [],
        fields: group.fields.map(item => ({
          ...item,
          isCheck: false,
          isDel: true,
          errValue: false,
          reValue: false,
          descReValue: false,
          showInput: false,
          isFirst: false,
          isDisabled: false,
          order: item.monitor_type === 'metric' ? 0 : 1
        }))
      }));
      this.localPluginData = {
        plugin_id: detailData.plugin_id,
        plugin_type: detailData.plugin_type,
        config_version: detailData.config_version,
        info_version: detailData.info_version
      };
    } else {
      this.localMetricData = this.metricJson;
      this.localMetricData.forEach(item => {
        item.rule_list = item.rule_list || [];
      });
      this.localPluginData = {
        plugin_id: this.pluginData.plugin_id,
        plugin_type: this.pluginData.plugin_type,
        config_version: this.pluginData.config_version,
        info_version: this.pluginData.info_version
      };
      this.isAutoCollect = this.pluginData.enable_field_blacklist;
      this.isHiddenTip = this.pluginData.is_split_measurement;
      this.localPluginType = this.pluginType;
    }
    this.createDefaultGroup(this.localMetricData);
    await this.getUnitListData();
    this.loading = false;
  }

  createDefaultGroup(data) {
    // 没有默认分组，添加默认分组
    if (!data.some(item => item.table_name === GROUP_DEFAULT_NAME)) {
      data.unshift({
        table_name: GROUP_DEFAULT_NAME,
        table_desc: this.$t('默认分组'),
        rule_list: [],
        fields: []
      });
    }
  }

  @Watch('localMetricData', { deep: true })
  handleWatchMetricJson(newV) {
    this.tableData = JSON.parse(JSON.stringify(newV));
    this.handleTableDataChange();
  }

  /**
   * 是否允许继续添加指标维度
   * @param tableData 指标维度数据
   * @param isImport 是否导入数据
   **/
  isAllowAddItem(tableData = this.tableData, isImport = false) {
    const num = tableData.reduce((total, group) => (total += group.fields.length), 0);
    const max = this.isSnmp ? MAX_NUM_METRIC_DIM_SNMP : MAX_NUM_METRIC_DIM;
    return isImport ? num <= max : num < max;
  }
  /** 新增、导入指标维度超过最大值提示 */
  handleMaxMetircDimMsg() {
    const message = this.$t(
      this.isSnmp ? 'SNMP设置指标数量超过{n}，请删减非必要指标' : '设置指标数量超过{n}，请删减非必要指标',
      { n: this.isSnmp ? MAX_NUM_METRIC_DIM_SNMP : MAX_NUM_METRIC_DIM }
    );
    this.$bkMessage({
      message,
      theme: 'error'
    });
  }
  //  别名列表
  descNameList(fields) {
    return fields.map(item => item.description);
  }
  handleTableDataChange() {
    this.tableData.forEach(group => {
      group.fields.forEach(item => {
        item.id = random(10);
        if (item.monitor_type === 'metric' && item.type === 'double' && item.is_diff_metric) {
          item.type = 'diff';
        }
      });
    });
    this.handleSortTableData();
  }
  //  获取动态单位数据
  async getUnitListData() {
    await getUnitList()
      .then(data => {
        this.unitList = data.map(item => ({
          ...item,
          children: item.formats,
          id: item.name
        }));
      })
      .catch(() => {});
  }
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
        aix: null
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
      id: random(10)
    } as any;
    if (type === 'metric') {
      item.order = 1;
      item.dimensions = [];
      item.tag_list = [];
      item.type = 'double';
      item.unit = 'none';
    } else {
      item.order = 3;
      item.type = 'string';
      item.unit = '--';
    }
    return item;
  }
  //  排序
  handleSortTableData() {
    this.tableData.forEach(item => {
      item.fields.sort((a, b) => a.order - b.order);
    });
  }
  //  新增分组
  handleAddGroup() {
    this.groupDialog.isShow = true;
  }
  //  数据预览开关
  handleShowData() {
    this.dataPreview = !this.dataPreview;
  }
  //  保存分组校验
  handleSetGroup() {
    const group = this.groupDialog;
    // 校验分组名字是否符合命名规范
    const isTrueName = groupNameRegx.test(group.name) && group.name !== GROUP_DEFAULT_NAME;
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
    const res = this.tableData.some(item => {
      if (group.isEdit) {
        return item.table_name === group.name && item.table_name !== this.tableData[group.index].table_name;
      }
      return item.table_name === group.name;
    });

    if (res) {
      this.$bkMessage({ theme: 'error', message: `${this.$t('注意: 名字冲突')}` });
      return;
    }
    // 新增/编辑
    if (group.isEdit) {
      this.tableData[group.index].table_name = group.name;
      this.tableData[group.index].table_desc = group.desc || group.name;
      this.tableData[group.index].rule_list = group.rule_list;
      group.isEdit = false;
    } else {
      this.tableData.push({
        table_name: group.name,
        table_desc: group.desc || group.name,
        rule_list: group.rule_list,
        fields: []
      });
    }
    group.isShow = false;
  }
  // 编辑分组回填
  handleEditGroup(index) {
    const group = this.groupDialog;
    group.isShow = true;
    group.isEdit = true;
    group.index = index;
    group.name = this.tableData[index].table_name;
    group.desc = this.tableData[index].table_desc;
    group.rule_list = this.tableData[index].rule_list || [];
  }
  //  删除分组
  handleDelGroup(index) {
    this.tableData.splice(index, 1);
  }
  //  关闭dialog回调
  afterLeave() {
    this.groupDialog.name = '';
    this.groupDialog.desc = '';
    this.groupDialog.rule_list = [];
    this.groupDialog.isEdit = false;
    this.rule.isNameEmpty = false;
  }
  //  在当前行下新增一行
  handleAddRow(row, groupIndex) {
    if (!this.isAllowAddItem()) {
      /** 超出最大限制无法添加 */
      this.handleMaxMetircDimMsg();
      return;
    }
    const arr = this.tableData[groupIndex].fields;
    const item = this.getNewRow(row.monitor_type, '', true);
    const dataIndex = arr.findIndex(item => item.id === row.id);
    arr.splice(dataIndex + 1, 0, item);
  }
  //  删除行
  handleDelRow(row, groupIndex) {
    const group = this.tableData[groupIndex];
    const dataIndex = group.fields.findIndex(item => item.id === row.id);
    group.fields.splice(dataIndex, 1);
    // 删除指标，如果指标携带的维度没有其他指标关联，则把维度一起删除
    if (row.monitor_type === 'metric') {
      row.tag_list?.forEach(dimension => {
        const findIndex = group.fields.findIndex(field => field.name === dimension.field_name);
        // 指标携带的维度没有其他指标关联，删除维度
        if (findIndex !== -1 && !this.checkDimensionRelevance(group.fields[findIndex], group.fields)) {
          group.fields.splice(findIndex, 1);
        }
      });
    } else {
      // 删除维度，需要把所有关联此维度的指标的dimensions列表同步更改
      group.fields.forEach(field => {
        if (field.monitor_type === 'metric' && field.tag_list?.length) {
          field.tag_list = field.tag_list?.filter(dimension => dimension.field_name !== row.name);
        }
      });
    }
  }
  /** 行数据编辑 */
  handleEditRow({ type, data, groupIndex }) {
    const group = this.tableData[groupIndex];
    // 编辑维度时，需要把维度的修改同步给所关联指标
    if (data.monitor_type === 'dimension') {
      const targetName = type === 'name' ? data.oldName : data.name;
      const keyMap = {
        field_name: 'name'
      };
      group.fields.forEach(field => {
        if (field.monitor_type === 'metric' && field.tag_list?.length) {
          // 找到含有该编辑维度的指标
          const dimension = field.tag_list.find(item => item.field_name === targetName);
          dimension && Object.keys(dimension).forEach(key => (dimension[key] = data[keyMap[key] || key]));
        }
      });
    }
  }

  //  新增初始行
  handleAddFirstRow(groupIndex) {
    this.tableData[groupIndex].fields.push(this.getNewRow('metric', '', true));
    this.tableData[groupIndex].fields.push(this.getNewRow('dimension', '', true));
  }

  /**
   * 检查单个维度是否关联了num个以上的指标
   * @param dimension 维度
   * @param metrics 指标
   * @param num 判断数量
   * @returns boolean 是与否
   */
  checkDimensionRelevance(dimension, metrics, num = 1) {
    return metrics.filter(metric => metric.tag_list?.some(d => d.field_name === dimension.name)).length > num;
  }

  /**
   * 移动指标和维度到另外的分组
   * @param name 目标分组名
   */
  handleMoveGroup(name) {
    let targetGroup = null;
    /** 需要被移动的指标和维度 */
    const result = [];
    this.tableData.forEach(group => {
      if (group.table_name !== name) {
        const delList = new Set();
        group.fields.forEach(metric => {
          if (metric.isCheck && metric.monitor_type === 'metric') {
            delList.add(metric.id);
            metric.isCheck = false;
            result.push(deepClone(metric));
            // 根据移动的指标，找到需要被移动的维度
            metric.tag_list?.forEach(dimension => {
              /** 需要被移动的维度的索引 */
              const item = group.fields.find(field => field.name === dimension.field_name);
              if (!item) return;
              item.isCheck = false;
              result.push(deepClone(item));
              // 如果剩余的指标没有和该维度有关联，直接删除该维度
              if (!this.checkDimensionRelevance(item, group.fields, 0)) {
                delList.add(item.id);
              }
            });
          }
        });
        group.fields = group.fields.filter(item => !delList.has(item.id));
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
  }

  /**
   * 添加/编辑规则
   * @param val 规则名
   * @param index 规则索引 -1: 新增， 其他：编辑
   * @param group 当前规则的分组
   */
  handleAddRule(val: string, index: number, group: any) {
    // 添加新的规则
    if (index === -1) {
      group.rule_list.push(val);
    } else {
      // 修改规则
      group.rule_list.splice(index, 1, val);
    }
    this.moveMatchMetric(group);
  }

  handleDelRule(index: number, group) {
    group.rule_list.splice(index, 1);
  }

  /**
   * 移动匹配的指标
   * @param group 匹配规则变化的分组
   */
  moveMatchMetric(group) {
    // 默认分组
    const defaultGroup = this.tableData.find(item => item.table_name === GROUP_DEFAULT_NAME);

    // 把默认分组中匹配的指标以及指标所关联的维度移动到目标分组
    defaultGroup.fields.forEach(field => {
      // 找到匹配的指标
      if (field.monitor_type === 'metric' && group.rule_list.some(rule => matchRuleFn(field.name, rule))) {
        field.isCheck = true;
      }
    });
    this.handleMoveGroup(group.table_name);

    // 把目标分组中未匹配的指标以及指标所关联的维度移动到默认分组
    group.fields.forEach(field => {
      // 找到匹配的指标
      if (field.monitor_type === 'metric' && !group.rule_list.some(rule => matchRuleFn(field.name, rule))) {
        field.isCheck = true;
      }
    });
    this.handleMoveGroup(GROUP_DEFAULT_NAME);
  }

  //  保存指标/维度
  async handleSave() {
    const cacheData = JSON.parse(JSON.stringify(this.tableData));
    //  过滤新增但没填名字的指标/维度
    cacheData.forEach(group => {
      group.fields = group.fields.filter(item => item.name);
    });
    //  过滤不是默认分组且为空的分组
    const tableData = cacheData.filter(group => group.fields.length !== 0 || group.table_name === GROUP_DEFAULT_NAME);
    if (!this.haveData && !this.isAutoCollect) {
      this.$bkMessage({ theme: 'error', message: this.$t('每个分组至少设置一个指标并且是启用状态') });
      return;
    }
    if (!this.canSave) {
      this.$bkMessage({
        theme: 'error',
        message: this.$t('所有的指标/维度的英文名和别名不能重名或为空')
      });
      return;
    }
    if (this.loading) return;
    // 前端业务逻辑字段，传给后端时删掉
    const frontEndParams = ['descReValue', 'errValue', 'isCheck', 'isDel', 'isFirst', 'id', 'reValue', 'showInput'];
    const params = {
      plugin_id: this.localPluginData.plugin_id,
      plugin_type: this.localPluginData.plugin_type,
      config_version: this.localPluginData.config_version,
      info_version: this.localPluginData.info_version,
      enable_field_blacklist: this.isAutoCollect,
      metric_json: (tableData || []).map(item => ({
        ...item,
        table_desc: item.table_name === GROUP_DEFAULT_NAME ? '默认分组' : item.table_desc || item.table_name,
        fields: item.fields.map(set => {
          const tmpSet = { ...set };
          if (set.monitor_type === 'metric' && set.type === 'diff') {
            tmpSet.type = 'double';
            tmpSet.is_diff_metric = true;
          }
          frontEndParams.forEach(filed => {
            delete tmpSet[filed];
          });
          // 不满足规则且不在默认分组的指标, is_manual值为true
          tmpSet.is_manual =
            !item.rule_list.some(rule => matchRuleFn(set.name, rule)) && item.table_name !== GROUP_DEFAULT_NAME;
          return tmpSet;
        })
      }))
    } as any;
    if (this.isRoutePage || !this.isToken) {
      params.need_upgrade = true;
    }
    this.loading = true;
    this.$bkLoading({
      extCls: 'metric-dimension-confirm-loading'
    });
    const data = await saveMetric(params, { needMessage: false }).catch(err => {
      this.$bkMessage({ theme: 'error', message: err.message, ellipsisLine: 0 });
      return false;
    });
    if (data) {
      let result = true;
      if (data.token) {
        result = await releaseCollectorPlugin(this.localPluginData.plugin_id, data)
          .then(() => true)
          .catch(() => false);
      }
      result && this.handleSucessSave(data);
    }
    this.loading = false;
    this.$bkLoading.hide();
  }
  handleSucessSave(data) {
    this.isShowCancel = true;
    this.handleChangeVersion(data);
    this.handleCancel();
  }
  //  取消
  handleCancel() {
    if (this.isRoutePage) {
      this.$router.back();
    } else {
      this.handleShowChange(false);
    }
  }
  //  刷新指标数据
  handleRefreshData() {
    this.loading = true;
    setTimeout(() => {
      this.handleRefreshDataEmit(this.tableData);
      this.loading = false;
    }, 1000);
  }
  //  获取上传文件的信息
  async getFileInfo(e: any) {
    const files = Array.from(e.target.files);
    this.isImport = true;
    const result = [];
    let len = 0;
    await new Promise(resolve => {
      files.forEach((file: any) => {
        const reader = new FileReader();
        reader.onload = (e: any) => {
          const contents = JSON.parse(e.target.result);
          if (!Array.isArray(contents)) {
            this.$bkMessage({
              theme: 'error',
              message: this.$t('文件内容不符合规范')
            });
          } else {
            contents.forEach(item => {
              result.push({
                fields: Array.isArray(item.fields) ? item.fields : [],
                table_name: item.table_name || '',
                table_desc: item.table_desc || ''
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
  }
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
  }
  handleBackPlugin() {
    this.handleShowChange(false);
    this.handleBackPluginEmit();
  }
  handleExportMetric(cb) {
    typeof cb === 'function' &&
      cb(
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        this.tableData
          .filter(item => item.table_name)
          .map(item => ({
            ...item,
            fields: item?.fields
              ?.filter(item => item.name)
              .map(
                ({
                  description,
                  monitor_type,
                  is_diff_metric,
                  name,
                  type,
                  unit,
                  is_active,
                  dimensions = [],
                  tag_list = []
                }) => {
                  // eslint-disable-next-line camelcase
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
                      tag_list
                    };
                  }
                  return {
                    description,
                    monitor_type,
                    name,
                    type,
                    unit,
                    is_active
                  };
                }
              )
          })),
        `${this.localPluginData.plugin_id}-${dayjs.tz().format('YYYY-MM-DD HH-mm-ss')}.json`
      );
  }
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
            rule_list: item.rule_list || [],
            fields: []
          };
          const fieldList = [];
          const oldTableItem = this.tableData.find(set => set.table_name === item.table_name);
          item.fields.forEach((field, childIndex) => {
            if (!field.name) {
              errorList.push(
                this.$t('分组：{tableName} 第{index}个字段未填写名称', {
                  tableName: item.table_name,
                  index: childIndex + 1
                })
              );
            }
            if (fieldList.some(set => set.description !== '' && set.description === field.description)) {
              errorList.push(
                this.$t('分组：{tableName} 别名：{fieldName}重复', {
                  tableName: item.table_name,
                  fieldName: field.description
                })
              );
            }
            if (field.monitor_type === 'metric') {
              if (allMetricFieldList.some(set => set.name === field.name)) {
                errorList.push(
                  this.$t('分组：{tableName} 指标名：{fieldName}重复', {
                    tableName: item.table_name,
                    fieldName: field.name
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
                    fieldName: field.name
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
                  fieldName: field.name
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
        message: this.$t('未检测到需要导入的指标和维度')
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
        ellipsisLine: 0
      });
      return;
    }
    if (!this.isAllowAddItem(list, true)) {
      this.handleMaxMetircDimMsg();
      return;
    }
    this.tableData = JSON.parse(JSON.stringify(list));
    this.handleTableDataChange();
  }
  getDefaultMetric({
    description = '',
    // eslint-disable-next-line camelcase
    is_active = true,
    // eslint-disable-next-line camelcase
    is_diff_metric = false,
    name,
    type = 'double',
    unit = 'none',
    dimensions = [],
    tag_list = []
  }) {
    return {
      dimensions,
      tag_list,
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
        aix: null
      },
      order: 1,
      id: random(10)
    };
  }
  getDefaultDimension({
    description = '',
    // eslint-disable-next-line camelcase
    is_active = true,
    name
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
        aix: null
      },
      order: 3,
      id: random(10)
    };
  }

  @Emit('showChange')
  handleShowChange(v: boolean) {
    return v;
  }
  /* 返回调试 */
  @Emit('backDebug')
  handleBackDebug() {}
  /* 刷新数据 */
  @Emit('refreshData')
  handleRefreshDataEmit(data) {
    return data;
  }
  /* 切换版本 */
  @Emit('changeVersion')
  handleChangeVersion(data) {
    return data;
  }
  /* 返回插件定义 */
  @Emit('backPlugin')
  handleBackPluginEmit() {}

  handleOneClickTransFrom() {
    this.transFromAll = random(8);
  }

  handleAutoCollectChange(val) {
    // 打开状态且需要展示提示时
    if (val && !this.isHiddenTip) {
      this.$bkInfo({
        type: 'warning',
        extCls: 'auto-collect-info',
        title: this.$t('此操作存在危险'),
        subTitle: this.$t(
          '因为当前是旧的存储模式，开启采集新增指标后会切换成新的存储模式，旧的历史数据会丢失，请确认是否继续。'
        ),
        confirmFn: () => {
          this.isHiddenTip = true;
        },
        cancelFn: () => {
          this.isAutoCollect = false;
        }
      });
    }
  }

  contentRender() {
    return (
      <div class='metric-dimension-dialog-content'>
        <div class='header-operate'>
          <div class='operate-left'>
            <bk-button
              class='mr-8'
              icon='plus'
              v-authority={{
                active: !this.authority.MANAGE_AUTH
              }}
              onClick={() => (this.authority.MANAGE_AUTH ? this.handleAddGroup() : this.handleShowAuthorityDetail())}
            >
              {this.$t('新建组')}
            </bk-button>
            <bk-dropdown-menu disabled={!this.canMoveBtn}>
              <bk-button
                type='primary'
                slot='dropdown-trigger'
                class='move'
              >
                <span>{this.$t('移动到...')}</span>
                <i class='bk-icon icon-angle-down'></i>
              </bk-button>
              <ul
                class='bk-dropdown-list'
                style='overflow: auto'
                slot='dropdown-content'
                v-authority={{ active: !this.authority.MANAGE_AUTH }}
                onClick={() => !this.authority.MANAGE_AUTH && this.handleShowAuthorityDetail()}
              >
                {this.groupNameList.map((name, index) => (
                  <li
                    key={index}
                    class='move-btn'
                    onClick={() => this.authority.MANAGE_AUTH && this.handleMoveGroup(name)}
                  >
                    {name === GROUP_DEFAULT_NAME ? this.$t('默认分组') : name}
                  </li>
                ))}
              </ul>
            </bk-dropdown-menu>
            <bk-popover
              placement='top-start'
              tippy-options={this.tippyOptions}
              delay={200}
            >
              {!this.isRoutePage ? (
                <bk-button
                  class='ml-8'
                  icon='icon-monitor icon-mc-retry'
                  onClick={this.handleRefreshData}
                >
                  {/* <span class="icon-monitor icon-mc-retry"></span> */}
                </bk-button>
              ) : undefined}
              <div slot='content'>
                <div>{this.$t('此刷新仅追加新获取的指标和维度')}</div>
              </div>
            </bk-popover>
            <span class='auto-collect'>
              <bk-switcher
                v-model={this.isAutoCollect}
                size='small'
                theme='primary'
                onChange={this.handleAutoCollectChange}
              ></bk-switcher>
              <span>{this.$t('自动采集新增指标')}</span>
            </span>
            <i class='icon-monitor icon-remind mr-8'></i>
            <span class='tip-text mr-30'>{this.$t('打开后，除了采集启用的指标还会采集未来新增的指标。')}</span>
          </div>
          <div class='operate-right'>
            {(() => {
              if (!this.isRoutePage) {
                return [
                  <MonitorImport
                    class='mr-24'
                    return-text={true}
                    accept='application/json'
                    v-authority={{ active: !this.authority.MANAGE_AUTH }}
                    onChange={data =>
                      this.authority.MANAGE_AUTH ? this.handleImportMetric(data) : this.handleShowAuthorityDetail()
                    }
                  >
                    <span class='text-btn'>
                      <span class='icon-monitor icon-shangchuan'></span>
                      <span class='shangchuan'>{this.$t('导入')}</span>
                    </span>
                  </MonitorImport>,

                  <MonitorExport
                    class='ml-0 mr-24'
                    v-authority={{ active: !this.authority.MANAGE_AUTH }}
                    onClick={cb =>
                      this.authority.MANAGE_AUTH ? this.handleExportMetric(cb) : this.handleShowAuthorityDetail()
                    }
                  >
                    <span class='text-btn'>
                      <span class='icon-monitor icon-xiazai2'></span>
                      <span class='shangchuan'>{this.$t('导出')}</span>
                    </span>
                  </MonitorExport>,
                  <span
                    class='mr-12'
                    onClick={this.handleShowData}
                  >
                    {this.$t('数据预览')}
                  </span>,
                  <bk-switcher
                    v-model={this.dataPreview}
                    size='small'
                    theme='primary'
                  ></bk-switcher>
                ];
              }
              return [
                <MonitorImport
                  class='mr-24'
                  return-text={true}
                  v-authority={{ active: !this.authority.MANAGE_AUTH }}
                  onChange={data =>
                    this.authority.MANAGE_AUTH ? this.handleImportMetric(data) : this.handleShowAuthorityDetail()
                  }
                >
                  <span class='text-btn'>
                    <span class='icon-monitor icon-shangchuan'></span>
                    <span class='shangchuan'>{this.$t('导入')}</span>
                  </span>
                </MonitorImport>,
                <MonitorExport
                  class='mr-24'
                  v-authority={{ active: !this.authority.MANAGE_AUTH }}
                  onClick={cb =>
                    this.authority.MANAGE_AUTH ? this.handleExportMetric(cb) : this.handleShowAuthorityDetail()
                  }
                >
                  <span class='text-btn'>
                    <span class='icon-monitor icon-xiazai2'></span>
                    <span class='shangchuan'>{this.$t('导出')}</span>
                  </span>
                </MonitorExport>,
                <span class='tingyong-swtich'>
                  <span class='tip-text mr-10'>{this.$t('隐藏已停用')}</span>
                  <bk-switcher
                    v-model={this.hideStop}
                    size='small'
                    theme='primary'
                  ></bk-switcher>
                </span>
              ];
            })()}
          </div>
        </div>
        <div>
          {this.tableData.map((group, index) => (
            <MetricGroup
              key={index}
              is-default-group={group.table_name === GROUP_DEFAULT_NAME}
              metric-data={group.fields}
              group-name={
                group.table_name !== GROUP_DEFAULT_NAME
                  ? `${group.table_name}(${group.table_desc})`
                  : this.$t('默认分组')
              }
              group-index={index}
              group-rules={group.rule_list}
              unit-list={this.unitList}
              hide-stop={this.hideStop}
              is-show-data={this.dataPreview}
              os-type-list={this.osTypeList}
              name-list={this.nameList}
              desc-name-list={this.descNameList(group.fields)}
              is-from-home={this.isRoutePage}
              type-list={this.typeList}
              transFromAll={this.transFromAll}
              on-edit-group={this.handleEditGroup}
              on-del-group={this.handleDelGroup}
              on-add-row={this.handleAddRow}
              on-del-row={this.handleDelRow}
              on-edit-row={this.handleEditRow}
              on-add-first={this.handleAddFirstRow}
              on-add-rule={(val, index) => this.handleAddRule(val, index, group)}
              on-del-rule={index => this.handleDelRule(index, group)}
            />
          ))}
        </div>
        <bk-dialog
          v-model={this.groupDialog.isShow}
          mask-close={false}
          header-position={'left'}
          show-footer={false}
          width={480}
          title={this.groupDialog.isEdit ? this.$t('编辑指标分类') : this.$t('增加指标分类')}
          on-after-leave={this.afterLeave}
          on-confirm={this.handleSetGroup}
          class='metric-dimension-add-group-dialog'
        >
          <div class='metric-name'>
            <div class='hint'>
              <i class='icon-monitor icon-hint'></i>
              {this.$t('指标分类的定义影响指标检索的时候,如试图查看，仪表盘添加视图和添加监控策略时选择指标的分类。')}
            </div>
            <p class='item required'>{this.$t('名称')}</p>
            <VerifyInput
              class='verify-input'
              validator={{ content: this.$tc('输入指标名,以字母开头,允许包含下划线和数字且不能为group_default') }}
              show-validate={this.rule.isNameEmpty}
            >
              <bk-input
                placeholder={this.$t('英文名')}
                v-model={this.groupDialog.name}
                on-blur={() =>
                  (this.rule.isNameEmpty =
                    !groupNameRegx.test(this.groupDialog.name) || this.groupDialog.name === GROUP_DEFAULT_NAME)
                }
              />
            </VerifyInput>
            <p class='item'> {this.$t('别名')} </p>
            <VerifyInput class='verify-input'>
              <bk-input
                v-model={this.groupDialog.desc}
                placeholder={this.$t('别名')}
              ></bk-input>
            </VerifyInput>
            <p class='item'> {this.$t('匹配规则')} </p>
            <VerifyInput>
              <bk-tag-input
                v-model={this.groupDialog.rule_list}
                show-clear-only-hover
                allow-create={true}
                free-paste
                allow-auto-match
                placeholder={this.$t('匹配规则')}
              />
            </VerifyInput>
            <p class='rule-desc'>{this.$tc('支持JS正则匹配方式， 如子串前缀匹配go_，模糊匹配(.*?)_total')}</p>
          </div>
          <div class='footer'>
            <bk-button
              class='confirm-btn'
              theme='primary'
              onClick={this.handleSetGroup}
            >
              {this.$t('确认')}
            </bk-button>
            <bk-button onClick={() => (this.groupDialog.isShow = false)}>{this.$t('取消')}</bk-button>
          </div>
        </bk-dialog>
        {this.isRoutePage && (
          <div class='bottom-operate'>
            <bk-button
              class='mr-8'
              theme='primary'
              v-authority={{
                active: !this.authority.MANAGE_AUTH
              }}
              onClick={() => (this.authority.MANAGE_AUTH ? this.handleSave() : this.handleShowAuthorityDetail())}
            >
              {this.$t('保存')}
            </bk-button>
            <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
          </div>
        )}
      </div>
    );
  }

  render() {
    return this.isRoutePage ? (
      <div class='metric-dimension-settings-page'>
        <div class='metric-dimension-settings-page-content'>{this.contentRender()}</div>
      </div>
    ) : (
      <bk-dialog
        ext-cls='metric-dimension-dialog-component'
        value={this.show}
        mask-close={true}
        header-position='left'
        width={1280}
        on-value-change={this.handleShowChange}
      >
        {this.contentRender()}
        <div slot='header'>
          <div class='header-title'>
            <span class='title'>{this.$t('指标维度设置')}</span>
            <span class='subtitle'>
              {this.$t('数据时间')}: {this.dataTime}
            </span>
          </div>
        </div>
        <div
          slot='footer'
          class='footer-operate'
        >
          <span class='footer-tip'>
            {this.hasWrongFormat.length
              ? [
                  <span class='icon-monitor icon-remind'></span>,
                  <span>
                    {this.$t('当前有多项{0}存在格式错误，可对指标名称进行统一格式转换', [this.hasWrongFormat.join('')])}
                  </span>,
                  <span
                    class='zhuanhuang'
                    onClick={this.handleOneClickTransFrom}
                  >
                    <span class='icon-monitor icon-zhuanhuan'></span>
                    <span>{this.$t('一键转换')}</span>
                  </span>
                ]
              : undefined}
          </span>
          <span class='footer-opreate'>
            <bk-button
              class='mr-8'
              theme='primary'
              disabled={this.loading}
              onClick={this.handleSave}
            >
              {this.$t('保存')}
            </bk-button>
            <bk-button
              class='mr-8'
              onClick={this.handleBackPlugin}
            >
              {this.$t('返回插件定义')}
            </bk-button>
            <bk-button onClick={this.handleBackDebug}>{this.$t('返回调试')}</bk-button>
          </span>
        </div>
      </bk-dialog>
    );
  }
}
