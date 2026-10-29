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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone, random, transformDataKey } from 'monitor-common/utils/utils';
import { SET_NAV_ROUTE_LIST } from 'monitor-pc/store/modules/app';

import SetMealAddModule from '../../../../store/modules/set-meal-add';
import MealBasicInfo from './meal-basic-info/meal-basic-info';
import MealContentNew, { type IMealTypeList } from './meal-content/meal-content';
import {
  type IMealData,
  mealContentDataBackfill,
  mealDataInit,
  transformMealContentParams,
} from './meal-content/meal-content-data';
import MealDesc from './meal-desc/meal-desc';

import type { Route } from 'vue-router';

import './set-meal-add.scss';

Component.registerHooks(['beforeRouteLeave', 'beforeRouteEnter']);
@Component({
  name: 'SetMealAdd',
})
export default class SetMealAdd extends tsc<object> {
  @Ref('basicInfoRef') readonly basicInfoRefEl: MealBasicInfo;
  @Ref('mealContentRef') mealContentRef: MealContentNew;

  fromRouteName = '';
  configId = 0;
  type: 'add' | 'edit' = 'add';
  /** 套餐类型列表（get_plugins）——决定类型选择器选项与编辑态回填时机 */
  typeListLoading = false;
  /** 编辑态详情回显 */
  detailLoading = false;
  /** 详情已返回但套餐类型列表未就绪，暂存待回填；避免 mealTypeChange 因列表为空被跳过 */
  pendingMealInfo: Record<string, unknown> | null = null;
  mealInfo: any = {};

  // 基本信息
  basicInfo = {
    bizId: this.$store.getters.bizId,
    name: '',
    asStrategy: 0,
    enable: true,
    desc: '',
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
  /**
   * 页面遮罩：只等决定「能否安全交互」的请求——类型列表（新建/编辑）与详情（编辑）。
   * 其余 4 个元数据在后台并行填充，不再阻塞首屏；也不额外维护子区 loading/骨架。
   */
  get isLoading() {
    return this.typeListLoading || (this.type === 'edit' && this.detailLoading);
  }

  /** BKFara 等外链跳转新建套餐时带入的模板名（query: template_name） */
  get initialTemplateNameFromRoute(): string {
    if (this.type !== 'add') return '';
    const raw = this.$route.query?.template_name;
    const str = Array.isArray(raw) ? raw[0] : raw;
    return typeof str === 'string' ? str : '';
  }

  /** 套餐克隆 */
  get isClone() {
    return this.$route.name === 'clone-meal' || this.$route.query?.isClone;
  }

  async created() {
    this.initMeal();
  }

  public beforeRouteEnter(_to: Route, from: Route, next: (a: (b: SetMealAdd) => void) => void) {
    next((vm: SetMealAdd) => {
      vm.fromRouteName = from.name;
    });
  }

  async initMeal() {
    // 页面初始化重入保护；当前只在 created 调用一次，属防御性保护
    if (this.isLoading) return;
    this.typeListLoading = true;
    this.updateNavData(this.$route.params.id && !this.isClone ? this.$tc('编辑') : this.$tc('新建套餐'));
    const isEdit = Boolean(this.$route.params.id);
    if (isEdit) {
      this.configId = Number.parseInt(this.$route.params.id, 10);
      this.type = 'edit';
    } else {
      this.type = 'add';
      const presetMealName = this.$route.query?.name ? decodeURIComponent(this.$route.query.name as string) : '';
      if (presetMealName) {
        this.basicInfo.name = presetMealName;
      }
    }

    // 页面显示只等 get_plugins：这一个 promise 是 initMeal 唯一 await 的对象
    const typeListPromise = this.getMealTypeList()
      .catch(error => {
        console.error(error);
      })
      .finally(() => {
        this.typeListLoading = false;
      });
    // 其余 4 个：后台 Promise.all 并行执行，不参与页面显示
    Promise.all([
      // 渲染通知方式表格
      SetMealAddModule.getNoticeWay(),
      // 获取维度列表
      SetMealAddModule.getDimensionList(),
      // 获取收敛类型列表
      SetMealAddModule.getConvergeFunctionList(),
      // 获取变量列表
      SetMealAddModule.getVariableDataList(),
    ]).catch(error => {
      console.error(error);
    });
    // 编辑回显：请求与类型列表并行发起；回填在类型列表就绪后由 applyMealInfo 统一执行
    if (isEdit) this.loadDetail();

    // typeListPromise 已 catch 并在 finally 中复位 typeListLoading，此处不会抛出
    await typeListPromise;
    // 编辑态详情可能先返回：类型列表就绪后再回填，确保 mealTypeChange 能命中类型
    if (this.pendingMealInfo) {
      const pendingMealInfo = this.pendingMealInfo;
      this.pendingMealInfo = null;
      this.applyMealInfo(pendingMealInfo);
    }
    // 类型选择器就绪后再自动选型
    if (!isEdit) this.applyPresetMealType();
  }

  /**
   * 仅拉取编辑态详情，元数据仍在后台并行、不重复触发。
   * 失败态不新增 UI：记录错误后解除遮罩，由 save() 的内部守卫阻止用空表单覆盖真实配置。
   */
  protected loadDetail() {
    this.detailLoading = true;
    return SetMealAddModule.retrieveActionConfig(this.configId)
      .then(mealInfo => {
        // 顺序约定：先复位 detailLoading，再回填
        this.detailLoading = false;
        this.applyMealInfo(mealInfo);
      })
      .catch(error => {
        console.error(error);
      })
      .finally(() => {
        this.detailLoading = false;
      });
  }

  /** 编辑态回填：详情请求与类型列表并行，但回填需等类型列表就绪，保证 mealTypeChange 能命中类型 */
  applyMealInfo(mealInfo: Record<string, unknown> | null) {
    if (!mealInfo) return;
    if (this.typeListLoading) {
      this.pendingMealInfo = mealInfo;
      return;
    }
    this.pendingMealInfo = null;
    try {
      this.mealInfo = mealInfo;
      this.mealData = mealContentDataBackfill(deepClone(this.mealInfo));
      this.getBasicInfo();
      !this.isClone && this.updateNavData(`${this.$tc('编辑')} ${this.mealInfo.name}`);
      this.refreshKey = random(8);
    } catch (error) {
      console.error(error);
    }
  }

  /** 新建/克隆：按 URL 预置套餐类型（只依赖类型列表） */
  applyPresetMealType() {
    const { pluginType } = this.$route.params;
    const pluginName = this.$route.query?.plugin_name
      ? decodeURIComponent(this.$route.query.plugin_name as string)
      : '';
    if (!pluginType && !pluginName) return;
    this.$nextTick(() => {
      const mealTypes = [];
      this.mealTypeList.forEach(item => {
        mealTypes.push(...item.children);
      });
      let mealTypeItem: IMealTypeList | undefined;
      if (pluginType) {
        mealTypeItem = mealTypes.find(item => item.pluginType === pluginType);
      } else if (pluginName) {
        mealTypeItem = mealTypes.find(item => item.name === pluginName);
      }
      if (mealTypeItem) {
        this.mealContentRef?.mealTypeChange(mealTypeItem.id as number);
      }
    });
  }
  /** 更新面包屑 */
  updateNavData(name = '') {
    if (!name) return;
    const routeList = [];
    routeList.push({
      name,
      id: '',
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
  async validator(): Promise<boolean> {
    if (!this.basicInfoRefEl.validator()) {
      return false;
    }
    const isPass = await this.mealContentRef.validator();
    return isPass;
  }

  // 确定
  async save() {
    // 编辑态详情未成功回显时不提交：避免用空表单覆盖线上配置（不新增失败态 UI，静默返回）
    if (this.type === 'edit' && !this.mealData.id) return;
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
      pluginId: this.mealData.id,
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
      params: this.getParams(),
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
      mealId: `${id}`,
    };
    if (strategyId) {
      params.id = `${strategyId}`;
    }
    this.$router.replace({
      name: this.fromRouteName,
      params,
    });
  }

  // 点击取消
  cancel() {
    return new Promise(resolve => {
      this.$bkInfo({
        title: this.$t('是否放弃本次操作'),

        confirmFn: async () => {
          resolve(true);
          if (['strategy-config-edit', 'strategy-config-add'].includes(this.fromRouteName)) {
            this.$router.back();
            return;
          }
          this.$router.push({ path: '/set-meal' });
        },
      });
    });
  }
  handleRightShow(show: boolean) {
    this.rightShow = show;
  }

  async getMealTypeList() {
    let data = await SetMealAddModule.getMealTypeList(false);
    if (!Array.isArray(data)) {
      this.$bkInfo({
        extCls: 'set-meal-add__info',
        title: data.message || '',
        width: 520,
        type: 'warning',
      });
      data = [];
    }
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
          style={{ width: this.rightShow ? 'calc(100% - 400px)' : 'calc(100% - 16px)' }}
          class='set-meal-left'
        >
          <div class='set-meal-wrapper'>
            <div
              style={{ width: this.rightShow ? 'calc(100% - 400px)' : 'calc(100% - 16px)' }}
              class='set-warpper-container'
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
                />
              </div>
              <MealContentNew
                ref='mealContentRef'
                initialTemplateName={this.initialTemplateNameFromRoute}
                mealData={this.mealData}
                mealTypeList={this.mealTypeList}
                name={this.basicInfo.name}
                refreshKey={this.refreshKey}
                type={this.type}
                onChange={data => {
                  this.mealData = data;
                }}
              />
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
              style={{ width: this.rightShow ? '400px' : '16px' }}
              class='set-meal-right'
            >
              <MealDesc
                pluginType={this.mealData.pluginType}
                pluginTypeId={this.getMealType}
                show={this.rightShow}
                onChange={this.handleRightShow}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }
}
