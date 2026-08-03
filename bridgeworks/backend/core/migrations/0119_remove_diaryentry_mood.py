from django.db import migrations


def forwards_func(apps, schema_editor):
    if schema_editor.connection.vendor == 'sqlite':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_keys = OFF;")
            cursor.execute("""
                CREATE TABLE core_diaryentry_rebuild (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED,
                    title VARCHAR(255) NOT NULL,
                    note TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    hours DECIMAL NOT NULL,
                    entry_type VARCHAR(20) NOT NULL,
                    entry_date DATE NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                );
            """)
            cursor.execute("""
                INSERT INTO core_diaryentry_rebuild
                    (id, user_id, title, note, tags, hours, entry_type, entry_date, created_at, updated_at)
                SELECT id, user_id, title, note, tags, hours, entry_type, entry_date, created_at, updated_at
                FROM core_diaryentry;
            """)
            cursor.execute("DROP TABLE core_diaryentry;")
            cursor.execute("ALTER TABLE core_diaryentry_rebuild RENAME TO core_diaryentry;")
            cursor.execute("PRAGMA foreign_keys = ON;")
    else:
        with schema_editor.connection.cursor() as cursor:
            # For PostgreSQL and other databases
            cursor.execute("ALTER TABLE core_diaryentry DROP COLUMN IF EXISTS mood;")

def backwards_func(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute("ALTER TABLE core_diaryentry ADD COLUMN mood VARCHAR(20) NOT NULL DEFAULT 'neutral';")
        except Exception:
            pass


class Migration(migrations.Migration):
    """
    The `mood` VARCHAR(20) NOT NULL column exists in the core_diaryentry DB table
    but is no longer defined in the Django model. This causes every DiaryEntry
    INSERT to fail with:
        NOT NULL constraint failed: core_diaryentry.mood

    Since SQLite doesn't support DROP COLUMN cleanly with FK references, and
    Django's migration state already has no record of `mood`, we use a direct
    Python database operation to set a default value on every existing row and
    update the column to allow the database to accept new inserts.

    On SQLite (local dev): we back-fill existing rows with a default value.
    The NOT NULL constraint remains but all existing rows get a value, so old
    data is safe. New rows will fail if mood is required — but since the Django
    model no longer includes it, Django will never try to INSERT it.

    WAIT: SQLite does NOT include a column in INSERT if the model has no field
    for it — which means the NOT NULL constraint will still fire.

    The real fix for SQLite is: PRAGMA writable_schema to alter column type,
    or a proper table rebuild. We do the proper rebuild but we must temporarily
    disable FK checks, rebuild the table with full proper DDL, and re-enable.
    """

    dependencies = [
        ('core', '0118_freightinvoice_alter_codremittance_status_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards_func, backwards_func),
            ],
            state_operations=[],
        ),
    ]
