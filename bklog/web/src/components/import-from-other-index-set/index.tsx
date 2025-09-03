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
import { defineComponent, ref, watch, computed } from 'vue';
import useLocale from '@/hooks/use-locale';
import * as authorityMap from '@/common/authority-map';
import useStore from '@/hooks/use-store';
import $http from '@/api';
import { base64Decode } from '@/common/util';

import './index.scss';

export default defineComponent({
  name: 'OtherImport',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    const formRef = ref(null);
    const indexSetList = ref([]);
    const isShow = ref(false);
    const confirmLoading = ref(false);
    const indexSetLoading = ref(false);
    const indexSetData = ref({
      index_set_id: '',
      export_type: 'replace',
    });
    const indexSetRules = {
      index_set_id: [
        {
          validator: (value: string) => !!value,
          message: t('不能为空'),
          trigger: 'blur',
        },
      ],
    };

    const configId = computed(() => store.state.indexSetFieldConfig.clean_config?.extra.collector_config_id);

    let rulesList = [];

    watch(
      () => props.isShow,
      () => {
        isShow.value = props.isShow;
      },
      {
        immediate: true,
      },
    );

    const base64ToRuleArr = (str: string) => {
      if (!str) {
        return [];
      }

      try {
        const ruleList = JSON.parse(base64Decode(str));
        const ruleNewList = ruleList.reduce((pre, cur, index) => {
          const itemObj = {} as any;
          const matchVal = cur.match(/:(.*)/);
          const key = cur.substring(0, matchVal.index);
          itemObj[key] = matchVal[1];
          itemObj.__Index__ = index;
          pre.push(itemObj);
          return pre;
        }, []);
        return ruleNewList;
      } catch (e) {
        return [];
      }
    };

    const requestIndexSetList = () => {
      indexSetLoading.value = true;
      $http
        .request('retrieve/getIndexSetList', {
          query: {
            space_uid: store.state.spaceUid,
          },
        })
        .then(res => {
          if (res.data.length) {
            const list = [];
            for (const item of res.data) {
              if (item.permission?.[authorityMap.SEARCH_LOG_AUTH] && item.tags.map(item => item.tag_id).includes(8)) {
                list.push({
                  name: item.index_set_name,
                  id: item.index_set_id,
                });
              }
            }
            indexSetList.value = list;
          }
        })
        .catch(e => {
          console.error(e);
        })
        .finally(() => {
          indexSetLoading.value = false;
        });
    };

    const handleOpenToggle = (isShow: boolean) => {
      emit('show-change', isShow);
      if (isShow) {
        requestIndexSetList();
      } else {
        indexSetData.value.index_set_id = '';
        indexSetData.value.export_type = 'replace';
        indexSetList.value = [];
      }
    };

    const getClusterConfig = indexSetID => {
      try {
        const params = { index_set_id: indexSetID };
        const data = { collector_config_id: configId.value };
        return $http.request('/logClustering/getConfig', { params, data });
      } catch (e) {
        console.warn(e);
      }
    };

    const mergeAndDeduplicate = (arr1: number[], arr2: number[]) => {
      // 合并两个数组
      const combinedArray = [...arr1, ...arr2];
      // 创建一个集合用于去重
      const uniqueSet = new Set();
      // 结果数组
      const resultArray = [];
      combinedArray.forEach(item => {
        // 将对象转换为字符串进行比较，忽略 __Index__
        const key = Object.entries(item)
          .filter(([k]) => k !== '__Index__')
          .map(([k, v]) => `${k}:${v}`)
          .sort()
          .join('|');

        // 如果集合中没有该字符串，则添加到结果数组和集合中
        if (!uniqueSet.has(key)) {
          uniqueSet.add(key);
          resultArray.push(item);
        }
      });
      return resultArray;
    };

    const handleConfirm = () => {
      formRef.value
        .validate()
        .then(async () => {
          confirmLoading.value = true;
          const { index_set_id, export_type } = indexSetData.value;
          const res = await getClusterConfig(index_set_id);
          const importRuleArr = base64ToRuleArr(res.data.predefined_varibles);
          rulesList = export_type === 'replace' ? importRuleArr : mergeAndDeduplicate(importRuleArr, rulesList);
          isShow.value = false;
          emit('success', rulesList);
        })
        .catch(e => console.error(e))
        .finally(() => {
          confirmLoading.value = false;
        });
    };

    return () => (
      <bk-dialog
        width={640}
        ext-cls='add-rule'
        value={isShow.value}
        header-position='left'
        mask-close={false}
        title={t('其他索引集导入')}
        auto-close={false}
        loading={confirmLoading.value}
        on-value-change={handleOpenToggle}
        on-confirm={handleConfirm}
      >
        <bk-form
          ref={formRef}
          label-width={90}
          {...{
            props: {
              model: indexSetData.value,
              rules: indexSetRules,
            },
          }}
        >
          <bk-form-item
            label={t('选择索引集')}
            property='index_set_id'
            required
          >
            <bk-select
              style='width: 100%'
              value={indexSetData.value.index_set_id}
              v-bkloading={{ isLoading: indexSetLoading.value, size: 'small' }}
              clearable={false}
              searchable
              on-change={value => (indexSetData.value.index_set_id = value)}
            >
              {indexSetList.value.map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                />
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item
            label={t('导入模式')}
            class='bk-form-control'
            required
          >
            <bk-radio-group
              value={indexSetData.value.export_type}
              on-change={value => (indexSetData.value.export_type = value)}
            >
              <bk-radio value='replace'> {t('替换')} </bk-radio>
              <bk-radio value='assign'> {t('补齐')} </bk-radio>
            </bk-radio-group>
          </bk-form-item>
        </bk-form>
      </bk-dialog>
    );
  },
});
