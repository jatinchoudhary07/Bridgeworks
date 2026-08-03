from django.db import migrations, connection

SQL_UP = """
-- ── core_order ─────────────────────────────────────────────────────────────
ALTER TABLE core_order ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_order FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_isolation_core_order ON core_order;
CREATE POLICY org_isolation_core_order ON core_order
    AS PERMISSIVE
    FOR ALL
    TO public
    USING (
        org_id::text = current_setting('app.org_id', true)
        OR current_setting('app.bypass_rls', true) = 'true'
    );

-- ── core_returnrequest ───────────────────────────────────────────────────────
ALTER TABLE core_returnrequest ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_returnrequest FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_isolation_core_returnrequest ON core_returnrequest;
CREATE POLICY org_isolation_core_returnrequest ON core_returnrequest
    AS PERMISSIVE
    FOR ALL
    TO public
    USING (
        EXISTS (
            SELECT 1 FROM core_order
            WHERE core_order.id = core_returnrequest.order_id
              AND core_order.org_id::text = current_setting('app.org_id', true)
        )
        OR current_setting('app.bypass_rls', true) = 'true'
    );
"""

SQL_DOWN = """
ALTER TABLE core_order DISABLE ROW LEVEL SECURITY;
ALTER TABLE core_returnrequest DISABLE ROW LEVEL SECURITY;
"""


def enable_rls(apps, schema_editor):
    if connection.vendor != 'postgresql':
        print("Skipping RLS: connection is not PostgreSQL")
        return
    with connection.cursor() as cur:
        cur.execute(SQL_UP)


def disable_rls(apps, schema_editor):
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cur:
        cur.execute(SQL_DOWN)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0201_merge_20260615_1254"),
    ]

    operations = [
        migrations.RunPython(enable_rls, reverse_code=disable_rls),
    ]
