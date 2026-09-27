// Regression test for the bug a Portal steward hit live: after creating an
// event, every other write call showed "Missing or invalid parameters.
// Double check you have provided the correct parameters. Details:
// execution failed Version: viem@2.56.8" -- viem's generic wrapper around
// ANY rejected estimateTransactionFeesForWrite() dry run, no matter what
// the contract actually said. The fixtures below are real base64 payloads
// captured from genlayer-js's estimateTransactionFeesForWrite() against
// the live deployed contract (0x1428874208700fb96E3b563023dDd0E9aCe8321E)
// for four distinct real rejections -- not fabricated -- to prove the
// decoder matches GenVM's actual on-chain calldata encoding, not just an
// assumption about its shape.
import { describe, expect, it } from "vitest";
import { describeUserError, extractContractRevertMessage } from "@/src/lib/datum/errors";

function errorWithReceiptResult(resultB64: string | undefined) {
  return {
    name: "InvalidInputRpcError",
    message:
      "Missing or invalid parameters.\nDouble check you have provided the correct parameters.\n\nDetails: execution failed\nVersion: viem@2.56.8",
    cause: {
      code: -32000,
      message: "execution failed",
      data: { receipt: { result: resultB64 } },
    },
  };
}

describe("extractContractRevertMessage", () => {
  it.each([
    // label, real base64 captured live, expected decoded UserError text
    ["finalize on a nonexistent event", "AWV2ZW50IG5vdCBmb3VuZA==", "event not found"],
    ["cancel_event called by a non-party", "AW5vdCBhIHBhcnR5", "not a party"],
    ["appeal on an event in the wrong state", "AW5vdCBwZW5kaW5n", "not pending"],
    ["create_event with an invalid side", "AXNpZGUgbXVzdCBiZSBZRVMgb3IgTk8=", "side must be YES or NO"],
  ])("decodes a real captured revert payload: %s", (_label, resultB64, expected) => {
    expect(extractContractRevertMessage(errorWithReceiptResult(resultB64))).toBe(expected);
  });

  it("feeds the decoded message through describeUserError to the friendly text a user sees", () => {
    const err = errorWithReceiptResult("AW5vdCBhIHBhcnR5"); // "not a party"
    const message = extractContractRevertMessage(err) ?? "unreachable";
    expect(describeUserError(message)).toBe("Only a bonded party to this event can do that.");
  });

  it("returns null (falls back to the raw error) when there is no receipt.result", () => {
    expect(extractContractRevertMessage(new Error("network unreachable"))).toBeNull();
    expect(extractContractRevertMessage(errorWithReceiptResult(undefined))).toBeNull();
  });

  it("returns null on a malformed or non-string-tagged payload instead of throwing", () => {
    expect(extractContractRevertMessage(errorWithReceiptResult("not-valid-base64!!!"))).toBeNull();
    // tag byte 0x00 (not the string tag 0x01) -- must not be misread as text.
    expect(extractContractRevertMessage(errorWithReceiptResult("AGFieXRl"))).toBeNull();
  });
});
