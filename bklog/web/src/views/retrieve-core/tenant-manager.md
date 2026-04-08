# TenantManager 使用说明

## 简介

`TenantManager` 是一个用于管理租户用户信息的工具类，提供了用户信息的获取、缓存、分组管理等功能。它支持多租户环境下的用户信息批量获取，并提供了分组机制来满足不同业务场景的需求。

## 导入方式

```typescript
import { tenantManager, TenantManagerEvent, UserInfoLoadedEventData } from '@/views/retrieve-core/tenant-manager';
```

## 核心功能

### 1. 租户ID管理

#### `setTenantId(tenantId: string | null | undefined)`

设置当前租户ID。

```typescript
tenantManager.setTenantId('tenant-123');
```

#### `getTenantId(): string | null | undefined`

获取当前租户ID。

```typescript
const tenantId = tenantManager.getTenantId();
```

### 2. 获取用户信息

#### `getUserDisplayInfo(tenantId: string, group?: string): Promise<UserDisplayInfo | null>`

获取单个用户的显示信息。

**参数：**
- `tenantId`: 租户ID（在多租户环境下）或用户名（在非多租户环境下）
- `group`: 可选，分组名称，默认为 `'default'`

**返回：** `Promise<UserDisplayInfo | null>`

**示例：**

```typescript
// 使用默认分组
const userInfo = await tenantManager.getUserDisplayInfo('user001');

// 指定分组
const userInfo = await tenantManager.getUserDisplayInfo('user001', 'businessA');
```

#### `batchGetUserDisplayInfo(tenantIds: string[], group?: string): Promise<Map<string, UserDisplayInfo>>`

批量获取用户显示信息。

**参数：**
- `tenantIds`: 租户ID数组
- `group`: 可选，分组名称，默认为 `'default'`

**返回：** `Promise<Map<string, UserDisplayInfo>>`

**示例：**

```typescript
// 使用默认分组
const users = await tenantManager.batchGetUserDisplayInfo(['user001', 'user002', 'user003']);

// 指定分组
const users = await tenantManager.batchGetUserDisplayInfo(['user001', 'user002', 'user003'], 'businessA');
```

#### `getAllUserInfo(group?: string): Promise<Map<string, UserDisplayInfo>>`

获取所有用户信息。如果当前有执行中的请求，会等待所有请求完成后再返回。

**参数：**
- `group`: 可选，分组名称。如果指定，则只返回该分组下的用户信息

**返回：** `Promise<Map<string, UserDisplayInfo>>`

**示例：**

```typescript
// 获取所有用户
const allUsers = await tenantManager.getAllUserInfo();

// 获取指定分组下的用户
const businessAUsers = await tenantManager.getAllUserInfo('businessA');
```

#### `getUsersByGroup(group?: string): Map<string, UserDisplayInfo>`

同步获取指定分组下的所有用户信息（不需要等待请求完成）。

**参数：**
- `group`: 可选，分组名称，默认为 `'default'`

**返回：** `Map<string, UserDisplayInfo>`

**示例：**

```typescript
const users = tenantManager.getUsersByGroup('businessA');
```

### 3. 分组管理

TenantManager 支持分组功能，允许将用户信息按业务场景进行分组管理。每个用户可以属于多个分组。

**分组使用场景：**

- **业务A**：需要获取 User1, User2, User3，渲染时只显示这3个用户
- **业务B**：需要获取 User1, User4, User5，渲染时只显示这3个用户（即使缓存中有 User1-User5）

**示例：**

```typescript
// 业务A：获取 User1, User2, User3
await tenantManager.batchGetUserDisplayInfo(['User1', 'User2', 'User3'], 'businessA');
const usersA = await tenantManager.getAllUserInfo('businessA');
// usersA 只包含 User1, User2, User3

// 业务B：获取 User1, User4, User5
await tenantManager.batchGetUserDisplayInfo(['User1', 'User4', 'User5'], 'businessB');
const usersB = await tenantManager.getAllUserInfo('businessB');
// usersB 只包含 User1, User4, User5

// 获取所有用户（不指定分组）
const allUsers = await tenantManager.getAllUserInfo();
// allUsers 包含所有缓存的用户（User1-User5）

// 同步获取指定分组下的用户
const businessAUsers = tenantManager.getUsersByGroup('businessA');
```

### 4. 缓存管理

#### `clearCache(): void`

清除所有用户信息缓存和分组信息。

```typescript
tenantManager.clearCache();
```

#### `getCacheSize(): number`

获取缓存中用户信息的数量。

```typescript
const size = tenantManager.getCacheSize();
```

### 5. 事件监听

TenantManager 继承自 `EventEmitter`，支持事件监听机制。

#### 事件类型

- `userInfoLoaded`: 用户信息加载完成时触发
- `userInfoUpdated`: 用户信息更新时触发

#### `on(event: TenantManagerEvent, callback: (...args: any[]) => void): this`

监听事件。

**示例：**

```typescript
// 监听用户信息更新事件
tenantManager.on('userInfoUpdated', (data: UserInfoLoadedEventData) => {
  console.log('用户信息已更新:', data.tenantIds);
  console.log('用户信息:', data.userInfo);
  
  // data.tenantIds: string[] - 更新的用户ID列表
  // data.userInfo: Map<string, UserDisplayInfo> - 用户信息Map
});

// 监听用户信息加载事件
tenantManager.on('userInfoLoaded', (data: UserInfoLoadedEventData) => {
  console.log('用户信息已加载:', data.tenantIds);
});
```

#### `off(event: TenantManagerEvent, callback?: (...args: any[]) => void): void`

移除事件监听。

**示例：**

```typescript
const handler = (data: UserInfoLoadedEventData) => {
  console.log('用户信息更新:', data);
};

// 添加监听
tenantManager.on('userInfoUpdated', handler);

// 移除特定监听器
tenantManager.off('userInfoUpdated', handler);

// 移除该事件的所有监听器
tenantManager.off('userInfoUpdated');
```

## 数据接口

### UserDisplayInfo

用户信息接口定义：

```typescript
interface UserDisplayInfo {
  login_name: string;      // 登录名
  full_name: string;       // 全名
  display_name: string;    // 显示名称
  groups?: string[];      // 用户所属的分组列表
  [key: string]: any;      // 其他扩展字段
}
```

### UserInfoLoadedEventData

事件数据接口定义：

```typescript
interface UserInfoLoadedEventData {
  tenantIds: string[];                                    // 用户ID列表
  userInfo: Map<string, UserDisplayInfo>;                 // 用户信息Map
}
```

## 完整使用示例

### 示例1：基本使用

```typescript
import { tenantManager } from '@/views/retrieve-core/tenant-manager';

// 设置租户ID
tenantManager.setTenantId('tenant-123');

// 获取单个用户信息
const user = await tenantManager.getUserDisplayInfo('user001');
console.log(user?.display_name);

// 批量获取用户信息
const users = await tenantManager.batchGetUserDisplayInfo(['user001', 'user002', 'user003']);
users.forEach((userInfo, loginName) => {
  console.log(`${loginName}: ${userInfo.display_name}`);
});
```

### 示例2：分组管理

```typescript
import { tenantManager } from '@/views/retrieve-core/tenant-manager';

// 业务场景A：获取并管理用户列表
async function initBusinessA() {
  // 获取业务A需要的用户
  await tenantManager.batchGetUserDisplayInfo(['User1', 'User2', 'User3'], 'businessA');
  
  // 等待所有请求完成，获取业务A的用户列表
  const usersA = await tenantManager.getAllUserInfo('businessA');
  
  // 渲染用户列表
  renderUserList(Array.from(usersA.values()));
}

// 业务场景B：获取并管理用户列表
async function initBusinessB() {
  // 获取业务B需要的用户
  await tenantManager.batchGetUserDisplayInfo(['User1', 'User4', 'User5'], 'businessB');
  
  // 等待所有请求完成，获取业务B的用户列表
  const usersB = await tenantManager.getAllUserInfo('businessB');
  
  // 渲染用户列表（只显示业务B的用户）
  renderUserList(Array.from(usersB.values()));
}

// 使用
initBusinessA();
initBusinessB();
```

### 示例3：事件监听

```typescript
import { tenantManager, UserInfoLoadedEventData } from '@/views/retrieve-core/tenant-manager';

// 监听用户信息更新
const handleUserInfoUpdate = (data: UserInfoLoadedEventData) => {
  console.log('用户信息已更新:', data.tenantIds);
  
  // 更新UI
  data.userInfo.forEach((userInfo, loginName) => {
    updateUserDisplay(loginName, userInfo);
  });
};

tenantManager.on('userInfoUpdated', handleUserInfoUpdate);

// 批量获取用户信息（会自动触发事件）
await tenantManager.batchGetUserDisplayInfo(['user001', 'user002'], 'businessA');

// 清理：移除事件监听
tenantManager.off('userInfoUpdated', handleUserInfoUpdate);
```

### 示例4：等待所有请求完成

```typescript
import { tenantManager } from '@/views/retrieve-core/tenant-manager';

// 触发多个异步请求
tenantManager.getUserDisplayInfo('user001', 'group1');
tenantManager.getUserDisplayInfo('user002', 'group1');
tenantManager.batchGetUserDisplayInfo(['user003', 'user004'], 'group2');

// 等待所有请求完成，获取指定分组的用户信息
const group1Users = await tenantManager.getAllUserInfo('group1');
console.log('Group1 用户数量:', group1Users.size);

const group2Users = await tenantManager.getAllUserInfo('group2');
console.log('Group2 用户数量:', group2Users.size);
```

### 示例5：缓存管理

```typescript
import { tenantManager } from '@/views/retrieve-core/tenant-manager';

// 获取缓存大小
const cacheSize = tenantManager.getCacheSize();
console.log('当前缓存用户数:', cacheSize);

// 清除缓存
tenantManager.clearCache();
console.log('缓存已清除');
```

### 示例6：Vue组件中使用

```vue
<template>
  <div>
    <div v-for="user in userList" :key="user.login_name">
      {{ user.display_name }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { tenantManager, UserInfoLoadedEventData } from '@/views/retrieve-core/tenant-manager';

const userList = ref<UserDisplayInfo[]>([]);
const groupName = 'businessA';

// 事件处理函数
const handleUserInfoUpdate = (data: UserInfoLoadedEventData) => {
  // 只更新当前分组下的用户
  const groupUsers = tenantManager.getUsersByGroup(groupName);
  userList.value = Array.from(groupUsers.values());
};

onMounted(async () => {
  // 监听事件
  tenantManager.on('userInfoUpdated', handleUserInfoUpdate);
  
  // 获取用户列表
  await tenantManager.batchGetUserDisplayInfo(['user001', 'user002', 'user003'], groupName);
  
  // 等待所有请求完成
  const users = await tenantManager.getAllUserInfo(groupName);
  userList.value = Array.from(users.values());
});

onBeforeUnmount(() => {
  // 清理事件监听
  tenantManager.off('userInfoUpdated', handleUserInfoUpdate);
});
</script>
```

## 注意事项

1. **默认分组**：如果不指定分组，默认使用 `'default'` 分组
2. **异步请求**：`getUserDisplayInfo` 和 `batchGetUserDisplayInfo` 是异步的，会触发后台请求
3. **缓存机制**：用户信息会被缓存，重复请求相同用户不会重复发起API请求
4. **分组隔离**：不同分组的用户信息是隔离的，使用 `getAllUserInfo(group)` 只会返回指定分组的用户
5. **事件触发**：用户信息加载完成后会自动触发 `userInfoUpdated` 事件
6. **多租户环境**：在多租户环境下，需要先设置 `tenantId`，否则会直接返回租户ID作为用户名

## API 总结

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| `setTenantId` | 设置租户ID | `tenantId: string \| null \| undefined` | `void` |
| `getTenantId` | 获取租户ID | - | `string \| null \| undefined` |
| `getUserDisplayInfo` | 获取单个用户信息 | `tenantId: string, group?: string` | `Promise<UserDisplayInfo \| null>` |
| `batchGetUserDisplayInfo` | 批量获取用户信息 | `tenantIds: string[], group?: string` | `Promise<Map<string, UserDisplayInfo>>` |
| `getAllUserInfo` | 获取所有用户信息 | `group?: string` | `Promise<Map<string, UserDisplayInfo>>` |
| `getUsersByGroup` | 同步获取分组用户 | `group?: string` | `Map<string, UserDisplayInfo>` |
| `clearCache` | 清除缓存 | - | `void` |
| `getCacheSize` | 获取缓存大小 | - | `number` |
| `on` | 监听事件 | `event: TenantManagerEvent, callback: Function` | `this` |
| `off` | 移除事件监听 | `event: TenantManagerEvent, callback?: Function` | `void` |

