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
import { defineComponent, inject } from 'vue';

import HostObservePanel from './host-observe-panel';

import type { TimeRangeType } from '../../../../components/time-range/utils';

export const BRIDGE_PROPS_KEY = Symbol('hostObservePanelBridgeProps');
export const BRIDGE_EMIT_KEY = Symbol('hostObservePanelBridgeEmit');

const textProp = (value: unknown) => (value == null ? '' : String(value));

const rangeProp = (value: unknown): TimeRangeType => (Array.isArray(value) ? value : []);

/** Vue2 宿主桥：把 mount 传入的 props 交给单台主机面板，关闭时回传 sliderClose。 */
export default defineComponent({
  name: 'HostObservePanelApm',
  setup() {
    const bridgeProps = inject<Record<string, unknown>>(BRIDGE_PROPS_KEY, {});
    const bridgeEmit = inject<(event: string, ...args: unknown[]) => void>(BRIDGE_EMIT_KEY, () => undefined);
    const handleClose = () => {
      bridgeEmit('sliderClose');
    };
    return { bridgeProps, handleClose };
  },
  render() {
    const props = this.bridgeProps;
    const interval = Number(props.refreshInterval);
    return (
      <HostObservePanel
        activeTab={textProp(props.activeTab)}
        bkBizId={textProp(props.bkBizId)}
        bkCloudId={textProp(props.bkCloudId)}
        bkHostId={textProp(props.bkHostId)}
        hostProcessName={textProp(props.hostProcessName)}
        ip={textProp(props.ip)}
        isShow={!!props.isShow}
        mode='drawer'
        refreshInterval={Number.isFinite(interval) ? interval : -1}
        timeRange={rangeProp(props.timeRange)}
        timezone={textProp(props.timezone)}
        onClose={this.handleClose}
      />
    );
  },
});
