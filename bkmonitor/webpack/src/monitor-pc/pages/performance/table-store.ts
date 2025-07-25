import { commonPageSizeGet } from 'monitor-common/utils';
/* eslint-disable @typescript-eslint/prefer-for-of */
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
/*
 * @Date: 2021-06-14 21:01:49
 * @LastEditTime: 2021-07-01 17:23:59
 * @Description:
 */
// @ts-nocheck
import { isFullIpv6, padIPv6 } from 'monitor-common/utils/ip-utils';
import { typeTools } from 'monitor-common/utils/utils.js';

import type { CheckType, IConditionValue, IFieldConfig, IOption, ITableOptions, ITableRow } from './performance-type';

const IP_LIST_MATCH = new RegExp(/((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)/, 'g');
const IPV6_LIST_MATCH = new RegExp(/([\da-fA-F]{4}:){7}[\da-fA-F]{4}/, 'g');
const commonTopoLevel = ['biz', 'module', 'set'];
export default class TableStore {
  allClusterTopo = [];
  allData!: Readonly<Array<ITableRow>>;
  bizIdMap: Map<number, any> = new Map();
  cacheClusterMap = new Map();
  // 缓存options数据的字段
  cacheFieldOptionsSet = {
    bk_host_name: new Set(),
    bk_os_name: new Set(),
    bk_cloud_name: new Set(),
    display_name: new Set(), // 进程选项缓存
  };
  cacheModuleMap = new Map();
  checkType: CheckType = 'current';
  // selections: ITableRow[] = []
  conditionsList: IOption[] = [
    {
      name: '>',
      id: '>',
    },
    {
      name: '>=',
      id: '>=',
    },
    {
      name: '<',
      id: '<',
    },
    {
      name: '<=',
      id: '<=',
    },
    {
      name: '=',
      id: '=',
    },
  ];
  cpuData = [];
  diskData = [];
  fieldData: Array<IFieldConfig> = [
    {
      name: window.i18n.t('主机'),
      id: 'host_display_name',
      checked: true,
      disable: true,
      filterDisable: true,
      type: 'textarea',
      value: '',
      fuzzySearch: true,
      show: false,
    },
    {
      name: window.i18n.t('主机ID'),
      id: 'bk_host_id',
      checked: false,
      disable: false,
      filterChecked: false,
      filterDisable: false,
      type: 'textarea',
      value: '',
      fuzzySearch: true,
      show: false,
    },
    {
      name: window.i18n.t('内网IPv6'),
      id: 'bk_host_innerip_v6',
      checked: false,
      disable: false,
      // filterChecked: false,
      filterDisable: false,
      type: 'textarea',
      value: '',
      fuzzySearch: true,
      show: false,
    },
    {
      name: window.i18n.t('外网IPv6'),
      id: 'bk_host_outerip_v6',
      checked: false,
      disable: false,
      // filterChecked: false,
      filterDisable: false,
      type: 'textarea',
      value: '',
      fuzzySearch: true,
      show: false,
    },
    {
      name: window.i18n.t('内网IP'),
      id: 'bk_host_innerip',
      checked: true,
      disable: false,
      filterChecked: true,
      filterDisable: true,
      type: 'textarea',
      value: '',
      fuzzySearch: true,
      show: false,
    },
    {
      name: window.i18n.t('外网IP'),
      id: 'bk_host_outerip',
      checked: false,
      disable: false,
      filterChecked: false,
      filterDisable: false,
      type: 'textarea',
      value: '',
      fuzzySearch: true,
      show: false,
    },
    {
      name: window.i18n.t('采集状态'),
      id: 'status',
      checked: true,
      disable: true,
      filterChecked: true,
      filterDisable: true,
      type: 'checkbox',
      options: [
        {
          name: window.i18n.t('未知'),
          id: -1,
        },
        {
          name: window.i18n.t('正常'),
          id: 0,
        },
        {
          name: window.i18n.t('无数据上报'),
          id: 3,
        },
        {
          name: window.i18n.t('无Agent'),
          id: 2,
        },
      ],
      value: [],
      show: false,
    },
    {
      name: window.i18n.t('主机名'),
      id: 'bk_host_name',
      checked: false,
      disable: false,
      filterChecked: false,
      filterDisable: false,
      options: [],
      type: 'select',
      value: '',
      fuzzySearch: true,
      allowEmpt: true, // 允许空筛选选项出现
      show: false,
    },
    {
      name: window.i18n.t('OS名称'),
      id: 'bk_os_name',
      checked: false,
      disable: false,
      filterChecked: false,
      filterDisable: false,
      options: [],
      type: 'select',
      value: '',
      fuzzySearch: true,
      allowEmpt: true,
      show: false,
    },
    {
      name: window.i18n.t('管控区域'),
      id: 'bk_cloud_name',
      checked: false,
      disable: false,
      filterChecked: false,
      filterDisable: false,
      options: [],
      type: 'select',
      value: '',
      show: false,
    },
    {
      name: window.i18n.t('业务拓扑'),
      id: 'cluster_module',
      filterChecked: true,
      filterDisable: false,
      options: [],
      type: 'cascade',
      value: [],
      multiple: true,
      show: false,
    },
    {
      name: window.i18n.t('集群名'),
      id: 'bk_cluster',
      filterChecked: true,
      filterDisable: false,
      checked: false,
      disable: false,
      options: [],
      type: 'select',
      value: '',
      fuzzySearch: true,
      multiple: true,
      show: false,
    },
    {
      name: window.i18n.t('模块名'),
      id: 'bk_inst_name',
      filterChecked: true,
      filterDisable: false,
      checked: false,
      disable: false,
      options: [],
      type: 'select',
      value: '',
      fuzzySearch: true,
      multiple: true,
      show: false,
    },
    {
      name: window.i18n.t('未恢复告警'),
      id: 'alarm_count',
      checked: true,
      disable: false,
      type: 'number',
      show: false,
    },
    {
      name: window.i18n.t('CPU五分钟负载'),
      id: 'cpu_load',
      checked: false,
      disable: false,
      filterChecked: false,
      filterDisable: false,
      conditions: this.conditionsList,
      type: 'condition',
      value: [],
      show: false,
      headerPreIcon: 'icon-last',
    },
    {
      name: window.i18n.t('CPU使用率'),
      id: 'cpu_usage',
      checked: false,
      disable: false,
      filterChecked: true,
      filterDisable: false,
      conditions: this.conditionsList,
      type: 'condition',
      value: [],
      show: false,
      headerPreIcon: 'icon-last',
    },
    {
      name: window.i18n.t('磁盘空间使用率'),
      id: 'disk_in_use',
      checked: false,
      disable: false,
      filterChecked: false,
      filterDisable: false,
      conditions: this.conditionsList,
      type: 'condition',
      value: [],
      show: false,
      headerPreIcon: 'icon-max',
    },
    {
      name: window.i18n.t('磁盘IO使用率'),
      id: 'io_util',
      checked: false,
      disable: false,
      filterChecked: false,
      filterDisable: false,
      conditions: this.conditionsList,
      type: 'condition',
      value: [],
      show: false,
      headerPreIcon: 'icon-max',
    },
    {
      name: window.i18n.t('应用内存使用率'),
      id: 'mem_usage',
      checked: true,
      disable: false,
      filterChecked: false,
      filterDisable: false,
      conditions: this.conditionsList,
      type: 'condition',
      value: [],
      show: false,
      headerPreIcon: 'icon-last',
    },
    {
      name: window.i18n.t('物理内存使用率'),
      id: 'psc_mem_usage',
      checked: false,
      disable: false,
      filterChecked: false,
      filterDisable: false,
      conditions: this.conditionsList,
      type: 'condition',
      value: [],
      show: false,
      headerPreIcon: 'icon-last',
    },
    {
      name: window.i18n.t('业务名'),
      id: 'bk_biz_name',
      checked: false,
      disable: false,
      filterChecked: false,
      filterDisable: false,
      type: 'text',
      value: '',
      fuzzySearch: true,
      show: false,
    },
    {
      name: window.i18n.t('进程'),
      id: 'display_name',
      checked: true,
      disable: true,
      filterChecked: false,
      filterDisable: false,
      options: [],
      type: 'select',
      value: '',
      fuzzySearch: true,
      allowEmpt: true,
      show: false,
    },
  ];
  // 缓存当前筛选数据
  filterData!: Readonly<Array<ITableRow>>;
  keyWord = '';
  loading = false;
  menmoryData = [];

  order = 'descending';
  page = 1;
  pageList: Array<number> = [10, 20, 50, 100];
  pageSize: number = commonPageSizeGet();
  panelKey = '';
  sortKey = 'totalAlarmCount';
  stickyValue = {};
  topoNameMap = {};
  total = 0;
  unresolveData = [];
  constructor(data: Array<any>, options: ITableOptions, bizIdMap: Map<number, any>) {
    this.bizIdMap = bizIdMap;
    this.updateData(data, options);
  }

  get columns() {
    const columns = {};
    for (const field of this.fieldData) {
      columns[field.id] = field;
    }
    return columns;
  }

  // 获取级联对象
  convertToTree(topo_link, topo_link_display) {
    if (topo_link.length === 0 || topo_link_display.length === 0) {
      return null;
    }
    const id = topo_link.shift();
    const name = topo_link_display.shift();
    const node = { id, name };
    const child = this.convertToTree(topo_link, topo_link_display);
    if (child) {
      node.children = [...(node.children || []), child];
    }
    return node;
  }

  createTopoTree() {
    const topoNameMap = {};
    const list = [];
    for (const cur of this.allData) {
      const modules = cur.module || [];
      const moduleList = modules.map(({ topo_link, topo_link_display }) => {
        const topo = topo_link.map((id, index) => {
          topoNameMap[id] = topo_link_display[index];
          return {
            id,
            name: topo_link_display[index],
          };
        });
        return topo;
      });
      list.push(...moduleList);
    }
    // const list = this.allData.reduce((pre, cur) => {
    //   const modules = cur.module || [];
    //   const list = modules.map(({ topo_link, topo_link_display }) => {
    //     const topo = topo_link.map((id, index) => {
    //       topoNameMap[id] = topo_link_display[index];
    //       return {
    //         id,
    //         name: topo_link_display[index],
    //       };
    //     });
    //     return topo;
    //   });
    //   return pre.concat(list);
    // }, []);

    const dynamicRowData = this.allData
      ?.find(item => item?.module?.some(set => set.topo_link.length > 3))
      ?.module?.find(item => item.topo_link.length > 3);
    // .filter(item => !/^(set|module|biz)\|/.test(item.id));
    if (dynamicRowData) {
      const dynamicCol = Object.keys(dynamicRowData.bk_obj_name_map).filter(key => !commonTopoLevel.includes(key));
      const clusterIndex = this.fieldData.findIndex(field => field.id === 'bk_cluster');
      const setFieldList = [];
      const reverseList = dynamicCol.reverse();
      for (const id of reverseList) {
        if (!this.fieldData.some(field => field.id === id)) {
          const options = [];
          for (const [key, name] of Object.entries(topoNameMap)) {
            if (key.includes(`${id}|`)) {
              options.push({
                id: key,
                name,
              });
            }
          }
          setFieldList.push({
            name: dynamicRowData.bk_obj_name_map[id] || id,
            id,
            checked: false,
            disable: false,
            filterChecked: false,
            filterDisable: false,
            type: 'select',
            value: [],
            options,
            multiple: true,
            fuzzySearch: true,
            show: true,
            dynamic: true,
          });
        }
      }
      setFieldList.length && this.fieldData.splice(clusterIndex - 1, 0, ...setFieldList);
    }
    const treeList = [];
    const nodeMap = {};
    const createNode = data => ({
      id: data.id,
      name: data.name,
      children: [],
    });
    for (let i = 0; i < list.length; i++) {
      const pathList = list[i];
      let parentNode = null;

      for (let j = 0; j < pathList.length; j++) {
        const nodeData = pathList[j];
        if (!nodeMap[nodeData.id]) {
          nodeMap[nodeData.id] = createNode(nodeData);
          if (parentNode) {
            parentNode.children.push(nodeMap[nodeData.id]);
          } else {
            treeList.push(nodeMap[nodeData.id]);
          }
        }
        parentNode = nodeMap[nodeData.id];
      }
    }
    this.topoNameMap = topoNameMap;
    const filterList = this.fieldData.filter(item => ['bk_cluster'].includes(item.id));
    for (const fieldData of filterList) {
      const options = [];
      for (const [id, name] of Object.entries(topoNameMap)) {
        if (id.match(/^set\|/)) {
          options.push({
            id,
            name,
          });
        }
      }
      fieldData.options = options;
    }
    const topofield = this.fieldData.find(item => ['cluster_module'].includes(item.id));
    topofield.options = treeList;
    return treeList;
  }
  // 关键字匹配
  filterDataByKeyword(data: ITableRow[]) {
    // const keyWord = this.keyWord.trim().toLocaleLowerCase()
    const keyWord = this.keyWord.trim();
    const fieldData = this.fieldData.filter(item => item.fuzzySearch);
    if (isFullIpv6(padIPv6(keyWord))) {
      const ipv6Keyword = padIPv6(keyWord);
      const ipv6s = ipv6Keyword.match(IPV6_LIST_MATCH);
      if (ipv6s?.length > 0) {
        return data.filter(
          item => item.bk_host_innerip_v6.includes(keyWord) || ipv6s.includes(item.bk_host_innerip_v6)
        );
      }
    }
    // 多IP精确/单IP模糊筛选
    const ips = keyWord.match(IP_LIST_MATCH);
    if (ips?.length > 0) {
      return data.filter(item => item.bk_host_innerip.includes(keyWord) || ips.includes(item.bk_host_innerip));
    }
    return data.filter(item => {
      for (let i = 0, len = fieldData.length; i < len; i++) {
        const field = fieldData[i];
        let val = '';
        if (field.id === 'bk_inst_name') {
          // 模块
          val = item.moduleInstNames;
        } else if (field.id === 'display_name') {
          // 进程名
          val = item.componentNames;
        } else if (field.id === 'bk_cluster') {
          // 集群名
          val = item.clusterNames;
        } else {
          val = item[field.id] || '';
        }
        if (typeof val === 'number') {
          val = `${val}`;
        }
        // 耗时操作
        // val = val.toLocaleLowerCase()
        if (val.includes(keyWord)) {
          return true;
        }
      }
      return false;
    });
  }
  getCompareValue(item: ITableRow, field: IFieldConfig) {
    let originValue = item[field.id] === undefined ? '' : item[field.id]; // 当 field.id 为 模块、进程、集群、模块\集群时，该值为undefined
    let curValue = field.value === '' ? '' : field.value; // 筛选条件的值
    if (['bk_host_innerip', 'bk_host_outerip'].includes(field.id)) {
      // IP类型的值
      curValue = (field.value as string).replace(/\n|,/g, '|').replace(/\s+/g, '').split('|');
    } else if (field.id === 'bk_inst_name') {
      // 模块名称
      originValue = item.module ? item.module.map(m => m.bk_inst_name) : [];
    } else if (field.id === 'display_name') {
      // 进程名
      originValue = item.component ? item.component.map(com => com[field.id]) : [];
    } else if (field.id === 'bk_cluster') {
      // 集群ID（集群字段是前端拼接的，在initRowData方法里面）
      originValue = item.bk_cluster.map(cluster => cluster.id);
    } else if (field.id === 'cluster_module') {
      // 集群\模块（级联输入）
      originValue = item.module ? item.module.map(m => m.topo_link, []) : [];
      // const clusterIds = item.bk_cluster.map(cluster => cluster.id);
      // originValue = moduleIds.concat(clusterIds);
    } else if (field.dynamic) {
      const data = [];
      for (const m of item.module || []) {
        const dataIndex = m.topo_link.findIndex(t => t.includes(`${field.id}|`));
        if (dataIndex > -1) {
          data.push(m.topo_link[dataIndex]);
        }
      }
      originValue = data;
    }
    return {
      originValue,
      curValue,
    };
  }
  getTableData() {
    let data = [...(this.panelKey ? this[this.panelKey] : this.allData)];
    const fieldData = this.fieldData.filter(field =>
      Array.isArray(field.value) ? !!field.value.length : field.value !== '' && field.value !== undefined
    );
    for (const field of fieldData) {
      data = data.filter(item => this.isMatchedCondition(item, field));
    }
    if (this.keyWord.trim() !== '') {
      data = this.filterDataByKeyword(data);
    }
    const sortData = this.sortDataByKey(data);
    this.total = sortData.length;
    // 缓存当前过滤后数据，用于分页、换页、指标对比、采集下发和复制IP操作
    this.filterData = Object.freeze(sortData);

    return JSON.parse(JSON.stringify(this.pagination(sortData)));
  }

  // 初始化行属性（扩展属性）
  initRowData(item) {
    // 集群名称
    item.bk_cluster = [];
    // 填充options数据
    // forEach性能低
    for (const key in this.cacheFieldOptionsSet) {
      if (item[key] || key === 'display_name') {
        item[key] && this.cacheFieldOptionsSet[key].add(item[key]);
        // 进程添加可选项
        if (key === 'display_name') {
          // item?.component?.forEach(com => this.cacheFieldOptionsSet[key].add(com?.['display_name'] || ''))
          for (const com of item?.component || []) {
            this.cacheFieldOptionsSet[key].add(com?.display_name || '');
          }
        }
      }
    }
    const module = item.module || [];

    for (let i = 0; i < module.length; i++) {
      const currentModule = module[i];
      const {
        id: moduleId,
        bk_inst_name: moduleName,
        topo_link: topoLink,
        topo_link_display: topoLinkDisplay,
      } = currentModule;

      if (moduleId && moduleName) {
        this.cacheModuleMap.set(moduleId, {
          id: moduleName,
          name: moduleName,
          moduleId,
        });
      }

      if (topoLink && topoLink.length > 1) {
        const clusterIndex = topoLink.findIndex((id: string) => id.match(/^set\|/));
        const clusterId = topoLink[clusterIndex] || '';
        const clusterName = topoLinkDisplay[clusterIndex] || currentModule?.bk_obj_name_map?.set || '';
        if (!item.bk_cluster.find(i => i.id === clusterId)) {
          item.bk_cluster.push({
            name: clusterName,
            id: clusterId,
          });
        }
      }
    }
    // 行Id
    item.rowId = item.bk_host_id ?? `${item.bk_host_innerip}|${item.bk_cloud_id}`;
    // 未恢复告警总数
    item.totalAlarmCount = item.alarm_count?.reduce((pre, cur) => pre + cur.count, 0);
    // 当前悬浮状态
    // item.hover = false
    item.mark = Object.hasOwn(this.stickyValue, item.rowId);
    // item.order = this.sticky[item.rowId] ? 99999 : i
    // todo 排序进程
    for (const com of item?.component || []) {
      switch (+com.status) {
        case -1:
          com.status = 2;
          break;
        case 0:
          com.status = 3;
          break;
        default:
          com.status = 1;
      }
    }
    item?.component?.sort((b, a) => b.status - a.status);
    // 进程数量过多时是否省略
    // item.overflow = false
    // 业务名
    const bizItem = this.bizIdMap.get(+item.bk_biz_id);
    item.bk_biz_name = bizItem ? bizItem.text : '--';
    // 模块名
    item.bk_inst_name = item.module?.length ? item.module.map(m => m.bk_inst_name).join(' , ') : '--';
    // checkedbox
    item.selection = false;
    // 新增模糊搜索字段属性
    item.moduleInstNames = item.module ? item.module.map(m => m.bk_inst_name).join() : '';
    item.componentNames = item.component ? item.component.map(com => com.display_name).join() : '';
    item.clusterNames = item.bk_cluster.map(cluster => cluster.name).join();
    // 分类数据
    if (item.alarm_count && item.alarm_count.findIndex(data => +data.count > 0) > -1) {
      this.unresolveData.push(item);
    }
    if (item.cpu_usage >= 80) {
      this.cpuData.push(item);
    }
    if (item.mem_usage >= 80) {
      this.menmoryData.push(item);
    }
    if (item.disk_in_use >= 80) {
      this.diskData.push(item);
    }
    item.host_display_name = item.display_name || '';
    return item;
  }

  // 条件匹配
  isMatchedCondition(item: ITableRow, field: IFieldConfig) {
    const { curValue, originValue } = this.getCompareValue(item, field);
    if (field.dynamic) {
      const value = Array.isArray(curValue[0]) ? curValue[0] : Array.isArray(curValue) ? curValue : [curValue];
      return value.some(val => {
        return originValue.includes(val);
      });
    }
    // 处理空值
    if (curValue === '__empt__' || curValue[0] === '__empt__') {
      // 允许筛选空值的选项(进程)
      if (['display_name'].includes(field.id)) {
        return !originValue.length;
      }
      // 允许筛选空值的选项(主机名，os名)
      if (['bk_host_name', 'bk_os_name'].includes(field.id)) {
        return !originValue;
      }
    }
    if (Array.isArray(curValue) && !Array.isArray(originValue)) {
      // 原始值是当前值的子集
      // 当前值类型为 array，原始值类型为 string | number (eg: ip类型、CPU使用率等类型)
      if (field.conditions && field.conditions.length > 0) {
        // 匹配使用率类型
        return (curValue as IConditionValue[]).every(data => {
          // 空条件不匹配
          if (typeTools.isNull(data.value) || typeTools.isNull(data.condition)) return true;
          switch (data.condition) {
            case '>':
              return originValue > data.value;
            case '>=':
              return originValue >= data.value;
            case '<':
              return originValue < data.value;
            case '<=':
              return originValue <= data.value;
            case '=':
              return `${originValue}` === `${data.value}`;
            default:
              return false;
          }
        });
      }
      // IP单个模糊/多个精确筛选
      if (['bk_host_innerip', 'bk_host_outerip'].includes(field.id)) {
        // if(Array.isArray(curValue))
        const valueStr = curValue.toString();
        const targetIp = item[field.id] || '';
        const targetIpV6 = item[`${field.id}_v6`] || '';
        if (curValue.filter(Boolean).some(str => isFullIpv6(padIPv6(str)))) {
          const ipv6s = padIPv6(valueStr).match(IPV6_LIST_MATCH);
          if (ipv6s.length > 0) {
            return ipv6s.includes(targetIpV6);
          }
        } else if (curValue.filter(Boolean).some(str => IP_LIST_MATCH.test(str))) {
          const ips = valueStr.match(IP_LIST_MATCH);
          const len = ips?.length;
          if (len > 1) {
            return ips.includes(targetIp) || ips.includes(targetIpV6);
          }
          if (len === 1) {
            return targetIp.includes(ips[0]) || targetIpV6.includes(ips[0]);
          }
        }
        return targetIp.includes(valueStr) || targetIpV6.includes(valueStr);
      }
      // 匹配子集关系（eg: IP）
      return curValue.includes(originValue);
    }
    if (!Array.isArray(curValue) && Array.isArray(originValue)) {
      // 当前值是原始值的子集
      // 当前值类型为 string, 原始值为 array（eg: 模块名、进程名、集群名）
      return originValue.includes(curValue);
    }
    if (Array.isArray(curValue) && Array.isArray(originValue)) {
      if (field.id === 'cluster_module') {
        const isMutiple = Array.isArray(curValue[0]);
        if (!isMutiple) {
          return originValue.some(val => {
            return curValue.every(v => val.includes(v));
          });
        }
        return curValue.some(val => {
          return originValue.some(a => {
            return val.every(v => a.includes(v));
          });
        });
      }
      return curValue.some(val => {
        if (Array.isArray(val)) {
          return val.every(v => originValue.includes(v));
        }
        return originValue.includes(val);
      });
    }

    return originValue === curValue;
  }
  pagination(data: ITableRow[]) {
    return data.slice(this.pageSize * (this.page - 1), this.pageSize * this.page);
  }
  // 重新分页数据
  reLimitData() {
    // return this.reOrderData()
    return JSON.parse(JSON.stringify(this.pagination([...this.filterData])));
  }

  // 重新排序缓存数据
  reOrderData() {
    this.filterData = Object.freeze(this.sortDataByKey([...this.filterData]));
    return JSON.parse(JSON.stringify(this.pagination([...this.filterData])));
  }

  setState(rowId: string, key: string, value: any) {
    const row = this.allData.find(item => item.rowId === rowId);
    if (Object.hasOwn(row, key)) {
      row[key] = value;
    }
  }

  sortDataByKey(data: ITableRow[]) {
    data.sort((pre, next) => {
      const isPreTop = Object.hasOwn(this.stickyValue, pre.rowId) ? 1 : 0;
      const isNextTop = Object.hasOwn(this.stickyValue, next.rowId) ? 1 : 0;
      if (isPreTop === isNextTop) {
        return this.order === 'ascending'
          ? +pre[this.sortKey] - +next[this.sortKey]
          : +next[this.sortKey] - +pre[this.sortKey];
      }
      return isNextTop - isPreTop;
    });
    return data;
  }

  updateData(data: Array<any>, options?: ITableOptions) {
    this.stickyValue = options?.stickyValue || {};
    this.panelKey = options?.panelKey || '';
    this.unresolveData = [];
    this.cpuData = [];
    this.menmoryData = [];
    this.diskData = [];
    this.allData = Object.freeze(data.map(item => Object.seal(this.initRowData(item))));
    this.allClusterTopo = Object.freeze(this.createTopoTree());
    this.updateFieldDataOptions();
  }

  updateFieldDataOptions() {
    for (const key in this.cacheFieldOptionsSet) {
      const cacheFieldSet = this.cacheFieldOptionsSet[key];
      const fieldData = this.fieldData.find(item => item.id === key);
      if (cacheFieldSet.size && fieldData) {
        fieldData.options = [];
        for (const val of cacheFieldSet.values()) {
          fieldData.options.push({
            id: val,
            name: val,
          });
        }
      }
      // 添加空项筛选
      if (fieldData?.allowEmpt) {
        fieldData.options.unshift({ id: '__empt__', name: window.i18n.t('- 空 -') });
      }
    }
    const moduleFieldData = this.fieldData.find(item => item.id === 'bk_inst_name');
    if (moduleFieldData) {
      moduleFieldData.options = Array.from(this.cacheModuleMap.values()).reduce((pre, cur) => {
        if (!pre.find(item => item.id === cur.id)) pre.push(cur);
        return pre;
      }, []);
    }
    // // forEach性能低
    // for (const key in this.cacheFieldOptionsData) {
    //   this.cacheFieldOptionsData[key].clear()
    // }
    // this.cacheModule.clear()
    // this.cacheCluster.clear()
  }
}
