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
import { computed, defineComponent, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import { bkMessage } from 'bk-magic-vue';

import useStore from '../../../../hooks/use-store';
import RetrieveHelper from '../../../retrieve-helper';

export default defineComponent({
  props: {
    type: {
      type: String as PropType<
        'empty' | 'error' | 'hidden' | 'index-set-field-not-found' | 'index-set-not-found' | 'loading' | 'search-empty'
      >,
      default: 'hidden',
    },
    message: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    const { $t } = useLocale();
    const store = useStore();
    const isFieldSettingShow = computed(() => {
      return !(store.getters.isUnionSearch || isExternal.value);
    });

    const hasCollectorConfigId = computed(() => {
      const indexSetList = store.state.retrieve.flatIndexSetList;
      const indexSetId = store.state.indexId;
      const currentIndexSet = indexSetList.find(item => item.index_set_id === indexSetId);
      return currentIndexSet?.collector_config_id;
    });

    const isExternal = computed(() => store.state.isExternal);
    const openConfiguration = () => {
      if (isFieldSettingShow.value && store.state.spaceUid && hasCollectorConfigId.value) {
        RetrieveHelper.setIndexConfigOpen(true);
      } else {
        bkMessage({
          theme: 'primary',
          message: '第三方ES、计算平台索引集类型不支持自定义分词',
        });
      }
    };

    const getExceptionRender = () => {
      if (props.type === 'loading') {
        return (
          <bk-exception
            style='margin-top: 100px;'
            class='exception-wrap-item exception-part'
            scene='part'
            type='search-empty'
          >
            {$t('检索中')}...
          </bk-exception>
        );
      }

      if (props.type === 'search-empty') {
        return (
          <div class='bklog-empty-data'>
            <h1>{$t('检索无数据')}</h1>
            <div class='sub-title'>{$t('您可按照以下顺序调整检索方式')}</div>
            <div class='empty-validate-steps'>
              <div class='validate-step1'>
                <h3>1. {$t('优化查询语句')}</h3>
                <div class='step1-content'>
                  <span class='step1-content-label'>{$t('查询范围')}：</span>
                  <span class='step1-content-value'>
                    log: bklog*
                    <br />
                    {$t('包含')} bklog
                    <br />= bklog {$t('使用通配符')} (*)
                  </span>
                </div>
                <div class='step1-content'>
                  <span class='step1-content-label'>{$t('精准匹配')}：</span>
                  <span class='step1-content-value'>log: "bklog"</span>
                </div>
              </div>
              <div class='validate-step2'>
                <h3>2. {$t('检查是否为分词问题')}</h3>
                <div>
                  {$t('当您的鼠标移动至对应日志内容上时，该日志单词将展示为蓝色。')}
                  <br />
                  <br />
                  {$t('若目标内容为整段蓝色，或中间存在字符粘连的情况。')}
                  <br />
                  {$t('可能是因为分词导致的问题')}；
                  <br />
                  <span
                    class='segment-span-tag'
                    onClick={openConfiguration}
                  >
                    {$t('点击设置自定义分词')}
                  </span>
                  <br />
                  <br />
                  {$t('将字符粘连的字符设置至自定义分词中，等待 3～5 分钟，新上报的日志即可生效设置。')}
                </div>
              </div>
              <div class='validate-step3'>
                <h3>3.{$t('一键反馈')}</h3>
                <div>
                  {$t('若您仍无法确认问题原因，请点击下方反馈按钮与我们联系，平台将第一时间响应处理。')}
                  <br />
                  {/* <span class='segment-span-tag'>问题反馈</span> */}
                  <a
                    class='segment-span-tag'
                    href={'wxwork://message/?username=BK助手'}
                  >
                    {$t('问题反馈')}
                  </a>
                </div>
              </div>
            </div>
          </div>
        );
      }

      if (props.type === 'index-set-not-found') {
        return (
          <bk-exception
            style='margin-top: 100px;'
            class='exception-wrap-item exception-part'
            scene='part'
            type='500'
          >
            <div style='text-align: left; color: #313238;'>
              <div style='font-size: 14px; padding: 8px 0;'>{`找不到索引集“${props.message.replace(/^index-set-not-found:\((.*)\)/, '$1')}”的相关信息`}</div>
              <div style='font-size: 12px; color: #4d4f56;'>
                <div>您可以进行如下操作：</div>
                <div style='padding: 8px 0;'>1. 点击左上角重新选择索引集</div>
                <div>
                  2. 请检查顶部 URL 中的ID 是否正确。
                  <br />
                  参考格式： https://domain.com/#/retrieve/<mark>82600?</mark>
                </div>
              </div>
            </div>
          </bk-exception>
        );
      }

      if (props.type === 'index-set-field-not-found') {
        return (
          <bk-exception
            style='margin-top: 100px;'
            class='exception-wrap-item exception-part'
            scene='part'
            type='500'
          >
            <div style='text-align: left; color: #313238;'>
              <div style='font-size: 14px; padding: 8px 0;'>
                {'索引集字段列表查询失败，刷新页面尝试重新查询 '}
                <span
                  style={{ cursor: 'pointer', color: '#3a84ff' }}
                  onClick={() => window.location.reload()}
                >
                  刷新
                </span>
              </div>
            </div>
          </bk-exception>
        );
      }

      if (props.type === 'error') {
        return (
          <bk-exception
            style='margin-top: 100px;'
            class='exception-wrap-item exception-part'
            scene='part'
            type='search-empty'
          >
            {props.message}
          </bk-exception>
        );
      }

      return null;
    };

    return getExceptionRender;
  },
});
