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

import { defineComponent, ref, computed, onMounted, nextTick } from 'vue';

// #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
import LogIpSelector, { toSelectorNode, toTransformNode } from '@/components/log-ip-selector/log-ip-selector';
import useLocale from '@/hooks/use-locale';
import useRoute from '@/hooks/use-route';
import useRouter from '@/hooks/use-router';
import useStore from '@/hooks/use-store';
import { manageDraftCacheService } from '@/storage';

import http from '@/api';
// #else
// #code const LogIpSelector = () => null;
// #endif

import PreviewFiles from './preview-files.tsx';
import TextFilter from './text-filter.tsx';

import './index.scss';

export default defineComponent({
  name: 'ExtractCreate',
  components: {
    LogIpSelector,
    TextFilter,
    PreviewFiles,
  },
  setup(_props, { emit }) {
    const store = useStore();
    const { t } = useLocale();
    const router = useRouter();
    const route = useRoute();

    const showSelectDialog = ref(false);
    const ipList = ref<any[]>([]); // 下载目标（ip 列表，TOPO/SERVICE_TEMPLATE 时从 strategies 响应获取）
    const targetNodeType = ref<string>('INSTANCE'); // INSTANCE | TOPO | SERVICE_TEMPLATE
    const targetNodes = ref<any[]>([]); // TOPO/SERVICE_TEMPLATE 选中的节点
    const fileOrPath = ref(''); // 目录
    const availablePaths = ref<string[]>([]); // 目录可选列表
    const downloadFiles = ref<any[]>([]); // 下载的文件
    const remark = ref(''); // 备注
    const extractLinks = ref<any[]>([]); // 提取链路
    const linkId = ref<null | number>(null);
    const ipSelectorOriginalValue = ref<any>(null); // 编辑态ip选择器初始值
    const ipSelectNewNameList = ref<any[]>([]); // 生成新的展示所用的预览地址列表
    const isSubmitLoading = ref(false); // 提交按钮loading状态
    const showPreviewDialog = ref(false);
    const previewData = ref<any>(null);
    const previewDirection = ref('forward');

    // 组件引用
    const textFilterRef = ref<any>(null);
    const previewRef = ref<any>(null);

    const selectedCount = computed(() => {
      return targetNodeType.value === 'INSTANCE' ? ipList.value.length : targetNodes.value.length;
    });

    const submitFiles = computed(() => previewRef.value?.getDownloadFiles?.() ?? downloadFiles.value);
    const canSubmit = computed(() => !(selectedCount.value > 0 && submitFiles.value.length));
    const previewHostIps = computed(
      () =>
        (previewData.value?.ip_list ?? [])
          .map((host: any) => host.ip)
          .filter(Boolean)
          .join(', ') || '--',
    );
    const previewFilterText = computed(() => {
      const content = previewData.value?.filter_content ?? {};
      switch (previewData.value?.filter_type) {
        case 'match_word': {
          const modes = { keyword_and: t('与'), keyword_or: t('或'), keyword_not: t('非') };
          return `${t('关键字过滤')}：${content.keyword}（${t('关键字匹配模式')}：${modes[content.keyword_type] ?? ''}）`;
        }
        case 'match_range':
          return t('关键字范围: 从匹配{0}开始到匹配{1}之间的所有行', [content.start, content.end]);
        case 'tail_line':
          return t('最新行数：{0} 行', [content.line_num]);
        case 'line_range':
          return t('按行过滤: 从第{0}行到第{1}行', [content.start_line, content.end_line]);
        default:
          return t('不过滤');
      }
    });

    const isClone = computed(() => {
      return route.name === 'extract-clone' && !!sessionStorage.getItem('cloneData');
    });

    // ip选择器选中节点，根据 targetNodeType 返回不同结构
    const selectorNodes = computed(() => {
      if (targetNodeType.value === 'TOPO') {
        return { node_list: toSelectorNode(targetNodes.value, 'TOPO') };
      }
      if (targetNodeType.value === 'SERVICE_TEMPLATE') {
        return { service_template_list: toSelectorNode(targetNodes.value, 'SERVICE_TEMPLATE') };
      }
      return { host_list: toSelectorNode(ipList.value, 'INSTANCE') };
    });

    // 获取全局数据
    const globalsData = computed(() => store.getters.globalsData);

    // 检查是否为克隆模式并初始化克隆数据
    const checkIsClone = async () => {
      if (isClone.value) {
        let cloneData = JSON.parse(sessionStorage.getItem('cloneData') || '{}');
        if (!Object.keys(cloneData).length) {
          cloneData = (await manageDraftCacheService.get('cloneData')) || {};
        }
        sessionStorage.removeItem('cloneData');
        manageDraftCacheService.remove('cloneData').catch(() => {});

        const cloneNodeType = cloneData.target_node_type || 'INSTANCE';
        targetNodeType.value = cloneNodeType;
        ipList.value = cloneData.ip_list ?? [];

        if (cloneData.target_nodes?.length) {
          targetNodes.value = cloneData.target_nodes;
        } else if (cloneNodeType === 'INSTANCE' && ipList.value.length) {
          targetNodes.value = ipList.value.map(item => ({
            bk_obj_id: 'host',
            bk_inst_id: item.bk_host_id,
          }));
        } else {
          targetNodes.value = [];
        }

        fileOrPath.value = cloneData.preview_directory; // 克隆目录
        textFilterRef.value?.handleClone(cloneData); // 克隆文本过滤
        remark.value = cloneData.remark; // 克隆备注
        // 获取目录下拉列表和预览地址
        initCloneDisplayName(); // 克隆时 请求displayName列表来展示预览字段
        handleCloneAvailablePaths(cloneData);
        await nextTick();
        previewRef.value?.handleClone(cloneData);

        if (cloneNodeType === 'TOPO') {
          ipSelectorOriginalValue.value = { node_list: toSelectorNode(targetNodes.value, 'TOPO') };
        } else if (cloneNodeType === 'SERVICE_TEMPLATE') {
          ipSelectorOriginalValue.value = {
            service_template_list: toSelectorNode(targetNodes.value, 'SERVICE_TEMPLATE'),
          };
        } else {
          ipSelectorOriginalValue.value = { host_list: toSelectorNode(ipList.value, 'INSTANCE') };
        }
      }
    };

    // 初始化克隆模式的显示名称
    const initCloneDisplayName = () => {
      const requestIpList = ipList.value.map(item => {
        if (item?.bk_host_id) {
          return {
            host_id: item.bk_host_id,
          };
        }
        return {
          ip: item.ip ?? '',
          cloud_id: item.bk_cloud_id ?? '',
        };
      });
      http
        .request('extract/getIpListDisplayName', {
          data: {
            host_list: requestIpList,
          },
          params: {
            bk_biz_id: store.state.bkBizId,
          },
        })
        .then(res => {
          initSelectNewNameList(res.data, true);
        })
        .catch(err => {
          console.warn(err);
          ipSelectNewNameList.value = [];
        });
    };

    // 获取提取链路列表
    const getExtractLinkList = () => {
      http
        .request('extract/getExtractLinkList', {
          data: { bk_biz_id: store.state.bkBizId },
        })
        .then(res => {
          extractLinks.value = res.data;
          linkId.value = extractLinks.value[0]?.link_id || null;
        })
        .catch(e => {
          console.warn(e);
        });
    };

    // 处理克隆模式的可用路径
    const handleCloneAvailablePaths = (cloneData: any) => {
      const cloneNodeType = cloneData.target_node_type || 'INSTANCE';
      const requestData: any = {
        bk_biz_id: store.state.bkBizId,
        target_node_type: cloneNodeType,
      };
      if (cloneData.target_nodes?.length) {
        requestData.target_nodes = cloneData.target_nodes;
      } else {
        requestData.ip_list = cloneData.ip_list;
      }
      return http
        .request('extract/getAvailableExplorerPath', {
          data: requestData,
        })
        .then(res => {
          availablePaths.value = (res.data.strategies ?? []).map((item: any) => item.file_path);
          if (cloneNodeType !== 'INSTANCE' && res.data.ip_list?.length) {
            ipList.value = res.data.ip_list;
          }
        })
        .catch(e => {
          console.warn(e);
        });
    };

    // 处理文件路径更新
    const handleFileOrPathUpdate = (newFileOrPath: string) => {
      fileOrPath.value = newFileOrPath;
    };

    // 根据 strategies 接口返回的 ip_list 请求 displayName 并设置预览地址列表
    const initDisplayNameFromIpList = (responseIpList: any[]) => {
      const requestIpList = responseIpList.map(item => {
        if (item?.bk_host_id) {
          return { host_id: item.bk_host_id };
        }
        return {
          ip: item.ip ?? '',
          cloud_id: item.bk_cloud_id ?? '',
        };
      });
      http
        .request('extract/getIpListDisplayName', {
          data: { host_list: requestIpList },
          params: { bk_biz_id: store.state.bkBizId },
        })
        .then(res => {
          initSelectNewNameList(res.data, true);
        })
        .catch(err => {
          console.warn(err);
          ipSelectNewNameList.value = [];
        });
    };

    // 处理IP选择器确认选择，支持 INSTANCE / TOPO / SERVICE_TEMPLATE
    const handleConfirm = async (value: any) => {
      const { host_list: hostList, node_list: nodeList, service_template_list: serviceTemplateList } = value;

      let nodeType: string = 'INSTANCE';
      let rawNodes: any[] = [];
      if (nodeList?.length) {
        nodeType = 'TOPO';
        rawNodes = nodeList;
      } else if (serviceTemplateList?.length) {
        nodeType = 'SERVICE_TEMPLATE';
        rawNodes = serviceTemplateList;
      } else if (hostList?.length) {
        nodeType = 'INSTANCE';
        rawNodes = hostList;
      }

      targetNodeType.value = nodeType;

      try {
        if (nodeType === 'INSTANCE') {
          initSelectNewNameList(rawNodes);
          const newIpList = toTransformNode(rawNodes, 'INSTANCE', true);
          const newTargetNodes = newIpList.map(item => ({
            bk_obj_id: 'host',
            bk_inst_id: item.bk_host_id,
          }));
          const strategies = await http.request('extract/getAvailableExplorerPath', {
            data: {
              bk_biz_id: store.state.bkBizId,
              ip_list: newIpList,
              target_nodes: newTargetNodes,
              target_node_type: 'INSTANCE',
            },
          });
          ipList.value = strategies.data.ip_list ?? newIpList;
          targetNodes.value = ipList.value.map(item => ({
            bk_obj_id: 'host',
            bk_inst_id: item.bk_host_id,
          }));
          availablePaths.value = (strategies.data.strategies ?? []).map((item: any) => item.file_path);
        } else {
          const newTargetNodes = toTransformNode(rawNodes, nodeType as any);
          const strategies = await http.request('extract/getAvailableExplorerPath', {
            data: {
              bk_biz_id: store.state.bkBizId,
              target_nodes: newTargetNodes,
              target_node_type: nodeType,
            },
          });
          targetNodes.value = newTargetNodes;
          ipList.value = strategies.data.ip_list ?? [];
          availablePaths.value = (strategies.data.strategies ?? []).map((item: any) => item.file_path);
          initDisplayNameFromIpList(ipList.value);
        }
      } catch (error) {
        console.warn(error);
      }
    };

    // 初始化选择的新名称列表
    const initSelectNewNameList = (hostList: any[], newIsClone = false) => {
      if (newIsClone) {
        // 克隆 通过接口请求返回的display_name展示值
        ipSelectNewNameList.value = hostList.map(item => ({
          bk_host_id: item.bk_host_id,
          ip: item.bk_host_innerip,
          bk_cloud_id: item.bk_cloud_id,
          selectID: `${item.bk_host_id ?? ''}_${item.bk_host_innerip ?? ''}_${item.bk_cloud_id ?? ''}`, // select唯一key
          name: item.display_name,
        }));
      } else {
        // 新增 使用ip选择器里的值展示
        const priorityList = globalsData.value.host_identifier_priority ?? ['ip', 'host_name', 'ipv6'];
        ipSelectNewNameList.value = hostList.map(item => ({
          bk_host_id: item.host_id,
          ip: item.ip,
          bk_cloud_id: item.cloud_area.id,
          selectID: `${item.host_id ?? ''}_${item.ip ?? ''}_${item.cloud_area.id ?? ''}`, // select唯一key
          name: item[priorityList.find(pItem => Boolean(item[pItem]))] ?? '',
        }));
      }
    };

    // 预览与确认共用同一份参数快照，打开弹窗不创建任务。
    const handlePreview = () => {
      if (isSubmitLoading.value || canSubmit.value) {
        return;
      }
      const requestData: any = {
        bk_biz_id: store.state.bkBizId,
        ip_list: ipList.value,
        target_node_type: targetNodeType.value,
        target_nodes: targetNodes.value,
        preview_directory: fileOrPath.value,
        preview_ip_list: previewRef.value?.getFindIpList(),
        preview_time_range: previewRef.value?.timeRange,
        preview_start_time: previewRef.value?.timeStringValue[0],
        preview_end_time: previewRef.value?.timeStringValue[1],
        preview_is_search_child: previewRef.value?.isSearchChild,
        file_path: submitFiles.value,
        filter_type: textFilterRef.value.filterType,
        filter_content: textFilterRef.value.filterContent,
        remark: remark.value,
        link_id: linkId.value,
      };
      previewData.value = JSON.parse(JSON.stringify(requestData));
      previewDirection.value = previewRef.value?.extractionDirection ?? 'forward';
      showPreviewDialog.value = true;
    };

    const closePreview = () => {
      if (!isSubmitLoading.value) {
        showPreviewDialog.value = false;
      }
    };

    // 仅在预览弹窗确认后提交下载任务。
    const handleSubmit = () => {
      if (isSubmitLoading.value || !showPreviewDialog.value || !previewData.value) {
        return;
      }
      emit('loading', true);
      isSubmitLoading.value = true;
      http
        .request('extract/createDownloadTask', {
          data: previewData.value,
        })
        .then(() => {
          isSubmitLoading.value = false;
          showPreviewDialog.value = false;
          goToHome();
        })
        .catch(err => {
          console.warn(err);
          emit('loading', false);
          isSubmitLoading.value = false;
        });
    };

    // 跳转到任务列表页面
    const goToHome = () => {
      router.push({
        name: 'log-extract-task',
        query: {
          spaceUid: store.state.spaceUid,
        },
      });
    };

    // 生命周期
    onMounted(() => {
      checkIsClone();
      getExtractLinkList();
    });

    // 主渲染函数
    return () => (
      <div
        class='create-task-container'
        v-en-class="'en-title'"
      >
        <div class='create-task-body'>
          <section class='extract-card'>
            <h3 class='extract-card-title'>{t('提取范围')}</h3>
            <div class='row-container'>
              <div class='title'>
                {t('目标类型')}
                <span class='required'>*</span>
              </div>
              <div class='content'>
                <div class='bk-button-group target-type-group'>
                  <bk-button
                    class='is-selected'
                    theme='primary'
                    outline
                  >
                    {t('主机')}
                  </bk-button>
                  <bk-button disabled>{t('容器')}</bk-button>
                </div>
              </div>
            </div>
            <div class='row-container'>
              <div class='title'>
                {t('提取范围')}
                <span class='required'>*</span>
              </div>
              <div class='content'>
                <div class='target-selection'>
                  <bk-button
                    class='select-target-button'
                    data-test-id='addNewExtraction_button_selectTheServer'
                    icon='plus'
                    onClick={() => (showSelectDialog.value = true)}
                  >
                    {t('选择目标')}
                  </bk-button>
                  <div class='select-text'>
                    <i18n path='已选择{0}个节点'>
                      <span class={selectedCount.value ? 'primary' : 'error'}>{selectedCount.value}</span>
                    </i18n>
                  </div>
                </div>
                <LogIpSelector
                  height={670}
                  mode='dialog'
                  original-value={ipSelectorOriginalValue.value}
                  panel-list={['staticTopo', 'dynamicTopo']}
                  show-dialog={showSelectDialog.value}
                  show-view-diff={isClone.value}
                  value={selectorNodes.value}
                  allow-host-list-miss-host-id
                  extract-scene
                  keep-host-field-output
                  {...{
                    on: {
                      'update:show-dialog': (val: boolean) => (showSelectDialog.value = val),
                      change: handleConfirm,
                    },
                  }}
                />
              </div>
            </div>
          </section>

          <section class='extract-card'>
            <h3 class='extract-card-title'>{t('日志文件')}</h3>
            <div class='row-container files-row'>
              <div class='title'>
                {t('选择文件')}
                <span class='required'>*</span>
              </div>
              <PreviewFiles
                ref={previewRef}
                availablePaths={availablePaths.value}
                downloadFiles={downloadFiles.value}
                fileOrPath={fileOrPath.value}
                ipList={ipList.value}
                ipSelectNewNameList={ipSelectNewNameList.value}
                {...{
                  on: {
                    'update:downloadFiles': (val: any[]) => (downloadFiles.value = val),
                    'update:fileOrPath': handleFileOrPathUpdate,
                  },
                }}
              />
            </div>
          </section>

          <section class='extract-card'>
            <h3 class='extract-card-title'>{t('提取参数')}</h3>
            <div class='row-container'>
              <div class='title'>{t('过滤模式')}</div>
              <div class='content filter-content'>
                <TextFilter ref={textFilterRef} />
              </div>
            </div>
            <div class='row-container'>
              <div class='title'>{t('提取链路')}</div>
              <div class='content extract-parameter-content'>
                <bk-select
                  clearable={false}
                  data-test-id='addNewExtraction_select_selectLink'
                  value={linkId.value}
                  onChange={(val: number) => (linkId.value = val)}
                >
                  {extractLinks.value.map(link => (
                    <bk-option
                      id={link.link_id}
                      key={link.link_id}
                      name={link.show_name}
                    />
                  ))}
                </bk-select>
                <div class='extract-link-tips'>
                  <span class='bk-icon icon-info-circle' />
                  {t('选择离你最近的提取链路')}
                </div>
              </div>
            </div>
            <div class='row-container'>
              <div class='title'>{t('备注')}</div>
              <div class='content extract-parameter-content'>
                <bk-input
                  maxlength={255}
                  type='textarea'
                  value={remark.value}
                  show-word-limit
                  onInput={(val: string) => (remark.value = val)}
                />
              </div>
            </div>
          </section>
        </div>

        <div class='create-task-footer'>
          <bk-button
            class='preview-button'
            disabled={canSubmit.value || isSubmitLoading.value}
            loading={isSubmitLoading.value}
            theme='primary'
            outline
            onClick={handlePreview}
          >
            {t('预览')}
          </bk-button>
          <bk-button
            data-test-id='addNewExtraction_button_submitConfigure'
            disabled={canSubmit.value || isSubmitLoading.value}
            loading={isSubmitLoading.value}
            theme='primary'
            onClick={handlePreview}
          >
            {t('预览并下发')}
          </bk-button>
          <bk-button
            class='cancel-button'
            data-test-id='addNewExtraction_button_cancel'
            onClick={goToHome}
          >
            {t('取消')}
          </bk-button>
        </div>
        <bk-dialog
          width={640}
          auto-close={false}
          beforeClose={() => !isSubmitLoading.value}
          close-icon={!isSubmitLoading.value}
          esc-close={!isSubmitLoading.value}
          ext-cls='extract-task-preview-dialog'
          header-position='left'
          mask-close={false}
          title={t('预览')}
          value={showPreviewDialog.value}
          on-value-change={(value: boolean) => !value && closePreview()}
          onCancel={closePreview}
        >
          {previewData.value && (
            <div class='extract-preview-content'>
              <bk-alert
                class='extract-preview-risk'
                showIcon={false}
                type='warning'
              >
                <template slot='title'>
                  <span class='bk-icon icon-exclamation-circle' />
                  <div>
                    {t('风险提示：')}
                    <ul>
                      <li>{t('本次任务会从已授权的主机中临时提取日志，并生成有时效的下载链接')}</li>
                      <li>{t('请确认目标范围、文件范围和过滤条件符合授权用途')}</li>
                      <li>{t('下载链接过期后需要重新下发或重新生成')}</li>
                    </ul>
                  </div>
                </template>
              </bk-alert>
              <dl
                class='extract-preview-details'
                v-en-class="'en-title'"
              >
                <div class='extract-preview-row'>
                  <dt>{t('目标类型')}</dt>
                  <dd>{t('主机')}</dd>
                </div>
                <div class='extract-preview-row'>
                  <dt>{t('目标范围')}</dt>
                  <dd>
                    <div class='extract-preview-hosts'>
                      <div class='extract-preview-host'>
                        <span class='extract-preview-host-key'>
                          {t('主机IP')}
                          <span> = </span>
                        </span>
                        <span class='extract-preview-host-value'>{previewHostIps.value}</span>
                      </div>
                    </div>
                  </dd>
                </div>
                <div class='extract-preview-row'>
                  <dt>{t('命中目标')}</dt>
                  <dd>
                    <i18n path='{0} 个授权内主机'>
                      <span class='extract-preview-count'>{previewData.value.ip_list.length}</span>
                    </i18n>
                  </dd>
                </div>
                <div class='extract-preview-row'>
                  <dt>{t('文件范围')}</dt>
                  <dd>{previewData.value.preview_directory}</dd>
                </div>
                <div class='extract-preview-row'>
                  <dt>{t('提取方向')}</dt>
                  <dd>{previewDirection.value === 'reverse' ? t('反向提取') : t('正向提取')}</dd>
                </div>
                <div class='extract-preview-row'>
                  <dt>{previewDirection.value === 'reverse' ? t('提取文件') : t('已选文件')}</dt>
                  <dd>
                    <i18n path='{0} 个文件'>
                      <span class='extract-preview-count'>{previewData.value.file_path.length}</span>
                    </i18n>
                  </dd>
                </div>
                <div class='extract-preview-row'>
                  <dt>{t('文本过滤')}</dt>
                  <dd class='extract-preview-filter'>{previewFilterText.value}</dd>
                </div>
              </dl>
            </div>
          )}
          <div
            class='extract-preview-footer'
            slot='footer'
          >
            <bk-button
              class='confirm-extract-button'
              disabled={isSubmitLoading.value}
              loading={isSubmitLoading.value}
              theme='primary'
              onClick={handleSubmit}
            >
              {t('确认下发')}
            </bk-button>
            <bk-button
              class='modify-extract-button'
              disabled={isSubmitLoading.value}
              onClick={closePreview}
            >
              {t('返回修改')}
            </bk-button>
          </div>
        </bk-dialog>
      </div>
    );
  },
});
