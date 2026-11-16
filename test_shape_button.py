import tkinter as tk
import unittest

import theme
from controls_bar import ControlActions, ControlsBar
from repeat import RepeatMode
from shape_button import Shape, ShapeButton, ShapeColors
from tabs import Tabs
from theme import ThemeName

COLORS = ShapeColors(fill="accent", hover="accent_hover", foreground="on_accent")


class ShapeWidgetTest(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available")
        self.root.withdraw()
        theme.bind(self.root, bg="background")
        self.calls: list[str] = []

    def tearDown(self) -> None:
        self.root.destroy()
        theme.reset()

    def button(self, shape: Shape = Shape.CIRCLE, label: str = "") -> ShapeButton:
        button = ShapeButton(self.root, lambda: self.calls.append("run"), tooltip="Tip", shape=shape, colors=COLORS, size=40, icon="x", label=label)
        button.pack()
        self.root.update_idletasks()
        return button

    def test_enter_and_space_are_bound_to_the_action(self) -> None:
        button = self.button()
        for sequence in ("<Return>", "<space>"):
            self.assertTrue(button.bind(sequence))
        button.invoke()
        self.assertEqual(self.calls, ["run"])

    def test_pill_grows_with_its_label_and_circle_does_not(self) -> None:
        pill = self.button(Shape.PILL)
        circle = self.button(Shape.CIRCLE)
        narrow = pill.winfo_reqwidth()
        pill.set_content("x", "Reproducir")
        self.assertGreater(pill.winfo_reqwidth(), narrow)
        circle.set_content("x", "ignored")
        self.assertEqual(circle.winfo_reqwidth(), circle.winfo_reqheight())

    def test_takes_keyboard_focus(self) -> None:
        self.assertTrue(self.button().cget("takefocus"))


class ControlsBarThemeTest(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available")
        self.root.withdraw()
        theme.bind(self.root, bg="background")
        noop = lambda *_: None
        self.controls = ControlsBar(self.root, 50, RepeatMode.OFF, ControlActions(noop, noop, noop, noop, noop, noop))
        self.controls.pack()

    def tearDown(self) -> None:
        self.root.destroy()
        theme.reset()

    def test_play_button_shape_follows_the_theme(self) -> None:
        self.assertNotIsInstance(self.controls._toggle, ShapeButton)
        theme.select(ThemeName.NIGHT)
        self.assertIsInstance(self.controls._toggle, ShapeButton)
        theme.select(ThemeName.GLASS)
        self.assertNotIsInstance(self.controls._toggle, ShapeButton)

    def test_playing_state_survives_a_theme_change(self) -> None:
        self.controls.set_playing(True)
        theme.select(ThemeName.FROST)
        self.assertEqual(self.controls._toggle._label, "Pausa")
        self.controls.set_playing(False)
        self.assertEqual(self.controls._toggle._label, "Reproducir")


class TabsThemeTest(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available")
        self.root.withdraw()
        theme.bind(self.root, bg="background")
        self.changes: list[str] = []
        self.tabs = Tabs(self.root, self.changes.append)
        self.tabs.pack()
        for name in ("One", "Two", "Three"):
            self.tabs.add(name, lambda parent: tk.Frame(parent))
        self.tabs.select("Two")

    def tearDown(self) -> None:
        self.root.destroy()
        theme.reset()

    def test_selection_and_pages_survive_every_style(self) -> None:
        for name in ThemeName:
            theme.select(name)
            self.assertEqual(self.tabs.current, "Two")
            self.assertEqual(self.tabs.names, ["One", "Two", "Three"])
        self.tabs.select("Three")
        self.assertEqual(self.changes[-1], "Three")

    def test_underline_style_marks_only_the_selected_tab(self) -> None:
        theme.select(ThemeName.VINYL)
        marks = {name: underline.cget("bg") for name, underline in self.tabs._underlines.items()}
        self.assertEqual(marks, {"One": theme.VINYL.background, "Two": theme.VINYL.accent, "Three": theme.VINYL.background})


if __name__ == "__main__":
    unittest.main()
