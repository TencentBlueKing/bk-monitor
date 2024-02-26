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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deleteScenePanelConfig, saveScenePanelConfig } from '../../../../monitor-api/modules/data_explorer';
import { random } from '../../../../monitor-common/utils/utils';

import { addSceneResult, metric, orderList, sceneList, viewSettingParams } from './type';
import { delCollectScene } from './variable-set';
import ViewSettingsSide from './view-settings-side';

import './view-settings.scss';

interface IViewSettings {
  orderList?: any;
  id?: number;
  sceneList?: any[];
  routeType?: 'collect' | 'custom';
  dimensions?: metric[];
}
interface IPanels {
  name: string;
  label: string;
}

interface IViewSettingsEvent {
  onDelScene?: string;
  onAddScene?: addSceneResult;
  onUpdateSceneList?: void;
}

@Component({
  name: 'ViewSettings'
})
export default class ViewSettings extends tsc<IViewSettings, IViewSettingsEvent> {
  // 排序数据
  @Prop({ default: () => [], type: Array }) readonly orderList: orderList[];
  @Prop({ default: '' }) id: number;
  @Prop({ default: () => [], type: Array }) sceneList: sceneList[];
  @Prop({ type: String }) readonly routeType: 'collect' | 'custom';
  @Prop({ default: () => ({}), type: Object }) viewSettingParams: viewSettingParams;
  @Prop({ default: '', type: String }) sceneName: string;
  @Prop({ default: () => [], type: Array }) dimensions: metric[];
  @Prop({ default: false }) viewSortHide: boolean;

  isLoading = false;
  active = '';
  sideShow = false;
  panels: IPanels[] = [];

  get tabKey() {
    if (this.id && this.sceneList.length) {
      return random(8);
    }
    return 'tab-key';
  }

  @Watch('sceneName')
  handleSceneName(val: string) {
    this.active = val;
  }

  /**
   * @description: 切换组合
   * @param {string} val
   * @return {*}
   */
  @Emit('change')
  tabChange(val: string) {
    this.active = val;
    return this.sceneList.find(item => item.name === this.active);
  }

  /**
   * @description: tab排序
   * @param {number} from
   * @param {number} to
   * @return {*}
   */
  handleSortChange(from: number, to: number) {
    this.isLoading = true;
    const curItem = this.sceneList[from];
    const id = this.routeType === 'collect' ? `collect_config_${this.id}` : `custom_report_${this.id}`;
    const params = {
      id,
      index: to,
      config: {
        name: curItem.name
      }
    };
    saveScenePanelConfig(params).finally(() => {
      this.$emit('updateSceneList');
      this.isLoading = false;
    });
  }
  /**
   * @description: 添加tab(弹出侧栏)
   * @param {*}
   * @return {*}
   */
  tabAdd() {
    this.sideShow = true;
  }
  async tabDel(index: number) {
    if (this.sceneList.length === 1) return;
    this.isLoading = true;
    this.$bkInfo({
      title: `${this.$t('你确认要删除?')}?`,
      confirmLoading: true,
      cancelFn: () => {
        this.isLoading = false;
      },
      confirmFn: async () => {
        try {
          let id;
          if (this.routeType === 'collect') {
            id = `collect_config_${this.id}`;
          } else {
            id = `custom_report_${this.id}`;
          }
          await deleteScenePanelConfig({ id, name: this.sceneList[index].name })
            .then(() => {
              delCollectScene(`${this.id}`, this.sceneList[index].name, this.routeType);
              this.sceneDel(this.sceneList[index].name);
            })
            .catch(() => ({}))
            .finally(() => {
              this.isLoading = false;
            });
          this.$bkMessage({
            message: this.$t('删除成功'),
            theme: 'success'
          });
        } catch (e) {
          console.warn(e);
          return false;
        }
      }
    });
  }

  @Emit('delScene')
  sceneDel(sceneName) {
    return sceneName;
  }
  @Emit('addScene')
  handleAddScene(result: addSceneResult) {
    this.sideShow = false;
    this.$nextTick(() => {
      this.active = result.name;
    });
    return result;
  }

  sideChange(val: boolean) {
    this.sideShow = val;
  }

  render() {
    return (
      <div
        class='collect-view-settings'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        {this.sceneList?.length ? (
          <bk-tab
            active={this.active}
            addable
            key={this.tabKey}
            sortable
            sort-type='insert'
            on-sort-change={this.handleSortChange}
            on-tab-change={this.tabChange}
            on-add-panel={this.tabAdd}
          >
            {this.sceneList.map((item, index) => (
              <bk-tab-panel
                name={item.name}
                key={item.name}
              >
                <template slot='label'>
                  <div class='custom-tab-panel'>
                    <div class='panel-left'>
                      <i class='icon-monitor icon-mc-tuozhuai'></i>
                    </div>
                    <span>{item.name}</span>
                    <div class='panel-right'>
                      <span
                        onClick={e => {
                          e.stopPropagation();
                          this.tabDel(index);
                        }}
                        class={['icon-monitor', 'icon-mc-delete-line', { show: item.name !== this.sceneList[0].name }]}
                      ></span>
                    </div>
                  </div>
                </template>
              </bk-tab-panel>
            ))}
          </bk-tab>
        ) : undefined}
        <ViewSettingsSide
          show={this.sideShow}
          orderList={this.orderList}
          id={this.id}
          routeType={this.routeType}
          viewSettingParams={this.viewSettingParams}
          sceneList={this.sceneList}
          dimensions={this.dimensions}
          viewSortHide={this.viewSortHide}
          onChange={this.sideChange}
          onAddScene={this.handleAddScene}
        ></ViewSettingsSide>
      </div>
    );
  }
}
