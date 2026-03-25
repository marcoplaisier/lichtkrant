"""Tests for template variable resolution."""

from unittest.mock import patch

import pytest

from lichtkrant.templating import _symbol_cache, has_templates, render


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the symbol cache before each test."""
    _symbol_cache.clear()


class TestRender:
    """Tests for the render function."""

    def test_no_templates(self) -> None:
        """Plain text passes through unchanged."""
        assert render("Hello World") == "Hello World"

    def test_empty_string(self) -> None:
        assert render("") == ""

    def test_date_template(self) -> None:
        """{{date}} resolves to current date."""
        result = render("Today is {{date}}")
        assert result.startswith("Today is ")
        assert "{{" not in result
        # Should be in "DD Mon YYYY" format
        parts = result.split("Today is ")[1].split()
        assert len(parts) == 3

    def test_time_template(self) -> None:
        """{{time}} resolves to current time."""
        result = render("Now: {{time}}")
        assert ":" in result
        assert "{{" not in result

    def test_multiple_templates(self) -> None:
        """Multiple templates in one string are all resolved."""
        result = render("{{date}} at {{time}}")
        assert "{{" not in result

    def test_mixed_text_and_template(self) -> None:
        """Templates mixed with plain text."""
        result = render("The date is {{date}} ok?")
        assert result.startswith("The date is ")
        assert result.endswith(" ok?")

    @patch("lichtkrant.templating._fetch_price")
    def test_symbol_template(self, mock_fetch) -> None:
        """{{AAPL}} resolves to stock price."""
        mock_fetch.return_value = "198.50"
        result = render("Price: {{AAPL}}")
        assert result == "Price: AAPL 198.50"
        mock_fetch.assert_called_once_with("AAPL")

    @patch("lichtkrant.templating._fetch_price")
    def test_symbol_case_insensitive(self, mock_fetch) -> None:
        """Symbol names are uppercased."""
        mock_fetch.return_value = "150.00"
        result = render("{{aapl}}")
        assert result == "AAPL 150.00"
        mock_fetch.assert_called_once_with("AAPL")

    @patch("lichtkrant.templating._fetch_price")
    def test_symbol_fetch_failure(self, mock_fetch) -> None:
        """Failed fetch shows N/A."""
        mock_fetch.return_value = None
        result = render("{{AAPL}}")
        assert result == "AAPL:N/A"

    @patch("lichtkrant.templating._fetch_price")
    def test_symbol_caching(self, mock_fetch) -> None:
        """Second call uses cache, not another fetch."""
        mock_fetch.return_value = "200.00"
        render("{{TSLA}}")
        render("{{TSLA}}")
        mock_fetch.assert_called_once_with("TSLA")

    def test_date_and_symbol(self) -> None:
        """date builtin is not treated as a symbol."""
        with patch("lichtkrant.templating._fetch_price") as mock:
            render("{{date}}")
            mock.assert_not_called()


class TestHasTemplates:
    def test_has_templates(self) -> None:
        assert has_templates("Hello {{date}}") is True

    def test_no_templates(self) -> None:
        assert has_templates("Hello World") is False

    def test_partial_braces(self) -> None:
        assert has_templates("Hello {date}") is False
