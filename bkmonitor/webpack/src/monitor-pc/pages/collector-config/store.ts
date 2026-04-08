/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { formatWithTimezone } from 'monitor-common/utils/timezone';

export default class TableStore {
  public data: any[];
  public keyword: string;
  public page: number;
  public pageList: number[];
  public pageSize: number;
  public sortOrder: any;
  public sortProp: any;
  public startStatusList: string[];
  public stopStatusList: string[];
  public tabData: any;
  public total: number;
  public typeList: any;

  public constructor(originData, bizList) {
    this.setDefaultStore();
    const configList = originData.config_list || [];
    this.typeList = originData.type_list || [];
    const len = configList.length;
    this.total = configList.length;
    this.tabData = this.defaultTabData;
    this.data = [];
    const tabAllItem = this.tabData.All;
    this.startStatusList = ['STARTED', 'STOPPING', 'DEPLOYING', 'AUTO_DEPLOYING'];
    this.stopStatusList = ['STOPPED', 'STARTING'];
    let i = 0;
    while (i < len) {
      const item = configList[i];
      const { status } = item;
      const taskStatus = item.task_status;
      const needUpdate = item.need_upgrade;
      const runningTasks = item.running_tasks;
      const tabItem = this.tabData[item.collect_type];
      tabAllItem.total += 1;
      tabItem.total += 1;
      if (this.startStatusList.includes(status)) {
        tabItem.data.startedNum += 1;
        tabAllItem.data.startedNum += 1;
      } else if (this.stopStatusList.includes(status)) {
        tabItem.data.stoppedNum += 1;
        tabAllItem.data.stoppedNum += 1;
      }
      if (needUpdate) {
        tabItem.data.needUpdateNum += item.total_instance_count || 0;
        tabAllItem.data.needUpdateNum += item.total_instance_count || 0;
      }
      tabItem.data.errTargetNum += item.error_instance_count || 0;
      tabAllItem.data.errTargetNum += item.error_instance_count || 0;
      const biz = bizList.find(b => b.id === item.bk_biz_id) || {};
      const doingStatus =
        ['STARTING', 'STOPPING', 'DEPLOYING', 'AUTO_DEPLOYING', 'PREPARING'].includes(status) || taskStatus === 'TBC';
      const statusList = Object.keys(this.statusMap);
      // let targetString = ''
      const objectType = item.target_object_type;
      const nodeType = item.target_node_type;
      this.data.push({
        id: item.id,
        name: item.name,
        copyName: item.name,
        bizId: item.bk_biz_id,
        space_name: item.space_name,
        bizName: biz.text || '',
        collectName: this.typeMap[item.collect_type].name,
        collectType: item.collect_type,
        targetNodesCount: item.target_nodes_count,
        totalInstanceCount: item.total_instance_count,
        status,
        taskStatus,
        runningTasks,
        statusIndex: statusList.indexOf(status),
        statusName: this.statusMap[taskStatus],
        objectType: this.objectTypeMap[objectType],
        objectTypeEn: objectType,
        nodeType,
        errorNum: item.error_instance_count,
        doingStatus,
        autoStatus: status === 'AUTO_DEPLOYING',
        needUpdate: item.need_upgrade,
        overflow: false,
        targetString: '',
        objectLabel: item.label_info,
        pluginId: item.plugin_id,
        serviceLabel: item.label,
        updateUser: item.update_user,
        updateTime: formatWithTimezone(item.update_time),
        updateParams: {
          id: item.id,
          pluginId: item.plugin_id,
          configVersion: item.config_version,
          infoVersion: item.info_version,
        },
      });
      i += 1;
    }
    this.tabData = Object.values<any>(this.tabData).sort((a, b) => a.order - b.order);
  }

  public get defaultTabData(): any {
    const tabData = {
      All: {
        data: {
          startedNum: 0,
          stoppedNum: 0,
          errTargetNum: 0,
          needUpdateNum: 0,
        },
        total: 0,
        key: 'All',
        name: window.i18n.t('全部'),
      },
    };
    this.typeList.forEach(item => {
      if (item.id !== 'log' && item.id !== 'Built-In') {
        tabData[item.id] = {
          data: {
            startedNum: 0,
            stoppedNum: 0,
            errTargetNum: 0,
            needUpdateNum: 0,
          },
          total: 0,
          key: item.id,
          name: item.name,
        };
      }
    });
    return tabData;
  }

  public get objectTypeMap() {
    return {
      HOST: window.i18n.t('主机'),
      SERVICE: window.i18n.t('服务'),
    };
  }

  public get statusMap() {
    return {
      TBC: window.i18n.t('待确认'),
      FAILED: window.i18n.t('失败'),
      WARNING: window.i18n.t('异常'),
      SUCCESS: window.i18n.t('正常'),
      STOPPED: window.i18n.t('已停用'),
      STARTING: window.i18n.t('启用中'),
      STOPPING: window.i18n.t('停用中'),
      DEPLOYING: window.i18n.t('部署中'),
      AUTO_DEPLOYING: window.i18n.t('自动部署中'),
      PREPARING: window.i18n.t('准备中'),
    };
  }

  public get tabItemMap() {
    return {
      startedNum: window.i18n.t('已启用配置'),
      stoppedNum: window.i18n.t('已停用配置'),
      errTargetNum: window.i18n.t('异常采集目标'),
      needUpdateNum: window.i18n.t('待升级目标'),
    };
  }

  public get typeMap() {
    const data = {
      All: { name: window.i18n.t('全部'), order: 1 },
    };
    this.typeList.forEach((item, index) => {
      data[item.id] = {
        name: item.name,
        order: index + 2,
      };
    });
    return data;
  }

  public deleteDataById(id) {
    const index = this.data.findIndex(item => item.id === id);
    if (index > -1) {
      const itemList = this.data.splice(index, 1);
      const [item] = itemList;
      this.tabData.forEach(set => {
        if (set.key === 'All' || set.key === item.collectType) {
          set.data.stoppedNum -= 1;
        }
      });
    }
  }

  /**
   * @description: 获取当前被格式化后的数据格式
   * @param {*}
   * @return {*}
   */
  public getTableAllData() {
    const ret = Array.from(this.data || []);
    if (this.sortProp && this.sortOrder) {
      if (this.sortOrder === 'ascending') {
        ret.sort((a, b) => +a[this.sortProp] - +b[this.sortProp]);
      } else {
        ret.sort((a, b) => +b[this.sortProp] - +a[this.sortProp]);
      }
    }
    return ret;
  }

  public getTableData(type = 'All', typeLabel = '') {
    let ret = Array.from(this.data || []);
    if (!(type === 'All' && !typeLabel.length)) {
      ret = ret.filter(
        item =>
          (item.collectType === type || type === 'All') &&
          (!typeLabel.length ||
            (typeLabel.length &&
              ((typeLabel === 'startedNum' && this.startStatusList.includes(item.status)) ||
                (typeLabel === 'stoppedNum' && this.stopStatusList.includes(item.status)) ||
                (typeLabel === 'errTargetNum' && item.errorNum > 0) ||
                (typeLabel === 'needUpdateNum' && item.needUpdate))))
      );
    }

    if (this.keyword.length) {
      let { keyword } = this;
      if (keyword.includes(window.i18n.tc('插件ID:'))) {
        const [, newKeyWord] = keyword.trim().split(window.i18n.tc('插件ID:'));
        ret = ret.filter(item => item.pluginId.includes(newKeyWord));
      } else if (keyword.includes('ID:')) {
        const [, newKeyWord] = keyword.trim().split('ID:');
        ret = ret.filter(item => item.id === Number(newKeyWord));
      } else {
        keyword = keyword.toLocaleLowerCase();
        ret = ret.filter(item => item.name.toLocaleLowerCase().includes(keyword) || `${item.id}`.indexOf(keyword) > -1);
      }
    }
    this.total = ret.length;
    if (this.sortProp && this.sortOrder) {
      if (this.sortOrder === 'ascending') {
        ret.sort((a, b) => +a[this.sortProp] - +b[this.sortProp]);
      } else {
        ret.sort((a, b) => +b[this.sortProp] - +a[this.sortProp]);
      }
    }
    return ret.slice(this.pageSize * (this.page - 1), this.pageSize * this.page);
  }

  public setDefaultStore() {
    this.sortProp = null;
    this.sortOrder = null;
    this.keyword = '';
    this.page = 1;
    this.pageSize = +localStorage.getItem('__common_page_size__') || 10;
    this.pageList = [10, 20, 50, 100];
  }
}
