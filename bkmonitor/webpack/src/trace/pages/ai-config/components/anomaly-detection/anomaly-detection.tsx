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
import { defineComponent, onMounted } from 'vue';

import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { getSceneErrorKey, KPI_ERROR_KEY, useAnomalyDetection } from '../../composables/use-anomaly-detection';
import { SCENE_NAME_MAP } from '../../typings';
import ConfigCard from '../config-card/config-card';
import SchemeSelect from '../scheme-select/scheme-select';

import './anomaly-detection.scss';

/**
 * @description 异常检测：配置单指标与各场景的默认智能检测方案
 */
export default defineComponent({
  name: 'AnomalyDetection',
  setup(_props) {
    const { t } = useI18n();
    const {
      loading,
      saving,
      singleSchemeList,
      sceneSchemeList,
      kpiPlanId,
      sceneList,
      errors,
      isEdited,
      fetchData,
      handleKpiPlanChange,
      handleScenePlanChange,
      save,
    } = useAnomalyDetection();

    onMounted(fetchData);

    return {
      t,
      isEdited,
      save,
      loading,
      saving,
      singleSchemeList,
      sceneSchemeList,
      kpiPlanId,
      sceneList,
      errors,
      handleKpiPlanChange,
      handleScenePlanChange,
    };
  },
  render() {
    return (
      <div class='anomaly-detection'>
        <ConfigCard
          description={this.t('为单指标异常检测，配置默认的方案')}
          icon='icon-zhibiaojiansuo'
          title={this.t('单指标异常检测')}
        >
          <div class='config-form-block'>
            <SchemeSelect
              errorMsg={this.errors[KPI_ERROR_KEY]}
              list={this.singleSchemeList}
              loading={this.loading}
              modelValue={this.kpiPlanId}
              onChange={this.handleKpiPlanChange}
            />
          </div>
        </ConfigCard>

        <ConfigCard
          description={this.t('针对不同场景分别配置智能检测方案')}
          icon='icon-mc-intelligent-detection'
          title={this.t('场景智能异常检测')}
        >
          {this.sceneList.map(scene => (
            <div
              key={scene.type}
              class='config-form-block'
            >
              <span class='block-title'>{this.t(SCENE_NAME_MAP[scene.type])}</span>
              <SchemeSelect
                errorMsg={this.errors[getSceneErrorKey(scene.type)]}
                list={this.sceneSchemeList}
                loading={this.loading}
                modelValue={scene.planId}
                onChange={planId => this.handleScenePlanChange(scene.type, planId)}
              />
            </div>
          ))}
        </ConfigCard>

        <Button
          class='save-button'
          loading={this.saving}
          theme='primary'
          onClick={this.save}
        >
          {this.t('保存配置')}
        </Button>
      </div>
    );
  },
});
