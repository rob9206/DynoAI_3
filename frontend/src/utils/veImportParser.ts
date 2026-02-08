export interface ParsedCorrectionsImport {
  corrections: number[][];
  rpmBins: number[];
  mapBins: number[];
  format: "multiplier" | "percentage";
}

function parseNumber(value: string, label: string): number {
  const parsed = Number(value.trim());
  if (!Number.isFinite(parsed)) {
    throw new Error(`Invalid ${label} value: ${value}`);
  }
  return parsed;
}

function createGrid(
  rpmBins: number[],
  mapBins: number[],
  fillValue: number
): number[][] {
  return rpmBins.map(() => mapBins.map(() => fillValue));
}

export function parseDynoAIJSON(content: string): ParsedCorrectionsImport {
  const data = JSON.parse(content);
  if (!data || data.type !== "dynoai_ve_corrections") {
    throw new Error("Unsupported JSON format (expected dynoai_ve_corrections)");
  }

  const rpmBins: number[] = data?.bins?.rpm ?? [];
  const mapBins: number[] = data?.bins?.map ?? [];
  if (rpmBins.length === 0 || mapBins.length === 0) {
    throw new Error("Missing rpm/map bins in JSON export");
  }

  const front = createGrid(rpmBins, mapBins, 1.0);
  const rear = createGrid(rpmBins, mapBins, 1.0);

  for (const entry of data?.corrections?.front || []) {
    const rIdx = Number(entry?.rpmIdx);
    const mIdx = Number(entry?.mapIdx);
    const mult = Number(entry?.multiplier);
    if (!Number.isFinite(rIdx) || !Number.isFinite(mIdx) || !Number.isFinite(mult)) {
      continue;
    }
    if (rIdx >= 0 && mIdx >= 0 && rIdx < rpmBins.length && mIdx < mapBins.length) {
      front[rIdx][mIdx] = mult;
    }
  }

  for (const entry of data?.corrections?.rear || []) {
    const rIdx = Number(entry?.rpmIdx);
    const mIdx = Number(entry?.mapIdx);
    const mult = Number(entry?.multiplier);
    if (!Number.isFinite(rIdx) || !Number.isFinite(mIdx) || !Number.isFinite(mult)) {
      continue;
    }
    if (rIdx >= 0 && mIdx >= 0 && rIdx < rpmBins.length && mIdx < mapBins.length) {
      rear[rIdx][mIdx] = mult;
    }
  }

  const combined = createGrid(rpmBins, mapBins, 1.0);
  for (let r = 0; r < rpmBins.length; r++) {
    for (let m = 0; m < mapBins.length; m++) {
      const f = front[r][m];
      const rr = rear[r][m];
      if (Number.isFinite(f) && Number.isFinite(rr)) {
        combined[r][m] = (f + rr) / 2;
      } else if (Number.isFinite(f)) {
        combined[r][m] = f;
      } else if (Number.isFinite(rr)) {
        combined[r][m] = rr;
      }
    }
  }

  return {
    corrections: combined,
    rpmBins,
    mapBins,
    format: "multiplier",
  };
}

export function parseDynoAICSV(content: string): ParsedCorrectionsImport {
  const lines = content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"));

  if (lines.length < 2) {
    throw new Error("CSV appears empty or missing data rows");
  }

  const header = lines[0].split(",").map((cell) => cell.trim());
  if (header.length < 2 || header[0].toLowerCase() !== "map_kpa") {
    throw new Error("CSV header must start with MAP_kPa");
  }

  const rpmBins = header.slice(1).map((value) => parseNumber(value, "RPM bin"));
  const mapBins: number[] = [];

  const grid: number[][] = rpmBins.map(() => []);
  for (let i = 1; i < lines.length; i++) {
    const row = lines[i].split(",").map((cell) => cell.trim());
    if (row.length < rpmBins.length + 1) {
      throw new Error(`Row ${i + 1} is missing correction values`);
    }
    const mapKpa = parseNumber(row[0], "MAP bin");
    mapBins.push(mapKpa);
    const values = row.slice(1, rpmBins.length + 1).map((value) =>
      parseNumber(value, "correction")
    );

    for (let rpmIdx = 0; rpmIdx < rpmBins.length; rpmIdx++) {
      if (!grid[rpmIdx]) grid[rpmIdx] = [];
      grid[rpmIdx][mapBins.length - 1] = values[rpmIdx];
    }
  }

  return {
    corrections: grid,
    rpmBins,
    mapBins,
    format: "percentage",
  };
}
