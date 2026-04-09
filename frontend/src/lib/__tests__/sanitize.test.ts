import { describe, it, expect } from "vitest";
import { encodePathSegment, sanitizeDownloadName } from "../sanitize";

describe("encodePathSegment", () => {
  it("encodes slashes and special characters", () => {
    expect(encodePathSegment("foo/bar")).toBe("foo%2Fbar");
    expect(encodePathSegment("../secret")).toBe("..%2Fsecret");
  });

  it("leaves simple strings unchanged", () => {
    expect(encodePathSegment("abc-123")).toBe("abc-123");
  });

  it("handles empty string", () => {
    expect(encodePathSegment("")).toBe("");
  });
});

describe("sanitizeDownloadName", () => {
  it("returns fallback for empty input", () => {
    expect(sanitizeDownloadName("")).toBe("download");
    expect(sanitizeDownloadName("", "fallback.csv")).toBe("fallback.csv");
  });

  it("strips path separators", () => {
    expect(sanitizeDownloadName("path/to/file.csv")).toBe("file.csv");
    expect(sanitizeDownloadName("C:\\Users\\file.csv")).toBe("file.csv");
  });

  it("replaces reserved characters", () => {
    const result = sanitizeDownloadName('file:name*"test?.csv');
    expect(result).not.toContain(":");
    expect(result).not.toContain("*");
    expect(result).not.toContain('"');
    expect(result).not.toContain("?");
  });

  it("truncates very long names", () => {
    const longName = "a".repeat(300) + ".csv";
    const result = sanitizeDownloadName(longName);
    expect(result.length).toBeLessThanOrEqual(180);
    expect(result.endsWith(".csv")).toBe(true);
  });

  it("strips control characters", () => {
    const result = sanitizeDownloadName("file\x00name\x1F.csv");
    expect(result).toBe("filename.csv");
  });
});
