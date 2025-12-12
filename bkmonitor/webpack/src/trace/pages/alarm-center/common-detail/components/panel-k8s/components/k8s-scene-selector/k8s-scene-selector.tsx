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

import { type PropType, defineComponent } from 'vue';

import { Radio } from 'bkui-vue';

import { SceneEnum } from '../../../../../typings';

import './k8s-scene-selector.scss';

/** 可选择的容器监控场景数组 */
const SCENE_DIMENSIONS = [SceneEnum.Performance, SceneEnum.Network, SceneEnum.Capacity];
/** 场景别名映射表 */
export const SceneAliasMap = {
  [SceneEnum.Performance]: {
    alias: window.i18n.t('性能'),
    icon: 'icon-monitor icon-xingneng1',
  },
  [SceneEnum.Network]: {
    alias: window.i18n.t('网络'),
    icon: 'icon-monitor icon-wangluo',
  },
  [SceneEnum.Capacity]: {
    alias: window.i18n.t('容量'),
    icon: 'icon-monitor icon-rongliang',
  },
};

export default defineComponent({
  name: 'K8sSceneSelector',
  props: {
    /** 可选择的场景列表 */
    sceneList: {
      type: Array as PropType<SceneEnum[]>,
      default: () => SCENE_DIMENSIONS,
    },
    /** 场景选择器选中值 */
    scene: {
      type: String as PropType<SceneEnum>,
    },
  },
  emits: {
    sceneChange: (scene: SceneEnum) => typeof scene === 'string',
  },
  setup(_props, { emit }) {
    /**
     * @description 选择器值改变后回调
     * @param scene 容器场景
     */
    function handleSelectChange(scene: SceneEnum) {
      emit('sceneChange', scene);
    }
    return { handleSelectChange };
  },
  render() {
    return (
      <Radio.Group
        class='k8s-scene-selector'
        modelValue={this.scene}
        type='capsule'
        onChange={this.handleSelectChange}
      >
        {(this.sceneList ?? [])?.map?.(scene => (
          <Radio.Button
            key={scene}
            class='k8s-scene-selector-item'
            label={scene}
          >
            <div class='item-container'>
              <i class={['item-prefix-icon', SceneAliasMap[scene].icon]} />
              <span class='item-alias'>{SceneAliasMap[scene].alias}</span>
            </div>
          </Radio.Button>
        ))}
      </Radio.Group>
    );
  },
});
