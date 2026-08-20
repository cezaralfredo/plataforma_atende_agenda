from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.repositories import (
    AppointmentRepository,
    AvailabilityRepository,
    ServiceRepository,
)
from app.schemas.availability import AvailabilityCreate, AvailabilityUpdate, TimeSlot


class AvailabilityService:
    def __init__(self, db: Session):
        self.repo = AvailabilityRepository(db)
        self.appointment_repo = AppointmentRepository(db)
        self.service_repo = ServiceRepository(db)

    def create(self, data: AvailabilityCreate):
        return self.repo.create(**data.model_dump())

    def get(self, availability_id: int):
        return self.repo.get(availability_id)

    def list(self, professional_id: int | None = None):
        if professional_id is not None:
            return self.repo.list_by_professional(professional_id)
        return self.repo.list()

    def update(self, availability_id: int, data: AvailabilityUpdate):
        return self.repo.update(availability_id, **data.model_dump())

    def delete(self, availability_id: int):
        return self.repo.delete(availability_id)

    def check_availability(self, professional_id: int, date_str: str) -> list[TimeSlot]:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return []

        day_of_week = date_obj.weekday()

        # Get specific date availability first
        slots = self.repo.find_by_date(professional_id, date_obj)
        if not slots:
            # Fall back to recurring weekly availability
            slots = self.repo.find_by_day(professional_id, day_of_week)

        if not slots:
            return []

        available_slots: list[TimeSlot] = []

        for slot in slots:
            if slot.specific_date:
                slot_date = slot.specific_date
            else:
                slot_date = date_obj

            if slot.start_time and slot.end_time:
                slot_start = datetime.combine(slot_date, slot.start_time)
                slot_end = datetime.combine(slot_date, slot.end_time)
                available_slots.append(TimeSlot(start=slot_start, end=slot_end))

        # Get busy appointments for the day
        day_start = datetime.combine(date_obj, time.min)
        day_end = datetime.combine(date_obj, time.max)

        busy = self.appointment_repo.find_conflicting(
            professional_id, day_start.isoformat(), day_end.isoformat()
        )

        if not busy:
            return available_slots

        free_slots: list[TimeSlot] = []
        for slot in available_slots:
            current_start = slot.start
            for b in sorted(busy, key=lambda x: x.start_time):
                busy_start = b.start_time
                busy_end = b.end_time
                if isinstance(busy_start, str):
                    busy_start = datetime.fromisoformat(busy_start)
                if isinstance(busy_end, str):
                    busy_end = datetime.fromisoformat(busy_end)

                # An appointment outside this availability window must not
                # expand or consume this window.
                if busy_end <= current_start or busy_start >= slot.end:
                    continue
                if busy_start > current_start:
                    free_slots.append(TimeSlot(start=current_start, end=min(busy_start, slot.end)))
                current_start = max(current_start, min(busy_end, slot.end))
            if current_start < slot.end:
                free_slots.append(TimeSlot(start=current_start, end=slot.end))

        return free_slots

    def get_time_slots_for_service(self, professional_id: int, service_id: int, date_str: str) -> list[TimeSlot]:
        service = self.service_repo.get(service_id)
        if not service or service.professional_id != professional_id:
            return []

        free_periods = self.check_availability(professional_id, date_str)

        slots: list[TimeSlot] = []
        duration = timedelta(minutes=service.duration_minutes)

        for period in free_periods:
            period_start = period.start
            period_end = period.end
            cursor = period_start
            while cursor + duration <= period_end:
                end = cursor + duration
                slots.append(TimeSlot(
                    start=cursor,
                    end=end,
                ))
                cursor = end

        return slots

    def is_interval_available(self, professional_id: int, start: datetime, end: datetime) -> bool:
        """Return whether the entire requested interval is inside one free period."""
        date_str = start.date().isoformat()
        if end.date() != start.date():
            return False
        return any(period.start <= start and end <= period.end
                   for period in self.check_availability(professional_id, date_str))
