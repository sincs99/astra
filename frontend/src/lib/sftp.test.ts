import { describe, expect, it } from "vitest";
import { sftpUsername } from "./sftp";

describe("sftpUsername", () => {
  it("haengt die ersten 8 Zeichen der UUID an", () => {
    expect(sftpUsername("alice", "0f3a9c1e-1234-4abc-9def-aabbccddeeff")).toBe("alice.0f3a9c1e");
  });
  it("kommt mit kurzen UUIDs klar", () => {
    expect(sftpUsername("bob", "abc")).toBe("bob.abc");
  });
});
