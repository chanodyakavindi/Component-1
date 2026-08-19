import { describe, expect, it } from "vitest";
import { formatPercent, formatStatus } from "./utils";

describe("formatters", () => {
  it("formats risk as a percentage", () => {
    expect(formatPercent(0.59)).toBe("59%");
  });
  it("formats status labels", () => {
    expect(formatStatus("moderate_wasting")).toBe("Moderate Wasting");
  });
});
