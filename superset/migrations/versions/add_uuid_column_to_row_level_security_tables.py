# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""add_uuid_column_to_row_level_security_tables

Revision ID:
Revises:
Create Date: 2021-08-17 14:26:12.119363

Adapted from:
    superset.migrations.versions.c501b7c653a3_add_missing_uuid_column.py
    superset.migrations.versions.b56500de1855_add_uuid_column_to_import_mixin.py
"""

# revision identifiers, used by Alembic.
revision = ""
down_revision = ""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import load_only
from sqlalchemy_utils import UUIDType

from superset import db
from superset.migrations.versions.b56500de1855_add_uuid_column_to_import_mixin import (
    add_uuids,
    ImportMixin,
    update_dashboards,
)
from superset.migrations.versions.c501b7c653a3_add_missing_uuid_column import (
    has_uuid_column,
)

Base = declarative_base()

table_names = [
    # Row level security tables
    "row_level_security_filters",
    "rls_filter_roles",
    "rls_filter_tables",
]

models = {
    table_name: type(table_name, (Base, ImportMixin), {"__tablename__": table_name})
    for table_name in table_names
}


def upgrade():
    bind = op.get_bind()
    session = db.Session(bind=bind)

    for table_name, model in models.items():
        # this script adds missing uuid columns
        if has_uuid_column(table_name, bind):
            continue

        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "uuid", UUIDType(binary=True), primary_key=False, default=uuid4,
                ),
            )
        add_uuids(model, table_name, session)

        # add uniqueness constraint
        with op.batch_alter_table(table_name) as batch_op:
            # batch mode is required for sqllite
            batch_op.create_unique_constraint(f"uq_{table_name}_uuid", ["uuid"])

    # add UUID to Dashboard.position_json; this function is idempotent
    # so we can call it for all objects
    slice_uuid_map = {
        slc.id: slc.uuid
        for slc in session.query(models["slices"])
        .options(load_only("id", "uuid"))
        .all()
    }
    update_dashboards(session, slice_uuid_map)


def downgrade() -> None:
    bind = op.get_bind()
    session = db.Session(bind=bind)

    # remove uuid from position_json
    update_dashboards(session, {})

    # remove uuid column
    for table_name, model in models.items():
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(f"uq_{table_name}_uuid", type_="unique")
            batch_op.drop_column("uuid")
