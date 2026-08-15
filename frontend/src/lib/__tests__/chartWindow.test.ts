import { describe, expect, it } from "vitest";
import { defaultZoomStart, resolveZoom, DEFAULT_VISIBLE_BARS } from "../chartWindow";

describe("defaultZoomStart", () => {
  it("shows everything when bars are within the default window", () => {
    expect(defaultZoomStart(100)).toBe(0);
    expect(defaultZoomStart(DEFAULT_VISIBLE_BARS)).toBe(0);
  });

  it("shows the last DEFAULT_VISIBLE_BARS for larger data", () => {
    expect(defaultZoomStart(1000)).toBeCloseTo(75, 6);
    expect(defaultZoomStart(500)).toBeCloseTo(50, 6);
    expect(defaultZoomStart(10000)).toBeCloseTo(97.5, 6);
  });
});

describe("resolveZoom", () => {
  it("falls back to the default window when no shared window exists", () => {
    expect(resolveZoom(null, 1000)).toEqual({ start: 75, end: 100 });
    expect(resolveZoom(undefined, 100)).toEqual({ start: 0, end: 100 });
  });

  it("keeps the shared window percentages (used for new charts and setOption restore)", () => {
    expect(resolveZoom({ start: 30, end: 100 }, 1000)).toEqual({ start: 30, end: 100 });
    expect(resolveZoom({ start: 50, end: 80 }, 200)).toEqual({ start: 50, end: 80 });
  });

  it("clamps out-of-range values and keeps end >= start", () => {
    expect(resolveZoom({ start: -10, end: 120 }, 1000)).toEqual({ start: 0, end: 100 });
    expect(resolveZoom({ start: 80, end: 40 }, 1000)).toEqual({ start: 80, end: 80 });
  });
});
