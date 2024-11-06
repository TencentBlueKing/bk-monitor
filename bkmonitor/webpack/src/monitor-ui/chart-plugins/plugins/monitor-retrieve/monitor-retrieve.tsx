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
import Vue from 'vue';
import { Component, InjectReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import {
  MonitorRetrieve as Log,
  initMonitorState,
  initGlobalComponents,
  logStore,
  i18n,
} from '@blueking/monitor-retrieve/main';
import { serviceRelationList } from 'monitor-api/modules/apm_log';

import type { IViewOptions } from '../../typings';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import '@blueking/monitor-retrieve/css/mainb34e140.css';
import './monitor-retrieve.scss';
@Component
export default class MonitorRetrieve extends tsc<void> {
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @InjectReactive('timezone') readonly timezone: string;
  // 是否立即刷新
  @InjectReactive('refleshImmediate') readonly refleshImmediate: string;
  // 视图变量
  @InjectReactive('viewOptions') viewOptions: IViewOptions;

  init = false;
  async created() {
    const spaceUid =
      window.space_list.find(item => +item.bk_biz_id === +window.bk_biz_id)?.space_uid || window.bk_biz_id;
    window.space_uid = `${spaceUid}`;
    initMonitorState({
      bkBizId: window.bk_biz_id,
      spaceUid,
    });
    initGlobalComponents();
    window.mainComponent = new Vue({
      store: logStore,
      router: this.$router,
      i18n,
      render: h =>
        h(Log, {
          props: {
            indexSetApi: this.indexSetApi,
            timeRange: this.timeRange,
            timezone: this.timezone,
            refleshImmediate: this.refleshImmediate,
          },
        }),
    });
    await this.$nextTick();
    window.mainComponent.$mount(this.$el.querySelector('#main'));
  }
  beforeDestroy() {
    window.mainComponent.$destroy();
    window.mainComponent = null;
  }

  async indexSetApi() {
    const { app_name, service_name } = this.viewOptions;
    const data = await serviceRelationList({
      app_name,
      service_name,
    }).catch(() => []);
    return data;
  }

  render() {
    return (
      <div class='monitor-retrieve'>
        <div id='main' />
      </div>
    );
  }
}
