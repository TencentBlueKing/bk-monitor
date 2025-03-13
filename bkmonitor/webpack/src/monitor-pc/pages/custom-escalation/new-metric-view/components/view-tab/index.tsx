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

import { Component, Prop, Ref, Model } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getSceneViewList, deleteSceneView, getSceneView, updateSceneView } from 'monitor-api/modules/scene_view';

import RemoveConfirm from './components/remove-confirm';
import ViewSave from './components/view-save';

import './index.scss';

interface IProps {
  graphConfigPayload: Record<string, any>;
}

interface IEmit {
  onPayloadChange: (params: Record<string, any>) => void;
}

@Component
export default class ViewTab extends tsc<IProps, IEmit> {
  @Prop({ type: Object, default: () => ({}) }) readonly graphConfigPayload: IProps['graphConfigPayload'];

  @Model('change', { type: String, required: true }) readonly value: string;

  @Ref('tabRef') readonly tabRef: any;

  viewTab = 'default';
  isListLoading = true;
  isViewDetailLoading = false;
  viewList: { id: string; name: string }[] = [];
  sortViewIdList: string[] = [];

  get sceneId() {
    return `custom_metric_v2_${this.$route.params.id}`;
  }

  get currentSelectViewInfo() {
    return this.viewList.find(item => item.id === this.viewTab) || { id: 'default', name: 'default' };
  }

  async fetchViewList() {
    this.isListLoading = true;
    try {
      const result = await getSceneViewList({
        scene_id: this.sceneId,
        type: 'detail',
      });
      this.viewList = Object.freeze(result);
      this.sortViewIdList = Object.freeze(result.map(item => item.id));
    } finally {
      this.isListLoading = false;
    }
  }

  async fetchViewData() {
    this.isViewDetailLoading = true;
    try {
      if (this.viewTab !== 'default') {
        const payload = await getSceneView({
          scene_id: this.sceneId,
          id: this.viewTab,
          type: 'detail',
        });
        this.$emit('payloadChange', payload.options);
      } else {
        this.$emit('payloadChange', {});
      }
    } finally {
      this.$emit('change', this.viewTab);
      this.isViewDetailLoading = false;
    }
  }

  handleTabChange(value: string) {
    this.viewTab = value;
    this.fetchViewData();
  }

  handleSortChange() {
    updateSceneView({
      scene_id: this.sceneId,
      ...this.viewList[0],
      view_order: this.tabRef.visiblePanels.map(item => item.name),
    });
  }

  async handleRemoveView(id: string) {
    await deleteSceneView({
      scene_id: this.sceneId,
      id,
      type: 'detail',
    });
    this.viewTab = 'default';
    this.fetchViewList();
  }

  handleViewSaveSuccess() {
    this.fetchViewList();
  }

  created() {
    this.fetchViewList();
  }

  render() {
    return (
      <div>
        <div
          class='bk-monitor-new-metric-view-view-tab'
          v-bkloading={{ isListLoading: this.isListLoading }}
        >
          <bk-tab
            ref='tabRef'
            active={this.viewTab}
            labelHeight={42}
            sortable={true}
            type='unborder-card'
            {...{ on: { 'update:active': this.handleTabChange, 'sort-change': this.handleSortChange } }}
          >
            <bk-tab-panel
              label={this.$t('默认')}
              name='default'
              sortable={false}
            />
            {this.viewList.map(item => (
              <bk-tab-panel
                key={item.id}
                name={item.id}
              >
                <template slot='label'>
                  <i class='icon-monitor icon-mc-tuozhuai drag-flag' />
                  <span>{item.name}</span>
                  <RemoveConfirm
                    data={item}
                    onSubmit={() => this.handleRemoveView(item.id)}
                  >
                    <span class='remove-btn'>
                      <i class='icon-monitor icon-mc-clear' />
                    </span>
                  </RemoveConfirm>
                </template>
              </bk-tab-panel>
            ))}
          </bk-tab>
          <ViewSave
            class='view-save'
            payload={this.graphConfigPayload}
            sceneId={this.sceneId}
            viewId={this.viewTab}
            viewList={this.viewList}
            onSuccess={this.handleViewSaveSuccess}
          />
        </div>
        <div v-bkloading={{ isLoading: this.isViewDetailLoading }}>{this.$slots.default}</div>
      </div>
    );
  }
}
