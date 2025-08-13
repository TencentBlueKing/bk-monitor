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
import { computed, defineComponent, ref, toRefs } from 'vue';

import { Button, Input, Loading, Popover } from 'bkui-vue';
import loadingImg from 'monitor-pc/static/images/svg/spinner.svg';
import { useI18n } from 'vue-i18n';

import { useTraceStore } from '../../../store/modules/trace';

import './handle-btn.scss';

const IProps = {
  accurateQuery: {
    // 精准查询
    type: Boolean,
    default: false,
  },
  canQuery: {
    // 查询按钮是否可用
    type: Boolean,
    default: false,
  },
  autoQuery: {
    // 是否开启自动查询
    type: Boolean,
    default: false,
  },
};

export default defineComponent({
  name: 'HandleBtn',
  props: IProps,
  emits: ['query', 'clear', 'add', 'changeAutoQuery'],
  setup(props, { emit }) {
    const store = useTraceStore();
    const { t } = useI18n();

    const favDescInput = ref('');
    const favLoading = ref(false);
    const favPopover = ref<HTMLDivElement>();

    const isLoading = computed<boolean>(() => store.loading);

    /** 查询 */
    const handleQuery = () => emit('query');

    /** 清空配置 */
    const handleClearAll = () => emit('clear');

    /**
     * @description: 保存收藏
     * @return {value: '收藏描述', hideCallback: '收藏成功隐藏回调', favLoadingCallBack: '收藏接口loading'}
     */
    const handleAddFav = () => {
      // const favObj = {
      //   value: favDescInput.value,
      //   hideCallback: handleCancelFav,
      //   favLoadingCallBack: (val: boolean) => favLoading.value = val
      // };
      emit('add', {
        value: favDescInput.value,
        hideCallback: handleCancelFav,
        favLoadingCallBack: (val: boolean) => (favLoading.value = val),
      });
    };

    /**
     * @description: 取消收藏
     */
    const handleCancelFav = () => {
      favDescInput.value = '';
      document.body.click();
      (favPopover.value as any)?.hide?.();
    };

    /** 切换自动查询 */
    const handleChangeAutoQuery = () => {
      if (isLoading.value) return;

      emit('changeAutoQuery', !props.autoQuery);
    };

    const { canQuery, autoQuery } = toRefs(props);

    return {
      canQuery,
      autoQuery,
      favPopover,
      handleQuery,
      handleClearAll,
      handleAddFav,
      favLoading,
      handleCancelFav,
      favDescInput,
      handleChangeAutoQuery,
      isLoading,
      t,
    };
  },

  render() {
    const { accurateQuery } = this.$props;
    return (
      <div class={['handle-btn-group', { 'is-accurate': accurateQuery }]}>
        <span style='display:flex;'>
          <Popover
            autoVisibility={false}
            content={`${this.autoQuery ? this.t('切换手动查询') : this.t('切换自动查询')}`}
          >
            <Button
              class='toggle-auto-button'
              onClick={this.handleChangeAutoQuery}
            >
              {this.isLoading ? (
                <img
                  class='status-loading'
                  alt=''
                  src={loadingImg}
                />
              ) : (
                <span class={`icon-monitor icon-${this.autoQuery ? 'weibiaoti519' : 'kaishi11'}`} />
              )}
            </Button>
          </Popover>
          <Button
            class='query-button'
            disabled={!this.canQuery || this.isLoading}
            theme='primary'
            onClick={this.handleQuery}
          >
            {`${this.autoQuery ? this.t('自动查询') : this.t('查询')}`}
          </Button>
        </span>
        {!accurateQuery && (
          <Popover
            ref='favPopover'
            v-slots={{
              content: () => (
                <div
                  class='favorite-pop-content'
                  onClick={e => {
                    e.stopPropagation();
                  }}
                >
                  <Loading loading={this.favLoading}>
                    <div class='fav-title'>{this.t('收藏描述')} : </div>
                    <div class='fav-main'>
                      <Input
                        v-model={this.favDescInput}
                        placeholder={this.t('输入')}
                      />
                      <span
                        class='fav-btn'
                        onClick={this.handleAddFav}
                      >
                        <i class='icon-monitor icon-mc-check-small' />
                      </span>
                      <span
                        class='fav-btn'
                        onClick={this.handleCancelFav}
                      >
                        <i class='icon-monitor icon-mc-close' />
                      </span>
                    </div>
                  </Loading>
                </div>
              ),
            }}
            autoVisibility={false}
            theme='light'
            trigger='click'
          >
            <Button>
              <i class='icon-monitor icon-mc-uncollect' />
              {this.t('收藏')}
            </Button>
          </Popover>
        )}
        <Popover
          autoVisibility={false}
          content={this.t('清空')}
        >
          <Button
            class='clear-button'
            onClick={this.handleClearAll}
          >
            <i class='icon-monitor icon-mc-clear-query' />
          </Button>
        </Popover>
      </div>
    );
  },
});
