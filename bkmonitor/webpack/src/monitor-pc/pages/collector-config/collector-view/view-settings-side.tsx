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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { saveScenePanelConfig } from '../../../../monitor-api/modules/data_explorer';
import SortPanel from '../../performance/performance-detail/sort-panel.vue';

import { addSceneResult, metric, orderList, sceneList, viewSettingParams } from './type';
import { delCollectScene, getCollectVariable, setCollectVariable } from './variable-set';

import './view-settings-side.scss';

interface IViewSettingsSide {
  show?: boolean;
  isEdit?: boolean;
  orderList?: any;
  id?: number | string;
  routeType?: 'collect' | 'custom';
  viewSettingParams?: viewSettingParams;
  sceneList?: sceneList[];
  sceneName?: string;
  defaultOrderList?: orderList[];
  dimensions?: metric[];
  viewSortHide?: boolean;
}
interface IViewSettingsSideEvent {
  onChange?: boolean;
  onAddScene?: addSceneResult;
}

@Component({
  name: 'ViewSettingsSide'
})
export default class ViewSettingsSide extends tsc<IViewSettingsSide, IViewSettingsSideEvent> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Boolean, default: false }) isEdit: boolean;
  // 排序数据
  @Prop({ default: () => [], type: Array }) readonly orderList: orderList[];
  @Prop({ default: '', type: [String, Number] }) id: string;
  @Prop({ type: String }) readonly routeType: 'collect' | 'custom';
  @Prop({ default: () => ({}), type: Object }) viewSettingParams: viewSettingParams;
  @Prop({ default: () => [], type: Array }) sceneList: sceneList[];
  @Prop({ default: '', type: String }) sceneName: string;
  @Prop({ default: () => [], type: Array }) defaultOrderList: orderList[];
  @Prop({ default: () => [], type: Array }) dimensions: metric[];
  @Prop({ default: false }) viewSortHide: boolean;
  @Ref('sortPanel') sortPanelRef: any;

  isShow = false; // 是否展开
  isLoading = false;
  showChartSort = true;
  labelName = ''; // 场景名/标签名
  isCreate = false; // 创建分组切换输入框
  createName = ''; // 创建分组名
  groupList = []; // 分组
  order = ''; // 当前分组名
  verify = false; // 校验
  isChecked = false; // 是否选中了分组
  isLabelDisable = false;

  @Watch('sceneName')
  handleSceneName(v) {
    if (v) {
      this.isLabelDisable = false;
      this.labelName = v;
    }
  }

  @Watch('show')
  handleShow(v) {
    this.verify = false;
    if (!this.isEdit) {
      this.labelName = '';
    }
    if (this.labelName === this.sceneList[0].name) {
      this.isLabelDisable = true;
    }
    this.isShow = v;
  }

  @Emit('change')
  hiddenChange() {
    this.isLabelDisable = false;
    return false;
  }
  @Emit('editChange')
  editChange(result: addSceneResult) {
    return result;
  }
  @Emit('addScene')
  addScene(result: addSceneResult) {
    return result;
  }

  /**
   * @description: 保存配置
   * @param {any} arr
   * @return {*}
   */
  async handleSortChange(arr: any[]) {
    this.labelNameVerify(this.labelName);
    if (this.verify) return;
    if (this.labelName === '') return;
    let id;
    if (this.routeType === 'collect') {
      id = `collect_config_${this.id}`;
    } else {
      id = `custom_report_${this.id}`;
    }
    this.isLoading = true;
    const params: any = {
      bk_biz_id: this.$store.getters.bizId,
      id,
      config: {
        name: this.labelName,
        variables: this.isEdit
          ? this.viewSettingParams.variableResult.map(item => ({ id: item.key, name: item.name }))
          : this.dimensions.slice(0, 3).map(item => ({ id: item.englishName, name: item.englishName })),
        order: arr
      }
    };
    if (this.isEdit) {
      params.name = this.sceneName;
    }
    await saveScenePanelConfig(params)
      .then(() => {
        if (this.isEdit) {
          const tempVariables = getCollectVariable(`${this.id}`, params.name, 'variables', this.routeType) || {};
          delCollectScene(`${this.id}`, params.name, this.routeType);
          setCollectVariable(
            `${this.id}`,
            this.labelName,
            Object.keys(tempVariables).map(key => ({ id: key, value: tempVariables[key] })),
            this.routeType
          );
          this.editChange(params.config);
        } else {
          this.addScene(params.config);
        }
      })
      .catch(() => ({}))
      .finally(() => (this.isLoading = false));
  }

  /**
   * @description: 创建分组输入框
   * @param {*} isCreate
   * @return {*}
   */
  createGroup(isCreate = false) {
    this.isCreate = !this.isCreate;
    if (isCreate) {
      this.sortPanelRef.handleSaveNewGroup(this.createName);
    }
    this.createName = '';
  }
  /**
   * @description: 分组变更
   * @param {object} list
   * @return {*}
   */
  groupsChange(list: { id: string; name: string }[]) {
    this.groupList = list;
    this.order = this.groupList[0].id;
  }
  /**
   * @description: 创建分组
   * @param {*}
   * @return {*}
   */
  addGroupPanels() {
    this.order !== '' && this.sortPanelRef.checkedSortSet(this.order);
  }

  /**
   * @description: 校验
   * @param {string} val
   * @return {*}
   */
  labelNameVerify(val: string) {
    const sceneNames = this.sceneList.map(item => item.name);
    if (val === '') {
      this.verify = true;
      return;
    }
    if (sceneNames.includes(val)) {
      if (this.isEdit) {
        this.verify = sceneNames.filter(item => item !== this.sceneName).includes(val);
        return;
      }
      this.verify = true;
      return;
    }
  }

  render() {
    return (
      <bk-sideslider
        ext-cls='view-settings-side'
        title={this.$t('视图设置')}
        width={524}
        is-show={this.isShow}
        {...{ on: { 'update:isShow': val => (this.isShow = val) } }}
        quick-close={true}
        show-mask={false}
        on-hidden={this.hiddenChange}
      >
        <div
          slot='content'
          class={{ 'view-sort-hide': this.viewSortHide }}
          v-bkloading={{ isLoading: this.isLoading }}
        >
          <div class='settings-side-abs'>
            <div class='label-setting-title'>{this.$t('视图标签')}</div>
            <div class='label-setting-content'>
              <div class='content-label'>
                {this.$t('视图标签名')}
                {this.verify ? <span class='err-red'>{this.$t('视图标签名不能为空且不能相同')}</span> : undefined}
              </div>
              <bk-input
                on-focus={() => (this.verify = false)}
                v-model={this.labelName}
                disabled={this.isLabelDisable}
                maxlength={20}
                show-word-limit
              ></bk-input>
            </div>
            <div
              class='sort-setting-title'
              style={this.viewSortHide ? 'display: none' : undefined}
            >
              <span class='title'>{this.$t('视图设置')}</span>
              <span class='title-create'>
                {!this.isCreate ? (
                  <span
                    class='title-label'
                    onClick={() => this.createGroup(false)}
                  >
                    {this.$t('创建分组')}
                  </span>
                ) : (
                  <div class='create-input'>
                    <bk-input
                      v-model={this.createName}
                      maxlength={20}
                      show-word-limit
                    ></bk-input>
                    <i
                      class='ml5 bk-icon icon-check-1'
                      onClick={() => this.createGroup(true)}
                    ></i>
                    <i
                      class='ml5 icon-monitor icon-mc-close'
                      onClick={() => this.createGroup(false)}
                    ></i>
                  </div>
                )}
              </span>
            </div>
            {this.isChecked ? (
              <div class='sort-setting-content'>
                <bk-select
                  ext-cls='setting-content-select'
                  v-model={this.order}
                >
                  {this.groupList.map(item => (
                    <bk-option
                      id={item.id}
                      name={item.title}
                      key={item.id}
                    ></bk-option>
                  ))}
                </bk-select>
                <bk-button
                  theme='default'
                  onClick={this.addGroupPanels}
                >
                  {this.$t('加进分组')}
                </bk-button>
              </div>
            ) : undefined}
          </div>
          <SortPanel
            ref='sortPanel'
            is-not-dialog={true}
            v-model={this.showChartSort}
            groups-data={this.orderList}
            need-group={true}
            defaultOrderList={this.defaultOrderList}
            viewSortHide={this.viewSortHide}
            on-save={this.handleSortChange}
            on-groups-change={this.groupsChange}
            on-checked-change={v => (this.isChecked = v)}
          ></SortPanel>
        </div>
      </bk-sideslider>
    );
  }
}
