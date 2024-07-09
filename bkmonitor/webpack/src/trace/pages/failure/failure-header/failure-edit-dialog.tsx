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
import { computed, defineComponent, inject, nextTick, onMounted, Ref, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { Button, Dialog, Form, Input, Message, Radio, TagInput } from 'bkui-vue';

import { editIncident } from '../../../../monitor-api/modules/incident';
import { strategyLabelList } from '../../../../monitor-api/modules/strategies';
import MemberSelector from '../../alarm-shield/components/member-selector';
import { IIncident } from '../types';

import './failure-edit-dialog.scss';

export default defineComponent({
  name: 'FailureEditDialog',
  props: {
    visible: {
      type: Boolean,
      required: false,
    },
    levelList: {
      type: Object,
      default: () => {},
    },
  },
  emits: ['editSuccess', 'update:isShow'],
  setup(props, { emit }) {
    const userApi = `${location.origin}${location.pathname || '/'}rest/v2/commons/user/list_users/`;
    const { t } = useI18n();
    const btnLoading = ref<boolean>(false);
    const incidentDetail = inject<Ref<IIncident>>('incidentDetail');
    const customLabelsList = ref([]);
    const editDialogRef = ref(null);
    const incidentDetailData = computed(() => {
      return JSON.parse(JSON.stringify(incidentDetail.value));
    });
    function valueChange(v) {
      emit('update:isShow', v);
    }
    const getLabelList = () => {
      const params = {
        strategy_id: 0,
      };
      strategyLabelList(params).then(res => {
        customLabelsList.value = res.custom.map(item =>
          Object.assign(item, { id: item.id.replace(/\//g, ''), name: item.label_name })
        );
      });
    };
    const editIncidentHandle = () => {
      editDialogRef.value?.validate().then(() => {
        btnLoading.value = true;
        const { incident_name, level, assignees, labels, incident_reason, id, incident_id } = incidentDetailData.value;
        editIncident({ incident_name, level, assignees, labels, incident_reason, incident_id, id })
          .then(() => {
            Message({
              theme: 'success',
              message: t('修改成功'),
            });
            nextTick(() => {
              valueChange(false);
              emit('editSuccess');
            });
          })
          .catch(() => {
            valueChange(true);
          })
          .finally(() => (btnLoading.value = false));
      });
    };
    const handleUserChange = v => {
      incidentDetailData.value.assignees = v;
    };
    onMounted(() => {
      getLabelList();
    });
    return {
      t,
      incidentDetailData,
      btnLoading,
      valueChange,
      editIncidentHandle,
      customLabelsList,
      editDialogRef,
      userApi,
      handleUserChange,
    };
  },
  render() {
    return (
      <Dialog
        ext-cls='failure-edit-dialog'
        v-slots={{
          footer: () => (
            <div>
              <Button
                loading={this.btnLoading}
                theme='primary'
                onClick={this.editIncidentHandle}
              >
                {this.t('确定')}
              </Button>
              <Button
                class='ml10'
                onClick={() => this.valueChange(false)}
              >
                {this.t('取消')}
              </Button>
            </div>
          ),
        }}
        dialog-type='operation'
        is-show={this.$props.visible}
        title={this.t('编辑故障属性')}
        onUpdate:isShow={this.valueChange}
      >
        <Form
          ref='editDialogRef'
          form-type={'vertical'}
          model={this.incidentDetailData}
        >
          <Form.FormItem
            label={this.t('故障名称')}
            property='incident_name'
            required
          >
            <Input
              v-model={this.incidentDetailData.incident_name}
              maxlength={50}
              placeholder={this.t('由中英文、下划线或数字组成')}
            />
          </Form.FormItem>
          <Form.FormItem
            label={this.t('故障级别')}
            property='level'
            required
          >
            <Radio.Group v-model={this.incidentDetailData.level}>
              {Object.values(this.$props.levelList || {}).map((item: any) => (
                <Radio label={item.name}>
                  <i class={`icon-monitor icon-${item.key} radio-icon ${item.key}`}></i>
                  {this.t(item.label)}
                </Radio>
              ))}
            </Radio.Group>
          </Form.FormItem>
          <Form.FormItem
            label={this.t('故障负责人')}
            property='assignees'
            required
          >
            <MemberSelector
              class='width-940'
              api={this.userApi}
              value={this.incidentDetailData.assignees}
              onChange={this.handleUserChange}
            ></MemberSelector>
          </Form.FormItem>
          <Form.FormItem label={this.t('故障标签')}>
            <TagInput
              v-model={this.incidentDetailData.labels}
              list={this.customLabelsList}
              trigger='focus'
              has-delete-icon
            />
          </Form.FormItem>
          <Form.FormItem label={this.t('故障原因')}>
            <Input
              v-model={this.incidentDetailData.incident_reason}
              maxlength={300}
              type='textarea'
            />
          </Form.FormItem>
        </Form>
      </Dialog>
    );
  },
});
