import { describe, expect, it } from "vitest";
import {
  CONCEPT_FILTER_KEYS,
  setSerialize,
  visibleRows,
  type Filters,
} from "../../src/shared/filters";
import type { Site } from "../../src/shared/types";

function emptyFilters(): Filters {
  return {
    region: new Set(),
    conceptAxis: new Set(),
    view: new Set(),
    facility: new Set(),
    kidsFacility: new Set(),
    surface: new Set(),
    space: new Set(),
    parking: new Set(),
    audience: new Set(),
    vibe: new Set(),
    terrain: new Set(),
    collection: new Set(),
    facilityRaw: new Set(),
    management: new Set(),
  };
}

describe("setSerialize", () => {
  it("returns empty string for empty set", () => {
    expect(setSerialize(new Set())).toBe("");
  });

  it("returns empty string for undefined", () => {
    expect(setSerialize(undefined)).toBe("");
  });

  it("returns sorted pipe-joined string", () => {
    expect(setSerialize(new Set(["b", "a", "c"]))).toBe("a|b|c");
  });
});

describe("CONCEPT_FILTER_KEYS", () => {
  it("matches the spec'd 9 slots", () => {
    expect(CONCEPT_FILTER_KEYS).toEqual([
      "conceptAxis",
      "view",
      "facility",
      "kidsFacility",
      "surface",
      "space",
      "parking",
      "audience",
      "vibe",
    ]);
  });
});

describe("visibleRows", () => {
  const rows: Site[] = [
    { id: "1", sido: "강원도", lat: 37.5, lon: 127.0, location_types: ["valley"] },
    { id: "2", sido: "경기도", lat: 37.7, lon: 127.2, location_types: ["forest"] },
    { id: "3", sido: "경기도", lat: null, lon: null, location_types: ["valley"] },
  ];

  it("returns all rows for empty filter set", () => {
    expect(visibleRows(rows, emptyFilters())).toHaveLength(3);
  });

  it("OR-unions multi-region selection client-side", () => {
    const f = emptyFilters();
    f.region = new Set(["강원도", "경기도"]);
    expect(visibleRows(rows, f).map((r) => r.id)).toEqual(["1", "2", "3"]);
  });

  it("ANDs terrain selection", () => {
    const f = emptyFilters();
    f.terrain = new Set(["valley"]);
    expect(visibleRows(rows, f).map((r) => r.id).sort()).toEqual(["1", "3"]);
  });

  it("attaches _distanceKm and sorts closest-first when userLoc set", () => {
    const out = visibleRows(rows, emptyFilters(), {
      userLoc: { lat: 37.5, lon: 127.0 },
    });
    expect(out[0]!.id).toBe("1");
    expect(out[0]!._distanceKm).toBeCloseTo(0, 5);
    // Row 3 has null coords → falls to bottom.
    expect(out[out.length - 1]!.id).toBe("3");
    expect(out[out.length - 1]!._distanceKm).toBeNull();
  });
});
