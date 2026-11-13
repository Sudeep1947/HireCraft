import { describe, expect, it } from "vitest";

import { getErrorMessage, getServerErrorMessage } from "./error";

function axiosError(data?: unknown, withResponse = true) {
  return withResponse ? { isAxiosError: true, response: { data } } : { isAxiosError: true };
}

describe("getServerErrorMessage", () => {
  it("prefers the message the server wrote for a user", () => {
    expect(
      getServerErrorMessage(
        axiosError({ detail: "That slot is no longer available." }),
        "fallback",
      ),
    ).toBe("That slot is no longer available.");
  });

  it("reads a nested error message", () => {
    expect(
      getServerErrorMessage(
        axiosError({ error: { message: "Not permitted." } }),
        "fallback",
      ),
    ).toBe("Not permitted.");
  });

  it("joins validation errors, so every offending field is named", () => {
    expect(
      getServerErrorMessage(
        axiosError({ detail: [{ msg: "field required" }, { msg: "too long" }] }),
        "fallback",
      ),
    ).toBe("field required, too long");
  });

  it("does not surface a transport-level message that says nothing useful", () => {
    // "Network Error" is not a sentence a recruiter can act on.
    const networkError = axiosError(undefined, false);
    Object.assign(networkError, { message: "Network Error" });
    expect(getServerErrorMessage(networkError, "Please try again.")).toBe(
      "Please try again.",
    );
  });

  it("never echoes a locally thrown error, whose text is not written for a user", () => {
    expect(
      getServerErrorMessage(
        new Error("Cannot read properties of undefined (reading 'id')"),
        "Unable to load the job. Please refresh and try again.",
      ),
    ).toBe("Unable to load the job. Please refresh and try again.");
  });

  it("falls back when the response carries no usable detail", () => {
    expect(getServerErrorMessage(axiosError({}), "fallback")).toBe("fallback");
    expect(getServerErrorMessage(axiosError({ detail: "   " }), "fallback")).toBe(
      "fallback",
    );
    expect(getServerErrorMessage(undefined, "fallback")).toBe("fallback");
    expect(getServerErrorMessage("a string", "fallback")).toBe("fallback");
  });
});

describe("getErrorMessage", () => {
  it("still surfaces the underlying message, which is what logging wants", () => {
    expect(
      getErrorMessage(new Error("ECONNREFUSED 127.0.0.1:8000"), "fallback"),
    ).toBe("ECONNREFUSED 127.0.0.1:8000");
  });
});
