// @vitest-environment jsdom
import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, describe, it, expect } from "vitest";
import { cleanup } from "@testing-library/react";
afterEach(cleanup);
import { SkipLink } from "./SkipLink";

describe("SkipLink", () => {
  it("springt per Klick zum Hauptinhalt und fokussiert ihn", () => {
    render(<><SkipLink /><main id="main-content" tabIndex={-1}>x</main></>);
    fireEvent.click(screen.getByText("Zum Inhalt springen"));
    expect(document.activeElement?.id).toBe("main-content");
  });
});
