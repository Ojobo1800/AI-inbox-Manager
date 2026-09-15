"""
Unit tests for execution/fetch_emails.py IMAP operations.

Regression coverage for two incidents:

1. **2026-09-08** -- the classify -> move pipeline identified messages by IMAP
   *sequence number*, resolved in one connection and mutated minutes later in
   another.  Sequence numbers renumber on every expunge, so labels landed on
   the wrong messages, the right messages never left the inbox, and each
   2-hourly run smeared another label onto some unrelated email.
   Fix: every handle is a UID (stable across sessions and expunges); move/
   delete verify the handle against the folder's live UID set and, if it has
   shifted, recover it via the RFC 5322 Message-ID header.

2. **2026-09-15** -- the organize path applied the destination label correctly
   (``STORE +X-GM-LABELS``) but then tried to leave the source folder with
   ``STORE -X-GM-LABELS (\\Inbox)``. That call always returned ``OK`` on this
   Gmail account but silently never removed the message from Inbox -- emails
   piled up in the Inbox, correctly labeled, for weeks, and every run's log
   claimed "Successfully moved N of N". A ``\\Deleted`` + expunge fallback was
   tested and rejected: on this account it strips every label and sends the
   message straight to Trash, even when another label is already applied.
   Fix: ``UID MOVE`` (RFC 6851) -- a single atomic command, verified directly
   against the account to correctly leave the source folder, land labeled in
   the destination, and never touch Trash.

The one intentional hard delete (confirmed-spam purge) is unaffected -- still
``\\Deleted`` + UID EXPUNGE, scoped to only the targeted UIDs.

All tests use an in-memory fake IMAP client -- nothing touches a real server.
"""

import sys
from pathlib import Path

import pytest

_EXECUTION_DIR = Path(__file__).resolve().parents[2] / "execution"
if str(_EXECUTION_DIR) not in sys.path:
    sys.path.insert(0, str(_EXECUTION_DIR))

import fetch_emails
from fetch_emails import (
    delete_emails,
    move_emails,
    search_emails,
    EmailFetchError,
)


class FakeIMAP:
    """Records every command; rejects the sequence-number primitives outright."""

    def __init__(self, uids_present, uid_to_msgid=None):
        self._uids = [str(u) for u in uids_present]
        self._uid_to_msgid = {str(k): v for k, v in (uid_to_msgid or {}).items()}
        self.calls = []
        self.label_ops = []       # (uid, "+"/"-", label_atom) -- STORE-based, delete path only
        self.move_ops = []        # (uid, destination_folder) -- UID MOVE, organize path
        self.flag_ops = []        # (uid, flag_atom)
        self.uid_expunged = []    # arg passed to UID EXPUNGE
        self.plain_expunge_called = False
        self.selected = None
        self.untagged_responses = {}
        self.move_fails_for = set()  # uids whose UID MOVE returns NO

    # -- connection lifecycle -------------------------------------------------
    def select(self, mailbox, readonly=False):
        self.selected = mailbox
        self.calls.append(("select", mailbox, readonly))
        return ("OK", [b"1"])

    def close(self):
        pass

    def logout(self):
        self.calls.append(("logout",))
        return ("BYE", [b""])

    # -- the only mutation path we allow ------------------------------------
    def uid(self, command, *args):
        cmd = command.upper()
        self.calls.append(("uid", cmd) + tuple(args))

        if cmd == "SEARCH":
            return ("OK", [" ".join(self._uids).encode()])

        if cmd == "FETCH":
            spec = args[1] if len(args) > 1 else ""
            if "MESSAGE-ID" in spec.upper():
                resp = []
                for u in self._uids:
                    mid = self._uid_to_msgid.get(u)
                    if mid:
                        resp.append((
                            f"{u} (UID {u} BODY[HEADER.FIELDS (MESSAGE-ID)] {{40}}".encode(),
                            f"Message-ID: {mid}\r\n\r\n".encode(),
                        ))
                        resp.append(b")")
                return ("OK", resp)
            uid = str(args[0])
            return ("OK", [(f"{uid} (UID {uid} RFC822 {{3}}".encode(), b"raw")])

        if cmd == "STORE":
            uid, op, val = str(args[0]), args[1], args[2]
            if op == "+X-GM-LABELS":
                self.label_ops.append((uid, "+", val))
                return ("OK", [b"done"])
            if op == "-X-GM-LABELS":
                self.label_ops.append((uid, "-", val))
                return ("OK", [b"done"])
            if op == "+FLAGS":
                self.flag_ops.append((uid, val))
                return ("OK", [b"done"])
            return ("OK", [b"done"])

        if cmd == "MOVE":
            uid, dest = str(args[0]), args[1]
            if uid in self.move_fails_for:
                return ("NO", [b"over quota"])
            self.move_ops.append((uid, dest))
            return ("OK", [None])

        if cmd == "EXPUNGE":
            self.uid_expunged.append(args[0])
            return ("OK", [b"1 2"])

        return ("OK", [b""])

    def expunge(self):
        self.plain_expunge_called = True
        return ("OK", [b""])

    # -- sequence-number primitives: must never be called ------------------
    def store(self, *a):
        raise AssertionError("plain store() is a sequence-number op — forbidden")

    def copy(self, *a):
        raise AssertionError("plain copy() is a sequence-number op — forbidden")

    def search(self, *a):
        raise AssertionError("plain search() is a sequence-number op — forbidden")

    def fetch(self, *a):
        raise AssertionError("plain fetch() is a sequence-number op — forbidden")


@pytest.fixture
def patch_connect(monkeypatch):
    def _install(fake):
        monkeypatch.setattr(fetch_emails, "connect_to_imap", lambda *a, **k: fake)
        return fake
    return _install


# ── search_emails ───────────────────────────────────────────────────────────

def test_search_uses_uid_search_and_returns_uids():
    fake = FakeIMAP(["5", "6", "7"])
    assert search_emails(fake, "UNSEEN") == ["5", "6", "7"]
    assert ("uid", "SEARCH", None, "UNSEEN") in fake.calls


def test_search_newest_first_reverses_order():
    fake = FakeIMAP(["5", "6", "7"])
    assert search_emails(fake, "UNSEEN", newest_first=True) == ["7", "6", "5"]


def test_search_limit_applied_after_ordering():
    fake = FakeIMAP(["1", "2", "3", "4", "5"])
    assert search_emails(fake, "UNSEEN", limit=2, newest_first=True) == ["5", "4"]


def test_search_excludes_gmail_labels():
    fake = FakeIMAP(["9"])
    search_emails(fake, "UNSEEN", exclude_gm_labels=["InboxGenius-Processed"])
    assert (
        "uid", "SEARCH", None, "UNSEEN",
        "NOT", "X-GM-LABELS", "InboxGenius-Processed",
    ) in fake.calls


# ── move_emails ─────────────────────────────────────────────────────────────

def test_move_uses_uid_move_never_deletes(patch_connect):
    fake = patch_connect(FakeIMAP(["10", "11"], {"10": "<a@x>", "11": "<b@x>"}))

    moved = move_emails("s", 993, "e", "p", {"10": "Job Alerts", "11": "Rejection"})

    assert moved == 2
    assert ("10", '"Job Alerts"') in fake.move_ops
    assert ("11", '"Rejection"') in fake.move_ops
    # organize path must not touch labels via STORE, \Deleted, or expunge
    assert fake.label_ops == []
    assert fake.flag_ops == []
    assert fake.uid_expunged == []
    assert fake.plain_expunge_called is False


def test_move_skips_handle_not_in_folder(patch_connect):
    fake = patch_connect(FakeIMAP(["10"], {"10": "<a@x>"}))

    moved = move_emails("s", 993, "e", "p", {"99": "Rejection"})

    assert moved == 0
    assert fake.move_ops == []


def test_move_recovers_stale_uid_via_message_id(patch_connect):
    # handle 99 is stale; the message is really at UID 10 now
    fake = patch_connect(FakeIMAP(["10"], {"10": "<a@x>"}))

    moved = move_emails(
        "s", 993, "e", "p",
        {"99": "Rejection"},
        id_to_message_id={"99": "<a@x>"},
    )

    assert moved == 1
    assert ("10", '"Rejection"') in fake.move_ops


def test_move_reports_failure_and_retries_next_run(patch_connect):
    fake = patch_connect(FakeIMAP(["10"], {"10": "<a@x>"}))
    fake.move_fails_for = {"10"}

    moved = move_emails("s", 993, "e", "p", {"10": "Rejection"})

    assert moved == 0


def test_move_selects_named_source_folder(patch_connect):
    fake = patch_connect(FakeIMAP(["10"], {"10": "<a@x>"}))

    moved = move_emails(
        "s", 993, "e", "p",
        {"10": "Job Alerts"},
        source_folder="Spam Review",
    )

    assert moved == 1
    assert ("select", '"Spam Review"', False) in fake.calls
    assert ("10", '"Job Alerts"') in fake.move_ops


# ── delete_emails ──────────────────────────────────────────────────────────

def test_delete_flags_and_uid_expunges_only_targets(patch_connect):
    fake = patch_connect(
        FakeIMAP(["10", "11", "12"], {"10": "<a>", "11": "<b>", "12": "<c>"})
    )

    deleted = delete_emails(
        "s", 993, "e", "p",
        email_ids=["10", "12"],
        folder="Spam Review",
    )

    assert deleted == 2
    assert ("10", "(\\Deleted)") in fake.flag_ops
    assert ("12", "(\\Deleted)") in fake.flag_ops
    assert ("11", "(\\Deleted)") not in fake.flag_ops
    assert fake.uid_expunged == ["10,12"]          # scoped, not a blind expunge
    assert fake.plain_expunge_called is False
    assert ("select", '"Spam Review"', False) in fake.calls


def test_delete_recovers_stale_uid_via_message_id(patch_connect):
    fake = patch_connect(FakeIMAP(["10"], {"10": "<a@x>"}))

    deleted = delete_emails(
        "s", 993, "e", "p",
        email_ids=["77"],
        folder="Spam Review",
        id_to_message_id={"77": "<a@x>"},
    )

    assert deleted == 1
    assert ("10", "(\\Deleted)") in fake.flag_ops
    assert fake.uid_expunged == ["10"]


def test_delete_skips_unresolvable_handle(patch_connect):
    fake = patch_connect(FakeIMAP(["10"], {"10": "<a@x>"}))

    deleted = delete_emails(
        "s", 993, "e", "p",
        email_ids=["999"],
        folder="Spam Review",
    )

    assert deleted == 0
    assert fake.flag_ops == []
    assert fake.uid_expunged == []


def test_delete_empty_list_is_noop(patch_connect):
    fake = patch_connect(FakeIMAP(["10"]))
    assert delete_emails("s", 993, "e", "p", email_ids=[]) == 0
    assert fake.calls == []
