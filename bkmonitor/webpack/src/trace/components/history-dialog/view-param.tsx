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
import { defineComponent } from 'vue';

import { Dialog, Tag } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './view-param.scss';

export default defineComponent({
  name: 'ViewParam',
  props: {
    title: {
      type: String,
      default: '标题',
    },
    visible: {
      type: Boolean,
      required: true,
    },
    list: {
      type: Array,
      default: () => [],
    },
    onChange: {
      type: Function,
      default: _v => {},
    },
  },
  setup(props) {
    const { t } = useI18n();
    /** 多租户人名改造 */
    const multiTenantWhitelist = [t('创建人'), t('最近更新人')];
    function valueChange(v) {
      props.onChange(v);
    }
    return {
      valueChange,
      multiTenantWhitelist,
    };
  },
  render() {
    return (
      <Dialog
        width={400}
        dialogType={'show'}
        isShow={this.visible}
        title={this.title}
        onUpdate:isShow={this.valueChange}
      >
        {(this.$slots?.default?.() as any)?.props ? (
          this.$slots?.default?.()
        ) : (
          <div class='param-body'>
            {this.list.map((item: any, index) => (
              <div
                key={index}
                class='item'
              >
                <div class='label'>{item.label} ：</div>
                {Array.isArray(item.value) ? (
                  <div class='value'>
                    {item.value.map(tag => (
                      <Tag key={tag}>{tag}</Tag>
                    ))}
                  </div>
                ) : this.multiTenantWhitelist.includes(item.label) && item.value ? (
                  <div class='value'>
                    <bk-user-display-name user-id={item.value} />
                  </div>
                ) : (
                  <div class='value'>{item.value || '--'}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </Dialog>
    );
  },
});
