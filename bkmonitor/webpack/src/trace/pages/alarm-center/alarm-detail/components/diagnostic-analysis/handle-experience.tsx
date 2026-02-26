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
import { computed, defineComponent, shallowRef } from 'vue';

import { Alert, Button, Dialog, Radio } from 'bkui-vue';

import MarkdownEditor from '../../../../../components/markdown-editor/editor';
import UiSelector from '../../../../../components/retrieval-filter/ui-selector';
import { EFieldType } from '@/components/retrieval-filter/typing';
import { useAlarmFilter } from '@/pages/alarm-center/components/alarm-retrieval-filter/hooks/use-alarm-filter';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';

import './handle-experience.scss';
export default defineComponent({
  name: 'HandleExperience',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['update:show'],

  setup(_props, { emit }) {
    const alarmStore = useAlarmCenterStore();
    const bindTarget = shallowRef('metric');
    const editorValue = shallowRef('');

    const { getRetrievalFilterValueData } = useAlarmFilter(() => ({
      alarmType: alarmStore.alarmType,
      commonFilterParams: alarmStore.commonFilterParams,
      filterMode: alarmStore.filterMode,
    }));

    /**
     * @description 检索栏字段列表
     */
    const retrievalFilterFields = computed(() => {
      const filterFields = [...alarmStore.alarmService.filterFields];
      const spliceIndex = filterFields.findIndex(item => item.name === 'tags');
      if (spliceIndex !== -1) {
        filterFields.splice(
          spliceIndex,
          1,
          ...alarmStore.dimensionTags.map(item => ({
            name: item.id,
            alias: item.name,
            methods: [
              {
                alias: '=',
                value: 'eq',
              },
              {
                alias: '!=',
                value: 'neq',
              },
            ],
            isEnableOptions: true,
            type: EFieldType.keyword,
          }))
        );
      }
      return filterFields;
    });

    const uiValue = shallowRef([]);

    const handleUiValueChange = (value: any) => {
      console.log(value);
      uiValue.value = value;
    };

    const handleConfirm = () => {
      handleShowChange(false);
    };

    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    return {
      bindTarget,
      editorValue,
      retrievalFilterFields,
      uiValue,
      handleShowChange,
      getRetrievalFilterValueData,
      handleConfirm,
      handleUiValueChange,
    };
  },
  render() {
    return (
      <Dialog
        width={960}
        class='handle-experience-dialog'
        v-slots={{
          default: () => (
            <div class='handle-experience-dialog-wrapper'>
              <Alert
                theme='info'
                title={this.$t('处理经验可以与指标或维度进行绑定，可以追加多种处理经验方便共享。')}
              />
              <div class='bind-target form-item'>
                <div class='form-label'>{this.$t('绑定')}</div>
                <div class='form-content'>
                  <Radio.Group v-model={this.bindTarget}>
                    <Radio label='metric'>
                      <span>{this.$t('指标')}: kube_pod_status_phase,kube_pod_owner</span>
                    </Radio>
                    <Radio label='dimension'>
                      <span>{this.$t('维度')}</span>
                    </Radio>
                  </Radio.Group>
                  {this.bindTarget === 'dimension' && (
                    <UiSelector
                      fields={this.retrievalFilterFields}
                      getValueFn={this.getRetrievalFilterValueData}
                      hasShortcutKey={false}
                      hasTagHidden={false}
                      value={this.uiValue}
                      zIndex={4000}
                      onChange={this.handleUiValueChange}
                    />
                  )}
                </div>
              </div>
              <div class='edit-experience form-item'>
                <div class='form-label'>{this.$t('经验')}</div>
                <div class='form-content'>
                  <MarkdownEditor
                    height={'100%'}
                    value={this.editorValue}
                  />
                </div>
              </div>
            </div>
          ),
          footer: () => (
            <div class='handle-experience-dialog-footer'>
              <Button
                theme='primary'
                onClick={this.handleConfirm}
              >
                {this.$t('确认')}
              </Button>
              <Button
                onClick={() => {
                  this.handleShowChange(false);
                }}
              >
                {this.$t('取消')}
              </Button>
            </div>
          ),
        }}
        isShow={this.show}
        title={this.$t('处理经验')}
        onConfirm={() => false}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
