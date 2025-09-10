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

import { defineComponent, ref } from 'vue';

import useLocale from '@/hooks/use-locale';

import { useOperation } from '../../hook/useOperation';
import BaseInfo from '../business-comp/step2/base-info';
import DragTag from '../common-comp/drag-tag';
import InfoTips from '../common-comp/info-tips';

import './step2-bk-data-collection.scss';

export default defineComponent({
  name: 'StepBkDataCollection',

  emits: ['next', 'prev'],

  setup(props, { emit }) {
    console.log('props', props);
    const { t } = useLocale();
    const { cardRender } = useOperation();
    const isShowDialog = ref(false);
    const sortFieldList = ref([
      { id: 'hello', label: 'hello' },
      { id: 'world', label: 'world' },
      { id: '5000140_bcs', label: '5000140_bcs' },
      { id: 'log_mosc', label: 'log_mosc' },
      { id: 'bcs_sys_log', label: 'bcs_sys_log' },
      { id: 'bcs_sys_', label: 'bcs_sys_' },
    ]);
    const valueList = ref([
      { id: '5000140_bcs_sys_log_mosc', label: '5000140_bcs_sys_log_mosc' },
      { id: '5000140_bcs_sys_log_hello', label: '5000140_bcs_sys_log_hello' },
      { id: '5000140_bcs_sys_log', label: '5000140_bcs_sys_log' },
      { id: '5000140_bcs_sys_log_mosc1', label: '5000140_bcs_sys_log_mosc1' },
      { id: '5000140_bcs_sys_log_hello1', label: '5000140_bcs_sys_log_hello1' },
      { id: '5000140_bcs_sys_log1', label: '5000140_bcs_sys_log1' },
      { id: '5000140_bcs_sys_log_mosc2', label: '5000140_bcs_sys_log_mosc2' },
      { id: '5000140_bcs_sys_log_hello2', label: '5000140_bcs_sys_log_hello2' },
      { id: '5000140_bcs_sys_log2', label: '5000140_bcs_sys_log2' },
    ]);

    const handleAddDataSource = () => {
      isShowDialog.value = true;
    };
    const handleCancel = () => {
      isShowDialog.value = false;
    };

    /** 基本信息 */
    const renderBaseInfo = () => <BaseInfo typeKey='bk-data' />;
    /** 数据源 */
    const renderDataSource = () => (
      <div class='data-source-box'>
        <div class='label-form-box'>
          <span class='label-title'>{t('数据源')}</span>
          <div class='form-box'>
            <DragTag
              addType={'custom'}
              sortable={false}
              on-custom-add={handleAddDataSource}
            />
            <div class='data-source-table'>
              <bk-table data={[]}>
                <bk-table-column
                  label={t('名称')}
                  prop='ip'
                />
                <bk-table-column
                  label={t('类型')}
                  prop='source'
                />
              </bk-table>
            </div>
          </div>
        </div>
      </div>
    );
    /** 字段设置 */
    const renderFieldSetting = () => (
      <div class='field-setting-box'>
        <bk-alert
          class='field-setting-alert'
          title={t('未匹配到对应字段，请手动指定字段后提交。')}
          type='warning'
        />
        <div class='label-form-box'>
          <span class='label-title'>{t('目标字段')}</span>
          <div class='form-box'>
            <bk-select
              class='select-sort'
              multiple
            />
            <InfoTips
              class='block'
              tips={t('用于标识日志文件来源及唯一性')}
            />
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title'>{t('排序字段')}</span>
          <div class='form-box'>
            <DragTag
              addType={'select'}
              selectList={sortFieldList.value}
              value={valueList.value}
            />
            <InfoTips
              class='block'
              tips={t('用于控制日志排序的字段')}
            />
          </div>
        </div>
      </div>
    );
    const cardConfig = [
      {
        title: t('基础信息'),
        key: 'baseInfo',
        renderFn: renderBaseInfo,
      },
      {
        title: t('数据源'),
        key: 'dataSource',
        renderFn: renderDataSource,
      },
      {
        title: t('字段设置'),
        key: 'fieldSetting',
        renderFn: renderFieldSetting,
      },
    ];
    return () => (
      <div class='operation-step2-bk-data-collection'>
        {cardRender(cardConfig)}
        <div class='classify-btns-fixed'>
          <bk-button
            class='mr-8'
            on-click={() => {
              emit('prev');
            }}
          >
            {t('上一步')}
          </bk-button>
          <bk-button
            class='width-88 mr-8'
            theme='primary'
          >
            {t('提交')}
          </bk-button>
          <bk-button>{t('取消')}</bk-button>
        </div>
        <bk-dialog
          width={680}
          ext-cls='bk-data-index-dialog'
          header-position={'left'}
          mask-close={false}
          ok-text={t('添加')}
          theme='primary'
          title={t('新增索引')}
          value={isShowDialog.value}
          on-cancel={handleCancel}
        >
          <bk-form label-width={60}>
            <bk-form-item
              label={t('索引')}
              property={'name'}
              required={true}
            >
              <bk-select searchable />
            </bk-form-item>
            <bk-form-item>
              <bk-table
                key={isShowDialog.value}
                data={[]}
              >
                <bk-table-column
                  label={t('名称')}
                  prop='ip'
                />
                <bk-table-column
                  label={t('类型')}
                  prop='source'
                />
              </bk-table>
            </bk-form-item>
          </bk-form>
        </bk-dialog>
      </div>
    );
  },
});
