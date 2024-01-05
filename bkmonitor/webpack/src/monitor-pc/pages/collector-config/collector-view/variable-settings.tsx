/* eslint-disable no-param-reassign */
/* eslint-disable @typescript-eslint/naming-convention */
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

import { saveScenePanelConfig } from '../../../../monitor-api/modules/data_explorer';
import { getVariableValue } from '../../../../monitor-api/modules/grafana';
import { deepClone } from '../../../../monitor-common/utils/utils';
import { Debounce } from '../../../components/ip-selector/common/util';

import { metric, orderList, variable } from './type';
import { getCollectVariable, setCollectVariable } from './variable-set';

import './variable-settings.scss';

/* eslint-disable camelcase */

interface IVariableSettings {
  metricDimension: {
    variableParams?: any; // 获取预览值所需参数
    metricList: { id: string; metrics: metric[]; result_table_id: string }[]; // 获取预览值需要的指标信息
    dimensionList: metric[]; // 维度列表
  };
  sceneName: string; // 场景名（动态）
  sceneList: { name: string; variables: { id: string; name: string }[] }[]; // 场景列表（存储变量值）
  orderList: orderList[];
  id: number;
  routeType: 'collect' | 'custom';
}

interface IVariableSettingsProps {
  onResultChange?: { key: string; value: string[]; groupId: string }[];
  onSaveChange?: {
    sceneName: string;
    variables: { id: string; name: string }[];
  };
}
interface Icache {
  sceneName: string; // 场景名
  previews: {
    // 预览值
    [propName: string]: { label: string; value: string }[];
  };
  checked?: { dimension: string; value: string[] }[];
}
export const selectAllItemKey = 'selecteAllItemKey';
@Component({
  name: 'VariableSettings'
})
export default class VariableSettings extends tsc<IVariableSettings, IVariableSettingsProps> {
  @Prop({ default: () => ({}), type: Object }) metricDimension: IVariableSettings['metricDimension'];
  @Prop({ default: '', type: String }) sceneName: string;
  @Prop({ default: () => [], type: Array }) sceneList: IVariableSettings['sceneList'];
  @Prop({ default: () => [], type: Array }) readonly orderList: orderList[];
  @Prop({ default: '', type: Number }) id: number;
  @Prop({ type: String }) readonly routeType: 'collect' | 'custom';

  isLoading = false;
  variableList: variable[] = []; // 变量列表
  cache: Icache[] = []; // 预览值缓存
  isEdit = false; // 编辑按钮显示
  verify = false; // 校验
  cacheId = 0; // 缓存上一个采集id
  cacheValue = {}; // 缓存上一个预览值
  tempVariableList: variable[] = []; // 切换编辑的是否缓存数据

  // 已选维度
  get checkedDimensions() {
    return this.variableList.filter(item => item.dimension !== '').map(item => item.dimension);
  }
  /**
   * @description: 切换场景时调用
   * @param {*}
   * @return {*}
   */
  @Debounce(300)
  @Watch('sceneName')
  async handleSceneName(val: string) {
    this.isEdit = false;
    if (this.cacheId !== this.id) {
      this.cache = [];
      this.cacheId = this.id;
    }
    if (!val) return;
    if (!this.sceneList.map(item => item.name).includes(val)) {
      const index = this.cache.findIndex(c => c.sceneName === val);
      index > -1 && this.cache.splice(index, 1);
    }
    this.variableList = [];
    this.isLoading = true;
    const sceneItem = this.sceneList.find(item => item.name === this.sceneName);
    let resultDimensionList = [];
    const promiseList = [];
    this.cache.push({
      sceneName: this.sceneName,
      previews: {}
    });
    if (
      sceneItem.variables.length &&
      this.metricDimension.dimensionList.map(item => item.englishName).includes(sceneItem.variables[0].id)
    ) {
      // 如有变量结果则取维度交集
      resultDimensionList = this.metricDimension.dimensionList.filter(
        item => sceneItem.variables.map(v => v.id).indexOf(item.englishName) !== -1
      );
    } else {
      // 没有则默认取前三个
      resultDimensionList = this.metricDimension.dimensionList.slice(0, 3);
    }
    const sceneVariables = {};
    sceneItem.variables.forEach(item => {
      sceneVariables[item.id] = item.name;
    });
    // 获取预览值
    resultDimensionList.forEach(dimension => {
      const metricObj = this.metricDimension.metricList.find(metric => dimension.groupId === metric.id);
      const params = {
        params: {
          ...this.metricDimension.variableParams,
          metric_field: metricObj.metrics[0].englishName,
          result_table_id: metricObj.result_table_id,
          field: dimension.englishName
        },
        type: 'dimension'
      };
      promiseList.push(this.getVariableValue(params, dimension, sceneVariables));
    });
    await Promise.all(promiseList);
    const variableListTemp = this.variableList.filter(item => item.dimension !== '');
    const result = variableListTemp.map(item => ({
      key: item.dimension,
      value: item.value,
      name: item.aliaName,
      groupId: this.metricDimension.dimensionList.find(dimension => dimension.englishName === item.dimension)?.groupId
    }));
    this.resultChange(result);
    this.isLoading = false;
  }

  /**
   * @description: 从缓存或者接口拉取预览值
   * @param {*} params
   * @param {*} dimension
   * @param {*} sceneVariables
   * @return {*}
   */
  async getVariableValue(params, dimension, sceneVariables) {
    const cacheItem = this.cache.find(item => item.sceneName === this.sceneName);
    const obj = {
      value:
        getCollectVariable(`${this.id}`, this.sceneName, 'variables', this.routeType)?.[dimension.englishName] || [],
      dimension: dimension.englishName,
      dimensionList: [...this.metricDimension.dimensionList],
      aliaName: sceneVariables[dimension.englishName] || `${dimension.aliaName || dimension.englishName}`
    };
    if (cacheItem.previews[params.params.field]) {
      this.variableList.push({
        ...obj,
        preview: this.canSelectedAllItem(cacheItem.previews[params.params.field])
      });
    } else {
      const data = await getVariableValue(params).catch(() => []);
      cacheItem.previews[params.params.field] = data;
      this.variableList.push({
        ...obj,
        preview: this.canSelectedAllItem(data)
      });
    }
  }

  // 第一项添加全选标识
  canSelectedAllItem(data: { label: string; value: string }[], isCan = true): { label: string; value: string }[] {
    if (isCan && data[0]?.value !== selectAllItemKey) {
      return [{ label: `${this.$t('全选')}`, value: selectAllItemKey }, ...data];
    }
    return data;
  }

  /**
   * @description: 点击编辑按钮
   * @param {*}
   * @return {*}
   */
  variableEditChange() {
    this.isEdit = !this.isEdit;
    if (this.isEdit) {
      this.tempVariableList = deepClone(this.variableList);
    }
  }
  /**
   * @description: 保存
   * @param {*}
   * @return {*}
   */
  async saveChange() {
    if (this.verifyMethod()) return;
    let id;
    if (this.routeType === 'collect') {
      id = `collect_config_${this.id}`;
    } else {
      id = `custom_report_${this.id}`;
    }
    this.isLoading = true;
    const result = {
      sceneName: this.sceneName,
      variables: this.variableList
        .filter(item => item.dimension !== '')
        .map(item => ({ id: item.dimension, name: item.aliaName }))
    };
    const params = {
      id,
      config: {
        name: result.sceneName,
        variables: result.variables,
        order: this.orderList
      }
    };
    await saveScenePanelConfig(params)
      .catch(() => ({}))
      .finally(() => (this.isLoading = false));
    this.isEdit = false;
    this.tempVariableList = [];
    this.handleSaveChange(result);
  }
  @Emit('saveChange')
  handleSaveChange(val) {
    return val;
  }
  /**
   * @description: 取消
   * @param {*}
   * @return {*}
   */
  cancelChange() {
    this.isEdit = false;
    this.variableList = deepClone(this.tempVariableList);
  }
  /**
   * @description: 添加变量
   * @param {number} index
   * @return {*}
   */
  addVariable(index: number) {
    if (this.checkedDimensions.length === this.metricDimension.dimensionList.length) return;
    this.variableList.splice(index + 1, 0, {
      value: [],
      dimension: '',
      dimensionList: this.metricDimension.dimensionList,
      aliaName: '',
      preview: []
    });
  }
  /**
   * @description: 删除变量
   * @param {number} index
   * @return {*}
   */
  delVariable(index: number) {
    if (this.variableList.length === 1) {
      this.$set(this.variableList, 0, {
        ...this.variableList[0],
        aliaName: '',
        dimension: '',
        preview: [],
        value: []
      });
      return;
    }
    this.variableList.splice(index, 1);
  }
  /**
   * @description: 选择维度
   * @param {string} val
   * @return {*}
   */
  async dimensionChange(val: string, item: variable, index: number) {
    if (!val) return;
    const dimension = item.dimensionList.find(opt => opt.englishName === val);
    const cacheItem = this.cache.find(c => c.sceneName === this.sceneName);
    if (cacheItem.previews?.[val]) {
      item.preview = this.canSelectedAllItem(cacheItem.previews[val]);
      item.aliaName = `${dimension.aliaName || dimension.englishName}`;
    } else {
      this.isLoading = true;
      const metricObj = this.metricDimension.metricList.find(metric => dimension.groupId === metric.id);
      const data = await getVariableValue({
        params: {
          ...this.metricDimension.variableParams,
          metric_field: metricObj.metrics[0].englishName,
          result_table_id: metricObj.result_table_id,
          field: val
        },
        type: 'dimension'
      })
        .catch(() => [])
        .finally(() => {
          this.isLoading = false;
        });
      cacheItem.previews[val] = this.canSelectedAllItem(data);
      this.variableList[index].preview = this.canSelectedAllItem(data);
      this.variableList[index].aliaName = `${dimension.aliaName || dimension.englishName}`;
      this.isLoading = false;
    }
  }

  /**
   * @description: 收回下拉框时
   * @param {boolean} val
   * @return {*}
   */
  handleToggle(val: boolean) {
    const variableListTemp = this.variableList.filter(item => item.dimension !== '');
    if (!val) {
      const isSame = variableListTemp.some(
        item => JSON.stringify(this.cacheValue[item.dimension]) !== JSON.stringify(item.value)
      );
      if (isSame) {
        const result = variableListTemp.map(item => ({
          key: item.dimension,
          value: item.value,
          name: item.aliaName,
          groupId: this.metricDimension.dimensionList.find(dimension => dimension.englishName === item.dimension)
            .groupId
        }));
        this.resultChange(result);
      }
    } else {
      this.cacheValue = {};
      variableListTemp.forEach(item => {
        this.cacheValue[item.dimension] = item.value;
      });
    }
    setCollectVariable(
      `${this.id}`,
      this.sceneName,
      { type: 'variables', variables: this.variableList.map(item => ({ id: item.dimension, value: item.value })) },
      this.routeType
    );
  }
  handleClear(index) {
    this.variableList[index].value = [];
    const variableListTemp = this.variableList.filter(item => item.dimension !== '');
    const result = variableListTemp.map(item => ({
      key: item.dimension,
      value: item.value,
      name: item.aliaName,
      groupId: this.metricDimension.dimensionList.find(dimension => dimension.englishName === item.dimension).groupId
    }));
    this.resultChange(result);
    setCollectVariable(
      `${this.id}`,
      this.sceneName,
      { type: 'variables', variables: this.variableList.map(item => ({ id: item.dimension, value: item.value })) },
      this.routeType
    );
  }

  @Emit('resultChange')
  resultChange(result: IVariableSettingsProps['onResultChange']) {
    return result;
  }

  get dimensionsPreviews() {
    return this.cache.find(item => item.sceneName === this.sceneName)?.previews || {};
  }

  /**
   * @description: 校验
   * @param {*}
   * @return {*}
   */
  verifyMethod() {
    const hash = {};
    return this.variableList
      .filter(item => item.dimension !== '')
      .some(item => {
        const { aliaName } = item;
        if (aliaName === '' || hash[aliaName]) {
          this.verify = true;
          return true;
        }
        hash[aliaName] = true;
        return false;
      });
  }
  async handleTagChange(tags, index) {
    const newVal = [...tags];
    const oldVal = this.variableList[index].value;
    if (oldVal.includes(selectAllItemKey) && newVal.includes(selectAllItemKey)) {
      const i = newVal.findIndex(str => str === selectAllItemKey);
      if (i > -1) {
        newVal.splice(i, 1);
        await this.$nextTick();
        this.variableList[index].value = newVal;
      }
    } else if (!oldVal.includes(selectAllItemKey) && newVal.includes(selectAllItemKey)) {
      await this.$nextTick();
      this.variableList[index].value = [selectAllItemKey];
    } else {
      this.variableList[index].value = newVal;
    }
  }
  handleTagsBlur() {
    this.handleToggle(false);
  }

  get errMsg() {
    return this.verify ? this.$t('显示名不能为空且不能相同') : '';
  }

  // 粘贴条件时触发(tag-input)
  handlePaste(v, item, index) {
    const data = `${v}`.replace(/\s/gim, '');
    const valList = Array.from(new Set(`${data}`.split(',').map(v => v.trim()))); // 支持逗号分隔
    valList.forEach(val => {
      !item.value.some(v => v === val) && val !== '' && item.value.push(val);
    });
    this.handleTagChange(item.value, index);
    return item.value;
  }

  render() {
    return this.variableList.length ? (
      <div
        class='collect-variable-settings'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        {!this.isEdit ? (
          [
            this.variableList.map((item, index) =>
              item.dimension !== '' ? (
                <div class='variable-item'>
                  <div
                    class='item-title'
                    v-bk-tooltips={{ content: `${item.dimension}`, placements: ['top'], allowHTML: false }}
                  >
                    {item.aliaName}
                  </div>
                  <div class='item-value'>
                    <bk-tag-input
                      ext-cls='item-value-select'
                      placeholder={`${this.$t('输入')}`}
                      clearable
                      allow-create
                      value={item.value}
                      list={item.preview.map(p => ({ id: p.value, name: p.label }))}
                      trigger={'focus'}
                      on-change={tags => this.handleTagChange(tags, index)}
                      on-blur={this.handleTagsBlur}
                      on-removeAll={() => this.handleClear(index)}
                      paste-fn={v => this.handlePaste(v, item, index)}
                    ></bk-tag-input>
                  </div>
                </div>
              ) : undefined
            ),
            !this.variableList.filter(item => item.dimension !== '').length ? (
              <div class='none-tip'>
                <span class='icon-monitor icon-hint'></span>{' '}
                <span class='none-tip-text'>{this.$t('当前数据无维度，所以没有变量选择')}。</span>
              </div>
            ) : undefined,
            <div
              class='variable-edit-icon'
              onClick={this.variableEditChange}
            >
              <span class='icon-monitor icon-bianji'></span>
            </div>
          ]
        ) : (
          <div class='variable-edit-items'>
            <table>
              <tr>
                <th>
                  <span class='dimension-select-title'>{this.$t('维度选择')}</span>
                </th>
                <th>
                  <span class='display-name-title'>{this.$t('显示名')}</span>
                </th>
                <th>
                  <span class='preview-value-title'>{this.$t('预览值')}</span>
                </th>
              </tr>
              {this.variableList.map((item, index) => (
                <tr key={index}>
                  <td>
                    <div class='dimension-select'>
                      <bk-select
                        ext-cls='item-edit-select'
                        clearable={false}
                        v-model={item.dimension}
                        searchable
                        on-change={val => this.dimensionChange(val, item, index)}
                      >
                        {item.dimensionList.map(dimension => (
                          <bk-option
                            id={dimension.englishName}
                            name={dimension.aliaName || dimension.englishName}
                            key={dimension.englishName}
                            disabled={this.checkedDimensions.includes(dimension.englishName)}
                          ></bk-option>
                        ))}
                      </bk-select>
                    </div>
                  </td>
                  <td>
                    <div class='display-name'>
                      <bk-input
                        on-focus={() => (this.verify = false)}
                        v-model={item.aliaName}
                        disabled
                        v-bk-tooltips={{
                          placements: ['top'],
                          content: `${this.$t('到指标维度设置')}`
                        }}
                      ></bk-input>
                    </div>
                  </td>
                  <td>
                    <div class='preview-value'>
                      {item.preview.map(obj =>
                        obj.value !== selectAllItemKey ? <span class='preview-value-item'>{obj.label}</span> : undefined
                      )}
                    </div>
                  </td>
                  <td>
                    <div class='add-del-btn'>
                      <span
                        class='icon-monitor icon-jia'
                        v-bk-tooltips={{
                          content: `${this.$t('没有维度了')}`,
                          placements: ['top'],
                          disabled: !(this.checkedDimensions.length === this.metricDimension.dimensionList.length)
                        }}
                        on-click={() => this.addVariable(index)}
                      ></span>
                      <span
                        class='icon-monitor icon-jian'
                        on-click={() => this.delVariable(index)}
                      ></span>
                    </div>
                  </td>
                </tr>
              ))}
            </table>
            {this.errMsg !== '' && <div class='err-red'>{this.errMsg}</div>}
            <div class='save-cancel'>
              <bk-button
                theme='primary'
                class='mr10'
                on-click={this.saveChange}
              >
                {this.$t('保存')}
              </bk-button>
              <bk-button
                theme='default'
                on-click={this.cancelChange}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          </div>
        )}
      </div>
    ) : (
      <div
        class='collect-variable-settings'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        <div class='none-tip'>
          <span class='icon-monitor icon-hint'></span>{' '}
          <span class='none-tip-text'>{this.$t('当前数据无维度，所以没有变量选择')}。</span>
        </div>
      </div>
    );
  }
}
