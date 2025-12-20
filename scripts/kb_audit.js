const fs = require("fs");
const path = require("path");

const MIN_CHARS = 200;
const MUST_HAVE_HEADINGS = ["## Суть", "## Факты", "## Важные нюансы", "## Как объяснять гостю"];
const FORBID_PHRASES = ["я как ИИ", "я бот", "я модель", "по данным", "не могу помочь", "я вас не понял"];

const REQUIRED_FILES = [
  "kb/nn/_meta_source_priority.md",
  "kb/nn/core/contacts.md",
  "kb/nn/core/location.md",
  "kb/nn/core/hours.md",

  "kb/nn/tickets/prices.md",
  "kb/nn/tickets/discounts.md",
  "kb/nn/tickets/after_20.md",
  "kb/nn/tickets/free_entry.md",

  "kb/nn/food/restaurant_general.md",
  "kb/nn/food/kids_menu.md",
  "kb/nn/food/banquet_menu.md",
  "kb/nn/food/own_food_rules.md",

  "kb/nn/rules/visit_rules.md",

  "kb/nn/services/vr.md",
  "kb/nn/services/phygital.md",
  "kb/nn/services/face_painting.md",
  "kb/nn/services/photographers.md",
  "kb/nn/services/gift_cards.md",
  "kb/nn/services/souvenirs.md",
  "kb/nn/services/app.md",

  "kb/nn/parties/birthday.md",
  "kb/nn/parties/graduation.md",
  "kb/nn/programs/animations.md",

  "kb/nn/links/social.md",
  "kb/nn/links/catalogs.md",
  "kb/nn/glossary/terms.md",
];

function readTextSafe(filePath) {
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch {
    return null;
  }
}

function hasForbidden(text) {
  const low = text.toLowerCase();
  return FORBID_PHRASES.filter((p) => low.includes(p.toLowerCase()));
}

function missingHeadings(text) {
  return MUST_HAVE_HEADINGS.filter((h) => !text.includes(h));
}

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function main() {
  ensureDir("reports");

  const missing = [];
  const problems = [];

  for (const rel of REQUIRED_FILES) {
    const abs = path.resolve(rel);
    const text = readTextSafe(abs);

    if (text === null) {
      missing.push(rel);
      continue;
    }

    const fileIssues = [];
    if (text.trim().length < MIN_CHARS) fileIssues.push(`короткий (<${MIN_CHARS} символов)`);
    const mh = missingHeadings(text);
    if (mh.length) fileIssues.push(`нет заголовка(ов): ${mh.join(", ")}`);
    const fp = hasForbidden(text);
    if (fp.length) fileIssues.push(`запрещённые фразы: ${fp.join(", ")}`);

    if (fileIssues.length) problems.push({ file: rel, issues: fileIssues });
  }

  const total = REQUIRED_FILES.length;
  const existCount = total - missing.length;

  let md = `# Отчёт по базе знаний — NN\n\n`;
  md += `_Сгенерировано: ${new Date().toISOString()}_\n\n`;
  md += `## Сводка\n`;
  md += `- Есть файлов: ${existCount} / ${total}\n`;
  md += `- Отсутствует файлов: ${missing.length}\n`;
  md += `- Файлов с проблемами: ${problems.length}\n\n`;

  md += `## Отсутствующие файлы\n`;
  if (!missing.length) md += `- (нет)\n`;
  else missing.forEach((f) => (md += `- \`${f}\`\n`));
  md += `\n`;

  md += `## Файлы с проблемами\n`;
  if (!problems.length) md += `- (нет)\n`;
  else {
    for (const p of problems) {
      md += `- \`${p.file}\`: ${p.issues.join("; ")}\n`;
    }
  }
  md += `\n`;

  md += `## Что сделать дальше\n`;
  md += `1) Создать отсутствующие файлы по шаблону (Суть/Факты/Нюансы/Как объяснять гостю)\n`;
  md += `2) Исправить проблемные файлы: добавить заголовки и убрать запрещённые фразы\n`;

  fs.writeFileSync("reports/kb_audit_nn.md", md, "utf8");
  console.log("OK: reports/kb_audit_nn.md обновлён");
}

main();

