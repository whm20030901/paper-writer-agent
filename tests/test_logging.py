import io
import logging

from paper_writer_agent.core.logging import setup_logging


class _CaptureStream(io.StringIO):
    def isatty(self) -> bool:
        return False


def test_setup_logging_includes_default_request_id_for_plain_records():
    stream = _CaptureStream()
    original_stream_handler = logging.StreamHandler

    try:
        logging.StreamHandler = lambda: original_stream_handler(stream)
        setup_logging("INFO")
        logger = logging.getLogger("test.logger")
        logger.info("hello world")
    finally:
        logging.StreamHandler = original_stream_handler

    output = stream.getvalue()
    assert "hello world" in output
    assert "request_id=-" in output


def test_setup_logging_preserves_explicit_request_id_and_level_override():
    stream = _CaptureStream()
    original_stream_handler = logging.StreamHandler

    try:
        logging.StreamHandler = lambda: original_stream_handler(stream)
        setup_logging("DEBUG")
        logger = logging.getLogger("test.logger.explicit")
        logger.debug("with request id", extra={"request_id": "req-42"})
    finally:
        logging.StreamHandler = original_stream_handler

    output = stream.getvalue()
    assert "with request id" in output
    assert "request_id=req-42" in output
    assert logging.getLogger().level == logging.DEBUG
