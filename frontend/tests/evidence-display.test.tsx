// Exercises the complete evidence-display path a Portal steward flagged as
// unproven: a real DatumRecord shaped exactly like evaluate_envelope()'s
// accepted_record.sources (see contracts/datum_lib.py's _row()) rendered
// through the actual ticket page component, not just asserted against the
// contract-side record shape in isolation. Covers both a source accepted
// after the real fetch-authentication check and one rejected by it, since
// that rejection reason ("raw citation does not match fetched data") is the
// exact behavior the steward's "official-source authentication" request
// added -- a test that never renders it would still miss the point.
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { DatumEvent, DatumRecord } from "@/src/lib/datum/types";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "42" }),
}));

// Both mocks return the SAME object reference on every call, not a fresh
// literal -- the real page keys a useEffect off this value's identity
// ([status, eventId]), so a mock that returns a new object each render
// retriggers that effect every render and the page never leaves "loading".
const liveStatus = { kind: "live" as const, address: "0x1428874208700fb96E3b563023dDd0E9aCe8321E" };
vi.mock("@/src/components/live", () => ({
  useLive: () => liveStatus,
  StatusBanner: () => null,
}));

const walletState = {
  available: false,
  account: null,
  chainId: null,
  balanceWei: "0",
  onRightChain: false,
  error: null,
  connect: vi.fn(),
  switchChain: vi.fn(),
};
vi.mock("@/src/components/Wallet", () => ({
  useWallet: () => walletState,
}));

const fixtureEvent: DatumEvent = {
  id: "42",
  creator: "0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537",
  created_at: 1_790_000_000,
  state: "FINALIZED",
  class: "STATION_TEMP",
  station_id: "KJFK",
  bbox: null,
  depth: null,
  metric: "temp_max",
  threshold: 2000,
  cmp: "gte",
  window: [1_790_400_000, 1_790_486_400],
  publishers: ["NWS_OBS", "GHCN_DAILY"],
  product_status_policy: "FINAL_ONLY",
  tolerance: 50,
  appeal_window: 3600,
  constitution_hash: "0xabc123",
  creator_side: "YES",
  creator_stake: 1_000_000_000_000_000_00,
  acceptor: "0x1111111111111111111111111111111111111a",
  acceptor_side: "NO",
  acceptor_stake: 1_000_000_000_000_000_00,
  create_bond: "50000000000000000",
  create_bond_slashed: false,
  adjudicate_bond_payer: "0x1111111111111111111111111111111111111a",
  adjudicate_bond: "20000000000000000",
  verdict: "YES",
  code: "CLEAR",
  agreed_value: 2110,
  finalized_at: 1_790_500_000,
  appeal: null,
  last_state_change_at: 1_790_500_000,
};

// Field-for-field the shape validate_source_reading()'s _row() returns
// (contracts/datum_lib.py), so this fixture is what a real accepted record
// actually looks like, not a shape invented for the test.
const fixtureRecord: DatumRecord = {
  verdict: "YES",
  code: "CLEAR",
  agreed_value: 2110,
  state: "FINALIZED",
  accepted_record: {
    verdict: "YES",
    code: "CLEAR",
    agreed_value: 2110,
    sources: {
      NWS_OBS: {
        usable: true,
        reason: null,
        converted: 2110,
        station_id: "KJFK",
        t: 1_790_450_000,
        value_native: 21.1,
        unit: "degC",
        product_status: "FINAL",
        digest: "3b1c9f2e7a5d6408b0c1e2f3a4b5c6d7e8f9001122334455667788990011aa",
      },
      GHCN_DAILY: {
        usable: false,
        reason: "raw citation does not match fetched data",
        converted: null,
        station_id: null,
        t: null,
        value_native: null,
        unit: null,
        product_status: null,
        digest: "9f8e7d6c5b4a392817263544536271809abcdef0123456789abcdef01234567",
      },
    },
  },
};

vi.mock("@/src/lib/datum/sdk", () => ({
  getEvent: vi.fn(async () => fixtureEvent),
  getRecord: vi.fn(async () => fixtureRecord),
  write: {
    acceptEvent: vi.fn(),
    adjudicate: vi.fn(),
    finalize: vi.fn(),
    appeal: vi.fn(),
    reAdjudicate: vi.fn(),
    lapseAppeal: vi.fn(),
    cancelEvent: vi.fn(),
    expireEvent: vi.fn(),
    claim: vi.fn(),
    recoverRefund: vi.fn(),
    reclaimBonds: vi.fn(),
  },
}));

describe("ticket page evidence display", () => {
  it("renders an authenticated accepted source and lets the fetch-rejected one be inspected", async () => {
    const { default: TicketPage } = await import("@/app/app/e/[id]/page");
    const user = userEvent.setup();

    render(<TicketPage />);

    // Record-level fields reach the DOM at all (the "record shape" half).
    await waitFor(() => expect(screen.getByText("CLEAR")).toBeInTheDocument());

    // Evidence tabs exist, one per publisher key in accepted_record.sources.
    const nwsTab = screen.getByRole("button", { name: "NWS_OBS" });
    const ghcnTab = screen.getByRole("button", { name: "GHCN_DAILY" });
    expect(nwsTab).toBeInTheDocument();
    expect(ghcnTab).toBeInTheDocument();

    // Default tab (first publisher): a genuinely authenticated, usable row.
    // "KJFK" also appears in the event's own top-level station id KV, so
    // this only checks it reaches the evidence row too, not that it's sole.
    expect(screen.getByText("usable")).toBeInTheDocument();
    expect(screen.getAllByText("KJFK").length).toBeGreaterThan(1);
    expect(
      screen.getByText("3b1c9f2e7a5d6408b0c1e2f3a4b5c6d7e8f9001122334455667788990011aa")
    ).toBeInTheDocument();

    // Switch to the source the real fetch-authentication check rejected --
    // this is the exact steward-cited behavior, not a generic unusable row.
    await user.click(ghcnTab);
    expect(screen.getByText("unusable")).toBeInTheDocument();
    expect(screen.getByText("raw citation does not match fetched data")).toBeInTheDocument();
    expect(
      screen.getByText("9f8e7d6c5b4a392817263544536271809abcdef0123456789abcdef01234567")
    ).toBeInTheDocument();
  });

  it("shows no accepted row for either publisher before an adjudication record exists", async () => {
    // publisherIds falls back to event.publishers when accepted_record is
    // null, so the constitution's locked publishers still show as tabs --
    // each one honestly says it has no accepted row yet, never a zero or a
    // placeholder reading standing in for one.
    const sdk = await import("@/src/lib/datum/sdk");
    vi.mocked(sdk.getRecord).mockResolvedValueOnce({
      verdict: null,
      code: null,
      agreed_value: null,
      accepted_record: null,
      state: "OPEN",
    });

    const { default: TicketPage } = await import("@/app/app/e/[id]/page");
    render(<TicketPage />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "NWS_OBS" })).toBeInTheDocument()
    );
    expect(
      screen.getByText(
        "No accepted row for this publisher yet. A publisher with no accepted row never counts as agreement, and never counts as a zero reading."
      )
    ).toBeInTheDocument();
    expect(screen.queryByText("usable")).not.toBeInTheDocument();
    expect(screen.queryByText("unusable")).not.toBeInTheDocument();
  });
});
