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
  modifyCustomTimeSeriesDesc,
  validateCustomEventGroupLabel,
  validateCustomTsGroupLabel,
} from 'monitor-api/modules/custom_report';
import { getFunctions } from 'monitor-api/modules/grafana';

import { defaultCycleOptionSec } from '../../../components/cycle-input/utils';
import CommonNavBar from '../../../pages/monitor-k8s/components/common-nav-bar';
import { matchRuleFn } from '../group-manage-dialog';
import IndicatorTableSlide from './metric-table-slide';
import TimeseriesDetailNew from './timeseries-detail';

import type {
  IDetailData,
  IEditParams,
  // IParams,
  IRefreshList,
  IShortcuts,
  ISideslider,
} from '../../../types/custom-escalation/custom-escalation-detail';

import './custom-escalation-detail.scss';

export const ALL_LABEL = '__all_label__';
export const NULL_LABEL = '__null_label__';

interface ICustomTSFields {
  dimensions: Item[];
  metrics: Item[];
}

interface Item {
  name: string;
  type: 'dimension' | 'metric';
  description: string;
  disabled?: boolean;
  unit?: string;
  hidden?: boolean;
  aggregate_method?: string;
  function?: object;
  interval?: number;
  label?: string[];
  dimensions?: string[];
  common?: boolean;
}
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
  isShow = false;
  @ProvideReactive('metricFunctions') metricFunctions = [];

  /** 分割线 ============================================= */
  descName = ''; // 别名
  loading = false;
  isCreat = ''; // 是否从创建过来
  // type = 'customEvent' // 展示类型：customEvent 自定义事件 customTimeSeries 自定义指标
  copyName = ''; // 修改的名字
  copyDataLabel = ''; // 修改的英文名
  copyDescribe = ''; // 修改的描述
  copyIsPlatform = false; // 是否为平台指标、事件
  isShowEditName = false; // 是否显示名字编辑框
  isShowRightWindow = true; // 是否显示右侧帮助栏
  isShowEditDataLabel = false; // 是否展示英文名编辑框
  isShowEditIsPlatform = false; // 是否展示平台师表
  isShowEditDesc = false; // 是否展示描述编辑框
  scenario = ''; // 分类
  protocol = ''; // 上报协议
  proxyInfo = []; // 云区域分类数据
  preData = ''; // 数据上报格式样例
  sdkData: any = {}; // sdk 接入数据
  timer = null; // 定时器
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
  };

  //  侧滑栏内容数据 事件数据
  sideslider: ISideslider = {
    isShow: false,
    title: '',
    data: {}, //  原始数据
  };

  //  事件列表数据 事件数据
  eventData = [];

  //  指标维度数据 时序数据
  metricData = [];
  isShowData = true; // 是否展示数据预览 时序数据
  unitList = []; // 单位list
  unit = {
    value: true,
    index: -1,
    toggle: false,
  };

  //  时间选择器选择项
  shortcuts: IShortcuts = {
    list: [],
    value: 1,
  };
  refreshList: IRefreshList;
  pagination = {
    page: 1,
    pageSize: 20,
    total: 100,
    pageList: [10, 20, 50, 100],
  };
  tableId = '';
  metricValue = {};
  dataLoading = false;

  batchGroupValue = [];

  groupSelectList: any = [
    {
      id: '',
      name: '未分组',
    },
  ];

  allCheckValue: 0 | 1 | 2 = 0; // 0: 取消全选 1: 半选 2: 全选
  metricCheckList: any = [];
  groupFilterList: string[] = [];
  metricFilterList: string[] = ['metric'];
  unitFilterList: string[] = [];
  groupManage = {
    show: false,
  };
  metricSearchValue = [];
  /* 筛选条件(简化) */
  metricSearchObj = {
    type: [],
    name: [],
    enName: [],
    unit: [],
    text: [],
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
  /* 分组标签pop实例 */
  groupTagInstance = null;
  /* 用于判断分组下拉列表展开期间是否选择过 */
  isUpdateGroup = false;

  /* 数据预览ALL */
  allDataPreview = {};

  eventDataLoading = false;

  /* 所有单位数据 */
  allUnitList = [];
  /* 列表中已选的单位数据 */
  tableAllUnitList = [];

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

  //  维度数量
  get dimensionNum() {
    return this.dimensions.length;
  }

  // 未分组数量
  get nonGroupNum() {
    return this.metricData.filter(item => item.monitor_type === 'metric').filter(item => !item.labels.length).length;
  }

  get selectionLeng() {
    const selectionList = this.metricTable.filter(item => item.selection);
    return selectionList.length;
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
    const labelsMatchTypes = labels => {
      let temp = [];
      for (const item of labels) {
        temp = temp.concat(item.match_type);
      }
      temp = [...new Set(temp)];
      return temp;
    };
    // 模糊匹配
    const fuzzyMatch = (str: string, pattern: string) => {
      const lowerStr = String(str).toLowerCase();
      const lowerPattern = String(pattern).toLowerCase();
      return lowerStr.includes(lowerPattern);
    };
    const leng1 = this.groupFilterList.length;
    const leng2 = this.metricFilterList.length;
    const leng3 = this.unitFilterList.length;
    const typeLeng = this.metricSearchObj.type.length;
    const nameLeng = this.metricSearchObj.name.length;
    const enNameLeng = this.metricSearchObj.enName.length;
    const unitLeng = this.metricSearchObj.unit.length;
    const textleng = this.metricSearchObj.text.length;
    const filterList = this.metricData.filter(item => {
      const isMetric = item.monitor_type === 'metric';
      return (
        (leng1
          ? this.groupFilterList.some(
            g => item.labels.map(l => l.name).includes(g) || (!item.labels.length && g === NULL_LABEL)
          ) && isMetric
          : true) &&
        (leng2 ? this.metricFilterList.includes(item.monitor_type) : true) &&
        (leng3
          ? this.unitFilterList.some(u => {
            if (u === 'none') {
              return isMetric && (item.unit === 'none' || !item.unit);
            }
            if (u === '--') {
              return !isMetric;
            }
            return item.unit === u;
          })
          : true) &&
        (typeLeng
          ? isMetric && this.metricSearchObj.type.some(t => labelsMatchTypes(item.labels).includes(t))
          : true) &&
        (nameLeng
          ? isMetric && this.metricSearchObj.name.some(n => item.labels.some(l => fuzzyMatch(l.name, n)))
          : true) &&
        (enNameLeng ? this.metricSearchObj.enName.some(n => fuzzyMatch(item.name, n)) : true) &&
        (unitLeng
          ? isMetric && this.metricSearchObj.unit.some(u => fuzzyMatch(item.unit || (isMetric ? 'none' : ''), u))
          : true) &&
        (textleng
          ? this.metricSearchObj.text.some(t => {
            const monitorType = {
              指标: 'metric',
              维度: 'dimension',
            };
            return (
              item.monitor_type === t ||
              monitorType?.[t] === item.monitor_type ||
              (isMetric && item.labels.some(l => fuzzyMatch(l.name, t))) ||
              fuzzyMatch(item.name, t) ||
              fuzzyMatch(item.unit || (isMetric ? 'none' : ''), t)
            );
          })
          : true)
      );
    });
    // this.handleGroupList(fiterList);
    return filterList;
    // this.changePageCount(filterList.length);
    // return filterList.slice(
    //   this.pagination.pageSize * (this.pagination.page - 1),
    //   this.pagination.pageSize * this.pagination.page
    // );
  }

  /**
   * @description: 获取指标函数列表
   * @param {*}
   * @return {*}
   */
  async handleGetMetricFunctions() {
    this.metricFunctions = await getFunctions().catch(() => []);
  }

  changePageCount(count: number) {
    this.pagination.total = count;
  }

  changeGroupFilterList(v: string) {
    this.groupFilterList = v === ALL_LABEL ? [] : [v];
  }

  created() {
    this.getDetailData();
    this.handleGetMetricFunctions();
  }

  updateAllSelection(v = false) {
    this.metricTable.forEach(item => item.monitor_type === 'metric' && (item.selection = v));
    this.updateCheckValue();
  }
  handleCheckChange({ value }) {
    this.updateAllSelection(value === 2);
    this.updateCheckValue();
  }

  updateCheckValue() {
    const metricLiist = this.metricTable.filter(item => item.monitor_type === 'metric');
    const checkedLeng = metricLiist.filter(item => item.selection).length;
    const allLeng = metricLiist.length;
    this.allCheckValue = 0;
    if (checkedLeng > 0) {
      this.allCheckValue = checkedLeng < allLeng ? 1 : 2;
    } else {
      this.allCheckValue = 0;
    }
  }

  //  获取详情
  async getDetailData() {
    this.loading = true;
    this.$store.commit('app/SET_NAV_TITLE', this.$t('加载中...'));
    const promiseItem: Promise<any>[] = [this.$store.dispatch('custom-escalation/getProxyInfo')];
    let title = '';
    let metricData: ICustomTSFields;
    promiseItem.push(
      this.$store.dispatch('custom-escalation/getCustomTimeSeriesDetail', {
        time_series_group_id: this.$route.params.id,
      })
    );
    promiseItem.push(
      this.$store.dispatch('custom-escalation/getCustomTSFields', {
        time_series_group_id: this.$route.params.id,
      })
    );
    promiseItem.push(this.$store.dispatch('strategy-config/getUnitList'));
    try {
      const data = await Promise.all(promiseItem);

      [this.proxyInfo] = data; // 云区域展示数据
      [, this.detailData = this.detailData] = data;
      [, , metricData] = data;
      if (this.type === 'customTimeSeries') {
        [, , , this.unitList] = data; // 单位list
        const allUnitList = [];
        const allUnitListMap = new Map();
        for (const groupItem of this.unitList) {
          for (const unitItem of groupItem?.formats || []) {
            if (unitItem.id) {
              allUnitList.push({
                id: unitItem.id,
                name: unitItem.name,
              });
              allUnitListMap.set(unitItem.id, unitItem.name);
            }
          }
        }
        this.allUnitList = allUnitList;
        title = `${this.$tc('route-' + '自定义指标').replace('route-', '')} - #${this.detailData.time_series_group_id
          } ${this.detailData.name}`;
        this.metricList = metricData?.metrics || [];
        this.dimensions = metricData?.dimensions || [];
        // this.metricList =
        //   this.detailData.metric_json?.[0]?.fields?.filter(item => item.monitor_type === 'metric') || [];

        // 获取表格内的单位数据
        const tempSet = new Set();
        const tableAllUnitList = [];
        for (const metricItem of this.metricList) {
          if (!tempSet.has(metricItem.unit)) {
            const unitName = allUnitListMap.get(metricItem.unit);
            if (unitName) {
              tableAllUnitList.push({
                id: metricItem.unit,
                name: unitName,
              });
            }
          }
          tempSet.add(metricItem.unit);
        }
        this.tableAllUnitList = [
          ...tableAllUnitList,
          {
            id: 'none',
            name: 'none',
          },
          {
            id: '--',
            name: '--',
          },
        ];

        await this.getGroupList();
        await this.getAllDataPreview(this.detailData.metric_json[0].fields, this.detailData.table_id);
      } else {
        title = `${this.$tc('route-' + '自定义事件').replace('route-', '')} - #${this.detailData.bk_event_group_id} ${this.detailData.name
          }`;
      }
      this.$store.commit('app/SET_NAV_TITLE', title);
      this.handleDetailData(this.detailData);
      this.loading = false;
    } catch (error) {
      console.error(error);
      this.loading = false;
    }
  }

  //  处理详情数据
  handleDetailData(detailData: IDetailData) {
    if (this.type === 'customTimeSeries') {
      this.tableId = detailData.table_id;
      this.metricData = this.metricList.map(item => ({
        ...item,
        selection: false,
        descReValue: false,
        // labels: [],
        monitor_type: 'metric',
      }));
      this.setMetricDataLabels();
      this.pagination.total = this.metricData.length;
      if (!this.metricData.length) {
        this.isShowData = false;
      }
    }
    this.scenario = `${detailData.scenario_display[0]} - ${detailData.scenario_display[1]}`;
    this.eventData = detailData.event_info_list;
    this.copyName = this.detailData.name;
    this.copyDataLabel = this.detailData.data_label || '';
    this.copyDescribe = this.detailData.desc || '';
    this.copyIsPlatform = this.detailData.is_platform ?? false;
    const str =
      this.type === 'customEvent'
        ? `# ${this.$t('事件标识名，最大长度128')}
                "event_name": "input_your_event_name",
                "event": {
                    # ${this.$t('事件内容，必需项')}
                    "content": "user xxx login failed"
                },`
        : `# ${this.$t('指标，必需项')}
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

  /* 获取所有数据预览数据 */
  async getAllDataPreview(fields: { monitor_type: 'dimension' | 'metric'; name: string }[], tableId) {
    const fieldList = fields.filter(item => item.monitor_type === 'metric').map(item => item.name);
    const data = await this.$store.dispatch('custom-escalation/getCustomTimeSeriesLatestDataByFields', {
      result_table_id: tableId,
      fields_list: fieldList,
    });
    this.allDataPreview = data?.fields_value || {};
    this.detailData.last_time =
      typeof data?.last_time === 'number'
        ? dayjs.tz(data.last_time * 1000).format('YYYY-MM-DD HH:mm:ss')
        : data?.last_time;
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
      this.$bkMessage({ theme: 'error', message: this.$tc('输入非中文符号') });
      return;
    }
    const ExistPass =
      this.type === 'customEvent'
        ? await validateCustomEventGroupLabel({
          data_label: this.copyDataLabel,
          bk_event_group_id: this.detailData.bk_event_group_id,
        }).catch(() => false)
        : await validateCustomTsGroupLabel({
          data_label: this.copyDataLabel,
          time_series_group_id: this.detailData.time_series_group_id,
        }).catch(() => false);
    if (!ExistPass) {
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
    const res =
      this.type === 'customEvent'
        ? await this.$store
          .dispatch('custom-escalation/validateCustomEventName', {
            params: { name: this.copyName, bk_event_group_id: this.detailData.bk_event_group_id },
          })
          .then(res => res.result ?? true)
          .catch(() => false)
        : await this.$store
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
    if (this.type === 'customEvent') {
      const params: IEditParams = {
        bk_event_group_id: this.detailData.bk_event_group_id,
        name: this.copyName,
        scenario: this.detailData.scenario,
        is_enable: true,
      };
      this.loading = true;
      await this.$store.dispatch('custom-escalation/editCustomEvent', params);
    } else {
      await this.handleEditFiled({
        name: this.copyName,
      });
    }
    this.detailData.name = this.copyName;
    this.isShowEditName = false;
    this.loading = false;
  }

  // /* 保存描述信息 */
  // async handleSaveDesc() {
  //   const params = {
  //     bk_biz_id: this.detailData.bk_biz_id,
  //     time_series_group_id: this.detailData.time_series_group_id,
  //     desc: this.copyDescribe,
  //   };
  //   return await modifyCustomTimeSeriesDesc(params).catch(({ message }) => {
  //     this.$bkMessage({ message, theme: 'error' });
  //   });
  // }
  // /* 保存描述信息 */
  // async handleSaveDesc() {
  //   const params = {
  //     bk_biz_id: this.detailData.bk_biz_id,
  //     time_series_group_id: this.detailData.time_series_group_id,
  //     desc: this.copyDescribe,
  //   };
  //   return await modifyCustomTimeSeriesDesc(params).catch(({ message }) => {
  //     this.$bkMessage({ message, theme: 'error' });
  //   });
  // }
  // 编辑描述
  async handleEditDescribe() {
    if (!this.copyDescribe.trim() || this.copyDescribe.trim() === this.detailData.desc) {
      this.copyDescribe = this.detailData.desc || '';
      this.isShowEditDesc = false;
      return;
    }
    this.isShowEditDesc = false;
    this.handleEditFiled({
      desc: this.copyDescribe,
    });
    // const data = await this.handleSaveDesc();
    // if (data) {
    //   this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
    //   return;
    // }
    this.detailData.desc = this.copyDescribe;
  }

  //  复制数据上报样例
  handleCopyData() {
    const str =
      this.type === 'customEvent'
        ? `"event_name": "input_your_event_name",
        "event": {
            "content": "user xxx login failed"
        },`
        : `"metrics": {
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
          name: 'new-custom-escalation-view',
          // name: 'custom-escalation-view',
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
              {'scenario'}
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
              {this.copyIsPlatform === false ? this.$t('本业务') : this.$t('全平台')}
            </span>
          </div>{' '}
          <div class='detail-information-row'>
            <span class='row-label'>{this.$t('别名')}: </span>
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
              <bk-input
                ref='dataLabelInput'
                style='width: 240px'
                v-model={this.copyDataLabel}
                onBlur={this.handleEditDataLabel}
              />
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
                style='width: 240px'
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
                style='width: 440px'
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
    const oldGroups = metricInfo ? metricInfo.groups : [];

    const oldSet = new Set(oldGroups);
    const newSet = new Set(newGroups);

    // 计算新增和删除的分组
    const added = [...newGroups].filter(group => !oldSet.has(group));
    const removed = [...oldGroups].filter(group => !newSet.has(group));

    return { added, removed };
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
    this.isUpdateGroup = true;
    this.metricTable[index].labels = labels;
    this.updateGroupList();
  }

  /* 更新分组管理 */
  updateGroupList() {
    this.groupList = this.groupList.map(item => ({
      ...item,
      manualList: this.groupsMap.get(item.name)?.manualList || [],
    }));
  }

  /** 批量更新 */
  async handleSaveSliderInfo(localTable) {
    this.isShow = false;
    await this.$store.dispatch('custom-escalation/modifyCustomTsFields', {
      time_series_group_id: this.$route.params.id,
      update_fields: localTable,
    });
    this.getDetailData();
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
            {
              this.type === 'customTimeSeries' ? (
                <TimeseriesDetailNew
                  class='detail-information detail-list'
                  customGroups={this.groupList}
                  dimensionNum={this.dimensionNum}
                  dimensionTable={this.dimensions}
                  groupSelectList={this.groupSelectList}
                  groupsMap={this.groupsMap}
                  metricGroupsMap={this.metricGroupsMap}
                  metricNum={this.metricNum}
                  metricTable={this.metricTable}
                  nameList={this.groupNameList}
                  nonGroupNum={this.nonGroupNum}
                  selectedLabel={this.groupFilterList[0] || ALL_LABEL}
                  unitList={this.unitList}
                  onChangeGroup={this.changeGroupFilterList}
                  onGroupDelByName={this.handleDelGroup}
                  onGroupListOrder={tab => (this.groupList = tab)}
                  onGroupSubmit={this.handleSubmitGroup}
                  onHandleClickSlider={v => {
                    this.isShow = v;
                  }}
                  onHandleSelectGroup={this.handleSelectGroup}
                  onHandleSelectToggle={this.saveSelectGroup}
                  onUpdateAllSelection={this.updateAllSelection}
                />
              ) : undefined /* TODO[自定义事件]  */
            }
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
            cycleOption={this.cycleOption}
            isShow={this.isShow}
            metricTable={this.metricTable}
            unitList={this.unitList}
            onHidden={v => (this.isShow = v)}
            onSaveInfo={this.handleSaveSliderInfo}
          />
        }
      </div>
    );
  }
}
