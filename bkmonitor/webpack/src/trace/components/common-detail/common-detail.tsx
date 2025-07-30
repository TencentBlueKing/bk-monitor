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
import { type PropType, type Ref, defineComponent, getCurrentInstance, inject, reactive, ref, watch } from 'vue';

import { CancelToken } from 'monitor-api/cancel';
import { isShadowEqual } from 'monitor-ui/chart-plugins/utils';
import { useI18n } from 'vue-i18n';

import { VariablesService } from '../../utils';
import EmptyStatus from '../empty-status/empty-status';
import MonitorDrag from '../monitor-drag/monitor-drag';
import HostDetailView from './host-detail-view';

import type { IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';

import './common-detail.scss';

const DEFAULT_WIDTH = 280;

export default defineComponent({
  name: 'CommonDetail',
  props: {
    title: { type: String, default: '' },
    panel: { required: true, type: Object as PropType<PanelModel> },
    startPlacement: { type: String as PropType<'bottom' | 'left' | 'right' | 'top'>, default: 'right' },
    maxWidth: { type: Number, default: 360 },
    minWidth: { type: Number, default: 180 },
    defaultWidth: { type: Number, default: DEFAULT_WIDTH },
    defaultShow: { type: Boolean, default: false },
    lineText: { type: String, default: '' },
  },
  setup(props) {
    const { t } = useI18n();
    const isShow = ref(false);
    const width = ref(props.defaultWidth);
    const data = ref([]);
    const loading = ref(false);
    const viewOptions = inject<Ref<IViewOptions>>('viewOptions', ref({ filters: {}, variables: {} }));
    const currentInstance = getCurrentInstance();
    let cancelToken = null;
    let oldParams = null;

    watch(
      () => props.defaultShow,
      val => {
        isShow.value = val;
      },
      {
        immediate: true,
      }
    );

    watch(
      () => viewOptions.value,
      () => {
        getPanelData();
      },
      {
        immediate: true,
      }
    );

    const activeCollapseName = reactive([]);

    async function getPanelData() {
      if (props.panel?.targets?.[0]) {
        loading.value = true;
        const [item] = props.panel.targets;
        const variablesService = new VariablesService({
          ...viewOptions.value,
          ...viewOptions.value.filters,
          ...viewOptions.value.variables,
        });
        if (cancelToken) {
          cancelToken?.();
          cancelToken = null;
        }
        const params: any = variablesService.transformVariables(item.data);
        if (
          Object.values(params || {}).some(v => typeof v === 'undefined') ||
          (oldParams && isShadowEqual(params, oldParams))
        ) {
          loading.value = false;
          return;
        }
        oldParams = { ...params };
        const res = await currentInstance?.appContext.config.globalProperties?.$api[item.apiModule]
          [item.apiFunc](params, {
            cancelToken: new CancelToken(cb => (cancelToken = cb)),
          })
          .catch(() => []);
        data.value =
          res.map?.(item => {
            if (item.type === 'list') {
              item.isExpand = false;
              item.isOverflow = false;
            }
            return item;
          }) || [];
        loading.value = false;
      }
    }

    function handleDragChange(widthVal: number) {
      if (widthVal < props.minWidth) {
        handleClickShrink(false);
      } else {
        width.value = widthVal;
      }
    }

    function handleClickShrink(val?: boolean) {
      isShow.value = val ?? !isShow.value;
      if (!isShow.value) width.value = props.defaultWidth;
    }

    return {
      t,
      isShow,
      loading,
      width,
      data,
      activeCollapseName,
      handleDragChange,
      handleClickShrink,
    };
  },
  render() {
    return (
      <div class='trace-common-detail'>
        <div
          style={{ width: this.isShow ? `${this.width}px` : 0 }}
          class='common-detail-container'
        >
          <div class='container-padding'>
            <div class='common-detail-header'>
              <div class='header-title'>{this.title || this.t('详情')}</div>
            </div>
            {this.loading ? (
              <div class='skeleton-container'>
                <div class='skeleton-element status' />
                {new Array(6).fill(null).map((item, index) => (
                  <div
                    key={index}
                    class='skeleton-element'
                  />
                ))}
              </div>
            ) : this.data.length ? (
              <HostDetailView data={this.data} />
            ) : (
              <EmptyStatus
                scene='part'
                type='empty'
              />
            )}
          </div>
        </div>

        <MonitorDrag
          isShow={this.isShow}
          lineText={this.lineText || this.t('详情')}
          maxWidth={this.maxWidth}
          minWidth={this.minWidth}
          startPlacement='left'
          theme='line'
          onMove={this.handleDragChange}
          onTrigger={() => this.handleClickShrink()}
        />
      </div>
    );
  },
});
