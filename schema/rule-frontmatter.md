# 规则文件 front-matter 规范

每个 `rules/<module>/<feature>.md` 必须以下列 front-matter 开头：

```yaml
---
module: <模块名>
feature: <功能名>
version: <规则版本，如 v2.1>
status: active          # active | superseded | draft
confirmed_by: <确认人>
confirmed_date: <yyyy-MM-dd>
source_requirement: <需求编号或证据文件路径>
---
```

## 字段说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `module` | 是 | 与目录名一致 |
| `feature` | 是 | 与文件名一致 |
| `version` | 是 | 规则版本，非接口版本 |
| `status` | 是 | `active` 生效 / `superseded` 被替代 / `draft` 草稿 |
| `confirmed_by` | 是 | 确认人，禁止为空或占位符 |
| `confirmed_date` | 是 | 确认日期 |
| `source_requirement` | 是 | 需求编号或证据文件相对路径，保证可追溯 |

## 约束

1. 缺少任一必填字段，校验器判 ERROR。
2. `status: draft` 的规则不得被用例设计引用为确定口径。
3. 规则被替代时，旧文件改 `status: superseded` 并注明新规则位置，不删除。
4. `confirmed_date` 超过 180 天触发复审告警。
5. 规则正文必须写明判定条件、边界值、数据来源；只有结论没有来源的不合格。

## 正文结构建议

```markdown
## 1. 规则定义
## 2. 判定条件与边界
## 3. 数据来源（表 / 字段 / 查询方式）
## 4. 例外与待确认
## 5. 关联用例
```
