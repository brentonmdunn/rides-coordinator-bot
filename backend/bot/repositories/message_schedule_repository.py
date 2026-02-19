"""Data access layer for message schedule pause operations."""

from datetime import date, datetime, timedelta

from sqlalchemy import select, update

from bot.core.database import AsyncSessionLocal
from bot.core.enums import JobName
from bot.core.logger import logger
from bot.core.models import MessageSchedulePause

# Valid job names — derived from the enum (single source of truth)
VALID_JOB_NAMES = tuple(j.value for j in JobName)


class MessageScheduleRepository:
    """Handles database operations for message schedule pauses."""

    @staticmethod
    async def get_pause_status(job_name: str) -> MessageSchedulePause | None:
        """Get the pause status for a specific job.

        Args:
            job_name: A JobName value ("friday", "sunday", "sunday_class").

        Returns:
            The MessageSchedulePause row, or None if not found.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(MessageSchedulePause).where(
                MessageSchedulePause.job_name == job_name
            )
            result = await session.execute(stmt)
            return result.scalars().first()

    @staticmethod
    async def get_all_pause_statuses() -> list[MessageSchedulePause]:
        """Get pause statuses for all jobs.

        Returns:
            A list of MessageSchedulePause rows.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(MessageSchedulePause).order_by(MessageSchedulePause.job_name)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def set_pause(
        job_name: str,
        is_paused: bool,
        resume_after_date: date | None = None,
    ) -> MessageSchedulePause | None:
        """Set the pause state for a job.

        Args:
            job_name: A JobName value ("friday", "sunday", "sunday_class").
            is_paused: Whether to pause the job.
            resume_after_date: Optional event date to resume after.

        Returns:
            The updated MessageSchedulePause row, or None if job not found.
        """
        async with AsyncSessionLocal() as session:
            stmt = (
                update(MessageSchedulePause)
                .where(MessageSchedulePause.job_name == job_name)
                .values(
                    is_paused=is_paused,
                    resume_after_date=resume_after_date,
                    updated_at=datetime.now(),
                )
            )
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount == 0:
                logger.warning(f"No pause row found for job '{job_name}'")
                return None

            # Fetch and return the updated row
            fetch_stmt = select(MessageSchedulePause).where(
                MessageSchedulePause.job_name == job_name
            )
            fetch_result = await session.execute(fetch_stmt)
            return fetch_result.scalars().first()

    @staticmethod
    async def clear_pause(job_name: str) -> None:
        """Clear the pause for a job (resume immediately).

        Args:
            job_name: A JobName value ("friday", "sunday", "sunday_class").
        """
        async with AsyncSessionLocal() as session:
            stmt = (
                update(MessageSchedulePause)
                .where(MessageSchedulePause.job_name == job_name)
                .values(
                    is_paused=False,
                    resume_after_date=None,
                    updated_at=datetime.now(),
                )
            )
            await session.execute(stmt)
            await session.commit()

    @staticmethod
    async def is_job_paused(job_name: str) -> bool:
        """Check if a job is currently paused.

        A job is paused if:
        - is_paused=True and resume_after_date is None (indefinite)
        - is_paused=True and the send-day (Wednesday) for the resume_after_date
          hasn't arrived yet

        For date-based pauses, the job stays paused until the Wednesday before
        the resume_after_date event. On that Wednesday, the job is considered
        "resumed" and sends normally.

        Args:
            job_name: A JobName value ("friday", "sunday", "sunday_class").

        Returns:
            True if the job should be blocked from sending.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(MessageSchedulePause).where(
                MessageSchedulePause.job_name == job_name
            )
            result = await session.execute(stmt)
            pause = result.scalars().first()

            if not pause or not pause.is_paused:
                return False

            # Indefinite pause
            if pause.resume_after_date is None:
                return True

            # Date-based pause: paused until the Wednesday before the event date
            today = date.today()
            send_wednesday = MessageScheduleRepository.get_send_wednesday(pause.resume_after_date)

            if today >= send_wednesday:
                # Auto-clear the pause since we've reached the send day
                clear_stmt = (
                    update(MessageSchedulePause)
                    .where(MessageSchedulePause.job_name == job_name)
                    .values(
                        is_paused=False,
                        resume_after_date=None,
                        updated_at=datetime.now(),
                    )
                )
                await session.execute(clear_stmt)
                await session.commit()
                logger.info(
                    f"Auto-cleared pause for '{job_name}' - send day {send_wednesday} reached"
                )
                return False

            return True

    @staticmethod
    def get_send_wednesday(event_date: date) -> date:
        """Calculate the Wednesday send-day before an event date.

        Args:
            event_date: The event date (a Friday or Sunday).

        Returns:
            The Wednesday before the event date.
        """
        days_to_subtract = (event_date.weekday() - 2) % 7
        if days_to_subtract == 0 and event_date.weekday() != 2:
            days_to_subtract = 7
        return event_date - timedelta(days=days_to_subtract)




