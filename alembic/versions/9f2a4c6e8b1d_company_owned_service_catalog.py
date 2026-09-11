"""Make services the company-owned commercial catalogue.

Revision ID: 9f2a4c6e8b1d
Revises: 8d3f6a1c5b7e
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9f2a4c6e8b1d"
down_revision: str | None = "8d3f6a1c5b7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalized(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    services = sa.Table("services", metadata, autoload_with=bind)
    assignments = sa.Table("professional_services", metadata, autoload_with=bind)
    appointments = sa.Table("appointments", metadata, autoload_with=bind)

    service_rows = {
        row.id: row
        for row in bind.execute(sa.select(services).order_by(services.c.id)).mappings()
    }
    assignment_rows = list(
        bind.execute(sa.select(assignments).order_by(assignments.c.id)).mappings()
    )
    assignments_by_service: dict[int, list] = {}
    for assignment in assignment_rows:
        assignments_by_service.setdefault(assignment.service_id, []).append(assignment)

    effective_terms: dict[int, tuple[int, int]] = {}
    invalid_orphans: list[int] = []
    for service_id, service in service_rows.items():
        price = service.price_cents
        duration = service.duration_minutes
        candidates = assignments_by_service.get(service_id, [])
        if price is None and candidates:
            price = candidates[0].price_cents
        if duration is None and candidates:
            duration = candidates[0].duration_minutes
        if price is None or duration is None:
            appointment_exists = bind.execute(
                sa.select(appointments.c.id)
                .where(appointments.c.service_id == service_id)
                .limit(1)
            ).first()
            if appointment_exists:
                raise RuntimeError(
                    f"Serviço {service_id} possui histórico, mas não tem valor e duração definidos"
                )
            invalid_orphans.append(service_id)
            continue
        effective_terms[service_id] = (int(price), int(duration))

    if invalid_orphans:
        bind.execute(
            assignments.delete().where(assignments.c.service_id.in_(invalid_orphans))
        )
        bind.execute(services.delete().where(services.c.id.in_(invalid_orphans)))
        for service_id in invalid_orphans:
            service_rows.pop(service_id, None)

    canonical_by_key: dict[tuple, int] = {}
    canonical_for_service: dict[int, int] = {}
    for service_id, service in service_rows.items():
        price, duration = effective_terms[service_id]
        key = (
            _normalized(service.name),
            _normalized(service.description),
            _normalized(service.category),
            price,
            duration,
        )
        canonical_id = canonical_by_key.setdefault(key, service_id)
        canonical_for_service[service_id] = canonical_id
        if canonical_id == service_id:
            bind.execute(
                services.update()
                .where(services.c.id == service_id)
                .values(price_cents=price, duration_minutes=duration)
            )

    for old_service_id, canonical_id in canonical_for_service.items():
        if old_service_id != canonical_id:
            bind.execute(
                appointments.update()
                .where(appointments.c.service_id == old_service_id)
                .values(service_id=canonical_id)
            )

    kept_assignment_by_pair: dict[tuple[int, int], int] = {}
    duplicate_assignment_ids: list[int] = []
    for assignment in assignment_rows:
        if assignment.service_id in invalid_orphans:
            continue
        canonical_id = canonical_for_service[assignment.service_id]
        pair = (assignment.professional_id, canonical_id)
        kept_id = kept_assignment_by_pair.setdefault(pair, assignment.id)
        if kept_id != assignment.id:
            duplicate_assignment_ids.append(assignment.id)

    if duplicate_assignment_ids:
        bind.execute(
            assignments.delete().where(assignments.c.id.in_(duplicate_assignment_ids))
        )

    for (professional_id, canonical_id), assignment_id in kept_assignment_by_pair.items():
        bind.execute(
            assignments.update()
            .where(
                assignments.c.id == assignment_id,
                assignments.c.professional_id == professional_id,
            )
            .values(service_id=canonical_id)
        )

    duplicate_ids = [
        service_id
        for service_id, canonical_id in canonical_for_service.items()
        if service_id != canonical_id
    ]
    if duplicate_ids:
        bind.execute(services.delete().where(services.c.id.in_(duplicate_ids)))

    with op.batch_alter_table("professional_services") as batch_op:
        batch_op.drop_column("duration_minutes")
        batch_op.drop_column("price_cents")

    with op.batch_alter_table("services") as batch_op:
        batch_op.alter_column(
            "duration_minutes", existing_type=sa.Integer(), nullable=False
        )
        batch_op.alter_column(
            "price_cents", existing_type=sa.Integer(), nullable=False
        )
        batch_op.drop_column("professional_id")


def downgrade() -> None:
    op.add_column("services", sa.Column("professional_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_services_professional_id",
        "services",
        "professionals",
        ["professional_id"],
        ["id"],
    )
    op.create_index(
        "ix_services_professional_id", "services", ["professional_id"], unique=False
    )
    op.add_column(
        "professional_services", sa.Column("price_cents", sa.Integer(), nullable=True)
    )
    op.add_column(
        "professional_services",
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE professional_services
        SET price_cents = services.price_cents,
            duration_minutes = services.duration_minutes
        FROM services
        WHERE professional_services.service_id = services.id
        """
    )
    op.execute(
        """
        UPDATE services
        SET professional_id = source.professional_id
        FROM (
            SELECT service_id, MIN(professional_id) AS professional_id
            FROM professional_services
            GROUP BY service_id
        ) AS source
        WHERE services.id = source.service_id
        """
    )
    op.alter_column(
        "professional_services", "price_cents", existing_type=sa.Integer(), nullable=False
    )
    op.alter_column(
        "professional_services",
        "duration_minutes",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_check_constraint(
        "check_professional_service_price",
        "professional_services",
        "price_cents >= 0",
    )
    op.create_check_constraint(
        "check_professional_service_duration",
        "professional_services",
        "duration_minutes > 0",
    )
