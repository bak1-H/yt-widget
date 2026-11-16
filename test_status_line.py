import tkinter as tk
import unittest

import texts
from components import StatusLine


class StatusLineUndoTest(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available")
        self.root.withdraw()
        self.status = StatusLine(self.root)
        self.status.pack()
        self.calls: list[str] = []

    def tearDown(self) -> None:
        self.root.destroy()

    def link_text(self) -> str:
        return self.status._link.cget("text")

    def test_undo_link_belongs_to_its_own_message(self) -> None:
        self.status.show_undoable("Removed", lambda: self.calls.append("undo"))
        self.assertEqual(self.link_text(), texts.UNDO)
        self.status.show("Something else")
        self.assertEqual(self.link_text(), "")
        self.status.undo()
        self.assertEqual(self.calls, [])

    def test_undo_runs_once_while_its_message_is_shown(self) -> None:
        self.status.show_undoable("Removed", lambda: self.calls.append("undo"))
        self.status.undo()
        self.status.undo()
        self.assertEqual(self.calls, ["undo"])
        self.assertEqual(self.link_text(), "")

    def test_expiring_the_message_removes_the_link(self) -> None:
        self.status.show_undoable("Removed", lambda: self.calls.append("undo"))
        self.status.dismiss()
        self.assertEqual(self.link_text(), "")
        self.assertEqual(self.status.message, "")

    def test_an_action_link_does_not_keep_an_older_undo(self) -> None:
        self.status.show_undoable("Removed", lambda: self.calls.append("undo"))
        self.status.show("Exists", "error", "Add there", lambda: self.calls.append("add"))
        self.assertEqual(self.link_text(), "Add there")
        self.status.clear()
        self.status.undo()
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
