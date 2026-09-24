"""SQLAlchemy Core tables for the scheduling subset of the frozen schema.

These mirror ``contracts/schema/001_init.sql`` and are never used to create it —
migrations are forward-only SQL owned by Workstream A. Keeping the definitions
narrow (the columns this API reads or writes) means a schema change that matters
shows up here as a mismatch rather than as silence.

``care_rule``, ``task``, ``task_event`` and ``calendar_feed`` are this
workstream's to write. Everything else here is read-only: ``specimen``,
``species``, ``care_value`` and ``location`` are C's and D's, and
``water_balance`` is E's.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

metadata = MetaData()

# ------------------------------------------------------------------ read-only

site = Table(
    "site",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", Text, nullable=False),
    Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False),
    Column("timezone", Text, nullable=False),
)

member = Table(
    "member",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("notify_prefs", JSONB),
    Column("archived_at", DateTime(timezone=True)),
)

location = Table(
    "location",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", Text, nullable=False),
    Column("is_outdoor", Boolean, nullable=False),
    Column("is_covered", Boolean, nullable=False),
)

species = Table(
    "species",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("accepted_name", Text, nullable=False),
    Column("common_names", ARRAY(Text)),
    Column("water_interval_days", Integer),
    Column("dormancy_months", ARRAY(Integer)),
)

#: Rule 6's provenance table. The scheduler reads it to find out whether the
#: interval it is about to schedule on is a fact or a guess.
care_value = Table(
    "care_value",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("species_id", Uuid, nullable=False),
    Column("field", Text, nullable=False),
    Column("value", JSONB, nullable=False),
    Column("source_id", Uuid),
    Column("confidence", Text, nullable=False),
    Column("is_user_override", Boolean, nullable=False),
)

specimen = Table(
    "specimen",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("species_id", Uuid),
    Column("nickname", Text),
    Column("location_id", Uuid),
    Column("is_outdoor", Boolean, nullable=False),
    Column("in_container", Boolean, nullable=False),
    Column("container_litres", Float),
    Column("acquired_on", Date),
    Column("water_interval_days_override", Integer),
    Column("archived_at", DateTime(timezone=True)),
)

#: Workstream E's, one row per specimen per day. Read for the latest day only.
water_balance = Table(
    "water_balance",
    metadata,
    Column("day", Date, nullable=False),
    Column("specimen_id", Uuid, nullable=False),
    Column("deficit_mm", Float, nullable=False),
    Column("threshold_mm", Float, nullable=False),
    Column("sensor_override_pct", Float),
)

# ----------------------------------------------------------------- written here

care_rule = Table(
    "care_rule",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("species_id", Uuid),
    Column("specimen_id", Uuid),
    Column("task_type", Text, nullable=False),
    Column("strategy", Text, nullable=False),
    Column("base_interval_days", Integer),
    Column("amount_ml", Integer),
    Column("modifiers", JSONB, nullable=False),
    Column("months", ARRAY(Integer)),
    Column("enabled", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True)),
)

task = Table(
    "task",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("specimen_id", Uuid, nullable=False),
    Column("care_rule_id", Uuid),
    Column("task_type", Text, nullable=False),
    Column("due_at", DateTime(timezone=True), nullable=False),
    Column("all_day", Boolean, nullable=False),
    Column("status", Text, nullable=False),
    Column("satisfied_by", Text),
    Column("amount_ml", Integer),
    Column("priority", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("plain_title", Text, nullable=False),
    Column("detail", Text),
    Column("completed_at", DateTime(timezone=True)),
    Column("completed_by", Uuid),
    Column("notes", Text),
    Column("ics_uid", Text, nullable=False),
    Column("ics_sequence", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)

#: The history. "When was the lemon last fed" is answered from here, not from
#: whatever the task row happens to say today.
task_event = Table(
    "task_event",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("task_id", Uuid, nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
    Column("kind", Text, nullable=False),
    Column("by_member", Uuid),
    Column("data", JSONB, nullable=False),
)

calendar_feed = Table(
    "calendar_feed",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("member_id", Uuid, nullable=False),
    Column("name", Text, nullable=False),
    Column("token", Text, nullable=False),
    Column("filters", JSONB, nullable=False),
    Column("push_target", Text),
    Column("push_config", JSONB, nullable=False),
    Column("last_rendered_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True)),
)

#: Columns a generated task may overwrite on an occurrence that has moved.
#: ``id``, ``ics_uid`` and ``ics_sequence`` are deliberately absent: the first
#: two never change and the third only ever increments.
TASK_REGENERATED = (
    "due_at",
    "all_day",
    "status",
    "satisfied_by",
    "amount_ml",
    "priority",
    "title",
    "plain_title",
    "detail",
)
