"""Tests for RAKS AI v1.0.1."""


class AutoGate:
    """Test-only approval gate; never used by terminal or browser interfaces."""

    def approve(self, request):
        return True
