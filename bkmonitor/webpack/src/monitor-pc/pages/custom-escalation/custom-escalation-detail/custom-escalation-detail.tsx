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
import { Component, ProvideReactive, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import {
  customTsGroupingRuleList,
  importCustomTimeSeriesFields,
  validateCustomTsGroupLabel,
} from 'monitor-api/modules/custom_report';
import { getFunctions } from 'monitor-api/modules/grafana';
import { Debounce } from 'monitor-common/utils';

import { defaultCycleOptionSec } from '../../../components/cycle-input/utils';
import VerifyInput from '../../../components/verify-input/verify-input.vue';
import CommonNavBar from '../../../pages/monitor-k8s/components/common-nav-bar';
import { downCsvFile } from '../../../pages/view-detail/utils';
import { matchRuleFn } from '../group-manage-dialog';
import DimensionTableSlide from './dimension-table-slide';
import IndicatorTableSlide, { fuzzyMatch } from './metric-table-slide';
import TimeseriesDetailNew from './timeseries-detail';

import type { IDetailData } from '../../../types/custom-escalation/custom-escalation-detail';

import './custom-escalation-detail.scss';

export const ALL_LABEL = '__all_label__';
export const NULL_LABEL = '__null_label__';

export interface IGroupListItem {
  name: string;
  matchRules: string[];
  manualList: string[];
  matchRulesOfMetrics?: string[]; // 匹配规则匹配的指标数
}

@Component
export default class CustomEscalationDetailNew extends tsc<any, any> {
  @Ref('nameInput') readonly nameInput!: HTMLInputElement;
  @Ref() readonly dataLabelInput!: HTMLInputElement;
  @Ref() readonly describeInput!: HTMLInputElement;
  @Ref('textCopy') readonly textCopy!: HTMLTextAreaElement;
  @ProvideReactive('metricFunctions') metricFunctions = [];

  isShowMetricSlider = false; // 展示指标抽屉
  isShowDimensionSlider = false; // 展示维度抽屉
  loading = false;
  copyName = ''; // 修改的名字
  copyDataLabel = ''; // 修改的英文名
  copyDescribe = ''; // 修改的描述
  copyIsPlatform = false; // 是否为平台指标、事件
  isShowEditName = false; // 是否显示名字编辑框
  isShowRightWindow = true; // 是否显示右侧帮助栏
  isShowEditDataLabel = false; // 是否展示英文名编辑框
  isShowEditDesc = false; // 是否展示描述编辑框
  scenario = ''; // 分类
  protocol = ''; // 上报协议
  proxyInfo = []; // 云区域分类数据
  preData = ''; // 数据上报格式样例
  sdkData: any = {}; // sdk 接入数据
  //  详情数据
  detailData: IDetailData = {
    bk_data_id: '',
    access_token: '',
    name: '',
    scenario: '',
    scenario_display: [],
    data_label: '',
    is_platform: false,
    protocol: '',
    last_time: '',
    auto_discover: false,
  };

  /** 指标表格搜索 */
  metricSearch = [];

  //  指标维度数据 时序数据
  metricData = [];
  unitList = []; // 单位list

  groupSelectList: any = [
    {
      id: '',
      name: '未分组',
    },
  ];

  allCheckValue: 0 | 1 | 2 = 0; // 0: 取消全选 1: 半选 2: 全选
  groupFilterList: string[] = [];

  /* 筛选条件(简化) */
  metricSearchObj = {
    name: [],
    description: [],
    unit: [],
    func: [],
    aggregate: [],
    show: [],
  };
  /* 分组管理列表 */
  groupList: IGroupListItem[] = [];
  /* 每个匹配规则包含指标 */
  matchRulesMap = new Map();
  /* 每个组所包含的指标 */
  groupsMap: Map<string, IGroupListItem> = new Map();
  /* 每个指标包含的组 */
  metricGroupsMap = new Map();
  /* 指标列表 */
  metricList = [];
  /* 维度列表 */
  dimensions = [];

  /* 数据预览ALL */
  allDataPreview = {};

  autoDiscover = false;

  rule = {
    dataLabelTips: '',
    dataLabel: false,
  };

  nonGroupNum = 0;

  get type() {
    return this.$route.name === 'custom-detail-event' ? 'customEvent' : 'customTimeSeries';
  }

  get isReadonly() {
    return !!this.detailData.is_readonly;
  }

  //  指标数量
  get metricNum() {
    return this.metricData.filter(item => item.monitor_type === 'metric').length;
  }

  get metricNameList() {
    return this.metricData.map(item => ({ name: item.name, description: item.description }));
  }

  //  维度数量
  get dimensionNum() {
    return this.dimensions.length;
  }

  // 上报周期
  get cycleOption() {
    return defaultCycleOptionSec.filter(({ id }) => id !== 'auto');
  }

  // 分组名称列表
  get groupNameList() {
    return this.groupList.map(item => item.name);
  }

  get metricTable() {
    const length = this.groupFilterList.length;
    const nameLength = this.metricSearchObj.name.length;
    const descriptionLength = this.metricSearchObj.description.length;
    const unitLength = this.metricSearchObj.unit.length;
    const aggregateLength = this.metricSearchObj.aggregate.length;
    const isShowLength = this.metricSearchObj.show.length;
    const filterList = this.metricData.filter(item => {
      return (
        (length
          ? this.groupFilterList.some(
              g => item.labels.map(l => l.name).includes(g) || (!item.labels.length && g === NULL_LABEL)
            )
          : true) &&
        (nameLength ? this.metricSearchObj.name.some(n => fuzzyMatch(item.name, n)) : true) &&
        (descriptionLength ? this.metricSearchObj.description.some(n => fuzzyMatch(item.description, n)) : true) &&
        (unitLength ? this.metricSearchObj.unit.some(u => fuzzyMatch(item.unit || 'none', u)) : true) &&
        (aggregateLength
          ? this.metricSearchObj.aggregate.some(a => fuzzyMatch(item.aggregate_method || 'none', a))
          : true) &&
        (isShowLength ? this.metricSearchObj.show.some(s => s === String(!item.hidden)) : true)
      );
    });
    return filterList;
  }

  /**
   * @description: 搜索
   * @param {*}
   * @return {*}
   */
  @Debounce(300)
  handleSearchChange(list = []) {
    this.metricSearch = list;
    const search = {
      name: [],
      description: [],
      unit: [],
      func: [],
      aggregate: [],
      show: [],
    };
    for (const item of this.metricSearch) {
      if (item.type === 'text') {
        item.id = 'name';
        item.values = [{ id: item.name, name: item.name }];
      }
      search[item.id] = [...new Set(search[item.id].concat(item.values.map(v => v.id)))];
    }
    this.metricSearchObj = search;
  }

  handleClearSearch() {
    this.handleSearchChange();
  }

  // 获取未分组数量
  getNonGroupNum() {
    return this.metricData.filter(item => item.monitor_type === 'metric').filter(item => !item.labels.length).length;
  }

  /** 处理导出 */
  handleExportMetric() {
    // 构建JSON内容
    const dimensions = this.dimensions.length
      ? this.dimensions.map(({ name, type, description, disabled, common }) => ({
          name,
          type,
          description,
          disabled,
          common,
        }))
      : [
          {
            name: 'dimension1',
            type: 'dimension',
            description: '',
            disabled: true,
            common: true,
          },
        ];
    const metrics = this.metricData.length
      ? this.metricData.map(
          ({
            name,
            type,
            description,
            disabled,
            unit,
            hidden,
            aggregate_method,
            interval,
            label,
            dimensions,
            function: func,
          }) => ({
            type,
            name,
            description,
            disabled,
            unit,
            hidden,
            aggregate_method,
            interval,
            label,
            dimensions,
            function: func,
          })
        )
      : [
          {
            name: 'metric1',
            type: 'metric',
            description: '',
            disabled: false,
            unit: '',
            hidden: false,
            aggregate_method: '',
            function: {},
            interval: 0,
            label: [],
            dimensions: ['dimension1'],
          },
        ];
    const groupRules = this.groupList
      ? this.groupList
      : [
          {
            name: '测试分组',
            manual_list: ['metric1'],
            auto_rules: ['rule1'],
          },
        ];
    const template = {
      dimensions,
      metrics,
      group_rules: groupRules,
    };
    // 生成动态文件名
    const generateFileName = () => {
      return `自定义指标-${this.detailData.name}-${dayjs.tz().format('YYYY-MM-DD_HH-mm-ss')}.json`;
    };
    // 执行下载
    downCsvFile(JSON.stringify(template, null, 2), generateFileName());
  }

  /** 处理导入 */
  async handleUploadMetric(jsonData) {
    if (!jsonData) {
      return;
    }
    await importCustomTimeSeriesFields({
      time_series_group_id: this.$route.params.id,
      ...JSON.parse(jsonData),
    });
    await this.getDetailData();
  }

  /**
   * @description: 获取指标函数列表
   * @param {*}
   * @return {*}
   */
  async handleGetMetricFunctions() {
    this.metricFunctions = await getFunctions().catch(() => []);
  }

  changeGroupFilterList(v: string) {
    this.handleClearSearch();
    this.groupFilterList = v === ALL_LABEL ? [] : [v];
    this.updateAllSelection();
  }

  // 一次性加载静态数据（云区域和单位列表）
  async loadStaticData() {
    try {
      const [proxyInfo, unitList] = await Promise.all([
        this.$store.dispatch('custom-escalation/getProxyInfo'),
        this.$store.dispatch('strategy-config/getUnitList'),
      ]);

      this.proxyInfo = proxyInfo;
      this.unitList = unitList;
    } catch (error) {
      console.error('Failed to load static data:', error);
    }
  }

  async created() {
    await this.loadStaticData();
    await this.getDetailData();
    this.handleGetMetricFunctions();
    this.nonGroupNum = this.getNonGroupNum();
  }

  updateAllSelection(v = false) {
    this.metricTable.forEach(item => item.monitor_type === 'metric' && (item.selection = v));
    this.updateCheckValue();
  }

  updateCheckValue() {
    const metricList = this.metricTable.filter(item => item.monitor_type === 'metric');
    const checkedLength = metricList.filter(item => item.selection).length;
    const allLength = metricList.length;
    this.allCheckValue = 0;
    if (checkedLength > 0) {
      this.allCheckValue = checkedLength < allLength ? 1 : 2;
    } else {
      this.allCheckValue = 0;
    }
  }

  //  获取详情
  async getDetailData(needLoading = true) {
    this.loading = needLoading;
    try {
      const [detailData, metricData] = await Promise.all([
        this.$store.dispatch('custom-escalation/getCustomTimeSeriesDetail', {
          time_series_group_id: this.$route.params.id,
        }),
        this.$store.dispatch('custom-escalation/getCustomTSFields', {
          time_series_group_id: this.$route.params.id,
        }),
      ]);

      this.detailData = detailData || this.detailData;
      this.autoDiscover = this.detailData.auto_discover;
      for (const item of metricData?.metrics || []) {
        if (!item?.function?.[0]) {
          item.function = [];
        }
      }
      this.metricList = metricData?.metrics || [];
      this.dimensions = metricData?.dimensions || [];

      await this.getGroupList();
      this.handleDetailData(this.detailData);
    } catch (error) {
      console.error(error);
    } finally {
      this.loading = false;
    }
  }

  //  处理详情数据
  handleDetailData(detailData: IDetailData) {
    if (this.type === 'customTimeSeries') {
      this.metricData = this.metricList.map(item => ({
        ...item,
        selection: false,
        descReValue: false,
        // labels: [],
        monitor_type: 'metric',
      }));
      this.setMetricDataLabels();
    }
    this.scenario = `${detailData.scenario_display[0]} - ${detailData.scenario_display[1]}`;
    this.copyName = this.detailData.name;
    this.copyDataLabel = this.detailData.data_label || '';
    this.copyDescribe = this.detailData.desc || '';
    this.copyIsPlatform = this.detailData.is_platform ?? false;
    const str = `# ${this.$t('指标，必需项')}
        "metrics": {
            "cpu_load": 10
        },`;
    this.preData = `{
        # ${this.$t('数据通道标识，必需项')}
        "data_id": ${detailData.bk_data_id},
        # ${this.$t('数据通道标识验证码，必需项')}
        "access_token": "${detailData.access_token}",
        "data": [{
            ${str}
            # ${this.$t('来源标识如IP，必需项')}
            "target": "127.0.0.1",
            # ${this.$t('自定义维度，非必需项')}
            "dimension": {
                "module": "db",
                "location": "guangdong",
                # ${this.$t('event_type 为非必须项，用于标记事件类型，默认为异常事件')}
                # ${this.$t('recovery:恢复事件，abnormal:异常事件')}
                "event_type": "abnormal"
            },
            # ${this.$t('数据时间，精确到毫秒，非必需项')}
            "timestamp": ${new Date().getTime()}
        }]
    }`;
    // 判断如果是 prometheus 类型则展示不同的内容
    if (detailData.protocol === 'prometheus') {
      // # ${this.$t('event_type 为非必须项，用于标记事件类型，默认为异常事件')}
      this.sdkData.preGoOne = `type bkClient struct{}
func (c *bkClient) Do(r *http.Request) (*http.Response, error) {
	r.Header.Set("X-BK-TOKEN", "$TOKEN")
  // TOKEN 即在 saas 侧申请的 token
	return http.DefaultClient.Do(r)
}

func main() {
	register := prometheus.NewRegistry()
	register.MustRegister(promcollectors.NewGoCollector())

	name := "reporter"
	// 1) 指定蓝鲸上报端点 $bk.host:$bk.port
	pusher := push.New("\${PROXY_IP}:4318", name).
  Gatherer(register)

	// 2) 传入自定义 Client
	pusher.Client(&bkClient{})

	ticker := time.Tick(15 * time.Second)
	for {
		<-ticker
		if err := pusher.Push(); err != nil {
			log.Println("failed to push records to the server,
      error:", err)
			continue
		}
		log.Println("push records to the server successfully")
	}
}`;

      this.sdkData.prePythonOne = `from prometheus_client.exposition import
default_handler

# 定义基于监控 token 的上报 handler 方法
def bk_handler(url, method, timeout, headers, data):
    def handle():
        headers.append(['X-BK-TOKEN', '$TOKEN'])
        # TOKEN 即在 saas 侧申请的 token
        default_handler(url, method, timeout, headers, data)()
    return handle

from prometheus_client import CollectorRegistry,
Gauge, push_to_gateway
from prometheus_client.exposition
import bk_token_handler

registry = CollectorRegistry()
g = Gauge('job_last_success_unixtime',
'Last time a batch job successfully finished', registry=registry)
g.set_to_current_time()
push_to_gateway('\${PROXY_IP}:4318', job='batchA',
registry=registry, handler=bk_handler) # 上述自定义 handler`;
    }
  }

  /* 获取分组管理数据 */
  async getGroupList() {
    const data = await customTsGroupingRuleList({
      time_series_group_id: this.detailData.time_series_group_id,
    }).catch(() => []);
    this.groupList = data.map(item => ({
      name: item.name,
      matchRules: item.auto_rules,
      manualList: item.manual_list,
    }));
    this.groupsDataTidy();
  }

  /* 分组数据整理 */
  groupsDataTidy() {
    const metricNames = this.metricList.map(item => item.name);
    const allMatchRulesSet = new Set();
    const metricGroupsMap = new Map();
    for (const item of this.groupList) {
      for (const rule of item.matchRules) {
        allMatchRulesSet.add(rule);
      }
    }
    const allMatchRules = Array.from(allMatchRulesSet);
    /* 整理每个匹配规则配的指标数据 */
    for (const rule of allMatchRules) {
      this.matchRulesMap.set(
        rule,
        metricNames.filter(name => matchRuleFn(name, rule as string))
      );
    }

    for (const item of this.groupList) {
      const tempSet = new Set();
      for (const rule of item.matchRules) {
        const metrics = this.matchRulesMap.get(rule) || [];
        for (const m of metrics) {
          tempSet.add(m);
        }
      }
      const matchRulesOfMetrics = Array.from(tempSet) as string[];
      this.groupsMap.set(item.name, {
        ...item,
        matchRulesOfMetrics,
      });
      /* 写入每个指标包含的组 */
      const setMetricGroup = (m, type) => {
        const metricItem = metricGroupsMap.get(m);
        if (metricItem) {
          const { groups, matchType } = metricItem;
          const targetGroups = [...new Set(groups.concat([item.name]))];
          const targetMatchType = JSON.parse(JSON.stringify(matchType));
          for (const t of targetGroups) {
            if (t === item.name) {
              targetMatchType[t as string] = [...new Set((matchType[t as string] || []).concat([type]))];
            }
          }
          metricGroupsMap.set(m, {
            groups: targetGroups,
            matchType: targetMatchType,
          });
        } else {
          const matchTypeObj = {
            [item.name]: [type],
          };
          metricGroupsMap.set(m, {
            groups: [item.name],
            matchType: matchTypeObj,
          });
        }
      };
      matchRulesOfMetrics.forEach(m => {
        setMetricGroup(m, 'auto');
      });
      item.manualList.forEach(m => {
        setMetricGroup(m, 'manual');
      });
    }
    this.metricGroupsMap = metricGroupsMap;
    this.groupSelectList = this.groupList.map(item => ({
      id: item.name,
      name: item.name,
    }));
  }

  //  点击icon展示name编辑
  handleShowEdit() {
    this.isShowEditName = true;
    this.$nextTick(() => {
      this.nameInput.focus();
    });
  }
  /** 点击显示英文名的编辑 */
  handleShowEditDataLabel() {
    this.isShowEditDataLabel = true;
    this.rule.dataLabelTips = '';
    this.rule.dataLabel = false;
    this.$nextTick(() => {
      this.dataLabelInput.focus();
    });
  }
  /** 点击显示描述的编辑 */
  handleShowEditDes() {
    this.isShowEditDesc = true;
    this.$nextTick(() => {
      this.describeInput.focus();
    });
  }
  /** 保存自动发现 */
  handleEditAutoDiscover(autoDiscover) {
    this.autoDiscover = autoDiscover;
    this.handleEditFiled({
      auto_discover: autoDiscover,
    });
  }

  async handleEditFiled(props, showMsg = true) {
    this.loading = true;
    try {
      const params = {
        time_series_group_id: this.detailData.time_series_group_id,
        ...props,
      };
      const data = await this.$store.dispatch('custom-escalation/editCustomTime', params);
      if (data && showMsg) {
        this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
      }
    } finally {
      this.loading = false;
    }
  }
  /** 编辑英文名 */
  async handleEditDataLabel() {
    if (!this.copyDataLabel || this.copyDataLabel === this.detailData.data_label) {
      this.copyDataLabel = this.detailData.data_label;
      this.isShowEditDataLabel = false;
      return;
    }
    if (/[\u4e00-\u9fa5]/.test(this.copyDataLabel)) {
      this.rule.dataLabelTips = this.$tc('输入非中文符号');
      this.rule.dataLabel = true;
      return;
    }
    const { message: errorMsg } = await validateCustomTsGroupLabel(
      {
        data_label: this.copyDataLabel,
        time_series_group_id: this.detailData.time_series_group_id,
      },
      {
        needMessage: false,
      }
    ).catch(err => err);
    if (errorMsg) {
      this.rule.dataLabelTips = this.$t(errorMsg) as string;
      this.rule.dataLabel = true;
      return;
    }
    await this.handleEditFiled({
      data_label: this.copyDataLabel,
    });
    this.detailData.data_label = this.copyDataLabel;
    this.isShowEditDataLabel = false;
    this.loading = false;
  }

  //  编辑名字
  async handleEditName() {
    if (!(this.copyName && this.copyName !== this.detailData.name)) {
      this.copyName = this.detailData.name;
      this.isShowEditName = false;
      return;
    }
    //  名字是否重复校验
    let isOkName = true;
    const res = await this.$store
      .dispatch('custom-escalation/validateCustomTimetName', {
        params: { name: this.copyName, time_series_group_id: this.detailData.time_series_group_id },
      })
      .then(res => res.result ?? true)
      .catch(() => false);
    if (!res) {
      isOkName = false;
    }
    if (!isOkName) {
      this.copyName = this.detailData.name;
      this.$nextTick(() => {
        this.nameInput.focus();
      });
      return;
    }
    await this.handleEditFiled({
      name: this.copyName,
    });
    this.detailData.name = this.copyName;
    this.isShowEditName = false;
    this.loading = false;
  }

  // 编辑描述
  async handleEditDescribe() {
    if (this.copyDescribe.trim() === this.detailData.desc) {
      this.copyDescribe = this.detailData.desc || '';
      this.isShowEditDesc = false;
      return;
    }
    this.isShowEditDesc = false;
    this.handleEditFiled({
      desc: this.copyDescribe,
    });
    this.detailData.desc = this.copyDescribe;
  }

  //  复制数据上报样例
  handleCopyData() {
    const str = `"metrics": {
            "cpu_load": 10
        },`;
    const example = `{
      "data_id": ${this.detailData.bk_data_id},
      "access_token": "${this.detailData.access_token}",
      "data": [{
          ${str}
          "target": "127.0.0.1",
          "dimension": {
              "module": "db",
              "location": "guangdong"
          },
          "timestamp": ${new Date().getTime()}
      }]
    }`;
    this.textCopy.value = example;
    this.textCopy.select();
    document.execCommand('copy');
    this.$bkMessage({
      theme: 'success',
      message: this.$t('样例复制成功'),
    });
  }

  // 复制Prometheus  sdk 接入流程代码
  handleCopyPrometheus(type) {
    this[type].value = type === 'golangCopy' ? this.sdkData.preGoOne : this.sdkData.prePythonOne;
    this[type].select();
    document.execCommand('copy');
    this.$bkMessage({
      theme: 'success',
      message: this.$t('样例复制成功'),
    });
  }
  /* 通过分组管理计算每个指标包含的组 */
  setMetricDataLabels() {
    for (const item of this.metricData) {
      if (item.monitor_type === 'metric') {
        const groupItem = this.metricGroupsMap.get(item.name);
        if (groupItem) {
          item.labels = groupItem.groups.map(g => ({
            name: g,
            match_type: groupItem.matchType[g],
          }));
        } else {
          item.labels = [];
        }
      }
    }
  }

  handleJump() {
    const { customMetricV2EnableList, bizId } = this.$store.getters;
    const toView = {
      customEvent: () => {
        this.$router.push({
          name: 'custom-escalation-event-view',
          params: { id: String(this.detailData.bk_event_group_id) },
          query: { name: this.detailData.name },
        });
      },
      customTimeSeries: () => {
        this.$router.push({
          name: customMetricV2EnableList.includes(bizId) ? 'new-custom-escalation-view' : 'custom-escalation-view',
          params: { id: String(this.detailData.time_series_group_id) },
          query: { name: this.detailData.name },
        });
      },
    };
    toView[this.type]();
  }
  getBaseInfoCmp() {
    return (
      <div class='detail-information'>
        <div class='detail-information-title'>{this.$t('基本信息')}</div>
        <div class='detail-information-content'>
          <div class='detail-information-row'>
            <span class='row-label'>{this.$t('数据ID')}: </span>
            <span
              class='row-content'
              v-bk-overflow-tips
            >
              {this.detailData.bk_data_id}
            </span>
          </div>
          <div class='detail-information-row'>
            <span class='row-label'>Token: </span>
            <span
              class='row-content'
              v-bk-overflow-tips
            >
              {this.detailData.access_token}
            </span>
          </div>
          <div class='detail-information-row'>
            <span class='row-label'>{this.$t('监控对象')}: </span>
            <span
              class='row-content'
              v-bk-overflow-tips
            >
              {this.detailData.scenario}
            </span>
          </div>
          <div class='detail-information-row'>
            <span class='row-label'>{this.$t('上报协议')}: </span>
            {this.detailData.protocol ? (
              <span
                class='row-content'
                v-bk-overflow-tips
              >
                {this.detailData.protocol === 'json' ? 'JSON' : 'Prometheus'}
              </span>
            ) : (
              <span> -- </span>
            )}
          </div>
          <div class={'detail-information-row'}>
            <span class='row-label'>
              {this.type === 'customEvent' ? this.$t('是否为平台事件') : this.$t('作用范围')}:{' '}
            </span>
            <span
              class='row-content'
              v-bk-overflow-tips
            >
              {this.copyIsPlatform === false ? this.$t('本空间') : this.$t('全局')}
            </span>
          </div>{' '}
          <div class='detail-information-row'>
            <span class='row-label'>{this.$t('数据标签')}: </span>
            {!this.isShowEditDataLabel ? (
              <div style='display: flex; min-width: 0'>
                <span
                  class='row-content'
                  v-bk-overflow-tips
                >
                  {this.detailData.data_label || '--'}
                </span>
                {!this.isShowEditDataLabel && !this.isReadonly && (
                  <i
                    class='icon-monitor icon-bianji edit-name'
                    onClick={this.handleShowEditDataLabel}
                  />
                )}
              </div>
            ) : (
              <VerifyInput
                show-validate={this.rule.dataLabel}
                validator={{ content: this.rule.dataLabelTips }}
              >
                <bk-input
                  ref='dataLabelInput'
                  // style='width: 240px'
                  v-model={this.copyDataLabel}
                  onBlur={this.handleEditDataLabel}
                  onInput={() => {
                    this.rule.dataLabel = false;
                    this.rule.dataLabelTips = '';
                  }}
                />
              </VerifyInput>
            )}
          </div>
          <div class='detail-information-row'>
            <span class='row-label'>{this.$t('名称')}: </span>
            {!this.isShowEditName ? (
              <div style='display: flex; min-width: 0'>
                <span
                  class='row-content'
                  v-bk-overflow-tips
                >
                  {this.detailData.name}
                </span>
                {this.detailData.name && !this.isReadonly && (
                  <i
                    class='icon-monitor icon-bianji edit-name'
                    onClick={this.handleShowEdit}
                  />
                )}
              </div>
            ) : (
              <bk-input
                ref='nameInput'
                // style='width: 240px'
                v-model={this.copyName}
                onBlur={this.handleEditName}
              />
            )}
          </div>
          <div class='detail-information-row last-row'>
            <span class='row-label'>{this.$t('描述')}: </span>
            {!this.isShowEditDesc ? (
              <div style='display: flex; min-width: 0'>
                <span
                  class='row-content'
                  v-bk-overflow-tips
                >
                  {this.detailData.desc || '--'}
                </span>
                {!this.isReadonly && (
                  <i
                    class='icon-monitor icon-bianji edit-name'
                    onClick={this.handleShowEditDes}
                  />
                )}
              </div>
            ) : (
              <bk-input
                ref='describeInput'
                // style='width: 440px'
                class='form-content-textarea'
                v-model={this.copyDescribe}
                rows={3}
                type='textarea'
                onBlur={this.handleEditDescribe}
              />
            )}
          </div>
        </div>
      </div>
    );
  }

  getGroupChanges(metricName, newGroups, metricMap) {
    // 获取原有分组信息
    const metricInfo = metricMap.get(metricName);
    const oldGroups = metricInfo?.groups || [];

    const oldSet = new Set(oldGroups);
    const newSet = new Set(newGroups);

    // 计算新增和删除的分组
    const added = [...newGroups].filter(group => !oldSet.has(group));
    const removed = [...oldGroups].filter(group => !newSet.has(group));
    return { added, removed };
  }

  /** 批量添加至分组 */
  async handleBatchAddGroup(groupName, manualList) {
    const group = this.groupsMap.get(groupName);
    if (!group) {
      return;
    }

    const currentMetrics = group.manualList || [];
    const newMetrics = [...new Set([...currentMetrics, ...manualList])];
    try {
      await this.submitGroupInfo({
        name: groupName,
        manual_list: newMetrics,
        auto_rules: group.matchRules || [],
      });
      this.updateCheckValue();
      this.getDetailData();
      this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
    } catch (error) {
      console.error(`Batch group ${groupName} update failed:`, error);
    }
  }

  async updateGroupInfo(metricName, groupNames, isAdd = true) {
    if (!groupNames?.length) return;

    const updatePromises = groupNames.map(async groupName => {
      const group = this.groupsMap.get(groupName);
      if (!group) {
        return;
      }

      const currentMetrics = group.manualList || [];
      const newMetrics = isAdd
        ? [...new Set([...currentMetrics, metricName])] // 防止重复添加
        : currentMetrics.filter(m => m !== metricName);

      try {
        await this.submitGroupInfo({
          name: groupName,
          manual_list: newMetrics,
          auto_rules: group.matchRules || [],
        });
      } catch (error) {
        console.error(`Group ${groupName} update failed:`, error);
      }
    });

    await Promise.all(updatePromises);
  }

  async saveSelectGroup(selectedGroups, metricName) {
    try {
      const changes = this.getGroupChanges(metricName, selectedGroups, this.metricGroupsMap);
      await Promise.all([
        this.updateGroupInfo(metricName, changes.added),
        this.updateGroupInfo(metricName, changes.removed, false),
      ]);
      this.getDetailData();
    } catch (error) {
      console.error('Group update failed:', error);
    }
  }

  async submitGroupInfo(config) {
    await this.$store.dispatch('custom-escalation/createOrUpdateGroupingRule', {
      time_series_group_id: this.$route.params.id,
      ...config,
    });
  }

  /** 更新自定义分组 */
  async handleSubmitGroup(config) {
    await this.submitGroupInfo(config);
    await this.getGroupList();
    this.changeGroupFilterList(config.name);
    this.getDetailData();
    this.nonGroupNum = this.getNonGroupNum();
  }

  /** 删除自定义分组 */
  async handleDelGroup(name) {
    await this.$store.dispatch('custom-escalation/deleteGroupingRule', {
      time_series_group_id: this.$route.params.id,
      name,
    });
    if (this.groupFilterList[0] === name) {
      this.changeGroupFilterList(ALL_LABEL);
    }
    this.getDetailData();
    this.nonGroupNum = this.getNonGroupNum();
  }

  /* 分组管理指标 */
  handleSelectGroup([value, index]) {
    const metricName = this.metricTable[index].name;
    const labels = [];
    for (const item of this.groupList) {
      const groupItem = this.groupsMap.get(item.name);
      const { matchRulesOfMetrics, manualList } = groupItem;
      const tempObj = {
        name: item.name,
        match_type: [],
      };
      if (matchRulesOfMetrics.includes(metricName)) {
        tempObj.match_type.push('auto');
      }
      if (value.includes(item.name)) {
        tempObj.match_type.push('manual');
        this.groupsMap.set(item.name, {
          ...groupItem,
          manualList: [...new Set(manualList.concat([metricName]))],
        });
      } else {
        this.groupsMap.set(item.name, {
          ...groupItem,
          manualList: manualList.filter(m => m !== metricName),
        });
      }
      if (tempObj.match_type.length) labels.push(tempObj);
    }
    this.metricTable[index].labels = labels;
    this.updateGroupList();
  }

  /* 更新分组管理 */
  updateGroupList() {
    this.groupList = this.groupList.map(item => ({
      ...item,
      manualList: this.groupsMap.get(item.name)?.manualList || [],
    }));
    this.nonGroupNum = this.getNonGroupNum();
  }

  /** 批量更新 */
  async handleSaveSliderInfo(localTable, delArray = []) {
    this.isShowMetricSlider = false;
    this.isShowDimensionSlider = false;
    await this.$store.dispatch('custom-escalation/modifyCustomTsFields', {
      time_series_group_id: this.$route.params.id,
      update_fields: localTable,
      delete_fields: delArray,
    });
    this.getDetailData();
    this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
  }
  render() {
    return (
      <div
        class='custom-detail-page-component'
        v-bkloading={{ isLoading: this.loading }}
      >
        <CommonNavBar
          class='common-nav-bar-single'
          needBack={true}
          routeList={this.$store.getters.navRouteList}
        >
          <div
            class='custom'
            slot='custom'
          >
            <span class='dec'>{this.$t('自定义指标管理')}</span>
            <span class='title'>{this.detailData.data_label || '-'}</span>
          </div>
          <div slot='append'>
            <span
              class={[this.isShowRightWindow ? 'active' : '', 'icon-monitor icon-audit']}
              onClick={() => (this.isShowRightWindow = !this.isShowRightWindow)}
            />
          </div>
        </CommonNavBar>
        <bk-alert class='hint-alert'>
          <i18n
            slot='title'
            path='数据上报好了，去 {0}'
          >
            <span
              style='color: #3a84ff; cursor: pointer'
              onClick={this.handleJump}
            >
              {this.$t('查看数据')}
            </span>
          </i18n>
        </bk-alert>
        <div class='custom-detail-page'>
          <div class='custom-detail'>
            {/* 基本信息 */}
            {this.getBaseInfoCmp()}
            {/* 指标/维度列表 */}
            <div class='custom-detail-page-table'>
              {this.type === 'customTimeSeries' ? (
                <TimeseriesDetailNew
                  class='detail-information detail-list'
                  allCheckValue={this.allCheckValue}
                  allDataPreview={this.allDataPreview}
                  autoDiscover={this.autoDiscover}
                  customGroups={this.groupList}
                  cycleOption={this.cycleOption}
                  dimensionNum={this.dimensionNum}
                  dimensionTable={this.dimensions}
                  groupSelectList={this.groupSelectList}
                  groupsMap={this.groupsMap}
                  metricGroupsMap={this.metricGroupsMap}
                  metricList={this.metricData}
                  metricNameList={this.metricNameList}
                  metricNum={this.metricNum}
                  metricTable={this.metricTable}
                  nameList={this.groupNameList}
                  nonGroupNum={this.nonGroupNum}
                  search={this.metricSearch}
                  selectedLabel={this.groupFilterList[0] || ALL_LABEL}
                  unitList={this.unitList}
                  onChangeGroup={this.changeGroupFilterList}
                  onDimensionChange={() => {
                    this.getDetailData(false);
                  }}
                  onGroupDelByName={this.handleDelGroup}
                  onGroupListOrder={tab => (this.groupList = tab)}
                  onGroupSubmit={this.handleSubmitGroup}
                  onHandleBatchAddGroup={this.handleBatchAddGroup}
                  onHandleClickSlider={v => {
                    this.isShowMetricSlider = v;
                  }}
                  onHandleExport={this.handleExportMetric}
                  onHandleSelectGroup={this.handleSelectGroup}
                  onHandleSelectToggle={this.saveSelectGroup}
                  onHandleUpload={this.handleUploadMetric}
                  onRowCheck={this.updateCheckValue}
                  onSearchChange={this.handleSearchChange}
                  onShowDimensionSlider={v => {
                    this.isShowDimensionSlider = v;
                  }}
                  onSwitcherChange={this.handleEditAutoDiscover}
                  onUpdateAllSelection={this.updateAllSelection}
                />
              ) : undefined}
            </div>
          </div>
          {/* <!-- 展开内容 --> */}
          <div class={['right-window', this.isShowRightWindow ? 'active' : '']}>
            {/* <!-- 右边展开收起按钮 --> */}
            <div
              class={['right-button', this.isShowRightWindow ? 'active-buttom' : '']}
              onClick={() => (this.isShowRightWindow = !this.isShowRightWindow)}
            >
              {this.isShowRightWindow ? (
                <i class='icon-monitor icon-arrow-right icon' />
              ) : (
                <i class='icon-monitor icon-arrow-left icon' />
              )}
            </div>
            <div class='right-window-title'>
              <span>{this.type === 'customEvent' ? this.$t('自定义事件帮助') : this.$t('自定义指标帮助')}</span>
              <span
                class='title-right'
                onClick={() => (this.isShowRightWindow = !this.isShowRightWindow)}
              >
                <span class='line' />
              </span>
            </div>
            <div class='right-window-content'>
              {this.detailData.protocol !== 'prometheus' && (
                <div>
                  <div class='content-title'>{this.$t('注意事项')}</div>
                  <span>{this.$t('API频率限制 1000/min，单次上报Body最大为500KB')}</span>
                </div>
              )}
              <div class={['content-title', this.detailData.protocol !== 'prometheus' ? 'content-interval' : '']}>
                {this.$t('使用方法')}
              </div>
              <div class='content-row'>
                <span>
                  {this.detailData.protocol === 'prometheus'
                    ? this.$t('不同云区域上报端点信息')
                    : this.$t('不同云区域Proxy信息')}
                </span>
                <div class='content-example'>
                  {this.proxyInfo.map((item, index) => (
                    <div key={index}>
                      {this.$t('管控区域')} {item.bkCloudId}
                      <span style={{ marginLeft: '10px' }}>{item.ip}</span>
                    </div>
                  ))}
                </div>
              </div>
              {this.detailData.protocol !== 'prometheus' && (
                <div class='content-row'>
                  <span>{this.$t('命令行直接调用样例')}</span>
                  <div class='content-example'>
                    curl -g -X POST http://$&#123;PROXY_IP&#125;:10205/v2/push/ -d "$&#123;REPORT_DATA&#125;"
                  </div>
                </div>
              )}
              {this.detailData.protocol === 'prometheus' ? (
                <div>
                  <div class='content-title content-interval'>{this.$t('数据上报端点样例')}</div>
                  <div class='content-row'>
                    <pre class='content-example'>http://$&#123;PROXY_IP&#125;:4318</pre>
                  </div>
                  <div class='content-row mt10'>
                    <div class='content-title content-interval'>{this.$t('sdk接入流程')}</div>
                    <div>
                      {this.$t(
                        '用户使用 prometheus 原始 SDK 上报即可，不过需要指定蓝鲸的上报端点（$host:$port）以及 HTTP Headers。'
                      )}
                    </div>
                    <pre class='content-example'>X-BK-TOKEN=$TOKEN</pre>
                    <div class='mt10'>
                      {this.$t('prometheus sdk 库：https://prometheus.io/docs/instrumenting/clientlibs/')}
                    </div>
                  </div>
                  {/* Golang 示例部分 */}
                  <div class='content-row mt10'>
                    <div>{this.$t('各语言接入示例')} :</div>
                    <div class='mt5'>Golang</div>
                    <div class='mt5'>
                      {this.$t(
                        '1. 补充 headers，用于携带 token 信息。定义 Client 行为，由于 prometheus sdk 没有提供新增或者修改 Headers 的方法，所以需要实现 Do() interface，代码示例如下：'
                      )}
                    </div>
                    <div class='mt5'>
                      {this.$t(
                        '2. 填写上报端点，在 `push.New("$endpoint", name)` 里指定。然后需要将自定义的 client 传入到 `pusher.Client($bkClient{})` 里面。'
                      )}
                    </div>
                    <div class='content-prometheus'>
                      <pre class='content-example'>{this.sdkData.preGoOne}</pre>
                      <div
                        class='content-copy-prometheus'
                        onClick={() => this.handleCopyPrometheus('golangCopy')}
                      >
                        <i class='icon-monitor icon-mc-copy' />
                      </div>
                      <textarea
                        ref='golangCopy'
                        class='copy-textarea'
                      />
                    </div>
                  </div>
                  {/* Python 示例部分 */}
                  <div class='content-row'>
                    <div>Python</div>
                    <div class='mt5'>{this.$t('1. 补充 headers，用于携带 token 信息。实现一个自定义的 handler。')}</div>
                    <div>
                      {this.$t(
                        '2. 填写上报端点，在 `push_to_gateway("$endpoint", ...)` 里指定。然后将自定义的 handler 传入到函数里。'
                      )}
                    </div>
                    <div class='content-prometheus'>
                      <pre class='content-example'>{this.sdkData.prePythonOne}</pre>
                      <div
                        class='content-copy-prometheus'
                        onClick={() => this.handleCopyPrometheus('pythonCopy')}
                      >
                        <i class='icon-monitor icon-mc-copy' />
                      </div>
                      <textarea
                        ref='pythonCopy'
                        class='copy-textarea'
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div class='content-row'>
                  <span>{this.$t('数据上报格式样例')}</span>
                  <pre class='content-example'>{this.preData}</pre>
                  <div
                    class='content-copy'
                    onClick={this.handleCopyData}
                  >
                    <i class='icon-monitor icon-mc-copy' />
                  </div>
                  <textarea
                    ref='textCopy'
                    class='copy-textarea'
                  />
                </div>
              )}
            </div>
          </div>
        </div>
        {
          <IndicatorTableSlide
            autoDiscover={this.autoDiscover}
            cycleOption={this.cycleOption}
            dimensionTable={this.dimensions}
            isShow={this.isShowMetricSlider}
            metricTable={this.metricTable}
            unitList={this.unitList}
            onHidden={v => (this.isShowMetricSlider = v)}
            onSaveInfo={this.handleSaveSliderInfo}
          />
        }
        {
          <DimensionTableSlide
            dimensionTable={this.dimensions}
            isShow={this.isShowDimensionSlider}
            onHidden={v => (this.isShowDimensionSlider = v)}
            onSaveInfo={this.handleSaveSliderInfo}
          />
        }
      </div>
    );
  }
}
