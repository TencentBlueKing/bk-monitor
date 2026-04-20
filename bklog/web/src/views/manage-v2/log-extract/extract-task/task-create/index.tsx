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

import http from '@/api';
// #else
// #code const LogIpSelector = () => null;
// #endif

import FilesInput from './files-input.tsx';
import PreviewFiles from './preview-files.tsx';
import TextFilter from './text-filter.tsx';

import './index.scss';

export default defineComponent({
  name: 'ExtractCreate',
  components: {
    LogIpSelector,
    FilesInput,
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
    const link_id = ref<null | number>(null);
    const ipSelectorOriginalValue = ref<any>(null); // 编辑态ip选择器初始值
    const ipSelectNewNameList = ref<any[]>([]); // 生成新的展示所用的预览地址列表
    const isSubmitLoading = ref(false); // 提交按钮loading状态

    // 组件引用
    const textFilterRef = ref<any>(null);
    const previewRef = ref<any>(null);

    const selectedCount = computed(() => {
      return targetNodeType.value === 'INSTANCE'
        ? ipList.value.length
        : targetNodes.value.length;
    });

    const canSubmit = computed(() => {
      return !(selectedCount.value > 0 && downloadFiles.value.length) && link_id.value != null;
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
        const cloneData = JSON.parse(sessionStorage.getItem('cloneData') || '{}');
        sessionStorage.removeItem('cloneData');

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
          link_id.value = extractLinks.value[0]?.link_id || null;
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
      http
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

    // 处理文件选择
    const handleFilesSelect = (newFileOrPath: string) => {
      previewRef.value?.getExplorerList({ path: newFileOrPath });
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

    // 处理提交下载任务
    const handleSubmit = () => {
      emit('loading', true);
      isSubmitLoading.value = true;
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
        file_path: downloadFiles.value,
        filter_type: textFilterRef.value.filterType,
        filter_content: textFilterRef.value.filterContent,
        remark: remark.value,
        link_id: link_id.value,
      };
      http
        .request('extract/createDownloadTask', {
          data: requestData,
        })
        .then(() => {
          isSubmitLoading.value = false;
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
        class={['main-container', 'create-task-container']}
        v-en-class="'en-title'"
      >
        {/* 文件来源主机 */}
        <div class='row-container'>
          <div class='title'>
            {t('文件来源主机')}
            <span class='required'>*</span>
          </div>
          <div class='content'>
            <div class='flex-box'>
              <bk-button
                data-test-id='addNewExtraction_button_selectTheServer'
                size='small'
                theme='primary'
                onClick={() => (showSelectDialog.value = true)}
              >
                {t('选择服务器')}
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

        {/* 目录或文件名 */}
        <div class='row-container'>
          <div class='title'>
            {t('目录或文件名')}
            <span class='required'>*</span>
            <span
              class='bklog-icon bklog-info-fill'
              v-bk-tooltips={`${t('以')}/${t('结尾查询指定目录下内容，否则默认查询该目录及其子目录下所有文件')}`}
            />
          </div>
          <div class='content'>
            <FilesInput
              availablePaths={availablePaths.value}
              value={fileOrPath.value}
              {...{
                on: {
                  'update:value': (val: string) => (fileOrPath.value = val),
                  'update:select': handleFilesSelect,
                },
              }}
            />
          </div>
        </div>

        {/* 预览地址 */}
        <div class='row-container'>
          <div class='title'>{t('预览地址')}</div>
          <PreviewFiles
            ref={previewRef}
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

        {/* 文本过滤 */}
        <div class='row-container'>
          <div class='title'>{t('文本过滤')}</div>
          <div class='content'>
            <TextFilter ref={textFilterRef} />
          </div>
        </div>

        {/* 备注 */}
        <div class='row-container'>
          <div class='title'>{t('备注')}</div>
          <div class='content'>
            <bk-input
              style='width: 261px'
              value={remark.value}
              {...{
                on: {
                  input: (val: string) => (remark.value = val),
                },
              }}
            />
          </div>
        </div>

        {/* 提取链路 */}
        <div class='row-container'>
          <div class='title'>{t('提取链路')}</div>
          <div class='content'>
            <bk-select
              style='width: 250px; margin-right: 20px; background-color: #fff'
              clearable={false}
              data-test-id='addNewExtraction_select_selectLink'
              value={link_id.value}
              {...{
                on: {
                  change: (val: number) => (link_id.value = val),
                },
              }}
            >
              {extractLinks.value.map(link => (
                <bk-option
                  id={link.link_id}
                  key={link.link_id}
                  name={link.show_name}
                />
              ))}
            </bk-select>
          </div>
          <div class='content'>{t('选择离你最近的提取链路')}</div>
        </div>

        {/* 按钮容器 */}
        <div class='button-container'>
          <bk-button
            style='width: 120px; margin-right: 16px'
            data-test-id='addNewExtraction_button_submitConfigure'
            disabled={canSubmit.value}
            loading={isSubmitLoading.value}
            theme='primary'
            onClick={handleSubmit}
          >
            {t('提交下载任务')}
          </bk-button>
          <bk-button
            style='width: 120px'
            data-test-id='addNewExtraction_button_cancel'
            onClick={goToHome}
          >
            {t('取消')}
          </bk-button>
        </div>
      </div>
    );
  },
});
