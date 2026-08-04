from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories import AvailabilityRepository, AppointmentRepository, ServiceRepository
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
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        day_of_week = date.weekday()

        slots = self.repo.find_by_date(professional_id, date_str)
        if not slots:
            slots = self.repo.find_by_day(professional_id, day_of_week)

        if not slots:
            return []

        available_slots: list[TimeSlot] = []
        day_start = date_str
        day_end = date_str

        for slot in slots:
            slot_start = f"{day_start}T{slot.start_time}"
            slot_end = f"{day_end}T{slot.end_time}"
            available_slots.append(TimeSlot(start=slot_start, end=slot_end))

        busy = self.appointment_repo.find_conflicting(
            professional_id, f"{date_str}T00:00", f"{date_str}T23:59"
        )

        if not busy:
            return available_slots

        free_slots: list[TimeSlot] = []
        for slot in available_slots:
            current_start = slot.start
            for b in sorted(busy, key=lambda x: x.start_time):
                if b.start_time > current_start:
                    free_slots.append(TimeSlot(start=current_start, end=b.start_time))
                current_start = max(current_start, b.end_time)
            if current_start < slot.end:
                free_slots.append(TimeSlot(start=current_start, end=slot.end))

        return free_slots

    def get_time_slots_for_service(self, professional_id: int, service_id: int, date_str: str) -> list[TimeSlot]:
        service = self.service_repo.get(service_id)
        if not service:
            return []

        free_periods = self.check_availability(professional_id, date_str)

        slots: list[TimeSlot] = []
        duration = timedelta(minutes=service.duration_minutes)

        for period in free_periods:
            period_start = datetime.fromisoformat(period.start)
            period_end = datetime.fromisoformat(period.end)
            cursor = period_start
            while cursor + duration <= period_end:
                end = cursor + duration
                slots.append(TimeSlot(
                    start=cursor.isoformat(),
                    end=end.isoformat(),
                ))
                cursor = end

        return slots
