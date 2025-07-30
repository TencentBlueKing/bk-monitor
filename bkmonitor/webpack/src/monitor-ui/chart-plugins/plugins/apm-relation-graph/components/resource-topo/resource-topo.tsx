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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import {
  type IResourceData,
  type IResourceEdge,
  type IResourceNode,
  type IResourceSidebar,
  createApp,
  MonitorTopo,
  h as vue3CreateElement,
} from '@blueking/monitor-resource-topo/vue2';
import { CancelToken } from 'monitor-api/cancel';
import { nodeRelation, nodeRelationDetail, topoLink } from 'monitor-api/modules/apm_topo';
import { Debounce, random } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { CommonSimpleChart } from '../../../common-simple-chart';
// import ResourceTopoSkeleton from './resource-topo-skeleton';

import './resource-topo.scss';
import '@blueking/monitor-resource-topo/vue2/vue2.css';
@Component
class ResourceTopo extends CommonSimpleChart {
  @Prop() serviceName: string;
  app = null;
  unWatchStack = [];
  refreshIntervalInstance = null;
  init = false;
  loading = false;
  topoEdges: IResourceEdge[] = [];
  topoNodes: IResourceNode[] = [];
  topoSidebars: IResourceSidebar[] = [];
  paths: string[] = [];
  refreshKey = random(10);
  cancelFn = null;

  @Watch('serviceName')
  handleServiceNameChange() {
    this.paths = [];
    this.topoEdges = [];
    this.topoNodes = [];
    this.topoSidebars = [];
    this.getPanelData();
  }
  beforeDestroy() {
    this.app?.unmount();
  }
  renderResourceTopoComponent() {
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    const that = this;
    this.app = createApp({
      render() {
        return vue3CreateElement(MonitorTopo, {
          key: that.refreshKey,
          topoEdges: that.topoEdges || [],
          topoNodes: that.topoNodes || [],
          topoSidebars: that.topoSidebars || [],
          getNodeDetails(params) {
            return that.getNodeDetail(params);
          },
          getNodeLink(params) {
            return that.getNodeLink(params);
          },
          showEventDetail(id: string) {
            that.showEventDetail(id);
          },
          t(key: string) {
            return that.$t(key);
          },
          onClickSidebarOption(paths: string[], rawSidebars) {
            that.handlePathTypeChange(paths, rawSidebars);
          },
        } as any);
      },
    });
  }
  @Debounce(100)
  async getPanelData() {
    const needFetch = await this.beforeGetPanelData();
    if (!needFetch) return;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const params = {
      start_time: startTime,
      end_time: endTime,
      service_name: this.serviceName || this.viewOptions?.filters?.service_name,
      app_name: this.viewOptions?.filters?.app_name,
      path_type: this.paths.length ? 'specific' : 'default',
      paths: this.paths.length ? this.paths.join(',') : 'default',
    };
    if (!params.app_name || !params.service_name) return;
    this.unregisterObserver();
    this.cancelFn?.();
    this.loading = true;
    const data: IResourceData = await nodeRelation(params, {
      cancelToken: new CancelToken(cb => {
        this.cancelFn = cb;
      }),
    })
      .then(data => {
        this.cancelFn = null;
        this.loading = false;
        return data;
      })
      .catch(e => {
        if (e.code) {
          this.cancelFn = null;
          this.loading = false;
        }
        return {
          edges: [],
          nodes: [],
          sidebars: [],
        };
      });
    if (data) {
      this.topoEdges = data.edges;
      this.topoNodes = data.nodes;
      if (!this.paths.length) {
        this.topoSidebars = data.sidebars;
      }
      this.renderResourceTopoComponent();
      this.$nextTick(() => {
        this.app?.mount(this.$el.querySelector('.apm-resource-topo__chart'));
      });
    }
  }
  async getNodeDetail(params) {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    // await new Promise(r => setTimeout(r, 10000000));
    return await nodeRelationDetail({
      app_name: this.viewOptions?.filters?.app_name,
      start_time: startTime,
      end_time: endTime,
      source_type: params.source_type,
      source_info: params.source_info,
    }).catch(() => ({}));
  }
  async getNodeLink(params) {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const url = await topoLink({
      app_name: this.viewOptions?.filters?.app_name,
      start_time: startTime,
      end_time: endTime,
      source_type: params.source_type,
      source_info: params.source_info,
      link_type: 'topo_source',
    }).catch(() => '');
    if (url) {
      if (url.startsWith('?bizId')) {
        window.open(url, '_blank');
        return;
      }
      window.open(location.href.replace(location.hash, `#${url}`), '_blank');
    }
  }
  showEventDetail(id) {
    window.__BK_WEWEB_DATA__?.showDetailSlider?.(id);
  }
  handlePathTypeChange(paths: string[], topoSidebars) {
    this.paths = paths;
    this.topoSidebars = topoSidebars;
    this.loading = true;
    this.getPanelData();
  }
  render() {
    if (!this.loading && !this.topoNodes?.length)
      return (
        <bk-exception
          style={{ marginTop: '60px' }}
          scene='part'
          type='empty'
        />
      );
    return (
      <div
        key={this.refreshKey}
        class='apm-resource-topo'
        v-bkloading={{ isLoading: this.loading }}
      >
        {this.loading ? <div /> : <div class='apm-resource-topo__chart' />}
        {/* {this.loading ? <ResourceTopoSkeleton /> : <div class='apm-resource-topo__chart' />} */}
      </div>
    );
  }
}
export default ofType<{
  serviceName: string;
}>().convert(ResourceTopo);
