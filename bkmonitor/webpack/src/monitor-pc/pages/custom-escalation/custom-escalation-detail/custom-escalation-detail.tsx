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
import IndicatorTableSlide from './metric-table-slide';
import TimeseriesDetailNew from './timeseries-detail';
import { type IGroupListItem, ALL_LABEL, NULL_LABEL } from './type';
import { fuzzyMatch } from './utils';

import type { IDetailData } from '../../../types/custom-escalation/custom-escalation-detail';

import './custom-escalation-detail.scss';

interface IMetricGroupMapItem {
  groups: string[];
  matchType: Record<string, string[]>;
}

interface IMetricSearchObject {
  aggregate: string[];
  description: string[];
  func: string[];
  name: string[];
  show: string[];
  unit: string[];
}

interface ISDKData {
  preGoOne?: string;
  prePythonOne?: string;
}

/**
 * 自定义指标详情页组件
 */
@Component
export default class CustomEscalationDetailNew extends tsc<any, any> {
  @Ref('nameInput') readonly nameInput!: HTMLInputElement;
  @Ref() readonly dataLabelInput!: HTMLInputElement;
  @Ref() readonly describeInput!: HTMLInputElement;
  @Ref('textCopy') readonly textCopy!: HTMLTextAreaElement;
  @ProvideReactive('metricFunctions') metricFunctions: any[] = [];

  isShowMetricSlider = false; // 展示指标抽屉
  isShowDimensionSlider = false; // 展示维度抽屉
  loading = false; // 加载状态
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
  proxyInfo: any[] = []; // 云区域分类数据
  preData = ''; // 数据上报格式样例
  sdkData: ISDKData = {}; // sdk 接入数据

  // 详情数据
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

  // 指标维度数据 时序数据
  metricData: any[] = [];
  unitList: any[] = []; // 单位list

  groupSelectList: any[] = [
    {
      id: '',
      name: '未分组',
    },
  ];

  allCheckValue: 0 | 1 | 2 = 0; // 0: 取消全选 1: 半选 2: 全选
  groupFilterList: string[] = []; // 分组过滤列表

  /* 筛选条件(简化) */
  metricSearchObj: IMetricSearchObject = {
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
  matchRulesMap: Map<string, string[]> = new Map();

  /* 每个组所包含的指标 */
  groupsMap: Map<string, IGroupListItem> = new Map();

  /* 每个指标包含的组 */
  metricGroupsMap: Map<string, IMetricGroupMapItem> = new Map();

  /* 指标列表 */
  metricList: any[] = [];

  /* 维度列表 */
  dimensions: any[] = [];

  /* 数据预览ALL */
  allDataPreview: Record<string, any> = {};

  autoDiscover = false;

  rule = {
    dataLabelTips: '',
    dataLabel: false,
  };

  nonGroupNum = 0; // 未分组数量

  /**
   * 获取当前页面类型：自定义事件或自定义时序
   */
  get type(): string {
    return this.$route.name === 'custom-detail-event' ? 'customEvent' : 'customTimeSeries';
  }

  /**
   * 检查数据是否为只读
   */
  get isReadonly(): boolean {
    return !!this.detailData.is_readonly;
  }

  /**
   * 获取上报周期选项（除了auto之外）
   */
  get cycleOption(): any[] {
    return defaultCycleOptionSec.filter(({ id }) => id !== 'auto');
  }

  /**
   * 获取过滤后的指标表格数据
   */
  get metricTable(): any[] {
    const length = this.groupFilterList.length;
    const nameLength = this.metricSearchObj.name.length;
    const descriptionLength = this.metricSearchObj.description.length;
    const unitLength = this.metricSearchObj.unit.length;
    const aggregateLength = this.metricSearchObj.aggregate.length;
    const isShowLength = this.metricSearchObj.show.length;

    return this.metricData.filter(item => {
      return (
        // 过滤分组
        (length
          ? this.groupFilterList.some(
              g => item.labels.map(l => l.name).includes(g) || (!item.labels.length && g === NULL_LABEL)
            )
          : true) &&
        // 过滤名称
        (nameLength ? this.metricSearchObj.name.some(n => fuzzyMatch(item.name, n)) : true) &&
        // 过滤描述
        (descriptionLength ? this.metricSearchObj.description.some(n => fuzzyMatch(item.description, n)) : true) &&
        // 过滤单位
        (unitLength ? this.metricSearchObj.unit.some(u => fuzzyMatch(item.unit || 'none', u)) : true) &&
        // 过滤聚合方法
        (aggregateLength
          ? this.metricSearchObj.aggregate.some(a => fuzzyMatch(item.aggregate_method || 'none', a))
          : true) &&
        // 过滤显示状态
        (isShowLength ? this.metricSearchObj.show.some(s => s === String(!item.hidden)) : true)
      );
    });
  }

  /**
   * 处理搜索变更，使用防抖减少频繁调用
   * @param list 搜索列表
   */
  @Debounce(300)
  handleSearchChange(list: any[] = []): void {
    const search: IMetricSearchObject = {
      name: [],
      description: [],
      unit: [],
      func: [],
      aggregate: [],
      show: [],
    };

    for (const item of list) {
      if (item.type === 'text') {
        item.id = 'name';
        item.values = [{ id: item.name, name: item.name }];
      }
      if (item.id === 'unit') {
        for (const v of item.values) {
          v.id = v.name;
        }
      }
      search[item.id] = [...new Set(search[item.id].concat(item.values.map(v => v.id)))];
    }

    this.metricSearchObj = search;
  }

  /**
   * 清除搜索条件
   */
  handleClearSearch(): void {
    this.handleSearchChange();
  }

  /**
   * 获取未分组数量
   */
  getNonGroupNum(): number {
    return this.metricData.filter(item => item.monitor_type === 'metric').filter(item => !item.labels.length).length;
  }

  /**
   * 处理导出指标数据
   */
  handleExportMetric(): void {
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
    const generateFileName = (): string => {
      return `自定义指标-${this.detailData.name}-${dayjs.tz().format('YYYY-MM-DD_HH-mm-ss')}.json`;
    };

    // 执行下载
    downCsvFile(JSON.stringify(template, null, 2), generateFileName());
  }

  /**
   * 处理导入指标数据
   * @param jsonData JSON字符串
   */
  async handleUploadMetric(jsonData: string): Promise<void> {
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
   * 获取指标函数列表
   */
  async handleGetMetricFunctions(): Promise<void> {
    this.metricFunctions = await getFunctions().catch(() => []);
  }

  /**
   * 更改分组过滤列表
   * @param v 分组值
   */
  changeGroupFilterList(v: string): void {
    this.handleClearSearch();
    this.groupFilterList = v === ALL_LABEL ? [] : [v];
    this.updateAllSelection();
  }

  /**
   * 加载静态数据（云区域和单位列表）
   */
  async loadStaticData(): Promise<void> {
    try {
      const [proxyInfo, unitList] = await Promise.all([
        this.$store.dispatch('custom-escalation/getProxyInfo'),
        this.$store.dispatch('strategy-config/getUnitList'),
      ]);

      this.proxyInfo = proxyInfo;
      this.unitList = unitList;
    } catch (error) {
      console.error('加载静态数据失败:', error);
    }
  }

  /**
   * 组件创建时的初始化
   */
  async created(): Promise<void> {
    await this.loadStaticData();
    await this.getDetailData();
    this.handleGetMetricFunctions();
    this.nonGroupNum = this.getNonGroupNum();
  }

  /**
   * 更新全选状态
   * @param v 是否选中
   */
  updateAllSelection(v = false): void {
    this.metricTable.forEach(item => item.monitor_type === 'metric' && (item.selection = v));
    this.updateCheckValue();
  }

  /**
   * 更新选中状态值
   */
  updateCheckValue(): void {
    const metricList = this.metricTable.filter(item => item.monitor_type === 'metric');
    const checkedLength = metricList.filter(item => item.selection).length;
    const allLength = metricList.length;

    if (checkedLength > 0) {
      this.allCheckValue = checkedLength < allLength ? 1 : 2;
    } else {
      this.allCheckValue = 0;
    }
  }

  /**
   * 获取详情数据
   * @param needLoading 是否显示加载状态
   */
  async getDetailData(needLoading = true): Promise<void> {
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

      // 处理指标函数数据
      for (const item of metricData?.metrics || []) {
        if (!item?.function?.[0]) {
          item.function = [];
        }
      }

      this.metricList = metricData?.metrics || [];
      this.dimensions = metricData?.dimensions || [];

      await this.getGroupList();
      await this.getAllDataPreview(this.detailData.metric_json[0].fields, this.detailData.table_id);
      this.handleDetailData(this.detailData);
    } catch (error) {
      console.error('获取详情数据失败:', error);
    } finally {
      this.loading = false;
    }
  }

  /**
   * 处理详情数据
   * @param detailData 详情数据
   */
  handleDetailData(detailData: IDetailData): void {
    if (this.type === 'customTimeSeries') {
      this.metricData = this.metricList.map(item => ({
        ...item,
        selection: false,
        descReValue: false,
        monitor_type: 'metric',
      }));
      this.setMetricDataLabels();
    }

    this.scenario = `${detailData.scenario_display[0]} - ${detailData.scenario_display[1]}`;
    this.copyName = this.detailData.name;
    this.copyDataLabel = this.detailData.data_label || '';
    this.copyDescribe = this.detailData.desc || '';
    this.copyIsPlatform = this.detailData.is_platform ?? false;

    // 生成数据上报样例
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

    // 处理 Prometheus 类型的特殊内容
    if (detailData.protocol === 'prometheus') {
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

  /* 获取所有数据预览数据 */
  async getAllDataPreview(fields: { monitor_type: 'dimension' | 'metric'; name: string }[], tableId) {
    const fieldList = fields.filter(item => item.monitor_type === 'metric').map(item => item.name);
    const data = await this.$store.dispatch('custom-escalation/getCustomTimeSeriesLatestDataByFields', {
      result_table_id: tableId,
      fields_list: fieldList,
    });
    this.allDataPreview = data?.fields_value || {};
  }

  /**
   * 获取分组管理数据
   */
  async getGroupList(): Promise<void> {
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

  /**
   * 整理分组数据
   */
  groupsDataTidy(): void {
    const metricNames = this.metricList.map(item => item.name);
    const allMatchRulesSet = new Set();
    const metricGroupsMap = new Map();
    this.groupsMap = new Map();
    // 收集所有匹配规则
    for (const item of this.groupList) {
      for (const rule of item.matchRules) {
        allMatchRulesSet.add(rule);
      }
    }
    const allMatchRules = Array.from(allMatchRulesSet);

    /* 整理每个匹配规则配的指标数据 */
    for (const rule of allMatchRules) {
      this.matchRulesMap.set(
        rule as string,
        metricNames.filter(name => matchRuleFn(name, rule as string))
      );
    }

    // 为每个组构建指标映射
    for (const item of this.groupList) {
      const tempSet = new Set();

      // 收集通过匹配规则匹配到的指标
      for (const rule of item.matchRules) {
        const metrics = this.matchRulesMap.get(rule) || [];
        for (const m of metrics) {
          tempSet.add(m);
        }
      }
      const matchRulesOfMetrics = Array.from(tempSet) as string[];

      // 更新组映射
      this.groupsMap.set(item.name, {
        ...item,
        matchRulesOfMetrics,
      });

      /* 为每个指标建立包含的组的映射 */
      const setMetricGroup = (metricName: string, type: string): void => {
        const metricItem = metricGroupsMap.get(metricName);
        if (metricItem) {
          const { groups, matchType } = metricItem;
          const targetGroups = [...new Set(groups.concat([item.name]))];
          const targetMatchType = JSON.parse(JSON.stringify(matchType));

          for (const t of targetGroups) {
            if (t === item.name) {
              targetMatchType[t] = [...new Set((matchType[t] || []).concat([type]))];
            }
          }

          metricGroupsMap.set(metricName, {
            groups: targetGroups,
            matchType: targetMatchType,
          });
        } else {
          const matchTypeObj = {
            [item.name]: [type],
          };
          metricGroupsMap.set(metricName, {
            groups: [item.name],
            matchType: matchTypeObj,
          });
        }
      };

      // 应用匹配规则匹配的指标
      matchRulesOfMetrics.forEach(m => {
        setMetricGroup(m, 'auto');
      });

      // 应用手动添加的指标
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

  /**
   * 显示名称编辑框
   */
  handleShowEdit(): void {
    this.isShowEditName = true;
    this.$nextTick(() => {
      this.nameInput.focus();
    });
  }

  /**
   * 显示英文名编辑框
   */
  handleShowEditDataLabel(): void {
    this.isShowEditDataLabel = true;
    this.rule.dataLabelTips = '';
    this.rule.dataLabel = false;
    this.$nextTick(() => {
      this.dataLabelInput.focus();
    });
  }

  /**
   * 显示描述编辑框
   */
  handleShowEditDes(): void {
    this.isShowEditDesc = true;
    this.$nextTick(() => {
      this.describeInput.focus();
    });
  }

  /**
   * 保存自动发现设置
   * @param autoDiscover 是否自动发现
   */
  handleEditAutoDiscover(autoDiscover: boolean): void {
    this.autoDiscover = autoDiscover;
    this.handleEditFiled({
      auto_discover: autoDiscover,
    });
  }

  /**
   * 编辑字段通用方法
   * @param props 字段属性
   * @param showMsg 是否显示成功消息
   */
  async handleEditFiled(props: Record<string, any>, showMsg = true): Promise<void> {
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

  /**
   * 编辑英文名
   */
  async handleEditDataLabel(): Promise<void> {
    // 如果英文名为空或未变更，则不做处理
    if (!this.copyDataLabel || this.copyDataLabel === this.detailData.data_label) {
      this.copyDataLabel = this.detailData.data_label;
      this.isShowEditDataLabel = false;
      return;
    }

    // 检查是否含有中文
    if (/[\u4e00-\u9fa5]/.test(this.copyDataLabel)) {
      this.rule.dataLabelTips = this.$tc('输入非中文符号');
      this.rule.dataLabel = true;
      return;
    }

    // 验证英文名唯一性
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

    // 保存英文名
    await this.handleEditFiled({
      data_label: this.copyDataLabel,
    });

    this.detailData.data_label = this.copyDataLabel;
    this.isShowEditDataLabel = false;
  }

  /**
   * 编辑名字
   */
  async handleEditName(): Promise<void> {
    // 如果名字为空或未变更，则不做处理
    if (!(this.copyName && this.copyName !== this.detailData.name)) {
      this.copyName = this.detailData.name;
      this.isShowEditName = false;
      return;
    }

    // 验证名字唯一性
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

    // 保存名字
    await this.handleEditFiled({
      name: this.copyName,
    });

    this.detailData.name = this.copyName;
    this.isShowEditName = false;
  }

  /**
   * 编辑描述
   */
  async handleEditDescribe(): Promise<void> {
    // 如果描述未变更，则不做处理
    if (this.copyDescribe.trim() === this.detailData.desc) {
      this.copyDescribe = this.detailData.desc || '';
      this.isShowEditDesc = false;
      return;
    }

    // 保存描述
    this.isShowEditDesc = false;
    this.handleEditFiled({
      desc: this.copyDescribe,
    });

    this.detailData.desc = this.copyDescribe;
  }

  /**
   * 复制数据上报样例
   */
  handleCopyData(): void {
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

  /**
   * 复制Prometheus SDK接入流程代码
   * @param type 复制类型（golang或python）
   */
  handleCopyPrometheus(type: string): void {
    this[type].value = type === 'golangCopy' ? this.sdkData.preGoOne : this.sdkData.prePythonOne;
    this[type].select();
    document.execCommand('copy');

    this.$bkMessage({
      theme: 'success',
      message: this.$t('样例复制成功'),
    });
  }

  /**
   * 通过分组管理计算每个指标包含的组
   */
  setMetricDataLabels(): void {
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

  /**
   * 处理路由跳转
   */
  handleJump(): void {
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
          name: 'custom-escalation-view',
          params: { id: String(this.detailData.time_series_group_id) },
          query: { name: this.detailData.name },
        });
      },
    };

    toView[this.type]();
  }

  /**
   * 获取基础信息组件
   * @returns 基础信息JSX
   */
  getBaseInfoCmp(): JSX.Element {
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

  /**
   * 获取指标分组变更信息
   * @param metricName 指标名称
   * @param newGroups 新分组列表
   * @param metricMap 指标映射Map
   * @returns 变更信息
   */
  getGroupChanges(
    metricName: string,
    newGroups: string[],
    metricMap: Map<string, any>
  ): { added: string[]; removed: string[] } {
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

  /**
   * 批量添加至分组
   * @param groupName 分组名称
   * @param manualList 手动添加的指标列表
   */
  async handleBatchAddGroup(groupName: string, manualList: string[]): Promise<void> {
    const group = this.groupsMap.get(groupName);
    if (!group) {
      return;
    }

    // 合并当前指标和新添加的指标
    const currentMetrics = group.manualList || [];
    const newMetrics = [...new Set([...currentMetrics, ...manualList])];

    try {
      await this.submitGroupInfo({
        name: groupName,
        manual_list: newMetrics,
        auto_rules: group.matchRules || [],
      });
      await this.getDetailData();
      this.updateCheckValue();
      this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
    } catch (error) {
      console.error(`批量添加分组 ${groupName} 更新失败:`, error);
    }
  }

  /**
   * 更新分组信息
   * @param metricName 指标名称
   * @param groupNames 分组名称列表
   * @param isAdd 是否添加
   */
  async updateGroupInfo(metricName: string, groupNames: string[], isAdd = true): Promise<void> {
    if (!groupNames?.length) return;

    const updatePromises = groupNames.map(async groupName => {
      const group = this.groupsMap.get(groupName);
      if (!group) {
        return;
      }

      const currentMetrics = group.manualList || [];
      const newMetrics = isAdd
        ? [...new Set([...currentMetrics, metricName])] // 防止重复添加
        : currentMetrics.filter(m => m !== metricName); // 移除指标

      try {
        await this.submitGroupInfo({
          name: groupName,
          manual_list: newMetrics,
          auto_rules: group.matchRules || [],
        });
      } catch (error) {
        console.error(`分组 ${groupName} 更新失败:`, error);
      }
    });

    await Promise.all(updatePromises);
  }

  /**
   * 保存选择的分组
   * @param selectedGroups 选中的分组列表
   * @param metricName 指标名称
   */
  async saveSelectGroup(selectedGroups: string[], metricName: string): Promise<void> {
    try {
      // 计算分组变更
      const changes = this.getGroupChanges(metricName, selectedGroups, this.metricGroupsMap);

      // 并行处理添加和移除操作
      await Promise.all([
        this.updateGroupInfo(metricName, changes.added),
        this.updateGroupInfo(metricName, changes.removed, false),
      ]);
      await this.getDetailData();
      this.updateCheckValue();
    } catch (error) {
      console.error('分组更新失败:', error);
    }
  }

  /**
   * 提交分组信息
   * @param config 分组配置
   */
  async submitGroupInfo(config: Record<string, any>): Promise<void> {
    await this.$store.dispatch('custom-escalation/createOrUpdateGroupingRule', {
      time_series_group_id: this.$route.params.id,
      ...config,
    });
  }

  /**
   * 更新自定义分组
   * @param config 分组配置
   */
  async handleSubmitGroup(config: Record<string, any>): Promise<void> {
    await this.submitGroupInfo(config);
    this.changeGroupFilterList(config.name);
    await this.getDetailData();
    this.nonGroupNum = this.getNonGroupNum();
  }

  /**
   * 删除自定义分组
   * @param name 分组名称
   */
  async handleDelGroup(name: string): Promise<void> {
    await this.$store.dispatch('custom-escalation/deleteGroupingRule', {
      time_series_group_id: this.$route.params.id,
      name,
    });

    // 如果当前选中的是被删除的分组，则重置筛选条件
    if (this.groupFilterList[0] === name) {
      this.changeGroupFilterList(ALL_LABEL);
    }
    await this.getDetailData();
    this.nonGroupNum = this.getNonGroupNum();
  }

  /**
   * 处理分组选择
   * @param data 选择数据
   */
  handleSelectGroup([value, index]: [string[], number]): void {
    const metricName = this.metricTable[index].name;
    const labels = [];

    for (const item of this.groupList) {
      const groupItem = this.groupsMap.get(item.name);
      const { matchRulesOfMetrics, manualList } = groupItem;
      const tempObj = {
        name: item.name,
        match_type: [],
      };

      // 处理自动匹配
      if (matchRulesOfMetrics.includes(metricName)) {
        tempObj.match_type.push('auto');
      }

      // 处理手动匹配
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

  /**
   * 更新分组管理列表
   */
  updateGroupList(): void {
    this.groupList = this.groupList.map(item => ({
      ...item,
      manualList: this.groupsMap.get(item.name)?.manualList || [],
    }));
    this.nonGroupNum = this.getNonGroupNum();
  }

  /**
   * 保存抽屉信息
   * @param localTable 本地表格数据
   * @param delArray 删除数组
   */
  async handleSaveSliderInfo(localTable: any[], delArray: any[] = []): Promise<void> {
    this.isShowMetricSlider = false;
    this.isShowDimensionSlider = false;

    await this.$store.dispatch('custom-escalation/modifyCustomTsFields', {
      time_series_group_id: this.$route.params.id,
      update_fields: localTable,
      delete_fields: delArray,
    });
    await this.getDetailData();
    this.allCheckValue = 0;
    this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
  }

  /**
   * 渲染组件
   * @returns 组件JSX
   */
  render(): JSX.Element {
    return (
      <div
        class='custom-detail-page-component'
        v-bkloading={{ isLoading: this.loading }}
      >
        {/* 导航栏 */}
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

        {/* 提示条 */}
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
                  dimensions={this.dimensions}
                  groupSelectList={this.groupSelectList}
                  groupsMap={this.groupsMap}
                  metricGroupsMap={this.metricGroupsMap}
                  metricList={this.metricData}
                  metricTable={this.metricTable}
                  nonGroupNum={this.nonGroupNum}
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

          {/* 右侧帮助面板 */}
          <div class={['right-window', this.isShowRightWindow ? 'active' : '']}>
            {/* 右边展开收起按钮 */}
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

            {/* 帮助标题 */}
            <div class='right-window-title'>
              <span>{this.type === 'customEvent' ? this.$t('自定义事件帮助') : this.$t('自定义指标帮助')}</span>
              <span
                class='title-right'
                onClick={() => (this.isShowRightWindow = !this.isShowRightWindow)}
              >
                <span class='line' />
              </span>
            </div>

            {/* 帮助内容 */}
            <div class='right-window-content'>
              {/* JSON协议注意事项 */}
              {this.detailData.protocol !== 'prometheus' && (
                <div>
                  <div class='content-title'>{this.$t('注意事项')}</div>
                  <span>{this.$t('API频率限制 1000/min，单次上报Body最大为500KB')}</span>
                </div>
              )}

              <div class={['content-title', this.detailData.protocol !== 'prometheus' ? 'content-interval' : '']}>
                {this.$t('使用方法')}
              </div>

              {/* 云区域信息 */}
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

              {/* JSON协议调用样例 */}
              {this.detailData.protocol !== 'prometheus' && (
                <div class='content-row'>
                  <span>{this.$t('命令行直接调用样例')}</span>
                  <div class='content-example'>
                    curl -g -X POST http://$&#123;PROXY_IP&#125;:10205/v2/push/ -d "$&#123;REPORT_DATA&#125;"
                  </div>
                </div>
              )}

              {/* Prometheus协议相关内容 */}
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
                    <div class='mt10'>
                      {this.$t(
                        '如果上报渠道不支持加入自定义 headers, 也可以使用 BasicAuth 进行验证, user: bkmonitor, password: $TOKEN'
                      )}
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
        <DimensionTableSlide
          dimensionTable={this.dimensions}
          isShow={this.isShowDimensionSlider}
          onHidden={v => (this.isShowDimensionSlider = v)}
          onSaveInfo={this.handleSaveSliderInfo}
        />
      </div>
    );
  }
}
