"""An approval must apply to this plan and originate from the configured owner."""

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
    def run_check(self, comments, *, state="open", plan=PLAN, action="check"):
        args = ["fleet-plan", action, "example/parser", "7", "22", "--owner-id", str(OWNER)]
        pages = [[plan], comments]
        with patch.object(sys, "argv", args), patch.dict(MAIN.__globals__, {
            "github": lambda path, paginate=False: pages if paginate else {"state": state},
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

    def test_closed_or_changed_or_missing_plan(self):
        for options in ({"state": "closed"}, {"plan": dict(PLAN, body="Wider scope")},
                        {"plan": dict(PLAN, updated_at="2025-01-02T00:00:00Z")},
                        {"plan": dict(PLAN, id=77)}):
            with self.subTest(options=options), self.assertRaises(SystemExit):
                self.run_check([reply(APPROVE)], **options)
