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
import { Component, Ref } from 'vue-property-decorator';
import { Route } from 'vue-router';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone, random, transformDataKey } from '../../../../../monitor-common/utils/utils';
import { SET_NAV_ROUTE_LIST } from '../../../../../monitor-pc/store/modules/app';
import SetMealAddModule from '../../../../store/modules/set-meal-add';

import MealBasicInfo from './meal-basic-info/meal-basic-info';
import MealContentNew, { IMealTypeList } from './meal-content/meal-content';
import {
  IMealData,
  mealContentDataBackfill,
  mealDataInit,
  transformMealContentParams
} from './meal-content/meal-content-data';
import MealDesc from './meal-desc/meal-desc';

import './set-meal-add.scss';

Component.registerHooks(['beforeRouteLeave', 'beforeRouteEnter']);
@Component({
  name: 'SetMealAdd'
})
export default class SetMealAdd extends tsc<{}> {
  @Ref('basicInfoRef') readonly basicInfoRefEl: MealBasicInfo;
  @Ref('mealContentRef') mealContentRef: MealContentNew;

  fromRouteName = '';
  configId = 0;
  type: 'add' | 'edit' = 'add';
  isLoading = false;
  mealInfo: any = {};

  // 基本信息
  basicInfo = {
    bizId: this.$store.getters.bizId,
    name: '',
    asStrategy: 0,
    enable: true,
    desc: ''
  };
  rightShow = true;
  mealData: IMealData = mealDataInit();
  mealTypeList: IMealTypeList[] = [];

  refreshKey = random(8);

  // 套餐类型
  get getMealType(): number {
    return this.mealData.id;
  }
  get pluginId() {
    return this.$route.params.id;
  }

  /** 套餐克隆 */
  get isClone() {
    return this.$route.name === 'clone-meal' || this.$route.query?.isClone;
  }

  async created() {
    this.initMeal();
  }

  public beforeRouteEnter(to: Route, from: Route, next: Function) {
    next((vm: SetMealAdd) => {
      vm.fromRouteName = from.name;
    });
  }

  async initMeal() {
    this.isLoading = true;
    this.updateNavData(this.$route.params.id && !this.isClone ? this.$tc('编辑') : this.$tc('新建套餐'));
    // 渲染通知方式表格
    await SetMealAddModule.getNoticeWay();
    // 获取维度列表
    await SetMealAddModule.getDimensionList();
    // 获取收敛类型列表
    await SetMealAddModule.getConvergeFunctionList();
    // 获取变量列表
    await SetMealAddModule.getVariableDataList();
    // 套餐类型列表
    await this.getMealTypeList();
    if (this.$route.params.id) {
      this.configId = parseInt(this.$route.params.id);

      // 编辑
      this.type = 'edit';
      this.mealInfo = await SetMealAddModule.retrieveActionConfig(this.configId);
      this.mealData = mealContentDataBackfill(deepClone(this.mealInfo));
      this.getBasicInfo();
      !this.isClone && this.updateNavData(`${this.$tc('编辑')} ${this.mealInfo.name}`);
      this.refreshKey = random(8);
    } else {
      // 新增
      this.type = 'add';
      if (this.$route.params.pluginType) {
        // 从策略跳转过来
        const { pluginType } = this.$route.params;
        this.$nextTick(() => {
          const mealTypes = [];
          this.mealTypeList.forEach(item => {
            mealTypes.push(...item.children);
          });
          const mealTypeItem = mealTypes.find(item => item.pluginType === pluginType);
          this.mealContentRef.mealTypeChange(mealTypeItem.id);
        });
      }
    }
    this.isLoading = false;
  }
  /** 更新面包屑 */
  updateNavData(name = '') {
    if (!name) return;
    const routeList = [];
    routeList.push({
      name,
      id: ''
    });
    this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
  }
  // 获取基本信息
  getBasicInfo() {
    const { name, desc, isEnabled, strategyCount } = this.mealInfo;
    this.basicInfo.name = name;
    if (this.isClone) {
      this.basicInfo.name = `${name}_copy`;
    }
    this.basicInfo.desc = desc;
    this.basicInfo.enable = isEnabled;
    this.basicInfo.asStrategy = strategyCount;
  }
  async validator() {
    // eslint-disable-next-line @typescript-eslint/no-misused-promises
    return new Promise(async (resolve, reject) => {
      // 校验基本信息
      if (!this.basicInfoRefEl.validator()) reject(false);
      const isPass = await this.mealContentRef.validator();
      if (!isPass) reject(false);
      resolve(true);
    });
  }

  // 确定
  async save() {
    const isPass = await this.validator().catch(err => console.log(err));
    if (!isPass) return;
    if (this.type === 'add') {
      this.postActionConfig();
    } else if (this.type === 'edit') {
      this.putActionConfig();
    }
  }

  // 获取编辑和新增参数
  getParams() {
    const executeConfigData: any = transformMealContentParams(this.mealData);
    const params = {
      executeConfig: executeConfigData,
      name: this.basicInfo.name,
      desc: this.basicInfo.desc,
      isEnabled: this.basicInfo.enable,
      pluginId: this.mealData.id
      // ...otherParams(this.mealData)
    };
    const res = transformDataKey(params, true);
    if (executeConfigData.templateId) {
      res.execute_config.template_detail = executeConfigData.templateDetail;
    }
    return res;
  }
  // 创建一个套餐
  async postActionConfig() {
    const result: any = await SetMealAddModule.createActionConfig(this.getParams());
    if (!result) return;
    if (['strategy-config-edit', 'strategy-config-add'].includes(this.fromRouteName)) {
      this.handleStrategyData(result.id);
      return;
    }
    if (result.id) {
      this.$router.push({ path: '/set-meal' });
    }
  }

  // 修改一个套餐
  async putActionConfig() {
    if (this.isClone) {
      this.postActionConfig();
      return;
    }
    const result: any = await SetMealAddModule.updateActionConfig({
      configId: this.configId,
      params: this.getParams()
    });
    if (!result) return;
    if (['strategy-config-edit', 'strategy-config-add'].includes(this.fromRouteName)) {
      this.handleStrategyData(result.id, true);
      return;
    }
    if (result.id) {
      this.$router.push({ path: '/set-meal' });
    }
  }

  // 处理来自策略的跳转
  handleStrategyData(id, isEdit = false) {
    if (isEdit) {
      this.$router.back();
      return;
    }
    const { strategyId } = this.$route.params;
    const params: { [field in string]: string } = {
      mealId: `${id}`
    };
    strategyId && (params.id = `${strategyId}`);
    this.$router.replace({
      name: this.fromRouteName,
      params
    });
  }

  // 点击取消
  cancel() {
    return new Promise(resolve => {
      this.$bkInfo({
        title: this.$t('是否放弃本次操作'),
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        confirmFn: async () => {
          resolve(true);
          if (['strategy-config-edit', 'strategy-config-add'].includes(this.fromRouteName)) {
            this.$router.back();
            return;
          }
          this.$router.push({ path: '/set-meal' });
        }
      });
    });
  }
  handleRightShow(show: boolean) {
    this.rightShow = show;
  }

  async getMealTypeList() {
    let data = await SetMealAddModule.getMealTypeList().finally(() => (this.isLoading = false));
    data = transformDataKey(data);
    this.mealTypeList = data as IMealTypeList[];
  }

  protected render() {
    return (
      <div
        class='set-meal-add'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        <div
          class='set-meal-left'
          style={{ width: this.rightShow ? 'calc(100% - 400px)' : 'calc(100% - 16px)' }}
        >
          <div class='set-meal-wrapper'>
            <div
              class='set-warpper-container'
              style={{ width: this.rightShow ? 'calc(100% - 400px)' : 'calc(100% - 16px)' }}
            >
              <div class='set-warpper'>
                <div
                  class='set-title'
                  v-en-style='width: 120px'
                >
                  {this.$t('基本信息')}
                </div>
                <MealBasicInfo
                  ref='basicInfoRef'
                  basicInfo={this.basicInfo}
                  type={this.type}
                ></MealBasicInfo>
              </div>
              <MealContentNew
                ref='mealContentRef'
                type={this.type}
                name={this.basicInfo.name}
                mealData={this.mealData}
                mealTypeList={this.mealTypeList}
                refreshKey={this.refreshKey}
                onChange={data => (this.mealData = data)}
              ></MealContentNew>
              <div class='operate-warpper'>
                <bk-button
                  theme='primary'
                  onClick={this.save}
                >
                  {this.$t('保存套餐')}
                </bk-button>
                <bk-button onClick={this.cancel}>{this.$t('取消')}</bk-button>
              </div>
            </div>
            <div
              class='set-meal-right'
              style={{ width: this.rightShow ? '400px' : '16px' }}
            >
              <MealDesc
                pluginType={this.mealData.pluginType}
                pluginTypeId={this.getMealType}
                show={this.rightShow}
                onChange={this.handleRightShow}
              ></MealDesc>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
