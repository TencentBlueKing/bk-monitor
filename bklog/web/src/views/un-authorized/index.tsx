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
import { computed, defineComponent, ref, watch } from 'vue';
import { join } from '@/global/utils/path';
import { t } from '@/hooks/use-locale';
import useRoute from '@/hooks/use-route';
import useRouter from '@/hooks/use-router';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { pickCurrentTenantId, resolveSpaceUnauthorizedMode } from './tenant-mismatch';

import './index.scss';

export default defineComponent({
  name: 'UnAuthorized',
  props: {
    type: { type: String, default: '' },
  },
  setup(props) {
    const route = useRoute();
    const router = useRouter();
    const store = useStore();
    const exceptionType = computed(() => props.type || route.query.type);
    const isExternal = computed(() => store.state.isExternal);
    const tenantMismatch = computed(() => store.state.tenantMismatch || {});
    const currentTenant = computed(() =>
      pickCurrentTenantId(tenantMismatch.value.current_tenant_id, store.state.userMeta?.bk_tenant_id),
    );
    const targetTenant = computed(() => `${tenantMismatch.value.target_tenant_id || ''}`.trim());
    const isCrossTenant = computed(
      () => resolveSpaceUnauthorizedMode(currentTenant.value, targetTenant.value) === 'cross-tenant',
    );
    const guideDialog = ref<'space' | 'indexset'>('space');
    const isGuideDialogVisible = ref(false);

    watch([exceptionType, isExternal, isCrossTenant], () => {
      isGuideDialogVisible.value = false;
    });

    const handleOpenGuide = (mode: 'space' | 'indexset') => {
      guideDialog.value = mode;
      isGuideDialogVisible.value = true;
    };

    const handleCloseGuide = () => {
      isGuideDialogVisible.value = false;
    };

    const handleApplyPermission = () => {
      const url = (window as any).BK_IAM_URL;
      url && window.open(join(url, '/apply-join-user-group'));
    };

    const handleCreateCollection = () => {
      handleCloseGuide();
      router.push({
        name: 'collectAdd',
        query: {
          spaceUid: store.state.spaceUid,
          bizId: store.state.bkBizId,
          step: '1',
        },
      });
    };

    /**
     * 移除业务参数重试
     * @returns
     */
    const handleRetry = () => {
      store.commit('updateStorage', {
        [BK_LOG_STORAGE.BK_SPACE_UID]: undefined,
        [BK_LOG_STORAGE.BK_BIZ_ID]: undefined,
      });

      const resolver = router.resolve({
        name: 'retrieve',
        params: {
          indexId: undefined,
        },
        query: {
          ...route.query,
          spaceUid: undefined,
          bizId: undefined,
          bkBizId: undefined,
          type: undefined,
          page_from: undefined,
        },
      });

      window.open(resolver.href, '_self');
    };

    const renderAssistantLink = (label = t('联系BK助手'), extraClass = '') => (
      <a
        class={['un-authorized-assistant', extraClass]}
        href='wxwork://message/?username=BK助手'
      >
        {label}
      </a>
    );

    const getExceptionText = () => {
      if (exceptionType.value === 'api') {
        return t('API无权限，请联系管理员申请');
      }
      return (
        <span>
          {t('无权限，请')} {renderAssistantLink()}
        </span>
      );
    };

    const renderGuide = (mode: 'space' | 'indexset' | 'tenant-mismatch') => {
      const guide = {
        space: {
          title: t('按业务角色申请权限'),
          note: t('用户组权限不足？在权限中心选择日志平台，补充申请所需权限。'),
          noteLink: t('查看申请方式'),
          steps: [
            {
              title: t('打开权限中心'),
              description: t('进入蓝鲸门户，打开「权限中心」，进入「权限申请」。'),
            },
            {
              title: t('申请加入用户组'),
              description: t('选择「加入用户组」，按业务名搜索，勾选对应角色的用户组并提交。'),
            },
            {
              title: t('审批后重新检测'),
              description: t('审批通过后，返回日志平台，点击「重新检测权限」。'),
            },
          ],
        },
        indexset: {
          title: t('从日志接入到检索，只需三步'),
          note: t('创建前，请准备好目标资源与日志路径，并确认资源访问权限。'),
          noteLink: t('了解采集配置'),
          steps: [
            {
              title: t('创建采集项'),
              description: t('选择日志来源，为采集项命名，关联当前业务或空间。'),
            },
            {
              title: t('配置并下发'),
              description: t('设置目标资源、日志路径和采集规则，完成采集配置下发。'),
            },
            {
              title: t('开始检索日志'),
              description: t('采集正常且数据入库后，选择对应索引集，即可检索日志。'),
            },
          ],
        },
        'tenant-mismatch': {
          title: t('如何切换到所属企业'),
          note: t('请确认选择的是该业务所属企业，切换后重新登录日志平台。'),
          noteLink: '',
          steps: [
            {
              title: t('退出当前登录'),
              description: t('点击页面右上角的个人名称，在菜单中选择「退出登录」。'),
            },
            {
              title: t('切换企业'),
              description: t('进入登录页后，点击右上角的「切换企业」。'),
            },
            {
              title: t('选择所属企业'),
              description: t('输入或选择你的所属企业，确认后重新登录日志平台。'),
            },
          ],
        },
      }[mode];

      return (
        <section class='un-authorized-guide'>
          <div class='un-authorized-guide-main'>
            <div class='un-authorized-guide-header'>
              <h2>{guide.title}</h2>
              {mode === 'space' && (
                <a
                  class='un-authorized-placeholder'
                  href={window.BK_LOG_PERMISSION_GUIDE_URL || undefined}
                  rel='noopener noreferrer'
                  target='_blank'
                >
                  {t('权限申请说明')}
                  <i class='bklog-icon bklog-jump' />
                </a>
              )}
            </div>
            <ol class='un-authorized-guide-steps'>
              {guide.steps.map((step, index) => (
                <li
                  key={index}
                  class='un-authorized-guide-step'
                >
                  <span class='un-authorized-guide-number'>{index + 1}</span>
                  <div class='un-authorized-guide-content'>
                    <h3>{step.title}</h3>
                    <p>{step.description}</p>
                  </div>
                  {index < guide.steps.length - 1 && <i class='bk-icon icon-angle-right un-authorized-guide-arrow' />}
                </li>
              ))}
            </ol>
          </div>
          <div class='un-authorized-guide-note'>
            <i class='bklog-icon bklog-info-fill' />
            <p>{guide.note}</p>
            {guide.noteLink && (
              <button
                class='un-authorized-placeholder un-authorized-text-button'
                type='button'
                onClick={() => handleOpenGuide(mode === 'space' ? 'space' : 'indexset')}
              >
                {guide.noteLink}
                <i class='bk-icon icon-angle-right' />
              </button>
            )}
          </div>
        </section>
      );
    };

    const renderGuideDialog = () => {
      const isPermission = guideDialog.value === 'space';
      return (
        <bk-dialog
          width={720}
          esc-close={true}
          ext-cls='un-authorized-help-dialog'
          header-position='left'
          mask-close={false}
          render-directive='if'
          title={isPermission ? t('选择合适的权限申请方式') : t('日志接入指引')}
          transfer={false}
          value={isGuideDialogVisible.value}
          on-value-change={(visible: boolean) => {
            if (!visible) handleCloseGuide();
          }}
        >
          {isPermission ? (
            <div class='un-authorized-permission-guide'>
              <p class='un-authorized-help-intro'>
                {t('进入蓝鲸门户，打开「权限中心」，在「权限申请」中按使用场景选择申请方式。')}
              </p>
              <section class='un-authorized-help-card'>
                <h3>
                  {t('按业务角色申请')}
                  <span class='un-authorized-help-recommended'>{t('推荐')}</span>
                </h3>
                <p class='un-authorized-help-path'>{t('权限申请 → 加入用户组 → 搜索业务名 → 勾选用户组')}</p>
                <p>
                  {t(
                    '选择与你的业务角色对应的用户组，确认组内包含所需权限后提交审批。加入用户组后，将继承该组的权限。',
                  )}
                </p>
              </section>
              <section class='un-authorized-help-card'>
                <h3>{t('只申请所需的单项权限')}</h3>
                <p class='un-authorized-help-path'>{t('在权限中心选择日志平台，申请所需权限')}</p>
                <p>
                  <span class='un-authorized-help-label'>{t('权限模板：')}</span>
                  {t('选择符合使用场景的模板，并按页面提示配置资源范围。')}
                </p>
                <p>
                  <span class='un-authorized-help-label'>{t('自定义：')}</span>
                  {t('勾选所需操作，点击「关联实例」，选择具体业务等资源实例后提交。')}
                </p>
              </section>
              <p class='un-authorized-help-notice'>
                {t(
                  '已有用户组权限不足时，可以继续申请单项权限；仅在 CMDB 中配置了运维人员，不代表已获得权限中心授权。审批通过后，返回本页重新检测权限。',
                )}
              </p>
            </div>
          ) : (
            <div class='un-authorized-collection-guide'>
              <ol class='un-authorized-help-steps'>
                <li>
                  <h3>{t('准备采集资源')}</h3>
                  <p>{t('主机日志需准备目标主机及日志路径；容器日志需准备集群、命名空间及日志来源。')}</p>
                </li>
                <li>
                  <h3>{t('配置并下发采集项')}</h3>
                  <p>{t('确认采集范围、文件编码和日志规则，完成配置下发并检查采集状态。')}</p>
                </li>
                <li>
                  <h3>{t('验证后开始检索')}</h3>
                  <p>{t('等待数据入库，选择对应索引集，确认可以检索到预期日志。')}</p>
                </li>
              </ol>
              <p class='un-authorized-help-notice'>{t('具体可用采集类型和配置方式，以当前环境的采集管理功能为准。')}</p>
            </div>
          )}
          <div
            slot='footer'
            class='un-authorized-help-footer'
          >
            {isPermission && (
              <a
                class='un-authorized-help-document'
                href={window.BK_LOG_PERMISSION_GUIDE_URL || undefined}
                rel='noopener noreferrer'
                target='_blank'
              >
                {t('查看完整说明')}
                <i class='bklog-icon bklog-jump' />
              </a>
            )}
            <div class='un-authorized-help-buttons'>
              <bk-button onClick={handleCloseGuide}>{t('关闭')}</bk-button>
              <bk-button
                theme='primary'
                onClick={isPermission ? handleApplyPermission : handleCreateCollection}
              >
                {isPermission ? t('申请权限') : t('创建采集项')}
                {isPermission && <i class='bklog-icon bklog-jump' />}
              </bk-button>
            </div>
          </div>
        </bk-dialog>
      );
    };

    const renderIllustration = () => (
      <bk-exception
        class='un-authorized-illustration'
        type='403'
        scene='part'
      >
        <span />
      </bk-exception>
    );

    const renderTenantMismatch = () => (
      <div class='un-authorized-page un-authorized-tenant-mismatch'>
        <div class='un-authorized-page-content'>
          <div class='un-authorized-hero'>
            {renderIllustration()}
            <h1>{t('暂时无法访问当前业务')}</h1>
            <div class='un-authorized-description'>
              <p>{t('请确认当前登录的企业与该业务所属企业一致。')}</p>
              <p>{t('如不一致，请按以下步骤切换企业后重新登录。')}</p>
            </div>
          </div>
          {renderGuide('tenant-mismatch')}
          <div class='un-authorized-operator-note'>
            <span class='un-authorized-operator-icon'>
              <i class='bklog-icon bklog-user-group' />
            </span>
            <div>
              <h2>
                <i18n path='企业选择正确，仍无法访问？请联系{0}确认授权'>
                  {renderAssistantLink(t('BK助手'), 'un-authorized-assistant-inline')}
                </i18n>
              </h2>
              <p>{t('请说明业务或空间、日志范围和登录账号；BK助手完成授权后，刷新页面重试。')}</p>
            </div>
          </div>
        </div>
      </div>
    );

    const renderExternalUnauthorized = () => (
      <div class='un-authorized-page un-authorized-external'>
        <div class='un-authorized-page-content'>
          <div class='un-authorized-hero'>
            {renderIllustration()}
            <h1>{t('暂无日志访问权限')}</h1>
            <div class='un-authorized-description'>
              <p>{t('当前账号尚未获得业务或空间的日志访问权限。')}</p>
            </div>
            <div class='un-authorized-operator-contact'>
              <i class='bklog-icon bklog-user-group' />
              <span>{t('请联系运维人员开通权限')}</span>
            </div>
            <p class='un-authorized-external-hint'>{t('运维人员完成授权后，刷新页面重试。')}</p>
          </div>
        </div>
      </div>
    );

    const renderOnboarding = (isIndexset: boolean) => (
      <div class='un-authorized-page'>
        <div class='un-authorized-page-content'>
          <div class='un-authorized-hero'>
            {renderIllustration()}
            <div class='un-authorized-status'>
              <i class={isIndexset ? 'bklog-icon bklog-ai-3' : 'bklog-icon bklog-info-fill'} />
              {isIndexset ? t('开始接入日志') : t('访问权限未开通')}
            </div>
            <h1>{isIndexset ? t('当前空间还没有采集项') : t('暂无业务 / 空间访问权限')}</h1>
            <div class='un-authorized-description'>
              {isIndexset ? (
                <p>{t('空间「{spaceName}」尚未配置日志采集。', { spaceName: store.state.space.space_name })}</p>
              ) : (
                <p>{t('你尚未获得任何业务或空间的访问权限，暂时无法使用日志平台。')}</p>
              )}
              <p>
                {isIndexset
                  ? t('创建第一个采集项，将主机或容器日志接入日志平台。')
                  : t('请到蓝鲸权限中心申请加入业务用户组，或申请日志平台所需权限。')}
              </p>
            </div>
            <div class='un-authorized-actions'>
              {isIndexset ? (
                <bk-button
                  theme='primary'
                  onClick={handleCreateCollection}
                >
                  <i class='bk-icon icon-plus un-authorized-create-icon' />
                  {t('创建采集项')}
                </bk-button>
              ) : (
                <bk-button
                  theme='primary'
                  onClick={handleApplyPermission}
                >
                  {t('申请权限')}
                  <i class='bklog-icon bklog-jump' />
                </bk-button>
              )}
              {isIndexset ? (
                <a
                  class='un-authorized-placeholder'
                  href={window.BK_LOG_ACCESS_GUIDE_URL || undefined}
                  rel='noopener noreferrer'
                  target='_blank'
                >
                  {t('查看接入文档')}
                  <i class='bklog-icon bklog-jump' />
                </a>
              ) : (
                <bk-button onClick={handleRetry}>
                  <i class='bklog-icon bklog-refresh-icon' />
                  {t('重新检测权限')}
                </bk-button>
              )}
            </div>
            <p class='un-authorized-hint'>
              {isIndexset
                ? t('首次接入建议先选择少量目标，确认采集正常后再扩大范围。')
                : t('申请入口：蓝鲸门户 → 权限中心；审批通过后重新检测权限。')}
            </p>
          </div>
          {renderGuide(isIndexset ? 'indexset' : 'space')}
          <div class='un-authorized-footer'>
            {isIndexset
              ? [
                  <span>{t('没有采集项创建权限？')}</span>,
                  <button
                    class='un-authorized-text-button'
                    type='button'
                    onClick={handleApplyPermission}
                  >
                    {t('申请创建权限')}
                  </button>,
                  <span class='un-authorized-footer-divider'>·</span>,
                  <span>{t('其他空间已接入日志？')}</span>,
                  <span>{t('切换空间')}</span>,
                ]
              : [<span>{t('找不到用户组，或不确定需要哪些权限？')}</span>, renderAssistantLink()]}
          </div>
        </div>
        {renderGuideDialog()}
      </div>
    );

    const exceptionStyle = `height: calc(100vh - 100px); 
      display: flex; 
      flex-direction: column; 
      justify-content: center; 
      align-items: center;`;

    const exceptionTextStyle = `display: flex; 
      flex-direction: column; 
      align-items: center;
      gap: 10px; 
      font-size: 14px; 
      font-weight: 500;`;

    return () => {
      if (isExternal.value) {
        return renderExternalUnauthorized();
      }
      if (exceptionType.value === 'space' && isCrossTenant.value) {
        return renderTenantMismatch();
      }
      if (exceptionType.value === 'indexset' || exceptionType.value === 'space') {
        return renderOnboarding(exceptionType.value === 'indexset');
      }
      return (
        <div class='un-authorized-fallback'>
          <bk-exception
            style={exceptionStyle}
            type='403'
            scene='part'
          >
            <div style={exceptionTextStyle}>{getExceptionText()}</div>
          </bk-exception>
        </div>
      );
    };
  },
});
