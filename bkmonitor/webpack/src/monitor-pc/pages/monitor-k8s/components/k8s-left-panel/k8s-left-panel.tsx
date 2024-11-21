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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import GroupItem from './group-item';

import './k8s-left-panel.scss';

@Component
export default class K8sLeftPanel extends tsc<object> {
  groupList = [
    {
      title: 'namespace',
      id: 'namespace',
      count: 4,
      children: [
        {
          id: '监控测试集群(BCS-K8S-26286)',
          title: '监控测试集群(BCS-K8S-26286)',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)__222',
          title: '监控测试集群(BCS-K8S-26286)__222',
        },
      ],
    },
    {
      title: 'workload',
      id: 'workload',
      count: 4,
      children: [
        {
          title: 'Deployments',
          id: 'Deployments',
          count: 1,
          children: [
            {
              id: 'monitor-test1',
              title: 'monitor-test1',
            },
          ],
        },
        {
          title: 'StatefulSets',
          count: 1,
          id: 'StatefulSets',
          children: [
            {
              id: 'monitor-test2',
              title: 'monitor-test2',
            },
          ],
        },
      ],
    },
  ];

  filterGroupList = JSON.parse(JSON.stringify(this.groupList));

  metricList = [
    {
      title: 'CPU',
      id: 'CPU',
      count: 3,
      children: [
        {
          id: 'CPU使用量',
          title: 'CPU使用量',
        },
        {
          id: 'CPU limit 使用率',
          title: 'CPU limit 使用率',
        },
        {
          id: 'CPU request 使用率',
          title: 'CPU request 使用率',
        },
      ],
    },
    {
      title: '内存',
      id: '内存',
      count: 4,
      children: [
        {
          id: '内存使用量(rss)',
          title: '内存使用量(rss)',
        },
      ],
    },
  ];

  searchValue = '';

  /** 已选择的检索 */
  selectData = {
    namespace: ['监控测试集群(BCS-K8S-26286)'],
    workload: [],
  };

  groupByList = ['namespace'];

  hiddenMetricList = [];

  handleSearch(val: string) {
    this.searchValue = val;
    const groupList = JSON.parse(JSON.stringify(this.groupList));
    if (!val) {
      this.filterGroupList = groupList;
      return;
    }
    this.filterGroupList = groupList.filter(item => {
      item.children = item.children.filter(child => {
        if (child.title.includes(this.searchValue)) {
          return true;
        }
        if (child.children) {
          child.children = child.children.filter(grandChild => grandChild.title.includes(this.searchValue));
          return child.children.length;
        }
      });
      return item.children.length;
    });
  }

  /** 检索 */
  handleGroupSearch(ids: string[], groupId: string) {
    this.selectData[groupId] = ids;
  }

  /** 下钻 */
  handleDrillDown({ id, drillDown }, groupId: string) {
    this.handleGroupByChange(true, drillDown);
    if (!this.selectData[groupId].includes(id)) {
      this.selectData[groupId].push(id);
    }
  }

  /** 修改groupBy */
  handleGroupByChange(val: boolean, groupId: string) {
    if (val) {
      this.groupByList.push(groupId);
    } else {
      this.groupByList = this.groupByList.filter(item => item !== groupId);
    }
  }

  /** 加载更多 */
  handleMoreClick(id: string) {
    console.log(id);
  }

  handleMetricHiddenChange(ids: string[]) {
    this.hiddenMetricList = ids;
  }

  render() {
    return (
      <div class='k8s-left-panel'>
        <div class='k8s-object'>
          <div class='panel-title'>{this.$t('K8s对象')}</div>
          <bk-input
            class='left-panel-search'
            right-icon='bk-icon icon-search'
            show-clear-only-hover={true}
            value={this.searchValue}
            clearable
            onChange={this.handleSearch}
          />

          <div class='object-group'>
            {this.filterGroupList.map(group => (
              <GroupItem
                key={group.id}
                isGroupBy={this.groupByList.includes(group.id)}
                list={group}
                showMore={group.id === 'namespace'}
                value={this.selectData[group.id]}
                onHandleDrillDown={val => this.handleDrillDown(val, group.id)}
                onHandleGroupByChange={val => this.handleGroupByChange(val, group.id)}
                onHandleMoreClick={() => this.handleMoreClick(group.id)}
                onHandleSearch={val => this.handleGroupSearch(val, group.id)}
              />
            ))}
          </div>
        </div>
        <div class='k8s-metric'>
          <div class='panel-title'>{this.$t('指标')}</div>
          {this.metricList.map(group => (
            <GroupItem
              key={group.id}
              hiddenList={this.hiddenMetricList}
              list={group}
              tools={['view']}
              onHandleHiddenChange={this.handleMetricHiddenChange}
            />
          ))}
        </div>
      </div>
    );
  }
}
