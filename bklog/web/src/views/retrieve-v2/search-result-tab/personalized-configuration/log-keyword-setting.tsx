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

import { computed, defineComponent, ref } from 'vue';

import { t } from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { bkColorPicker, bkMessage, bkInfoBox } from 'bk-magic-vue';
import http from '@/api';

import LogKeywordFormDialog from './log-keyword-form-dialog';
import { ActionType, FormData, MatchType } from './types';

import './log-keyword-setting.scss';

export default defineComponent({
  name: 'LogKeywordSetting',
  components: {
    bkColorPicker,
    LogKeywordFormDialog,
  },
  setup() {
    const store = useStore();

    const dialogVisible = ref(false); // Dialog 显示状态
    const formData = ref<FormData | null>(null); // 表单数据
    const dialogType = ref<'create' | 'edit' | 'view'>('create'); // 对话框类型
    const editIndex = ref<number>(-1); // 编辑的索引

    // 打开新建对话框
    const handleNewClick = () => {
      formData.value = null;
      dialogType.value = 'create';
      editIndex.value = -1;
      dialogVisible.value = true;
    };

    // 打开编辑对话框
    const handleEditClick = (row: FormData, index: number) => {
      formData.value = { ...row }; // 设置要编辑的数据
      dialogType.value = 'edit'; // 设置为编辑模式
      editIndex.value = index; // 记录编辑的索引
      dialogVisible.value = true; // 打开对话框
    };

    // 删除确认
    const handleDelete = (row: any, index: number) => {
      bkInfoBox({
        type: 'warning',
        subTitle: t('当前任务名称为{n}，确认要删除？', { n: row.taskName }),
        confirmFn: async () => {
          try {
            // 1. 获取现有的配置数据
            const existingSettings = store.state.indexFieldInfo.custom_config?.personalization?.settings || [];

            // 2. 根据索引删除配置项
            const updatedSettings = [...existingSettings];
            updatedSettings.splice(index, 1);

            // 3. 调用API进行全量保存
            const resp = await http.request('retrieve/setIndexSetCustomConfig', {
              data: {
                index_set_id: store.state.indexId,
                index_set_ids: store.state.indexItem.ids,
                index_set_type: store.state.indexItem.isUnionIndex ? 'union' : 'single',
                index_set_config: {
                  personalization: {
                    settings: updatedSettings, // 保存过滤后的配置数组
                  },
                },
              },
            });

            if (resp.result) {
              // 4. API调用成功，更新store
              store.commit('updateIndexSetCustomConfig', {
                personalization: {
                  settings: structuredClone(updatedSettings),
                },
              });
            } else {
              // API调用失败，显示错误信息
              bkMessage({
                theme: 'error',
                message: resp.message,
              });
            }
          } catch (error) {
            console.error('删除配置失败:', error);
          }
        },
      });
    };

    // 处理对话框确认
    const handleDialogConfirm = async (data: FormData) => {
      try {
        // 1. 获取现有的配置数据
        const existingSettings = store.state.indexFieldInfo.custom_config?.personalization?.settings || [];

        // 2. 将新配置添加到现有配置中（如果是新建）
        // 或者替换现有配置（如果是编辑）
        let updatedSettings: any[];
        if (dialogType.value === 'create') {
          // 新建：添加到数组末尾
          updatedSettings = [...existingSettings, data];
        } else if (dialogType.value === 'edit') {
          // 编辑：根据索引替换对应的配置项
          updatedSettings = [...existingSettings];
          updatedSettings[editIndex.value] = data;
        }

        // 3. 调用API进行全量保存
        const resp = await http.request('retrieve/setIndexSetCustomConfig', {
          data: {
            index_set_id: store.state.indexId,
            index_set_ids: store.state.indexItem.ids,
            index_set_type: store.state.indexItem.isUnionIndex ? 'union' : 'single',
            index_set_config: {
              personalization: {
                settings: updatedSettings, // 保存完整的配置数组
              },
            },
          },
        });

        if (resp.result) {
          // 4. API调用成功，更新store
          store.commit('updateIndexSetCustomConfig', {
            personalization: {
              settings: structuredClone(updatedSettings),
            },
          });
        } else {
          // API调用失败，显示错误信息
          bkMessage({
            theme: 'error',
            message: resp.message,
          });
        }
      } catch (error) {
        console.error('保存配置失败:', error);
      } finally {
        dialogVisible.value = false;
        editIndex.value = -1; // 重置编辑索引
      }
    };

    // 表格数据
    const tableData = computed(() => {
      return store.state.indexFieldInfo.custom_config?.personalization?.settings || [];
    });

    // 类型插槽
    const actionTypeSlot = {
      default: ({ row }) => {
        const typeTextMap = {
          [ActionType.MARK]: t('标记'),
          [ActionType.JUMP]: t('跳转'),
          [ActionType.RELATED]: t('关联'),
        };

        return <div>{typeTextMap[row.actionType] || row.actionType}</div>;
      },
    };

    // 正则表达式插槽
    const regexSlot = {
      default: ({ row }) => {
        if (row.regex) {
          return <span>{row.regex}</span>;
        }
        return <span class='jump-link-placeholder'>--</span>;
      },
    };

    // 创建人插槽
    const creatorSlot = {
      default: ({ row }) => <bk-user-display-name user-id={row.creator}></bk-user-display-name>,
    };

    // 跳转链接插槽
    const jumpLinkSlot = {
      default: ({ row }) => {
        // 如果执行动作类型是跳转，则显示前往按钮，否则显示 /
        if (row.actionType === ActionType.JUMP) {
          return (
            <bk-button
              text
              theme='primary'
            >
              {t('前往')}
            </bk-button>
          );
        }
        return <span class='jump-link-placeholder'>--</span>;
      },
    };

    // 操作项插槽
    const operateSlot = {
      default: ({ row, $index }) => (
        <div>
          <bk-button
            text
            theme='primary'
            class='mr16'
            on-click={() => handleEditClick(row, $index)}
          >
            {t('编辑')}
          </bk-button>
          <bk-button
            text
            theme='primary'
            on-click={() => handleDelete(row, $index)}
          >
            {t('删除')}
          </bk-button>
        </div>
      ),
    };

    // 展开行插槽
    const expandSlot = {
      default: ({ row }: { row: FormData }) => {
        const {
          taskName,
          matchType,
          selectField,
          regex,
          actionType,
          tagName,
          color,
          jumpLink,
          relatedResource,
          creator,
        } = row;

        // 基础字段
        const basicList: Array<{ label: string; value: any; type?: string }> = [
          {
            label: t('任务名称'),
            value: taskName,
          },
          {
            label: t('匹配类型'),
            value: matchType === MatchType.FIELD ? t('字段匹配') : t('正则匹配'),
          },
          {
            label: matchType === MatchType.FIELD ? t('选择字段') : t('正则表达式'),
            value: matchType === MatchType.FIELD ? selectField : regex,
          },
          {
            label: t('执行动作'),
            value: actionType === ActionType.MARK ? t('标记') : actionType === ActionType.JUMP ? t('跳转') : t('关联'),
          },
        ];

        if (tagName) {
          basicList.push({ label: t('tag 名称'), value: tagName });
        }

        // 根据类型追加不同字段
        if (actionType === ActionType.MARK) {
          basicList.push({ label: t('tag 颜色'), value: color, type: 'color' });
        } else if (actionType === ActionType.JUMP) {
          basicList.push({ label: t('跳转链接'), value: jumpLink });
        } else if (actionType === ActionType.RELATED) {
          basicList.push({ label: t('关联资源'), value: relatedResource });
        }

        // 添加创建人
        basicList.push({ label: t('创建人'), value: creator, type: 'creator' });

        return (
          <div class='expand-content'>
            {basicList.map((item, index) => (
              <div
                class='expand-item'
                key={index}
              >
                {item.label && <span class='expand-label'>{item.label}：</span>}
                <span class='expand-value'>
                  {item.type === 'color' ? (
                    <div class='color-box'>
                      <span
                        class='color-circle'
                        style={{ background: item.value }}
                      ></span>
                      <span>{item.value}</span>
                    </div>
                  ) : item.type === 'creator' ? (
                    <bk-user-display-name user-id={item.value}></bk-user-display-name>
                  ) : (
                    item.value || '--'
                  )}
                </span>
              </div>
            ))}
          </div>
        );
      },
    };

    return () => (
      <div class='log-keyword-setting'>
        {/* 新建按钮 */}
        <bk-button
          theme='primary'
          class='new-button'
          title={t('新建')}
          on-click={() => handleNewClick()}
        >
          {t('新建')}
        </bk-button>
        {/* 表格部分 */}
        <bk-table data={tableData.value}>
          <bk-table-column
            type='expand'
            scopedSlots={expandSlot}
          />
          <bk-table-column
            label={t('任务名称')}
            prop='taskName'
            min-width='120'
          />
          <bk-table-column
            label={t('正则表达式')}
            prop='regex'
            min-width='200'
            scopedSlots={regexSlot}
          />
          <bk-table-column
            label={t('类型')}
            prop='actionType'
            width='120'
            scopedSlots={actionTypeSlot}
          />
          <bk-table-column
            label={t('创建人')}
            prop='creator'
            min-width='120'
            scopedSlots={creatorSlot}
          />
          <bk-table-column
            label={t('跳转链接')}
            prop='jumpLink'
            width='120'
            scopedSlots={jumpLinkSlot}
          />
          <bk-table-column
            label={t('操作')}
            width='150'
            scopedSlots={operateSlot}
          />
        </bk-table>
        {/* 新建日志关键字表单 */}
        <LogKeywordFormDialog
          visible={dialogVisible.value}
          formData={formData.value}
          type={dialogType.value}
          on-confirm={handleDialogConfirm}
          on-cancel={() => (dialogVisible.value = false)}
        />
      </div>
    );
  },
});
