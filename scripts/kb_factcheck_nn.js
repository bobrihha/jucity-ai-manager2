const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const KB_DIR = path.join(ROOT, "kb", "nn");
const REPORTS_DIR = path.join(ROOT, "reports");
const REPORT_PATH = path.join(REPORTS_DIR, "kb_factcheck_nn.md");

const PATTERNS = [
  {
    id: "31.12 до 18:00",
    regex: /31\.12.*18:00|31.*до.*18:00/i,
    recommendFile: "kb/nn/core/hours.md",
  },
  {
    id: "01.01 не работает",
    regex: /01\.01.*не работает|1.*января.*не работает/i,
    recommendFile: "kb/nn/core/hours.md",
  },
  {
    id: "Сладкий сбор 1000",
    regex: /(сладк\w*\s+сбор).*(1000)|1000.*(сладк\w*\s+сбор)/i,
    recommendFile: "kb/nn/food/own_food_rules.md",
  },
  {
    id: "ОВЗ бесплатно пн–пт",
    regex: /(овз).*(бесплатн\w*).*(пн|понедельник).*(пт|пятниц)/i,
    recommendFile: "kb/nn/tickets/discounts.md",
  },
  {
    id: "СВО 30% пн–пт",
    regex: /(сво).*(30%).*(пн|понедельник).*(пт|пятниц)/i,
    recommendFile: "kb/nn/tickets/discounts.md",
  },
  {
    id: "14–18 лет 50%",
    regex: /(14).*(18).*(50%)/i,
    recommendFile: "kb/nn/tickets/discounts.md",
  },
  {
    id: "Пенсионеры 20% 15.07–15.08",
    regex: /(пенсион).*(20%).*(15\.07).*(15\.08)/i,
    recommendFile: "kb/nn/tickets/discounts.md",
  },
  {
    id: "VR отдельная услуга",
    regex: /(VR).*(отдельн\w*|не входит)/i,
    recommendFile: "kb/nn/services/vr.md",
  },
  {
    id: "Фиджитал отдельно",
    regex: /(фиджитал).*(отдельн\w*|дополнительно|не входит)/i,
    recommendFile: "kb/nn/services/phygital.md",
  },
  {
    id: "Правила про свою еду",
    regex: /(сво(я|ю)).*(ед(а|у)|напитк).*(нельз\w*)/i,
    recommendFile: "kb/nn/food/own_food_rules.md",
  },
];

function compileUnicodeRegex(re) {
  const source = re.source.replace(/\\w/g, "[\\p{L}\\p{N}_]");
  const flags = new Set(re.flags.split(""));
  flags.add("u");
  return new RegExp(source, Array.from(flags).join(""));
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
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

function toRel(p) {
  return path.relative(ROOT, p).split(path.sep).join("/");
}

function main() {
  ensureDir(REPORTS_DIR);

  const foundByPattern = new Map(); // id -> Set(relPath)
  const errors = [];
  let scannedFiles = 0;

  try {
    if (!fs.existsSync(KB_DIR)) {
      throw new Error(`KB directory not found: ${toRel(KB_DIR)}`);
    }

    const files = listMdFilesRecursive(KB_DIR);
    scannedFiles = files.length;

    for (const abs of files) {
      const text = readTextSafe(abs);
      if (text === null) {
        errors.push(`Не удалось прочитать файл: \`${toRel(abs)}\``);
        continue;
      }

      const rel = toRel(abs);
      for (const p of PATTERNS) {
        const rx = compileUnicodeRegex(p.regex);
        if (rx.test(text)) {
          if (!foundByPattern.has(p.id)) foundByPattern.set(p.id, new Set());
          foundByPattern.get(p.id).add(rel);
        }
      }
    }
  } catch (e) {
    errors.push(`Ошибка обхода: ${e && e.message ? e.message : String(e)}`);
  }

  const lines = [];
  lines.push("# Fact-check — NN (критичные факты)");
  lines.push("");
  lines.push(`_Сгенерировано: ${new Date().toISOString()}_`);
  lines.push("");

  const foundCount = PATTERNS.filter((p) => foundByPattern.has(p.id)).length;
  lines.push("## Сводка");
  lines.push(`- Файлов просканировано: ${scannedFiles}`);
  lines.push(`- Паттернов найдено: ${foundCount} / ${PATTERNS.length}`);
  lines.push("");

  if (errors.length) {
    lines.push("## Ошибки чтения");
    for (const err of errors) lines.push(`- ${err}`);
    lines.push("");
  }

  lines.push("## Найдено (✅)");
  const found = PATTERNS.filter((p) => foundByPattern.has(p.id));
  if (!found.length) {
    lines.push("- (ничего не найдено)");
  } else {
    for (const p of found) {
      const files = Array.from(foundByPattern.get(p.id)).sort();
      lines.push(`- ✅ ${p.id}: ${files.map((f) => `\`${f}\``).join(", ")}`);
    }
  }
  lines.push("");

  lines.push("## Не найдено (❌) + куда добавить");
  const missing = PATTERNS.filter((p) => !foundByPattern.has(p.id));
  if (!missing.length) {
    lines.push("- (нет)");
  } else {
    for (const p of missing) {
      lines.push(`- ❌ ${p.id}: добавить в \`${p.recommendFile}\``);
    }
  }
  lines.push("");

  fs.writeFileSync(REPORT_PATH, lines.join("\n"), "utf8");
  console.log("OK: reports/kb_factcheck_nn.md обновлён");
}

main();

// Запуск:
// node scripts/kb_factcheck_nn.js
