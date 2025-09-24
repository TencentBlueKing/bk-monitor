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

import { defineComponent, ref, computed } from 'vue';

import { xssFilter } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import BkUserSelector from '@blueking/user-selector';
import { Message } from 'bk-magic-vue';

import http from '@/api';

import './intro-panel.scss';

export default defineComponent({
  name: 'IntroPanel',
  props: {
    isOpenWindow: {
      type: Boolean,
      default: true,
    },
  },
  setup(props, { emit }) {
    const store = useStore();
    const { t } = useLocale();

    const isShowDialog = ref(false);
    const formDataAdmin = ref<any[]>([]); // 用户数据名
    const baseAdmin = ref<any[]>([]); // 本人和列表里的人物，不能够进行删除操作
    const chatName = ref(''); // 群聊名称
    const userApi = (window as any).BK_LOGIN_URL;

    const userMeta = computed(() => store.state.userMeta);
    const globalsData = computed(() => store.getters['globals/globalsData']);
    const esSourceList = computed(() => globalsData.value.es_source_type || []);
    const customTypeIntro = computed(() => filterSourceShow(esSourceList.value) || []);

    const filterSourceShow = list => {
      const filterList = list.filter(item => item.help_md || item.button_list.length);
      // help_md赋值标题
      const showList = filterList.reduce((pre, cur) => {
        const helpMd = `<h1>${cur.name}</h1>\n${cur.help_md}`;
        pre.push({
          ...cur,
          help_md: helpMd,
        });
        return pre;
      }, []);
      return showList || [];
    };

    const handleActiveDetails = (state: boolean | null) => {
      emit('handle-active-details', state !== null ? state : !props.isOpenWindow);
    };

    const handleCreateAGroup = (adminList: any) => {
      isShowDialog.value = true;
      chatName.value = adminList.chat_name;
      formDataAdmin.value = adminList.users.concat([userMeta.value.username]);
      baseAdmin.value = structuredClone(formDataAdmin.value);
    };

    const handleSubmitQWGroup = async () => {
      const data = {
        user_list: formDataAdmin.value,
        name: chatName.value,
      };
      try {
        const res = await http.request('collect/createWeWork', { data });
        if (res.data) {
          Message({ theme: 'success', message: t('创建成功') });
          isShowDialog.value = false;
        }
      } catch {
        Message({ theme: 'error', message: t('创建失败') });
        isShowDialog.value = false;
      }
    };

    const handleCancelQWGroup = () => {
      formDataAdmin.value = [];
      baseAdmin.value = [];
      chatName.value = '';
      isShowDialog.value = false;
    };

    const handleChangePrincipal = (val: any[]) => {
      // 删除操作时保留原来的基础人员
      const setList = new Set([...baseAdmin.value, ...val]);
      formDataAdmin.value = [...setList];
    };

    return () => (
      <div class='illustrate-panel'>
        <div class={`right-window ${props.isOpenWindow ? 'window-active' : ''}`}>
          <div
            class='create-btn details'
            onClick={() => handleActiveDetails(null)}
          >
            <span
              style={props.isOpenWindow ? 'color:#3A84FF;' : ''}
              class='bk-icon icon-text-file'
            />
          </div>
          <div class='top-title'>
            <p>{t('说明文档')}</p>
            <div
              class='create-btn close'
              onClick={() => handleActiveDetails(false)}
            >
              <span class='bk-icon icon-minus-line' />
            </div>
          </div>
          <div class='help-main'>
            {customTypeIntro.value.map((item, index) => (
              <div
                key={`${index}-${item}`}
                class='help-md-container'
              >
                <div
                  class='help-md'
                  // @ts-expect-error
                  domPropsInnerHTML={xssFilter(item.help_md)}
                />
                {!!item.button_list.length &&
                  item.button_list.map((sItem, sIndex) =>
                    sItem.type === 'blank' ? (
                      <a
                        key={`${sIndex}-${sItem}`}
                        class='help-a-link'
                        href={sItem.url}
                        target='_blank'
                      >
                        {t('跳转至')}
                        {item.name}
                        <span class='bklog-icon bklog-tiaozhuan' />
                      </a>
                    ) : (
                      <bk-button
                        key={`${sIndex}-${sItem}`}
                        class='wx-button'
                        outline={true}
                        size='small'
                        theme='primary'
                        onClick={() => handleCreateAGroup(sItem)}
                      >
                        {t('一键拉群')}
                      </bk-button>
                    ),
                  )}
              </div>
            ))}
          </div>
        </div>
        <bk-dialog
          width={600}
          headerPosition='left'
          maskClose={false}
          theme='primary'
          title={t('一键拉群')}
          value={isShowDialog.value}
          onCancel={handleCancelQWGroup}
          onConfirm={handleSubmitQWGroup}
        >
          <div class='group-container'>
            <div class='group-title-container'>
              <div class='qw-icon'>
                <span class='bklog-icon bklog-qiyeweixin' />
              </div>
              <div class='hint'>
                <p>{t('一键拉群功能')}</p>
                <p>{t('可以通过企业微信将需求的相关人员邀请到一个群里进行讨论')}</p>
              </div>
            </div>
            <div class='group-body-container'>
              <BkUserSelector
                api={userApi}
                emptyText={t('无匹配人员')}
                placeholder={t('请选择群成员')}
                tagClearable={false}
                value={formDataAdmin.value}
                onChange={handleChangePrincipal}
              />
            </div>
          </div>
        </bk-dialog>
      </div>
    );
  },
});
