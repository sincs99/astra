import { describe, expect, it } from "vitest";
import { loginUrl, safeRedirectPath } from "./redirect";

describe("safeRedirectPath", () => {
  it.each(["/shop", "/orders", "/instances/abc?tab=1", "/"])("erlaubt internen Pfad %s", (path) => {
    expect(safeRedirectPath(path)).toBe(path);
  });

  it.each([null, undefined, "", "shop", "https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)", "/a\nb"])(
    "weist %j ab und nutzt den Fallback", (value) => {
      expect(safeRedirectPath(value as string | null)).toBe("/");
      expect(safeRedirectPath(value as string | null, "/home")).toBe("/home");
    });

  it("baut den Login-Link mit kodiertem Ziel", () => {
    expect(loginUrl("/shop")).toBe("/login?redirect=%2Fshop");
  });
});
