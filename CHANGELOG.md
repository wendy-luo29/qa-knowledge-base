# 变更记录

## [Unreleased]

### 新增
- 从项目仓 `scripts/knowledge_guard.py` 抽取校验器，支持 `--project-root` / `--knowledge-root` / `--testcases-root` 三根参数，适配知识库与用例分仓。
- 新增知识库目录规范、规则 front-matter 规范、影响索引规范。
- 新增规则、踩坑、变更记录、影响索引四个模板。

### 约定
- 本仓不存放任何项目的业务规则；业务规则放各项目知识库实例。
- 空项目（`testcases/` 与 `tests/` 均无用例）不再触发 CASE-MAP 告警，避免框架模板在 `--strict` 下误阻断。
