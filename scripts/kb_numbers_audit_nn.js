const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const KB_DIR = path.join(ROOT, "kb", "nn");
const REPORTS_DIR = path.join(ROOT, "reports");
const REPORT_PATH = path.join(REPORTS_DIR, "kb_numbers_audit_nn.md");

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function toRel(p) {
  return path.relative(ROOT, p).split(path.sep).join("/");
}

function listMdFilesRecursive(dirPath) {
  const out = [];
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dirPath, entry.name);
    if (entry.isDirectory()) out.push(...listMdFilesRecursive(full));
    else if (entry.isFile() && entry.name.toLowerCase().endsWith(".md")) out.push(full);
  }
  return out;
}

function readTextSafe(filePath) {
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch {
    return null;
  }
}

function add(map, key, file) {
  if (!map.has(key)) map.set(key, new Set());
  map.get(key).add(file);
}

function normalizeMoney(raw) {
  const digits = raw.replace(/[^\d]/g, "");
  return `${digits} ₽`;
}

function normalizePercent(raw) {
  const digits = raw.replace(/[^\d]/g, "");
  return `${digits}%`;
}

function normalizePhone(raw) {
  const digits = raw.replace(/\D/g, "");
  if (!digits.startsWith("7")) return raw.trim();
  const rest = digits.slice(1);
  if (rest.length !== 10) return raw.trim();
  return `+7${rest}`;
}

function main() {
  ensureDir(REPORTS_DIR);

  const values = new Map(); // "990 ₽" / "50%" -> Set(files)
  const phones = new Map(); // "+7XXXXXXXXXX" -> Set(files)
  const errors = [];
  let scannedFiles = 0;

  try {
    if (!fs.existsSync(KB_DIR)) throw new Error(`KB directory not found: ${toRel(KB_DIR)}`);

    const files = listMdFilesRecursive(KB_DIR);
    scannedFiles = files.length;

    const moneyRe = /\b\d{2,5}\s*₽/g;
    const percentRe = /\b\d{1,3}\s*%/g;
    const phoneRe =
      /\+7[\s-]*(?:\(\s*\d{3}\s*\)|\d{3})[\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?:[\s-]*\d{2})?/g;

    for (const abs of files) {
      const text = readTextSafe(abs);
      if (text === null) {
        errors.push(`Не удалось прочитать файл: \`${toRel(abs)}\``);
        continue;
      }

      const rel = toRel(abs);

      const moneyMatches = text.match(moneyRe) || [];
      for (const m of moneyMatches) add(values, normalizeMoney(m), rel);

      const percentMatches = text.match(percentRe) || [];
      for (const p of percentMatches) add(values, normalizePercent(p), rel);

      const phoneMatches = text.match(phoneRe) || [];
      for (const ph of phoneMatches) add(phones, normalizePhone(ph), rel);
    }
  } catch (e) {
    errors.push(`Ошибка обхода: ${e && e.message ? e.message : String(e)}`);
  }

  function sortKeys(a, b) {
    const aMoney = a.endsWith("₽");
    const bMoney = b.endsWith("₽");
    if (aMoney !== bMoney) return aMoney ? -1 : 1;
    const aNum = Number(a.replace(/[^\d]/g, "")) || 0;
    const bNum = Number(b.replace(/[^\d]/g, "")) || 0;
    if (aNum !== bNum) return aNum - bNum;
    return a.localeCompare(b, "ru");
  }

  const lines = [];
  lines.push("# Аудит чисел — NN");
  lines.push("");
  lines.push(`_Сгенерировано: ${new Date().toISOString()}_`);
  lines.push("");
  lines.push("## Сводка");
  lines.push(`- Файлов просканировано: ${scannedFiles}`);
  lines.push(`- Уникальных значений (₽ и %): ${values.size}`);
  lines.push(`- Уникальных телефонов (+7…): ${phones.size}`);
  lines.push("");

  if (errors.length) {
    lines.push("## Ошибки чтения");
    for (const err of errors) lines.push(`- ${err}`);
    lines.push("");
  }

  lines.push("## Значения (₽ и %)");
  lines.push("| Значение | Файлы |");
  lines.push("|---|---|");
  const valueKeys = Array.from(values.keys()).sort(sortKeys);
  if (!valueKeys.length) {
    lines.push("| (нет) | |");
  } else {
    for (const key of valueKeys) {
      const fileList = Array.from(values.get(key)).sort();
      lines.push(`| ${key} | ${fileList.map((f) => `\`${f}\``).join(", ")} |`);
    }
  }
  lines.push("");

  lines.push("## Телефоны (+7…)");
  lines.push("| Телефон | Файлы |");
  lines.push("|---|---|");
  const phoneKeys = Array.from(phones.keys()).sort((a, b) => a.localeCompare(b));
  if (!phoneKeys.length) {
    lines.push("| (нет) | |");
  } else {
    for (const key of phoneKeys) {
      const fileList = Array.from(phones.get(key)).sort();
      lines.push(`| ${key} | ${fileList.map((f) => `\`${f}\``).join(", ")} |`);
    }
  }
  lines.push("");

  fs.writeFileSync(REPORT_PATH, lines.join("\n"), "utf8");
  console.log("OK: reports/kb_numbers_audit_nn.md обновлён");
}

main();

// Запуск:
// node scripts/kb_numbers_audit_nn.js

