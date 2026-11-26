# qa-knowledge-base

测试知识库的框架仓：定义目录规范、规则 front-matter、影响索引结构，并提供一致性校验器。

本仓**不存放任何项目的业务规则**。业务规则与 changelog 放在各项目的知识库实例中，通过本仓的规范约束。

## 目录结构

```text
qa-knowledge-base/
├── README.md
├── CHANGELOG.md
├── schema/
│   ├── knowledge-structure.md   知识库目录与分层规范
│   ├── rule-frontmatter.md      规则文件必备字段
│   └── impact-index.md          影响索引结构与校验规则
├── templates/
│   ├── rule.md                  业务规则模板
│   ├── gotcha.md                踩坑模板
│   ├── changelog.md             变更记录模板
│   └── impact-index.yaml        影响索引模板
└── tools/
    └── knowledge_guard.py       一致性校验器
```

## 接入方式

作为 submodule 挂到项目仓：

```powershell
git submodule add <本仓地址> vendor/knowledge-base
git submodule update --init --recursive
```

## 校验器用法

```powershell
# 传统单仓布局（knowledge/ 与 testcases/ 同在项目根）
python vendor/knowledge-base/tools/knowledge_guard.py --project-root . --strict

# 知识库与用例分仓（交付物库 + 代码仓）
python vendor/knowledge-base/tools/knowledge_guard.py `
  --project-root . `
  --knowledge-root ..\it-nas\Project-LspQuote\Common\知识库 `
  --testcases-root .\tests `
  --strict
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--project-root` | 脚本上两级目录 | 项目根，用于解析 `tests/` 等相对路径 |
| `--knowledge-root` | `<project-root>/knowledge` | 知识库实例目录 |
| `--testcases-root` | `<project-root>/testcases` | 用例清单目录 |
| `--strict` | 关闭 | 警告也视为失败 |
| `--quiet` | 关闭 | 只输出汇总 |

## 校验内容

| 编号 | 校验项 |
| --- | --- |
| A | 规则 front-matter 完整性与合法性 |
| B | 影响索引结构、ID 唯一、引用文档存在 |
| C | `regression_targets` 的 case_id 是否存在于用例清单 |
| D | 规则/踩坑的时效性（超过 180 天告警） |
| E | changelog 的 change_id 必须能在影响索引中找到 |
| G | 用例清单与脚本的 case_id 双向对齐 |
| H | 文档内链无死链 |

## 约定

1. 规则文件必须带完整 front-matter，无来源的规则不得写入。
2. 影响索引变更必须与知识库改动在同一次提交中完成。
3. 变更记录中的 `change_id` 必须对应影响索引条目。
4. 用例与脚本的 case_id 必须逐字符一致。
