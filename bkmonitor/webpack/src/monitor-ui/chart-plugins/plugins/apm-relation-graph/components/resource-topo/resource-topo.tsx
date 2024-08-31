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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { MonitorTopo, createApp, h as vue3CreateElement } from '@blueking/monitor-resource-topo/vue2';
import { nodeRelation } from 'monitor-api/modules/apm_topo';
import { Debounce } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { CommonSimpleChart } from '../../../common-simple-chart';
import ResourceTopoSkeleton from './resource-topo-skeleton';

import './resource-topo.scss';
import '@blueking/monitor-resource-topo/vue2/vue2.css';
@Component
export default class ResourceTopo extends CommonSimpleChart {
  @Prop() a: number;
  app = null;
  unWatchStack = [];
  refreshIntervalInstance = null;
  init = false;
  loading = false;
  created() {
    // const props = this.$props;
    // const emit = this.$emit.bind(this);
    let resourceTopoInstance;
    this.app = createApp({
      render() {
        // eslint-disable-next-line @typescript-eslint/no-this-alias
        resourceTopoInstance = this;
        return vue3CreateElement(MonitorTopo, {});
      },
    });
    this.unWatchStack = Object.keys(this.$props).map(k => {
      return this.$watch(k, v => {
        resourceTopoInstance[k] = v;
        resourceTopoInstance.$forceUpdate();
      });
    });
  }
  beforeDestroy() {
    for (const unWatch of this.unWatchStack) {
      unWatch?.();
    }
    this.app?.unmount();
  }
  @Debounce(100)
  async getPanelData() {
    const needFetch = await this.beforeGetPanelData();
    if (!needFetch) return;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const params = {
      start_time: startTime,
      end_time: endTime,
      service_name: this.viewOptions?.filters?.service_name || 'alone-only-report-callee',
      app_name: this.viewOptions?.filters?.app_name,
      path_type: 'default',
      path: 'default',
    };
    if (!params.app_name || !params.service_name) return;
    try {
      this.unregisterOberver();
      this.loading = true;
      const data = await nodeRelation(params);
      if (data) {
        this.$nextTick(() => {
          this.app?.mount(this.$el.querySelector('.apm-resource-topo__chart'));
        });
      }
      console.info(data, '=============++++++++++---');
    } catch {
    } finally {
      this.loading = false;
    }
  }
  render() {
    return (
      <div class='apm-resource-topo'>
        {this.loading ? <ResourceTopoSkeleton /> : <div class='apm-resource-topo__chart' />}
      </div>
    );
  }
}
