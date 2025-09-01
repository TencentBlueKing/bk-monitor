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
import { defineComponent, ref } from "vue";
import useLocale from "@/hooks/use-locale";
import { random } from "@/common/util";
import ValidateInput from "./validate-input";
import "./index.scss";

export interface RowData {
  rowKey: string;
  pattern: string;
  occupy: string;
  highlight: string;
  disabled?: boolean;
}

export default defineComponent({
  name: "RegexTable",
  components: {
    ValidateInput,
  },
  setup(props, { expose, emit }) {
    const { t } = useLocale();

    const tableRef = ref(null);
    const tableRenderKey = ref(0);
    const inputColumnsMapRef = ref({
      regex: [],
      occupy: [],
    });
    const tableData = ref<RowData[]>([]);

    const regexRules = [
      {
        validator: (value: string) => !!value,
        message: t("不能为空"),
      },
    ];

    const occupyRules = [
      {
        validator: (value: string) => !!value,
        message: t("不能为空"),
      },
      {
        validator: (value: string) => /^[A-Z_-]+$/.test(value),
        message: t("{n}不规范, 包含特殊符号.", { n: t("占位符") }),
      },
    ];

    let currentIndex = -1;
    let hoverRowIndex = -1;

    const handleDragStart = (index: number) => {
      currentIndex = index;
    };

    const handleDragOver = (index: number) => {
      hoverRowIndex = index;
    };

    const handleDragEnd = () => {
      if (hoverRowIndex === -1 || hoverRowIndex === currentIndex) {
        return;
      }

      const list = structuredClone(tableData.value);
      const currentItem = list[currentIndex];
      list.splice(currentIndex, 1);
      list.splice(hoverRowIndex, 0, currentItem);
      tableData.value = list;
      currentIndex = -1;
      hoverRowIndex = -1;
      tableRenderKey.value += 1;
      emit("change", tableData.value);
      setTimeout(() => {
        updateTableRenderKey();
      });
    };

    const handleDeleteItem = (index: number) => {
      const currentRow = tableData.value[index];
      if (currentRow.disabled) {
        return;
      }

      emit("delete", currentRow);
      tableData.value.splice(index, 1);
      emit("change", tableData.value);
      setTimeout(() => {
        updateTableRenderKey();
      });
    };

    const setItemRef =
      (type: string, index: number) => (el: HTMLElement | null) => {
        inputColumnsMapRef.value[type][index] = el;
      };

    const updateTableRenderKey = () => {
      inputColumnsMapRef.value = {
        regex: [],
        occupy: [],
      };
      setTimeout(() => {
        tableRenderKey.value += 1;
      });
    };

    const handleOpenClusterConfig = () => {
      emit("open-cluster-config");
    };

    expose({
      setDataList: (list: RowData[]) => {
        tableData.value = list.map((item) => ({ ...item, rowKey: random() }));
        updateTableRenderKey();
      },
      addItem: (item: Omit<RowData, "rowKey">) => {
        tableData.value.unshift({
          rowKey: random(),
          ...item,
        });
        emit("change", tableData.value);
        updateTableRenderKey();
      },
      getData: async () => {
        await Promise.all(
          inputColumnsMapRef.value.regex.map((el: any) => el.getValue()),
        );
        await Promise.all(
          inputColumnsMapRef.value.occupy.map((el: any) => el.getValue()),
        );
        return tableData.value;
      },
    });

    return () => (
      <table class="regex-table-main" ref={tableRef} key={tableRenderKey.value}>
        <thead>
          <tr>
            <th style="width:42px"></th>
            <th style="width:68px">{t("生效顺序")}</th>
            <th style="width:42px">{t("高亮")}</th>
            <th style="width:500px">{t("正则表达式")}</th>
            <th style="width:223px">{t("占位符")}</th>
            <th style="width:42px">{t("操作")}</th>
          </tr>
        </thead>
        <tbody>
          {tableData.value.map((row, index) => (
            <tr
              key={`${row.rowKey}_${index}`}
              draggable="true"
              on-dragstart={() => handleDragStart(index)}
              on-dragover={() => handleDragOver(index)}
              on-dragend={handleDragEnd}
            >
              <td>
                <div class="drag-column">
                  <log-icon type="drag-dots" />
                </div>
              </td>
              <td>
                <div class="index-column">{index + 1}</div>
              </td>
              <td>
                <div class="highlight-column">
                  <div class="rect" style={{ background: row.highlight }}></div>
                </div>
              </td>
              <td>
                <div class="input-column">
                  <bk-popover placement="top" disabled={!row.disabled}>
                    <ValidateInput
                      ref={setItemRef("regex", index)}
                      value={row.pattern}
                      rules={regexRules}
                      disabled={row.disabled}
                      on-input={(value) => (row.pattern = value.trim())}
                    />
                    <span slot="content">
                      <i18n path="聚类正则已生效，请前往 {0} 修改">
                        <bk-button
                          text
                          theme="primary"
                          size="small"
                          style="padding:0;color:#699DF4"
                          on-click={handleOpenClusterConfig}
                        >
                          {t("聚类设置")}
                        </bk-button>
                      </i18n>
                    </span>
                  </bk-popover>
                </div>
              </td>
              <td>
                <div class="input-column">
                  <bk-popover placement="top" disabled={!row.disabled}>
                    <ValidateInput
                      ref={setItemRef("occupy", index)}
                      value={row.occupy}
                      rules={occupyRules}
                      disabled={row.disabled}
                      on-input={(value) => (row.occupy = value.trim())}
                    />
                    <span slot="content">
                      <i18n path="聚类正则已生效，请前往 {0} 修改">
                        <bk-button
                          text
                          theme="primary"
                          size="small"
                          style="padding:0;color:#699DF4"
                          on-click={handleOpenClusterConfig}
                        >
                          {t("聚类设置")}
                        </bk-button>
                      </i18n>
                    </span>
                  </bk-popover>
                </div>
              </td>
              <td>
                <div class="action-column">
                  <span on-click={() => handleDeleteItem(index)}>
                    <log-icon
                      type="circle-minus-filled"
                      class={{
                        "delete-icon": true,
                        "is-disabled": row.disabled,
                      }}
                    />
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  },
});
