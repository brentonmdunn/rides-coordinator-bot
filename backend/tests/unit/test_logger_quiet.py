"""Unit tests for log_job_quiet and QuietJobFilter."""

import logging

import pytest

from shared.core.logger import QuietJobFilter, log_job_quiet


class TestLogJobQuiet:
    @pytest.mark.asyncio
    async def test_success_logs_no_info(self, caplog):
        @log_job_quiet
        async def sample_job():
            return "ok"

        with caplog.at_level(logging.DEBUG):
            result = await sample_job()

        assert result == "ok"
        info_records = [r for r in caplog.records if r.levelno >= logging.INFO]
        assert info_records == []

        debug_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
        assert any("started" in m for m in debug_messages)
        assert any("completed" in m for m in debug_messages)

    @pytest.mark.asyncio
    async def test_failure_logs_exception_and_reraises(self, caplog):
        @log_job_quiet
        async def failing_job():
            raise RuntimeError("boom")

        with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError, match="boom"):
            await failing_job()

        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) == 1
        assert "failed" in error_records[0].getMessage()
        assert error_records[0].exc_info is not None


class TestQuietJobFilter:
    def _make_record(self, message: str, level: int = logging.INFO) -> logging.LogRecord:
        return logging.LogRecord(
            name="apscheduler.executors.default",
            level=level,
            pathname=__file__,
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )

    def test_drops_info_records_for_quieted_job(self):
        job_filter = QuietJobFilter({"run_temp_driver_expiry"})
        record = self._make_record('Running job "run_temp_driver_expiry (trigger: ...)"')

        assert job_filter.filter(record) is False

    def test_keeps_info_records_for_other_jobs(self):
        job_filter = QuietJobFilter({"run_temp_driver_expiry"})
        record = self._make_record('Running job "run_friday_pickups_summary (trigger: ...)"')

        assert job_filter.filter(record) is True

    def test_keeps_warning_records_for_quieted_job(self):
        job_filter = QuietJobFilter({"run_temp_driver_expiry"})
        record = self._make_record(
            "Job run_temp_driver_expiry raised an exception", level=logging.WARNING
        )

        assert job_filter.filter(record) is True

    def test_keeps_error_records_for_quieted_job(self):
        job_filter = QuietJobFilter({"run_temp_driver_expiry"})
        record = self._make_record("Job run_temp_driver_expiry failed", level=logging.ERROR)

        assert job_filter.filter(record) is True

    def test_empty_sweep_produces_no_info_records(self, caplog):
        """An empty sweep tick with the filter installed shouldn't emit INFO records."""
        job_filter = QuietJobFilter({"run_temp_driver_expiry"})
        apscheduler_logger = logging.getLogger("apscheduler.executors.default")
        apscheduler_logger.addFilter(job_filter)
        try:
            with caplog.at_level(logging.DEBUG, logger="apscheduler.executors.default"):
                apscheduler_logger.info('Running job "run_temp_driver_expiry (trigger: ...)"')
                apscheduler_logger.info(
                    'Job "run_temp_driver_expiry (trigger: ...)" executed successfully'
                )
            assert caplog.records == []
        finally:
            apscheduler_logger.removeFilter(job_filter)
