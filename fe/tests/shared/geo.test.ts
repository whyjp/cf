import { describe, expect, it } from "vitest";
import { formatKm, haversineKm } from "../../src/shared/geo";

describe("haversineKm", () => {
  it("returns 0 for same point", () => {
    expect(haversineKm(37.5, 127.0, 37.5, 127.0)).toBeCloseTo(0, 5);
  });

  it("approx Seoul → Busan ~325km", () => {
    const km = haversineKm(37.5665, 126.978, 35.1796, 129.0756);
    expect(km).toBeGreaterThan(300);
    expect(km).toBeLessThan(360);
  });

  it("is symmetric", () => {
    const ab = haversineKm(37.5665, 126.978, 35.1796, 129.0756);
    const ba = haversineKm(35.1796, 129.0756, 37.5665, 126.978);
    expect(ab).toBeCloseTo(ba, 9);
  });
});

describe("formatKm", () => {
  it("renders < 1km in m", () => {
    expect(formatKm(0.42)).toBe("420 m");
  });

  it("renders < 10km with one decimal", () => {
    expect(formatKm(3.7)).toBe("3.7 km");
  });

  it("renders >= 10km as integer", () => {
    expect(formatKm(42.3)).toBe("42 km");
  });

  it("returns empty for null", () => {
    expect(formatKm(null)).toBe("");
  });

  it("returns empty for undefined", () => {
    expect(formatKm(undefined)).toBe("");
  });
});
