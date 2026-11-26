#!/usr/bin/env python3
"""知识库一致性校验（knowledge guard）。

分层约定：
    requirements/  证据层（需求原文、OpenAPI 快照、待确认清单），不可变
    knowledge/     结论层（rules / gotchas / changelog / impact-index），需定期复核

校验项：
    A. rules/*.md       front-matter 完整性、同 (module, feature) 只允许一个 active、过期未复核
    B. impact-index     change 结构完整性、ID 唯一、knowledge_docs / gotchas 路径存在
    C. impact-index     regression_targets 的 case_id 是否存在于 testcases/（默认 WARN）
    D. gotchas/         NNN 编号唯一、文件名规范
    E. changelog/       必须有 change_id(s) 且能在 impact-index 找到对应条目
    F. knowledge/       内部 Markdown 相对链接死链（WARN）
    G. testcases/*.yaml 与 tests/**/*.py 的 case_id 双向对齐

用法：
    python scripts/knowledge_guard.py
    python scripts/knowledge_guard.py --strict    # WARN 也返回非 0
退出码：0 = 无 ERROR；1 = 存在 ERROR（--strict 时含 WARN）
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"
TESTCASES = ROOT / "testcases"

RULES_DIR = KNOWLEDGE / "rules"
GOTCHAS_DIR = KNOWLEDGE / "gotchas"
CHANGELOG_DIR = KNOWLEDGE / "changelog"
INDEX_FILE = KNOWLEDGE / "impact-index.yaml"


def configure(
    project_root: str | None = None,
    knowledge_root: str | None = None,
    testcases_root: str | None = None,
) -> None:
    """按命令行参数切换校验根目录，支持知识库与用例分仓存放。"""
    global ROOT, KNOWLEDGE, TESTCASES
    global RULES_DIR, GOTCHAS_DIR, CHANGELOG_DIR, INDEX_FILE
    if project_root:
        ROOT = Path(project_root).resolve()
    KNOWLEDGE = Path(knowledge_root).resolve() if knowledge_root else ROOT / "knowledge"
    TESTCASES = Path(testcases_root).resolve() if testcases_root else ROOT / "testcases"
    RULES_DIR = KNOWLEDGE / "rules"
    GOTCHAS_DIR = KNOWLEDGE / "gotchas"
    CHANGELOG_DIR = KNOWLEDGE / "changelog"
    INDEX_FILE = KNOWLEDGE / "impact-index.yaml"

STALE_DAYS = 180
REQUIRED_RULE_FIELDS = ("module", "feature", "version", "status", "confirmed_by", "confirmed_date")
VALID_STATUS = {"active", "superseded", "draft"}

GOTCHA_NAME_RE = re.compile(r"^gotcha_(\d{3})_.+\.md$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CASE_ID_RE = re.compile(r"case_id:\s*[\"']?([A-Za-z0-9_\-]+)")
CHANGE_ID_RE = re.compile(r"CHG-[0-9A-Za-z]+")

errors: list[str] = []
warnings: list[str] = []


def err(code: str, msg: str) -> None:
    errors.append(f"[{code}] {msg}")


def warn(code: str, msg: str) -> None:
    warnings.append(f"[{code}] {msg}")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_front_matter(path: Path) -> dict | None:
    """解析 Markdown YAML front-matter；无 front-matter 返回 None。"""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        err("READ", f"{rel(path)} 读取失败：{exc}")
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("\n---", 2)
    if len(parts) < 2:
        return None
    body = parts[0].lstrip("-").strip()
    try:
        data = yaml.safe_load(body) or {}
    except yaml.YAMLError as exc:
        err("YAML", f"{rel(path)} front-matter 解析失败：{exc}")
        return None
    return data if isinstance(data, dict) else None


def parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def load_index() -> dict:
    if not INDEX_FILE.is_file():
        err("INDEX", "缺少 knowledge/impact-index.yaml")
        return {}
    try:
        data = yaml.safe_load(INDEX_FILE.read_text(encoding="utf-8-sig")) or {}
    except yaml.YAMLError as exc:
        err("INDEX", f"impact-index.yaml 解析失败：{exc}")
        return {}
    return data if isinstance(data, dict) else {}


def collect_case_ids() -> set[str]:
    """从 testcases/*.yaml 收集 case_id（xlsx 不在校验范围）。"""
    found: set[str] = set()
    if not TESTCASES.is_dir():
        return found
    for path in TESTCASES.rglob("*.yaml"):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        found.update(CASE_ID_RE.findall(text))
    return found


def collect_script_case_ids() -> set[str]:
    """从 tests/**/*.py 的 `# case_id:` 注释收集实际可执行用例编号。"""
    found: set[str] = set()
    tests_dir = ROOT / "tests"
    if not tests_dir.is_dir():
        return found
    for path in tests_dir.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        found.update(CASE_ID_RE.findall(text))
    return found


def check_case_mapping(list_ids: set[str], script_ids: set[str]) -> None:
    """用例清单与脚本双向对齐。

    清单有、脚本无 → ERROR（回归索引会指向跑不了的用例）；
    脚本有、清单无 → WARN（脚本未登记，报告无法关联 AC）。
    """
    if not list_ids and not script_ids:
        warn("CASE-MAP", "testcases/*.yaml 与 tests/**/*.py 均未声明 case_id")
        return
    for cid in sorted(list_ids - script_ids):
        err("CASE-MAP", f"用例清单中的 {cid} 在 tests/ 脚本里找不到 `# case_id:`，清单不可执行")
    for cid in sorted(script_ids - list_ids):
        warn("CASE-MAP", f"脚本中的 {cid} 未登记到 testcases/ 用例清单")


def check_rules() -> None:
    if not RULES_DIR.is_dir():
        warn("RULES", "knowledge/rules/ 不存在")
        return

    active_by_feature: dict[tuple[str, str], list[str]] = {}
    today = date.today()

    for path in sorted(RULES_DIR.rglob("*.md")):
        fm = read_front_matter(path)
        if fm is None:
            err("RULES-FM", f"{rel(path)} 缺少 front-matter")
            continue

        missing = [f for f in REQUIRED_RULE_FIELDS if not fm.get(f)]
        if fm.get("status") == "draft":
            missing = [f for f in missing if f not in ("confirmed_by", "confirmed_date")]
        if missing:
            err("RULES-FM", f"{rel(path)} front-matter 缺少字段：{', '.join(missing)}")

        status = fm.get("status")
        if status not in VALID_STATUS:
            err("RULES-STATUS", f"{rel(path)} status 非法：{status!r}")

        if status == "active":
            key = (str(fm.get("module")), str(fm.get("feature")))
            active_by_feature.setdefault(key, []).append(rel(path))
            confirmed = parse_date(fm.get("confirmed_date"))
            if confirmed is None:
                err("RULES-DATE", f"{rel(path)} confirmed_date 不是合法日期：{fm.get('confirmed_date')!r}")
            elif (today - confirmed).days > STALE_DAYS:
                warn(
                    "RULES-STALE",
                    f"{rel(path)} 已 {(today - confirmed).days} 天未复核"
                    f"（> {STALE_DAYS} 天，建议确认后更新 confirmed_date）",
                )

        source = fm.get("source_requirement")
        if source:
            target = (ROOT / str(source)).resolve()
            if not target.is_file():
                err("RULES-SOURCE", f"{rel(path)} source_requirement 指向的文件不存在：{source}")
        elif status == "active":
            warn("RULES-SOURCE", f"{rel(path)} 未声明 source_requirement，追溯链断裂")

    for (module, feature), docs in active_by_feature.items():
        if len(docs) > 1:
            err(
                "RULES-DUP",
                f"{module}/{feature} 存在多个 active 规则文档：{', '.join(docs)}",
            )


def check_gotchas() -> None:
    if not GOTCHAS_DIR.is_dir():
        warn("GOTCHA", "knowledge/gotchas/ 不存在")
        return
    seen: dict[str, Path] = {}
    for path in sorted(GOTCHAS_DIR.glob("*.md")):
        m = GOTCHA_NAME_RE.match(path.name)
        if not m:
            err("GOTCHA-NAME", f"{rel(path)} 命名不符合 gotcha_NNN_<主题>.md")
            continue
        number = m.group(1)
        if number in seen:
            err("GOTCHA-DUP", f"gotcha 编号 {number} 重复：{rel(seen[number])} / {rel(path)}")
        else:
            seen[number] = path


def check_index(index: dict, case_ids: set[str]) -> set[str]:
    changes = index.get("changes") or []
    if not isinstance(changes, list):
        err("INDEX", "changes 必须是列表")
        return set()

    ids: set[str] = set()
    for i, change in enumerate(changes, start=1):
        if not isinstance(change, dict):
            err("INDEX", f"changes 第 {i} 项不是映射")
            continue
        cid = change.get("id")
        where = f"changes[{i}]" + (f" ({cid})" if cid else "")
        if not cid:
            err("INDEX", f"{where} 缺少 id")
        elif cid in ids:
            err("INDEX", f"{where} id 重复")
        else:
            ids.add(str(cid))

        for field in ("module", "feature", "date", "type"):
            if not change.get(field):
                err("INDEX", f"{where} 缺少字段 {field}")
        if not change.get("regression_targets") and not change.get("coverage_gap"):
            err(
                "INDEX",
                f"{where} 缺少 regression_targets（无自动化用例时必须用 coverage_gap 说明原因）",
            )

        if change.get("date") and parse_date(change["date"]) is None:
            err("INDEX", f"{where} date 非法：{change['date']!r}")

        for doc in change.get("knowledge_docs") or []:
            if not (ROOT / str(doc)).is_file():
                err("INDEX-DOC", f"{where} knowledge_docs 不存在：{doc}")

        for gotcha in change.get("gotchas") or []:
            candidates = list(GOTCHAS_DIR.glob(f"{gotcha}*.md"))
            if not candidates:
                err("INDEX-GOTCHA", f"{where} gotchas 引用的文件不存在：{gotcha}")

        for case_id in change.get("regression_targets") or []:
            if not case_ids:
                warn("INDEX-CASE", f"{where} 无法校验 case_id（testcases/ 未找到 YAML 用例）")
                break
            if str(case_id) not in case_ids:
                warn(
                    "INDEX-CASE",
                    f"{where} regression_targets 中的 {case_id} 不在 testcases/ 中（幽灵回归项）",
                )

    registry = index.get("module_registry") or {}
    if registry and not isinstance(registry, dict):
        err("INDEX", "module_registry 必须是映射")
    for module, info in (registry.items() if isinstance(registry, dict) else []):
        if not isinstance(info, dict):
            err("INDEX", f"module_registry.{module} 必须是映射")
            continue
        for feature, finfo in (info.get("features") or {}).items():
            if not isinstance(finfo, dict):
                continue
            for field in ("config_path", "test_path"):
                target = finfo.get(field)
                if target and not (ROOT / str(target)).exists():
                    warn(
                        "INDEX-REG",
                        f"module_registry.{module}.{feature}.{field} 不存在：{target}",
                    )
    return ids


def check_changelog(index_ids: set[str], index: dict) -> None:
    if not CHANGELOG_DIR.is_dir():
        warn("CHANGELOG", "knowledge/changelog/ 不存在")
        return
    referenced: set[str] = set()
    for path in sorted(CHANGELOG_DIR.glob("*.md")):
        fm = read_front_matter(path)
        if fm is None:
            err("CHANGELOG-FM", f"{rel(path)} 缺少 front-matter（需声明 change_id / change_ids）")
            continue
        ids = fm.get("change_ids") or fm.get("change_id")
        if isinstance(ids, str):
            ids = [ids]
        if not ids:
            err("CHANGELOG-FM", f"{rel(path)} 未声明 change_id / change_ids")
            continue
        for cid in ids:
            referenced.add(str(cid))
            if index_ids and str(cid) not in index_ids:
                err("CHANGELOG-ORPHAN", f"{rel(path)} 引用的 {cid} 在 impact-index 中不存在")

    for change in index.get("changes") or []:
        if not isinstance(change, dict):
            continue
        cid = str(change.get("id") or "")
        if cid and referenced and cid not in referenced:
            warn("INDEX-CHLOG", f"change {cid} 没有对应的 changelog 记录")


def check_links() -> None:
    if not KNOWLEDGE.is_dir():
        return
    for path in KNOWLEDGE.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for raw in LINK_RE.findall(text):
            target = raw.strip().split()[0]
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            if not (path.parent / target).resolve().exists():
                warn("LINK", f"{rel(path)} 死链：{raw}")


def main() -> int:
    parser = argparse.ArgumentParser(description="知识库一致性校验")
    parser.add_argument("--strict", action="store_true", help="把 WARN 也视为失败")
    parser.add_argument("--quiet", action="store_true", help="只输出汇总")
    parser.add_argument("--project-root", help="项目根目录，默认取脚本上级目录")
    parser.add_argument("--knowledge-root", help="知识库目录，默认 <project-root>/knowledge")
    parser.add_argument("--testcases-root", help="用例目录，默认 <project-root>/testcases")
    args = parser.parse_args()

    configure(args.project_root, args.knowledge_root, args.testcases_root)

    if not KNOWLEDGE.is_dir():
        print(f"未找到知识库目录：{KNOWLEDGE}")
        return 1

    check_rules()
    check_gotchas()
    index = load_index()
    list_ids = collect_case_ids()
    script_ids = collect_script_case_ids()
    check_case_mapping(list_ids, script_ids)
    index_ids = check_index(index, list_ids or script_ids)
    check_changelog(index_ids, index)
    check_links()

    if not args.quiet:
        for line in errors:
            print(f"ERROR {line}")
        for line in warnings:
            print(f"WARN  {line}")

    print(f"\n知识库校验：{len(errors)} 个错误，{len(warnings)} 个警告")
    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
