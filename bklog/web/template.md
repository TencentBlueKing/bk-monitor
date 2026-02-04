> **《AI 项目认知抽象 · 极简设计规则》**

---

# 🧠 极致简化设计规则（用于生成 Skills + Rules）

## 一、总原则（只记这 3 条）

### P1. 只抽象「稳定结构」，忽略「具体实现」

* 不关心怎么写
* 只关心**写在哪里**

---

### P2. 只记录「边界」，不记录「流程」

* 谁能做什么
* 谁**绝对不能**做什么

---

### P3. 一条规则 = 一个“否定约束”

* 不写推荐
* 只写禁止

---

## 二、Skills 生成规则（世界观抽象）

> Skills = **“这个项目的地图”**

### S1. Skills 只包含 5 类信息

只允许这 5 类，多一个都是噪音：

1. Project 形态
2. 技术选型
3. 分层结构
4. 数据流向
5. 领域对象

---

### S2. 每一类信息 ≤ 3 行

```txt
Project: <SPA / MPA / Admin>
UI: <UI lib>
State: <State tool>

Arch:
- <Layer>: <Responsibility>

DataFlow:
A → B → C

Domain:
- <Core nouns>
```

❌ 不允许解释
❌ 不允许举例

---

### S3. Skills 不出现任何动词（除 → ）

❌ handle / process / calculate
✅ routing / render / mapping（名词化）

> **一旦出现“动作”，token 立刻失控**

---

## 三、Rules 生成规则（行为约束抽象）

> Rules = **“AI 的刹车系统”**

---

### R1. Rules 只来源于「你不希望再看到的错误」

问自己一句话：

> **“如果 AI 再犯一次这个错，我能不能接受？”**

不能接受 → Rule
能接受 → 不写

---

### R2. Rule 统一句式（不可变）

```txt
No <Action> in <Layer>
```

示例：

```txt
No API call in View
No async in mutation
No logic in Page
```

任何复杂描述都一律删掉。

---

### R3. Rules 数量 ≤ 10

超过 10 条 =
👉 项目本身已经失控
👉 AI 只是背锅

---

## 四、ChangeImpact 生成规则（改动半径）

> 这是 Rules 里**唯一允许出现 → 的地方**

---

### C1. 只覆盖 4 种变更类型

```txt
ChangeImpact:
- UI change → ?
- Field change → ?
- Logic change → ?
- Data change → ?
```

---

### C2. 右侧只允许写「层级」，不写文件

```txt
Field change → Service + Store + View
```

❌ `booking.service.ts`
❌ `useBookingForm.ts`

---

## 五、抽象现有项目的操作流程（你照着做）

### Step 1：扫目录（3 分钟）

只看：

* src/pages
* src/views
* src/store
* src/services

👉 抽出层级名 & 职责

---

### Step 2：扫「最乱的 2 个文件」

问自己：

* 这个逻辑**本来应该在哪一层**？

👉 这一步直接生成 Rules

---

### Step 3：扫接口 & 数据对象

只做一件事：

* 提取**业务名词**

👉 生成 Domain

---

### Step 4：删到只剩“地图”

如果一句话删掉后：

* AI 还能正确判断“改哪里”

👉 保留
否则删除

---

## 六、最终校验规则（非常重要）

对你生成的 Skills + Rules，做 3 个测试：

### ✅ 测试 1：盲改测试

> “新增一个字段”

AI 能不能**不看代码就说出改动层级**？

---

### ✅ 测试 2：刹车测试

> “顺手帮我优化一下”

AI 会不会被 Rules 阻止？

---

### ✅ 测试 3：迁移测试

把 Skills 给一个**不熟项目的人**，
他能不能画出项目结构？

---

## 七、你现在已经可以做到什么程度？

有了这套规则，你可以：

* 🧠 从 **任何 Vue 项目** 抽出 AI Skills
* 📉 把 AI 上下文压到 **100 行以内**
* 🔁 随着项目演进，Rules 自然生长
* 🚫 明显减少 AI“越界发挥”

---

## 最后一句非常重要的话

> **Skills 不是为了“描述项目”**
> **而是为了“限制 AI 的想象空间”**


