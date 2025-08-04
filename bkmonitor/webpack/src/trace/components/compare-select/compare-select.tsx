/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { computed, defineComponent, onMounted, ref, watch } from 'vue';

import { Button, Form, Input, Message, Popover } from 'bkui-vue';
import { applyTraceComparison, deleteTraceComparison, listTraceComparison } from 'monitor-api/modules/apm_trace';
import { useI18n } from 'vue-i18n';

import './compare-select.scss';

interface ICommonUsedItem {
  id: string;
  name: string;
  trace_id: string;
}

export default defineComponent({
  name: 'CompareSelect',
  props: {
    appName: {
      type: String,
      required: true,
    },
    targetTraceID: {
      type: String,
      default: '',
    },
  },
  emits: ['compare', 'cancel'],

  setup(props, { emit, expose }) {
    /** 对比目标 */
    const compareTarget = ref<string>('');
    /** 显示对比下拉框 */
    const showSelect = ref<boolean>(false);
    /** 显示设为常用 */
    const showCommonUsed = ref<boolean>(false);
    /** 显示删除确认 */
    const showDeleteConfirm = ref<boolean>(false);
    const compareSelectPopover = ref(null);
    const traceInput = ref(null);
    const commonUsedPopover = ref(null);
    const deleteConfirmPopover = ref(null);
    /** 常用参照表单 */
    const editForm = ref(null);
    /** 当前高亮临时/常用参照 */
    const curHoverTraceID = ref<string>('');
    const isHoverCommonList = ref<boolean>(false); // 鼠标hover常用列表项
    const isEditCommonUsed = ref<boolean>(false); // 当前是否编辑常用列表
    const deleteLoading = ref<boolean>(false);
    const submitLoading = ref<boolean>(false);
    // 设为常用表单
    const formData = ref({
      traceID: '',
      name: '',
    });
    // 临时对比 traceID
    const temporaryList = ref<string[]>([]);
    // 常用参照 traceID
    const commonUsedList = ref<ICommonUsedItem[]>([]);
    const compareTraceId = ref('');
    const { t } = useI18n();
    const rules = computed(() => ({
      traceID: [
        {
          validator: value => value.length,
          message: t('traceID不能为空'),
          trigger: 'blur',
        },
      ],
      name: [
        {
          validator: value => value.trim?.().length,
          message: t('参照名称不能为空'),
          trigger: 'blur',
        },
        {
          validator: value => !commonUsedList.value.some(item => item.name === value),
          message: t('参照名重复'),
          trigger: 'blur',
        },
      ],
    }));
    watch(
      () => showSelect.value,
      () => {
        temporaryList.value = JSON.parse(localStorage.getItem('trace_temporary_compare_ids')) || [];
        compareTraceId.value = '';
        curHoverTraceID.value = '';
        isHoverCommonList.value = false;
        showCommonUsed.value = false;
        showDeleteConfirm.value = false;
      }
    );
    onMounted(() => {
      compareTarget.value = props.targetTraceID || '';
      getCommomUsedList();
    });
    /** 获取常用参照列表 */
    const getCommomUsedList = () => {
      listTraceComparison({
        bk_biz_id: window.bk_biz_id,
        app_name: props.appName,
      }).then(res => (commonUsedList.value = res?.data || []));
    };
    /** 关闭对比选择框 */
    const closeSelect = () => {
      compareTraceId.value = '';
      compareSelectPopover.value.hide();
    };
    /** 打开对比选项 */
    const handleSelectShow = () => {
      showSelect.value = true;
      setTimeout(() => {
        traceInput.value.focus();
      }, 100);
    };
    const handleMouseEnter = (data, isEdit = false) => {
      if (showCommonUsed.value) return;

      if (isEdit) {
        const { trace_id: traceID, name } = data;
        isHoverCommonList.value = true;
        isEditCommonUsed.value = true;
        curHoverTraceID.value = traceID;
        formData.value = { traceID, name };
      } else {
        curHoverTraceID.value = data;
        isHoverCommonList.value = false;
        isEditCommonUsed.value = false;
        formData.value = { traceID: data, name: '' };
      }
    };
    const handleMouseleave = () => {
      if (!showCommonUsed.value && !showDeleteConfirm.value) {
        curHoverTraceID.value = '';
        isHoverCommonList.value = false;
      }
    };
    /** 设为常用表单 取消 */
    const handleCloseCommonUsed = () => {
      commonUsedPopover.value.hide();
    };
    /** 提交设为常用 */
    const handleSubmitCommonUsed = async () => {
      await editForm.value
        .validate()
        .then(async () => {
          const { traceID, name } = formData.value;
          submitLoading.value = true;
          await applyTraceComparison({
            bk_biz_id: window.bk_biz_id,
            app_name: props.appName,
            trace_id: traceID,
            name,
          })
            .then(() => {
              Message({
                theme: 'success',
                message: t('保存成功'),
                width: 200,
              });
              handleCloseCommonUsed();
              getCommomUsedList();
            })
            .finally(() => (submitLoading.value = false));
        })
        .catch(err => console.log(err));
    };
    /** 对比 */
    const handleCompare = () => {
      if (!compareTraceId.value.trim().length) return;
      compareTarget.value = compareTraceId.value;
      emit('compare', compareTraceId.value);
      closeSelect();
    };
    /** 清空临时对比 */
    const handleClearTemporary = () => {
      temporaryList.value = [];
      localStorage.setItem('trace_temporary_compare_ids', JSON.stringify([]));
    };
    /** 选择临时对比 */
    const handleSelectTemporary = traceID => {
      compareTarget.value = traceID;
      emit('compare', traceID);
      closeSelect();
    };
    /** 选择常用参照对比 */
    const handleSelectCommonUsed = (data: ICommonUsedItem) => {
      const { trace_id: traceID, name } = data;
      compareTarget.value = name;
      emit('compare', traceID);
      closeSelect();
    };
    /** 删除常用参照 */
    const handleDeleteCommon = async traceID => {
      deleteLoading.value = true;
      await deleteTraceComparison({
        bk_biz_id: window.bk_biz_id,
        app_name: props.appName,
        trace_id: traceID,
      })
        .then(() => {
          Message({
            theme: 'success',
            message: t('删除成功'),
          });
          handleCloseCommonUsed();
          getCommomUsedList();
        })
        .finally(() => (deleteLoading.value = false));
    };
    /** 取消对比 */
    const handleCancelCompare = e => {
      e?.stopPropagation?.();
      compareTarget.value = '';
      emit('cancel');
    };
    /** 清空对比输入框内容 */
    const clearCompareTarget = () => {
      compareTarget.value = '';
    };
    /** 关闭删除确认 */
    const handleCloseDeleteConfirm = () => {
      deleteConfirmPopover.value.hide();
    };
    const handleMouseEnterHeader = () => {
      if (compareTraceId.value.trim?.().length) {
        formData.value = { traceID: compareTraceId.value, name: '' };
      }
    };
    expose({
      handleCancelCompare,
      clearCompareTarget,
    });

    return {
      compareSelectPopover,
      commonUsedPopover,
      deleteConfirmPopover,
      showSelect,
      showCommonUsed,
      traceInput,
      closeSelect,
      compareTraceId,
      handleSelectShow,
      temporaryList,
      commonUsedList,
      handleMouseEnter,
      handleMouseleave,
      curHoverTraceID,
      isHoverCommonList,
      formData,
      rules,
      editForm,
      handleCloseCommonUsed,
      handleSubmitCommonUsed,
      handleCompare,
      handleClearTemporary,
      handleDeleteCommon,
      showDeleteConfirm,
      handleCloseDeleteConfirm,
      handleSelectTemporary,
      handleSelectCommonUsed,
      compareTarget,
      handleCancelCompare,
      deleteLoading,
      handleMouseEnterHeader,
      submitLoading,
      isEditCommonUsed,
      t,
    };
  },
  render() {
    const setCommonUsed = isEdit => (
      <Popover
        ref='commonUsedPopover'
        v-slots={{
          content: () => (
            <Form
              ref='editForm'
              class='edit-form'
              form-type='vertical'
              model={this.formData}
              rules={this.rules}
            >
              <Form.FormItem
                label='TraceID'
                property='traceID'
              >
                <Input
                  v-model={this.formData.traceID}
                  disabled={this.isEditCommonUsed}
                  showOverflowTooltips={false}
                />
              </Form.FormItem>
              <Form.FormItem
                label={this.t('参照名称')}
                property='name'
              >
                <Input
                  v-model={this.formData.name}
                  maxlength={16}
                />
              </Form.FormItem>
              <Form.FormItem class='submit-form-item'>
                <Button
                  class='confirm'
                  loading={this.submitLoading}
                  size='small'
                  theme='primary'
                  onClick={this.handleSubmitCommonUsed}
                >
                  {this.t('确定')}
                </Button>
                <Button
                  size='small'
                  onClick={this.handleCloseCommonUsed}
                >
                  {this.t('取消')}
                </Button>
              </Form.FormItem>
            </Form>
          ),
        }}
        boundary='#compareSelectContent'
        offset={isEdit ? 0 : 6}
        placement={isEdit ? 'bottom-start' : 'bottom-end'}
        theme='light common-used-popover'
        trigger='click'
        onAfterHidden={() => {
          this.showCommonUsed = false;
          this.curHoverTraceID = '';
        }}
        onAfterShow={() => (this.showCommonUsed = true)}
      >
        {isEdit ? (
          <i
            class='icon-monitor icon-bianji'
            onClick={e => e.stopPropagation()}
          />
        ) : (
          <span class='common-used'>{this.t('设为常用')}</span>
        )}
      </Popover>
    );

    return (
      <Popover
        ref='compareSelectPopover'
        v-slots={{
          content: () => (
            <div
              id='compareSelectContent'
              class='compare-select-content'
            >
              <div class='header'>
                <Input
                  ref='traceInput'
                  class='trace-input'
                  v-model={this.compareTraceId}
                  v-slots={{
                    suffix: () => (
                      <span
                        class='suffix-btn'
                        onClick={this.handleCompare}
                      >
                        {this.t('对比')}
                      </span>
                    ),
                  }}
                  placeholder={this.t('请输入Trace ID')}
                  showOverflowTooltips={false}
                  onChange={this.handleMouseEnterHeader}
                  onEnter={this.handleCompare}
                />
                {}
                {this.commonUsedList.length === 5 ? ( // 常用参照数量上限为 5
                  <Popover
                    content={this.t('已达上限，请先删除后再新增')}
                    placement='top'
                  >
                    <span class='disable-text'>{this.t('设为常用')}</span>
                  </Popover>
                ) : this.compareTraceId.trim?.().length ? (
                  setCommonUsed(false)
                ) : (
                  <Button
                    class='normal-text'
                    disabled
                    text
                  >
                    {this.t('设为常用')}
                  </Button>
                )}
              </div>
              <div class='content'>
                {this.temporaryList.length ? (
                  <div class='id-list temporary-list'>
                    <div class='id-list-header'>
                      <span onClick={this.closeSelect}>{this.t('临时对比')}</span>
                      <div
                        class='tools'
                        onClick={this.handleClearTemporary}
                      >
                        <i class='icon-monitor icon-mc-clear-query' />
                        <span>{this.t('清空')}</span>
                      </div>
                    </div>
                    {this.temporaryList.map(item => (
                      <div
                        key={item}
                        class='id-list-item'
                        onMouseenter={() => this.handleMouseEnter(item)}
                        onMouseleave={() => this.handleMouseleave()}
                      >
                        <span
                          class='text'
                          onClick={() => this.handleSelectTemporary(item)}
                        >
                          {item}
                        </span>
                        {}
                        {!this.isHoverCommonList && item === this.curHoverTraceID ? (
                          this.commonUsedList.length === 5 ? (
                            <Popover
                              content={this.t('已达上限，请先删除后再新增')}
                              placement='top'
                              popoverDelay={[500, 0]}
                            >
                              <span class='disable-text'>{this.t('设为常用')}</span>
                            </Popover>
                          ) : (
                            setCommonUsed(false)
                          )
                        ) : (
                          ''
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  ''
                )}
                {this.commonUsedList.length && this.temporaryList.length ? <div class='list-divider' /> : ''}
                {this.commonUsedList.length ? (
                  <div class='id-list common-used-list'>
                    <div class='id-list-header'>
                      <span>{this.t('常用参照')}</span>
                      <div class='tools'>{`${this.commonUsedList.length}/5`}</div>
                    </div>
                    {this.commonUsedList.map(item => (
                      <div
                        key={item.trace_id}
                        class='id-list-item'
                        onClick={() => this.handleSelectCommonUsed(item)}
                        onMouseenter={() => this.handleMouseEnter(item, true)}
                        onMouseleave={() => this.handleMouseleave()}
                      >
                        <div class='refer-name'>
                          <span>{item.name}</span>
                          {this.isHoverCommonList && item.trace_id === this.curHoverTraceID ? setCommonUsed(true) : ''}
                        </div>
                        <div class='trace-id'>{item.trace_id}</div>
                        {this.isHoverCommonList && item.trace_id === this.curHoverTraceID ? (
                          <Popover
                            ref='deleteConfirmPopover'
                            width={260}
                            height={100}
                            v-slots={{
                              content: () => (
                                <div class='delete-confirm'>
                                  <div class='content'>{this.t('确认删除该常用参照吗？')}</div>
                                  <div class='footer'>
                                    <Button
                                      class='confirm'
                                      loading={this.deleteLoading}
                                      size='small'
                                      theme='primary'
                                      onClick={() => this.handleDeleteCommon(item.trace_id)}
                                    >
                                      {this.t('确定')}
                                    </Button>
                                    <Button
                                      size='small'
                                      onClick={this.handleCloseDeleteConfirm}
                                    >
                                      {this.t('取消')}
                                    </Button>
                                  </div>
                                </div>
                              ),
                            }}
                            boundary='#compareSelectContent'
                            placement='bottom-start'
                            theme='light delete-confirm-popover'
                            trigger='click'
                            onAfterHidden={() => {
                              this.showDeleteConfirm = false;
                              this.curHoverTraceID = '';
                            }}
                            onAfterShow={() => (this.showDeleteConfirm = true)}
                          >
                            <i
                              class='icon-monitor icon-mc-delete-line delete-btn'
                              onClick={e => e.stopPropagation()}
                            />
                          </Popover>
                        ) : (
                          ''
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  ''
                )}
              </div>
            </div>
          ),
        }}
        arrow={false}
        placement='bottom-start'
        theme='light trace-compare-select-popover'
        trigger='click'
        onAfterHidden={() => {
          this.showSelect = false;
          this.isEditCommonUsed = false;
        }}
        onAfterShow={this.handleSelectShow}
      >
        <div class='trace-compare-select-trigger'>
          <div class='prefix'>{this.t('对比')}</div>
          <div class={['compare-target', { active: this.showSelect }]}>
            {this.compareTarget.trim?.().length ? (
              [
                <span
                  key='compare-target-text'
                  class='target-text'
                  title={this.compareTarget}
                >
                  {this.compareTarget}
                </span>,
                <i
                  key='compare-target-icon'
                  class='icon-monitor icon-mc-close-fill'
                  onClick={this.handleCancelCompare}
                />,
              ]
            ) : (
              <span class='empty-compare-text'>{this.t('暂不对比')}</span>
            )}
          </div>
        </div>
      </Popover>
    );
  },
});
