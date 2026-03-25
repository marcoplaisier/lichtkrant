"""Tests for the spy SPI driver."""

import logging

from lichtkrant.config import Config
from lichtkrant.protocol import Color, MessageBuilder
from lichtkrant.spi.spy import SpySPIDriver


class TestSpySPIDriver:
    def test_send_records_history(self) -> None:
        """Messages are recorded in history."""
        config = Config()
        spy = SpySPIDriver(config)
        spy.open()

        msg = MessageBuilder().add_text("Test", Color.WHITE).build()
        result = spy.send(msg)

        assert result is True
        assert len(spy.history) == 1
        assert spy.history[0] == msg

    def test_send_multiple(self) -> None:
        """Multiple sends are all recorded."""
        config = Config()
        spy = SpySPIDriver(config)
        spy.open()

        for i in range(3):
            msg = MessageBuilder().add_text(f"Msg{i}", Color.WHITE).build()
            spy.send(msg)

        assert len(spy.history) == 3

    def test_send_logs_decoded_output(self, caplog) -> None:
        """Send logs decoded message lines."""
        config = Config()
        spy = SpySPIDriver(config)
        spy.open()

        msg = (
            MessageBuilder(speed=42)
            .add_text("Hello", Color.RED)
            .add_pause(3)
            .build()
        )

        with caplog.at_level(logging.INFO):
            spy.send(msg)

        log_text = caplog.text
        assert "Header: bg=NONE speed=42 font=KONGTEXT" in log_text
        assert '"Hello" color=RED' in log_text
        assert "Pause 3s" in log_text
        assert "Hex:" in log_text

    def test_wait_for_request_always_true(self) -> None:
        config = Config()
        spy = SpySPIDriver(config)
        assert spy.wait_for_request() is True

    def test_context_manager(self) -> None:
        config = Config()
        with SpySPIDriver(config) as spy:
            msg = MessageBuilder().add_text("X", Color.WHITE).build()
            assert spy.send(msg) is True
        assert len(spy.history) == 1
