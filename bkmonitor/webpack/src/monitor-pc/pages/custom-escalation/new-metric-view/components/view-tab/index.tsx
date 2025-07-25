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

import { Component, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';
import { deleteSceneView, getSceneView, getSceneViewList, updateSceneView } from 'monitor-api/modules/scene_view';

import { optimizedDeepEqual } from '../../metric-chart-view/utils';
import RemoveConfirm from './components/remove-confirm';
import ViewManage from './components/view-manage';
import ViewSave from './components/view-save';
import customEscalationViewStore from '@store/modules/custom-escalation-view';

import './index.scss';

interface IEmit {
  onPayloadChange: (params: Record<string, any>) => void;
}

interface IProps {
  graphConfigPayload: Record<string, any>;
}

const DEFAULT_VALUE = 'default';

@Component
export default class ViewTab extends tsc<IProps, IEmit> {
  @Prop({ type: Object, default: () => ({}) }) readonly graphConfigPayload: IProps['graphConfigPayload'];

  @Model('change', { type: String, default: DEFAULT_VALUE }) readonly value: string;

  @Ref('tabRef') readonly tabRef: any;

  isNeedParseUrl = true;
  isTabListInit = false; // bk-tab 组件默认传入active时，并且bk-tab-panel异步加载因为组件内部有正确性校验会改变 active 的值
  isListLoading = true;
  isViewDetailLoading = false;
  viewTab = '';
  viewList: { id: string; name: string }[] = [];
  sortViewIdList: string[] = [];

  get metricGroupList() {
    return customEscalationViewStore.metricGroupList;
  }

  get sceneId() {
    return `custom_metric_v2_${this.$route.params.id}`;
  }

  get currentSelectViewInfo() {
    return this.viewList.find(item => item.id === this.viewTab) || { id: DEFAULT_VALUE, name: DEFAULT_VALUE };
  }

  @Watch('graphConfigPayload')
  graphConfigPayloadChange(val, old) {
    if (optimizedDeepEqual(val, old)) {
      return;
    }
    this.$router.replace({
      query: {
        ...this.$route.query,
        key: `${Date.now()}`, // query 相同时 router.replace 会报错
        viewTab: this.viewTab,
        viewPayload: JSON.stringify(this.graphConfigPayload),
      },
    });
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
      if (!result.find(item => item.id === this.viewTab)) {
        this.viewTab = DEFAULT_VALUE;
      }
    } finally {
      this.isListLoading = false;
      this.isTabListInit = true;
    }
  }

  async fetchViewData() {
    this.isViewDetailLoading = true;
    this.tabRef.updateActiveBarPosition(this.viewTab);
    this.tabRef.checkActiveName();

    const updateCurrentSelectedMetricNameList = (metricNameList: string[]) => {
      // 视图保存的 metric 可能被隐藏，需要过滤掉不存在 metric
      const allMetricNameMap = this.metricGroupList.reduce<Record<string, boolean>>((result, groupItem) => {
        for (const metricItem of groupItem.metrics) {
          Object.assign(result, {
            [metricItem.metric_name]: true,
          });
        }
        return result;
      }, {});
      const realMetricNameList = _.filter(metricNameList, item => allMetricNameMap[item]);
      // 更新 Store 上的 currentSelectedMetricNameList
      customEscalationViewStore.updateCurrentSelectedMetricNameList(realMetricNameList);
    };

    try {
      // url 上面附带的参数优先级高
      const urlPayload = this.parseUrlPayload();
      if (urlPayload) {
        updateCurrentSelectedMetricNameList(urlPayload.metrics);
        this.$emit('payloadChange', urlPayload);
        return;
      }

      // 默认视图选择第一个 metric
      if (this.viewTab === DEFAULT_VALUE) {
        updateCurrentSelectedMetricNameList(
          this.metricGroupList.length > 0 ? [this.metricGroupList[0].metrics[0].metric_name] : []
        );
        this.$emit('payloadChange', {
          metrics: this.metricGroupList.length > 0 ? [this.metricGroupList[0].metrics[0].metric_name] : [],
        });

        this.isViewDetailLoading = false;
        return;
      }

      // 获取自定义视图详情数据
      const payload = await getSceneView({
        scene_id: this.sceneId,
        id: this.viewTab,
        type: 'detail',
      });

      updateCurrentSelectedMetricNameList(payload.options.metrics);
      this.$emit('payloadChange', payload.options);
    } finally {
      this.$emit('change', this.viewTab);
      this.isViewDetailLoading = false;
    }
  }

  parseUrlPayload() {
    if (!this.$route.query.viewPayload || !this.isNeedParseUrl) {
      this.isNeedParseUrl = false;
      return undefined;
    }
    this.isNeedParseUrl = false;
    const paylaod = JSON.parse((this.$route.query.viewPayload as string) || '') as Record<string, any>;
    return _.isObject(paylaod) ? paylaod : undefined;
  }

  handleTabChange(value: string) {
    if (this.isListLoading) {
      return;
    }

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
    this.$bkMessage({
      theme: 'success',
      message: this.$t('视图删除成功'),
    });
  }

  handleViewSaveSuccess() {
    this.fetchViewList();
  }

  async created() {
    this.viewTab = this.value;
    await this.fetchViewList();
    this.fetchViewData();
  }

  render() {
    return (
      <div>
        <div
          class='bk-monitor-new-metric-view-view-tab'
          v-bkloading={{ isListLoading: this.isListLoading }}
        >
          {this.isTabListInit && (
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
                    {/* <div class='drag-flag'>
                      <i class='icon-monitor icon-mc-tuozhuai' />
                    </div> */}
                    <span>{item.name}</span>
                    {/* <RemoveConfirm
                      data={item}
                      onSubmit={() => this.handleRemoveView(item.id)}
                    >
                      <span class='remove-btn'>
                        <i class='icon-monitor icon-mc-clear' />
                      </span>
                    </RemoveConfirm> */}
                  </template>
                </bk-tab-panel>
              ))}
            </bk-tab>
          )}
          <div class='extend-action'>
            {this.viewList.length > 0 && (
              <ViewManage
                payload={this.graphConfigPayload}
                sceneId={this.sceneId}
                viewList={this.viewList}
                onSuccess={() => {
                  this.isTabListInit = false;
                  this.handleViewSaveSuccess();
                }}
              />
            )}
            <ViewSave
              payload={this.graphConfigPayload}
              sceneId={this.sceneId}
              viewId={this.viewTab}
              viewList={this.viewList}
              onSuccess={this.handleViewSaveSuccess}
            />
          </div>
        </div>
        <div v-bkloading={{ isLoading: this.isViewDetailLoading }}>{this.$slots.default}</div>
      </div>
    );
  }
}
