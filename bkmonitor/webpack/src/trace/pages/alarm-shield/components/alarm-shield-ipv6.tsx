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
import { type PropType, defineAsyncComponent, defineComponent, nextTick, ref, watch } from 'vue';

import { Ipv6FieldMap } from '../typing';

import type { IIpV6Value } from '../../../components/monitor-ip-selector/typing';

import './alarm-shield-ipv6.scss';
const MonitorIpSelector = defineAsyncComponent(
  () => import('../../../components/monitor-ip-selector/monitor-ip-selector')
);
export default defineComponent({
  name: 'AlarmShieldIpv6',
  props: {
    showDialog: { type: Boolean, default: false },
    showViewDiff: { type: Boolean, default: false },
    shieldDimension: { type: String, default: '' },
    checkedValue: { type: Object as PropType<IIpV6Value>, default: () => ({}) },
    originCheckedValue: { type: Object as PropType<IIpV6Value>, default: () => ({}) },
    onChange: { type: Function as PropType<(v: { value: IIpV6Value }) => void>, default: () => {} },
    onCloseDialog: { type: Function as PropType<(v: boolean) => void>, default: () => {} },
  },
  setup(props) {
    const panelList = ref<string[]>([]);
    const ipCheckValue = ref<IIpV6Value>({});
    const inited = ref(false);
    watch(
      () => props.shieldDimension,
      (v: string) => {
        panelList.value = [];
        inited.value = false;
        nextTick(() => {
          ipCheckValue.value = Ipv6FieldMap[props.shieldDimension]
            ? {
                [Ipv6FieldMap[props.shieldDimension]]: props.checkedValue?.[Ipv6FieldMap[props.shieldDimension]] || [],
              }
            : undefined;
          panelList.value = getPanelListByDimension(v);
          // magic code  bk-dialog animate time
          setTimeout(() => (inited.value = true), 400);
        });
      },
      { immediate: true }
    );
    watch(
      () => props.checkedValue,
      () => {
        ipCheckValue.value = !Ipv6FieldMap[props.shieldDimension]
          ? undefined
          : {
              [Ipv6FieldMap[props.shieldDimension]]: props.checkedValue?.[Ipv6FieldMap[props.shieldDimension]] || [],
            };
      },
      { immediate: true }
    );
    function getPanelListByDimension(v: string) {
      if (v === 'instance') return ['serviceInstance'];
      if (v === 'ip') return ['staticTopo', 'manualInput'];
      if (v === 'node') return ['dynamicTopo'];
      if (v === 'dynamic_group') return ['dynamicGroup'];
      return [];
    }
    function clearMask() {
      const clear = (els: Element[] | NodeListOf<Element>) => {
        els.forEach((el: Element) => {
          el.parentNode.removeChild(el);
        });
      };
      clear(document.querySelectorAll('[data-bk-mask-uid]'));
      clear(document.querySelectorAll('[data-bk-backup-uid]'));
    }
    function handleIpChange(v: IIpV6Value) {
      props.onChange({ value: v });
      clearMask();
    }
    function closeDialog(v: boolean) {
      props.onCloseDialog(v);
    }
    return () => (
      <div class='alarm-shield-ipv6-component'>
        {!!panelList.value.length && (
          <MonitorIpSelector
            class='alarm-shield-bk-ip-selector-box'
            mode={'dialog'}
            originalValue={props.originCheckedValue}
            panelList={panelList.value}
            showDialog={inited.value && props.showDialog}
            showView={true}
            showViewDiff={props.showViewDiff}
            value={ipCheckValue.value}
            onChange={handleIpChange}
            onCloseDialog={closeDialog}
          />
        )}
      </div>
    );
  },
});
