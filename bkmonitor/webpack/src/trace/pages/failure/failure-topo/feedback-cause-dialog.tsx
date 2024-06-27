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
import { computed, defineComponent, inject, Ref, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { Button, Collapse, Dialog, Form, Input, Message } from 'bkui-vue';

import { feedbackIncidentRoot, incidentRecordOperation } from '../../../../monitor-api/modules/incident';
import { IncidentDetailData } from './types';

import './feedback-cause-dialog.scss';

export default defineComponent({
  name: 'FeedbackCauseDialog',
  props: {
    visible: {
      type: Boolean,
      required: false,
    },
    /** 节点信息 */
    data: {
      type: Object,
      default: () => ({}),
    },
    onChange: {
      type: Function,
      default: _v => {},
    },
  },
  emits: ['editSuccess', 'update:isShow', 'refresh'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const activeIndex = ref<number[]>([0, 1]);
    const btnLoading = ref<boolean>(false);
    const formData = ref({
      feedbackContent: '',
    });
    const formRef = ref<HTMLDivElement>();
    const incidentDetail = inject<Ref<IncidentDetailData>>('incidentDetail');
    const incidentDetailData = computed<IncidentDetailData>(() => {
      return incidentDetail.value;
    });
    function valueChange(v) {
      emit('update:isShow', v);
    }
    const handleFeedbackIncidentRoot = () => {
      (formRef.value as any)?.validate().then(() => {
        btnLoading.value = true;
        const { id, incident_id, bk_biz_id } = incidentDetailData.value;
        const params = {
          id,
          incident_id,
          bk_biz_id,
          feedback: {
            incident_root: props.data.entity.entity_id,
            content: formData.value.feedbackContent,
          },
        };
        feedbackIncidentRoot(params)
          .then(() => {
            Message({
              theme: 'success',
              message: t('反馈成功'),
            });
            valueChange(false);
            emit('editSuccess');
            incidentRecordOperation({
              id,
              incident_id,
              bk_biz_id,
              operation_type: 'feedback',
              extra_info: {
                feedback_incident_root: formData.value.feedbackContent,
                is_cancel: false,
              },
            }).then(res => {
              res && setTimeout(() => emit('refresh'), 2000);
            });
          })
          .catch(() => {
            valueChange(true);
          })
          .finally(() => (btnLoading.value = false));
      });
    };

    return {
      t,
      valueChange,
      formData,
      formRef,
      activeIndex,
      handleFeedbackIncidentRoot,
      btnLoading,
      incidentDetailData,
    };
  },
  render() {
    const { content } = this.incidentDetailData?.current_snapshot || {};
    const originalFaultFn = () => <div class='fault-item'>{content?.incident_name || '--'}</div>;
    const newFeedback = () => {
      const { bk_biz_id, bk_biz_name, entity } = this.$props.data;
      const { entity_type, rank, entity_id } = entity;
      return (
        <Form
          ref='formRef'
          class='feedback-form'
          label-width={100}
          model={this.formData}
        >
          <Form.FormItem label={this.t('根因所属节点') + ':'}>{entity_id}</Form.FormItem>
          <Form.FormItem label={this.t('分类') + ':'}>{rank?.rank_alias || '--'}</Form.FormItem>
          <Form.FormItem label={this.t('节点类型') + ':'}>{entity_type}</Form.FormItem>
          <Form.FormItem label={this.t('所属业务') + ':'}>{`[${bk_biz_id}] ${bk_biz_name}`}</Form.FormItem>
          <Form.FormItem
            label={this.t('故障根因描述')}
            property='feedbackContent'
            required
          >
            <Input
              v-model={this.formData.feedbackContent}
              maxlength={300}
              type='textarea'
            />
          </Form.FormItem>
        </Form>
      );
    };
    const collapseList = [
      { name: this.t('原故障根因'), renderFn: originalFaultFn },
      { name: this.t('反馈新根因'), renderFn: newFeedback },
    ];
    return (
      <Dialog
        width={660}
        ext-cls='feedback-cause-dialog'
        v-slots={{
          footer: () => (
            <div>
              <Button
                loading={this.btnLoading}
                theme='primary'
                onClick={this.handleFeedbackIncidentRoot}
              >
                {this.t('确定')}
              </Button>
              <Button
                class='ml10'
                onClick={() => {
                  this.valueChange(false);
                  this.formData.feedbackContent = '';
                }}
              >
                {this.t('取消')}
              </Button>
            </div>
          ),
        }}
        dialog-type='operation'
        is-loading={this.btnLoading}
        is-show={this.$props.visible}
        title={this.t('反馈新根因')}
        onUpdate:isShow={this.valueChange}
      >
        <Collapse
          class='feedback-cause-collapse'
          v-model={this.activeIndex}
          v-slots={{
            content: (item: any) => item.renderFn(),
          }}
          header-icon='right-shape'
          list={collapseList}
        />
      </Dialog>
    );
  },
});
