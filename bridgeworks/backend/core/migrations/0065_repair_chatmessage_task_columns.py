from django.db import migrations


def add_missing_chatmessage_columns(apps, schema_editor):
    connection = schema_editor.connection
    table_name = 'core_chatmessage'

    with connection.cursor() as cursor:
        columns = {
            col.name for col in connection.introspection.get_table_description(cursor, table_name)
        }

    statements = []
    if 'task_status' not in columns:
        statements.append(
            "ALTER TABLE core_chatmessage ADD COLUMN task_status varchar(20) NOT NULL DEFAULT 'pending'"
        )
    if 'task_source_message_id' not in columns:
        statements.append(
            "ALTER TABLE core_chatmessage ADD COLUMN task_source_message_id integer NULL"
        )

    for sql in statements:
        schema_editor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0064_chatmessage_task_fields'),
    ]

    operations = [
        migrations.RunPython(add_missing_chatmessage_columns, migrations.RunPython.noop),
    ]
