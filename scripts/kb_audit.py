from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any


try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
CHECKLIST_PATH = ROOT / "kb" / "_checklists" / "nn.yml"
REPORT_PATH = ROOT / "reports" / "kb_audit_nn.md"


@dataclass(frozen=True)
class FileIssue:
    too_short: bool
    missing_headings: list[str]
    forbidden_found: list[str]

    def any(self) -> bool:
        return self.too_short or bool(self.missing_headings) or bool(self.forbidden_found)


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is not installed (import yaml failed).")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _audit_file(
    text: str,
    *,
    min_chars: int,
    must_have_headings: list[str],
    forbid_phrases: list[str],
) -> FileIssue:
    normalized = text.strip()
    too_short = len(normalized) < int(min_chars)

    missing_headings = [h for h in must_have_headings if h not in text]

    lower = text.casefold()
    forbidden_found = [p for p in forbid_phrases if p.casefold() in lower]

    return FileIssue(
        too_short=too_short,
        missing_headings=missing_headings,
        forbidden_found=forbidden_found,
    )


def _recommendation(path: str, issue: FileIssue, *, min_chars: int) -> str:
    parts: list[str] = []
    if issue.too_short:
        parts.append(f"Расширить текст до ≥ {min_chars} символов (добавить факты/нюансы/формулировки).")
    if issue.missing_headings:
        parts.append("Добавить разделы: " + ", ".join(issue.missing_headings) + ".")
    if issue.forbidden_found:
        parts.append("Убрать/переформулировать фразы: " + ", ".join({p for p in issue.forbidden_found}) + ".")

    if not parts:
        return f"- `{path}`: ок."

    recommendation = " ".join(parts)
    return f"- `{path}`: {recommendation}"


def main() -> int:
    timestamp = _dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    report_lines: list[str] = [
        "# Отчёт по базе знаний — NN",
        "",
        f"_Сгенерировано: {timestamp}_",
        "",
    ]

    missing: list[str] = []
    issues: dict[str, FileIssue] = {}

    try:
        data = _load_yaml(CHECKLIST_PATH)
        park = (data.get("parks") or {}).get("nn") or {}

        required_files: list[str] = list(park.get("required_files") or [])
        rules = park.get("content_rules") or {}

        must_have_headings: list[str] = list(rules.get("must_have_headings") or [])
        min_chars: int = int(rules.get("min_chars_per_file") or 0)
        forbid_phrases: list[str] = list(rules.get("forbid_phrases") or [])

        total = len(required_files)
        present = 0

        for rel in required_files:
            file_path = ROOT / rel
            if not file_path.exists():
                missing.append(rel)
                continue

            present += 1
            text = file_path.read_text(encoding="utf-8")
            issue = _audit_file(
                text,
                min_chars=min_chars,
                must_have_headings=must_have_headings,
                forbid_phrases=forbid_phrases,
            )
            if issue.any():
                issues[rel] = issue

        report_lines += [
            "## Сводка",
            f"- Есть файлов: {present} / {total}",
            f"- Отсутствует файлов: {len(missing)}",
            f"- Файлов с проблемами: {len(issues)}",
            "",
        ]

        report_lines.append("## Отсутствующие файлы")
        if missing:
            report_lines += [f"- `{p}`" for p in missing]
        else:
            report_lines.append("- Нет.")
        report_lines.append("")

        report_lines.append("## Файлы с проблемами")
        if issues:
            for rel, issue in sorted(issues.items()):
                tags: list[str] = []
                if issue.too_short:
                    tags.append("короткий")
                if issue.missing_headings:
                    tags.append("нет заголовка(ов)")
                if issue.forbidden_found:
                    tags.append("запрещённые фразы")
                detail = ", ".join(tags) if tags else "проблема"
                report_lines.append(f"- `{rel}`: {detail}")
                if issue.missing_headings:
                    report_lines.append(f"  - Не хватает: {', '.join(issue.missing_headings)}")
                if issue.forbidden_found:
                    found = ", ".join(sorted({p for p in issue.forbidden_found}))
                    report_lines.append(f"  - Найдено: {found}")
        else:
            report_lines.append("- Нет.")
        report_lines.append("")

        report_lines.append("## Рекомендации что дописать")
        if missing or issues:
            if missing:
                for rel in missing:
                    report_lines.append(f"- `{rel}`: создать файл и заполнить по шаблону (суть/факты/нюансы/скрипт ответа).")
            for rel, issue in sorted(issues.items()):
                report_lines.append(_recommendation(rel, issue, min_chars=min_chars))
        else:
            report_lines.append("- Нет.")
        report_lines.append("")

    except Exception as exc:  # always return 0; still write report
        report_lines += [
            "## Ошибка аудита",
            "",
            f"Не удалось выполнить аудит: `{type(exc).__name__}` — {exc}",
            "",
            "Проверьте:",
            f"- наличие чеклиста: `{CHECKLIST_PATH.relative_to(ROOT)}`",
            "- установлен ли PyYAML (`pip install pyyaml`)",
            "",
        ]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Запуск:
# python scripts/kb_audit.py

