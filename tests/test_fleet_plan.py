"""Owner decisions are scoped to an exact plan or reviewed PR revision."""

import contextlib
import hashlib
import io
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOL = Path(__file__).resolve().parents[1] / "features/agents.gascity/bin/fleet-plan"
MAIN = runpy.run_path(str(TOOL))["main"]
OWNER = 101
PLAN = {"id": 22, "body": "Test the parser.", "updated_at": "2025-01-01T01:00:00Z"}
DIGEST = hashlib.sha256(PLAN["body"].encode()).hexdigest()
APPROVE = f"/fleet approve 22 {DIGEST}"


def reply(body, number=23, actor=OWNER, **updates):
    return {
        "id": number, "body": body, "user": {"type": "User", "id": actor},
        "created_at": "2025-01-01T02:00:00Z", "updated_at": "2025-01-01T02:00:00Z",
        "html_url": "https://example.test/approval", **updates,
    }


class ApprovalTests(unittest.TestCase):
    def run_check(self, comments, *, state="open", plan=PLAN, action="check", confirmed=True):
        args = ["fleet-plan", action, "example/parser", "7", "22", "--owner-id", str(OWNER)]
        pages = [[plan], comments]
        with patch.object(sys, "argv", args), patch.dict(MAIN.__globals__, {
            "github": lambda path, paginate=False: pages if paginate else {"state": state},
            "confirm_comments": lambda plan, approval: confirmed,
        }), contextlib.redirect_stdout(io.StringIO()) as output:
            MAIN()
        return output.getvalue().strip()

    def test_show_and_approved_second_page(self):
        self.assertEqual(self.run_check([], action="show"), "> Test the parser.\n\n" + APPROVE)
        self.assertIn("https://example.test/approval", self.run_check([reply(APPROVE)]))

    def test_hold_and_reapproval(self):
        hold = reply("/fleet hold 22", number=24)
        with self.assertRaises(SystemExit):
            self.run_check([hold, reply(APPROVE)])
        self.assertIn(APPROVE, self.run_check([reply(APPROVE, number=25), hold]))

    def test_ineligible_approvals(self):
        cases = [
            [], [reply(APPROVE, actor=202)], [reply(APPROVE, performed_via_github_app={"id": 1})],
            [reply(APPROVE, updated_at="2025-01-01T03:00:00Z")],
            [reply(APPROVE.replace("22 ", "23 "))], [reply("Looks good!")],
        ]
        for comments in cases:
            with self.subTest(comments=comments), self.assertRaises(SystemExit):
                self.run_check(comments)

    def test_approval_must_survive_final_read(self):
        with self.assertRaises(SystemExit):
            self.run_check([reply(APPROVE)], confirmed=False)

    def test_closed_or_changed_or_missing_plan(self):
        for options in ({"state": "closed"}, {"plan": dict(PLAN, body="Wider scope")},
                        {"plan": dict(PLAN, updated_at="2025-01-02T00:00:00Z")},
                        {"plan": dict(PLAN, id=77)}):
            with self.subTest(options=options), self.assertRaises(SystemExit):
                self.run_check([reply(APPROVE)], **options)


class FinishTests(unittest.TestCase):
    base = "a" * 40
    head = "b" * 40

    def report(self, verdict="ready"):
        return dict(PLAN, body=f"/fleet review main {self.base} {self.head} {verdict}\nReviewed the write path.")

    def acceptance(self, report):
        digest = hashlib.sha256(report["body"].encode()).hexdigest()
        return f"/fleet accept {report['id']} {digest}"

    def check(self, report, comments, pulls=None, action="check-finish", confirmed=True):
        current = {"state": "open", "base": {"ref": "main", "sha": self.base}, "head": {"sha": self.head}}
        responses = iter([current, current] if pulls is None else pulls)

        def github(path, paginate=False):
            if path == "repos/example/parser/pulls/7":
                return next(responses)
            if path == "repos/example/parser/issues/7/comments?per_page=100" and paginate:
                return [[report], comments]
            self.assertEqual(path, "repos/example/parser/issues/7")
            return {"state": "open"}

        args = ["fleet-plan", action, "example/parser", "7", "22", "--owner-id", str(OWNER)]
        with patch.object(sys, "argv", args), patch.dict(MAIN.__globals__, {
            "github": github, "confirm_comments": lambda plan, approval: confirmed,
        }), contextlib.redirect_stdout(io.StringIO()) as output:
            MAIN()
        return output.getvalue().strip()

    def test_exact_report_can_be_accepted(self):
        report = self.report()
        command = self.acceptance(report)
        self.assertTrue(self.check(report, [], action="show-finish").endswith(command))
        self.assertIn("https://example.test/approval", self.check(report, [reply(command)]))

    def test_preflight_and_other_decisions_do_not_accept_this_report(self):
        report = self.report()
        accept = self.acceptance(report)
        for comments in ([], [reply(APPROVE)], [reply(accept, actor=202)],
                         [reply(accept), reply("/fleet hold-finish", number=24)],
                         [reply(accept), reply(accept.replace("accept 22", "accept 44"), number=24)]):
            with self.subTest(comments=comments), self.assertRaises(SystemExit):
                self.check(report, comments)
        with self.assertRaises(SystemExit):
            self.check(report, [reply(accept)], confirmed=False)
        with self.assertRaises(SystemExit):
            self.check(dict(report, body=report["body"] + " Revised."), [reply(accept)])

    def test_unready_or_missing_evidence_cannot_be_accepted(self):
        for verdict in ("changes", "evidence"):
            report = self.report(verdict)
            with self.subTest(verdict=verdict), self.assertRaises(SystemExit):
                self.check(report, [reply(self.acceptance(report))])

    def test_revision_and_target_checked_again_at_handoff(self):
        report = self.report()
        current = {"state": "open", "base": {"ref": "main", "sha": self.base}, "head": {"sha": self.head}}
        for change in ({"state": "closed"}, {"head": {"sha": "c" * 40}},
                       {"base": {"ref": "main", "sha": "d" * 40}},
                       {"base": {"ref": "release", "sha": self.base}}):
            with self.subTest(change=change), self.assertRaises(SystemExit):
                self.check(report, [reply(self.acceptance(report))], [current, dict(current, **change)])
