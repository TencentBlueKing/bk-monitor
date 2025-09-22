# table & search-select 联动

## 核心实现机制

1. 双向数据同步
   - 从表格筛选器到搜索框：通过handleFilterChange方法实现
   - 从搜索框到表格筛选器：通过handleSearchChange方法实现
2. 数据结构映射
   - 搜索框使用searchKey数组存储条件
   - 表格筛选器使用createdValues和updatedByValues数组存储筛选值
   - 通过tableKey强制重新渲染表格

## 实现步骤详解

### 步骤1：初始化数据属性

```typescript
searchKey: any[] = []; // 搜索条件
createdValues: string[] = []; // 创建者筛选值
updatedByValues: string[] = []; // 更新者筛选值
tableKey = 0; // 表格重新渲染key
```

### 步骤2：实现搜索框到表格的联动 (handleSearchChange)

1. 从searchKey中提取创建者和更新者条件
2. 更新对应的筛选值数组(createdValues, updatedByValues)
3. 递增tableKey强制表格重新渲染
4. 调用getTableData()获取新数据

### 步骤3：实现表格到搜索框的联动 (handleFilterChange)

1. 监听表格的on-filter-change事件
2. 创建新的搜索条件数组
3. 将表格筛选器的值同步到搜索框条件中
4. 处理创建者和更新者的条件添加/更新/删除
5. 更新searchKey并重新获取数据

### 步骤4：模板配置

1. 搜索框设置：onChange={this.handleSearchChange}
2. 表格设置：
   - key={this.tableKey}用于强制重新渲染
   - on-filter-change={this.handleFilterChange}监听筛选变化
3. 表格列设置：
   - filtered-value={this.createdValues}绑定筛选值
   - column-key="createdBy"设置列标识
   
## 具体代码
```tsx
searchKey: any[] = []; // 计算任务搜索内容
createdValues: string[] = [];
updatedByValues: string[] = [];

handleSearchChange() {
    // 提取创建者和更新者的筛选值
    const creatorCondition = this.searchKey.find(item => item.id === 'creator');
    const updaterCondition = this.searchKey.find(item => item.id === 'updater');

    // 更新筛选值
    this.createdValues = creatorCondition ? creatorCondition.values.map((item: any) => item.id) : [];
    this.updatedByValues = updaterCondition ? updaterCondition.values.map((item: any) => item.id) : [];

    // 强制重新渲染表格
    this.tableKey += 1;

    // 获取表格数据
    this.getTableData();
  }

  handleFilterChange(filters: { [key: string]: string[] }) {
    // 处理筛选器变化，将值同步到搜索框
    console.log('Filter changed:', filters);

    // 创建新的搜索条件数组
    const newSearchKey = [...this.searchKey];

    // 处理createdBy筛选器
    if (filters.createdBy && filters.createdBy.length > 0) {
      // 查找是否已存在creator条件
      const creatorIndex = newSearchKey.findIndex(item => item.id === 'creator');
      const creatorValues = filters.createdBy.map((value: string) => ({ id: value, name: value }));

      if (creatorIndex >= 0) {
        // 更新现有条件
        newSearchKey[creatorIndex] = {
          id: 'creator',
          name: this.$t('RESOURCE:创建者'),
          values: creatorValues
        };
      } else {
        // 添加新条件
        newSearchKey.push({
          id: 'creator',
          name: this.$t('RESOURCE:创建者'),
          values: creatorValues
        });
      }
    } else {
      // 移除creator条件
      const creatorIndex = newSearchKey.findIndex(item => item.id === 'creator');
      if (creatorIndex >= 0) {
        newSearchKey.splice(creatorIndex, 1);
      }
    }

    // 处理updatedBy筛选器 (注意：表格列中使用的是updatedBy)
    if (filters.updatedBy && filters.updatedBy.length > 0) {
      // 查找是否已存在updater条件
      const updaterIndex = newSearchKey.findIndex(item => item.id === 'updater');
      const updaterValues = filters.updatedBy.map((value: string) => ({ id: value, name: value }));

      if (updaterIndex >= 0) {
        // 更新现有条件
        newSearchKey[updaterIndex] = {
          id: 'updater',
          name: this.$t('RESOURCE:更新者'),
          values: updaterValues
        };
      } else {
        // 添加新条件
        newSearchKey.push({
          id: 'updater',
          name: this.$t('RESOURCE:更新者'),
          values: updaterValues
        });
      }
    } else {
      // 移除updater条件
      const updaterIndex = newSearchKey.findIndex(item => item.id === 'updater');
      if (updaterIndex >= 0) {
        newSearchKey.splice(updaterIndex, 1);
      }
    }

    // 更新搜索条件
    this.searchKey = newSearchKey;

    // 重新获取表格数据
    this.getTableData();
  }
  
public render(h: CreateElement) {
	return (
    //...
    <bk-search-select
    	style="width: 640px;"
        show-condition={false}
        v-model={this.searchKey}
        data={this.searchData}
        placeholder={this.$t('集群名称、归属业务、创建者、更新者')}
        onChange={this.handleSearchChange}
        />
    <bk-table
    	key={this.tableKey}
        v-bkloading={{ isLoading: this.loading }}
        data={this.tableData}
        pagination={this.pagination}
        on-page-change={this.handlePageChange}
        on-page-limit-change={this.handlePageLimitChange}
        on-filter-change={this.handleFilterChange}
            >
            <bk-table-column
            	label={this.$t('RESOURCE:创建者')}
                prop="createdBy"
                filters={this.createdByFilters}
                filterMethod={(value: string, row: import('./types').AddonCluster) => {
                  return row.createdBy === value;
                }}
                filtered-value={this.createdValues}
                column-key="createdBy"
              ></bk-table-column>
        </bk-table>
    )


}
```