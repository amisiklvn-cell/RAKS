import unittest

from raks.commands import CommandInterpreter


class CommandInterpreterTests(unittest.TestCase):
    def setUp(self):
        self.interpreter = CommandInterpreter()

    def test_slash_commands(self):
        for raw, expected in (
            ("/help", "help"),
            ("/STATUS", "status"),
            ("/clear", "clear"),
            ("/menu", "menu"),
            ("/exit", "exit"),
            ("/conversation", "conversation"),
            ("/plan", "plan"),
            ("/project", "project"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(self.interpreter.parse(raw).action, expected)

    def test_unknown_slash_command(self):
        result = self.interpreter.parse("/delete-everything")
        self.assertEqual(result.action, "unknown_command")
        self.assertEqual(result.value, "/delete-everything")

    def test_menu_numbers(self):
        self.assertEqual(self.interpreter.parse("3").action, "menu_item")
        self.assertEqual(self.interpreter.parse("10").value, "10")
        self.assertEqual(self.interpreter.parse("11").action, "invalid_menu")

    def test_plain_text_is_chat_not_shell(self):
        result = self.interpreter.parse("rm -rf /")
        self.assertEqual(result.action, "chat")
        self.assertEqual(result.value, "rm -rf /")

    def test_empty_input(self):
        self.assertEqual(self.interpreter.parse("   ").action, "empty")
