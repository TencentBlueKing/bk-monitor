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

import { computed, defineComponent, ref, watch } from "vue";
import useLocale from "@/hooks/use-locale";
import useStore from "@/hooks/use-store";
import { bkMessage } from "bk-magic-vue";
import { formatDate } from "@/common/util";
import $http from "@/api";

import "./index.scss";

interface Remark {
  create_time: number; // 时间戳（毫秒）
  remark: string;
  showTime: string; // 格式化的日期时间字符串
  username: string;
}

export default defineComponent({
  name: "RemarkEditTip",
  props: {
    requestData: {
      type: Object,
      require: true,
    },
    rowData: {
      type: Object,
      default: () => ({}),
    },
    indexId: {
      type: String,
      require: true,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();

    const remarkTipsRef = ref<HTMLElement>();
    const formRef = ref<any>(null);
    const isShowEditRemarkDialog = ref(false);
    /** 当前备注信息 */
    const currentRemarkList = ref<Remark[]>([]);
    /** 输入框弹窗的字符串 */
    const verifyData = ref({
      textInputStr: "",
    });

    const username = computed(() => store.state.userMeta?.username);

    const rules = {
      textInputStr: [
        {
          validator: (value: string) => !!value,
          trigger: "blur",
          message: t("不能为空"),
        },
      ],
    };

    let catchOperatorVal = {};
    let currentOperateType = "edit";

    watch(
      () => props.rowData.remark,
      () => {
        if (!props.rowData.remark) {
          return;
        }
        currentRemarkList.value = props.rowData.remark
          .map((item) => ({
            ...item,
            showTime: item.create_time > 0 ? formatDate(item.create_time) : "",
          }))
          .sort((a, b) => b.create_time - a.create_time);
      },
      { immediate: true, deep: true }
    );

    const handleEditRemark = (remarkItem: Remark | null, type: string) => {
      currentOperateType = type;
      emit("hide-self");
      if (type === "delete") {
        catchOperatorVal = {
          remark: remarkItem!.remark,
          create_time: remarkItem!.create_time,
        };
        updateRemark(type);
        return;
      } else if (type === "update") {
        verifyData.value.textInputStr = remarkItem!.remark;
        catchOperatorVal = {
          old_remark: remarkItem!.remark,
          create_time: remarkItem!.create_time,
        };
      } else {
        verifyData.value.textInputStr = "";
      }
      isShowEditRemarkDialog.value = true;
    };

    const handleConfirmUpdateRemark = () => {
      formRef.value
        .validate()
        .then(() => {
          updateRemark(currentOperateType);
        })
        .catch((e) => console.error(e));
    };

    // 将分组的数组改成对像
    const getGroupsValue = (group: string[]) => {
      if (!props.requestData?.group_by.length) return {};
      return props.requestData.group_by.reduce((acc, cur, index) => {
        acc[cur] = group?.[index] ?? "";
        return acc;
      }, {});
    };

    // 设置备注
    const updateRemark = (markType = "add") => {
      let additionData;
      let queryStr;
      const inputRemark = verifyData.value.textInputStr.trim();
      switch (markType) {
        case "update":
          queryStr = "updateRemark";
          additionData = {
            new_remark: inputRemark,
            ...catchOperatorVal,
          };
          break;
        case "delete":
          queryStr = "deleteRemark";
          additionData = {
            remark: inputRemark,
            ...catchOperatorVal,
          };
          break;
        case "add":
          queryStr = "setRemark";
          additionData = {
            remark: inputRemark,
          };
          break;
      }
      $http
        .request(`/logClustering/${queryStr}`, {
          params: {
            index_set_id: props.indexId,
          },
          data: {
            signature: props.rowData.signature,
            ...additionData,
            origin_pattern: props.rowData.origin_pattern,
            groups: getGroupsValue(props.rowData.group),
          },
        })
        .then((res) => {
          if (res.result) {
            const { remark } = res.data;
            emit("update", remark);
            bkMessage({
              theme: "success",
              message: t("操作成功"),
            });
            isShowEditRemarkDialog.value = false;
          }
        })
        .finally(() => {
          verifyData.value.textInputStr = "";
        });
    };

    expose({
      tipRef: remarkTipsRef,
    });

    return () => (
      <div v-show={false}>
        <div class="remark-popover-main" ref={remarkTipsRef}>
          <div class="remark-list" v-show={currentRemarkList.value.length}>
            {currentRemarkList.value.map((remark, index) => (
              <div key={index} class="remark-item">
                <div class="remark-main">
                  <div class="content">{remark.remark}</div>
                  <div class="relate-info">
                    {remark.username && (
                      <span>
                        <span>{remark.username}</span>
                        <span class="split-line">|</span>
                      </span>
                    )}
                    <span>{remark.showTime}</span>
                  </div>
                </div>
                {remark.username === username.value && (
                  <div class="operates">
                    <span on-click={() => handleEditRemark(remark, "update")}>
                      <log-icon common type="edit-line" />
                    </span>
                    <span on-click={() => handleEditRemark(remark, "delete")}>
                      <log-icon common type="delete" />
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div
            class="add-new-remark"
            style={{
              paddingBottom: currentRemarkList.value.length > 0 ? "4px" : "0px",
            }}
          >
            <bk-button
              text
              theme="primary"
              size="small"
              on-click={() => handleEditRemark(null, "add")}
            >
              <log-icon
                common
                type="plus"
                style="font-size: 22px;margin-right: 6px;"
              />
              {t("新增备注")}
            </bk-button>
          </div>
        </div>
        <bk-dialog
          value={isShowEditRemarkDialog.value}
          confirm-fn={handleConfirmUpdateRemark}
          on-cancel={() => (isShowEditRemarkDialog.value = false)}
          title={t("备注")}
          width={480}
          header-position="left"
        >
          <bk-form
            ref={formRef}
            style="width: 100%"
            label-width={0}
            {...{
              props: {
                model: verifyData.value,
                rules,
              },
            }}
          >
            <bk-form-item error-display-type="normal" property="textInputStr">
              <bk-input
                value={verifyData.value.textInputStr}
                // maxlength={100}
                placeholder={t("请输入")}
                rows={5}
                type="textarea"
                on-change={(val) =>
                  (verifyData.value.textInputStr = val.trim())
                }
              />
            </bk-form-item>
          </bk-form>
        </bk-dialog>
      </div>
    );
  },
});
