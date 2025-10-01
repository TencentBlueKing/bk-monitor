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

import { defineComponent, ref, onMounted } from 'vue';

import useLocale from '@/hooks/use-locale';

import InfoTips from '../../common-comp/info-tips';
import $http from '@/api';

import './device-metadata.scss';
/**
 * 设备元数据
 */
export default defineComponent({
  name: 'DeviceMetadata',
  props: {
    valueList: {
      type: Array,
      default: () => [],
    },
  },

  emits: ['update'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const extraLabelList = ref([]);
    const groupList = ref([]);
    const selectValue = ref([]);

    onMounted(() => {
      getDeviceMetaData();
    });

    // 获取元数据
    const getDeviceMetaData = async () => {
      try {
        const res = await $http.request('linkConfiguration/getSearchObjectAttribute');
        const { scope = [], host = [] } = res.data;
        groupList.value.push(
          ...scope.map(item => {
            item.key = 'scope';
            return item;
          }),
        );
        groupList.value.push(
          ...host.map(item => {
            item.key = 'host';
            return item;
          }),
        );
        selectValue.value = props.valueList.map(item => {
          if (item.key.startsWith('host.')) {
            return item.key.slice(5);
          }
        });
        extraLabelList.value = props.valueList
          .filter(metadataItem => {
            const isDuplicate = groupList.value.some(groupItem => groupItem.field === metadataItem.key.slice(5));
            return !isDuplicate;
          })
          .map(item => {
            return {
              key: item.key,
              value: item.value,
              duplicateKey: false,
            };
          });
      } catch (e) {
        console.warn(e);
      }
    };
    const handleAdd = () => {
      emit('update', [...props.valueList, '']);
    };
    const handleDel = index => {
      const nextList = [...props.valueList];
      nextList.splice(index, 1);
      emit('update', nextList);
    };
    const handleChange = (index: number, val: any, key: string) => {
      const nextList = [...props.valueList];
      nextList[index][key] = String(val);
      emit('update', nextList);
    };
    const handleSelect = value => {
      selectValue.value = value;
    };
    const renderInputItem = (item, index) => (
      <div class='device-metadata-input-item'>
        <bk-input
          value={item.key}
          onInput={(val: any) => handleChange(index, val, 'key')}
        />
        <span class='symbol'>=</span>
        <bk-input
          value={item.value}
          onInput={(val: any) => handleChange(index, val, 'value')}
        />
        <span
          class='bk-icon icon-plus-circle-shape icons'
          on-Click={handleAdd}
        />
        <span
          class='bk-icon icon-minus-circle-shape icons'
          on-Click={() => handleDel(index)}
        />
      </div>
    );
    return () => (
      <div class='device-metadata-main'>
        <bk-select
          value={selectValue.value}
          display-tag
          multiple
          searchable
          on-selected={handleSelect}
        >
          {groupList.value.map(item => (
            <bk-option
              id={item.field}
              key={item.field}
              class='device-metadata-option'
              name={`${item.field}(${item.name})`}
            >
              <bk-checkbox
                class='mr-5'
                value={selectValue.value.includes(item.field)}
              />
              {`${item.field}(${item.name})`}
            </bk-option>
          ))}
        </bk-select>
        <div class='device-metadata-tips-box'>
          <span
            class='form-link'
            on-click={handleAdd}
          >
            {t('添加自定义标签')}
          </span>
          <InfoTips tips={t('如果CMDB的元数据无法满足您的需求，可以自行定义匹配想要的结果')} />
        </div>
        <div class='device-metadata-input-list'>
          {props.valueList.map((item: string, index: number) => renderInputItem(item, index))}
        </div>
      </div>
    );
  },
});
