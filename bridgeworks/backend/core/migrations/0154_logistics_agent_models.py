from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0153_merge_20260521_1548'),
    ]

    operations = [
        migrations.CreateModel(
            name='LogisticsAgentConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Default Logistics Agent Config', max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('response_style', models.CharField(
                    choices=[('Concise', 'Concise'), ('Balanced', 'Balanced'), ('Detailed', 'Detailed')],
                    default='Balanced', max_length=20,
                )),
                ('persona', models.CharField(
                    choices=[
                        ('default', 'Default (Professional Analyst)'),
                        ('warm', 'Warm & Encouraging'),
                        ('calm', 'Calm & Measured'),
                        ('genz', 'Gen Z (Casual & Energetic)'),
                        ('aggressive', 'Aggressive (Bold & Direct)'),
                        ('zen', 'Zen (Minimal & Mindful)'),
                    ],
                    default='default', max_length=20,
                )),
                ('system_prompt', models.TextField(help_text='Master instructions for deep logistics audit analysis.')),
                ('general_prompt', models.TextField(
                    blank=True, default='',
                    help_text='Master instructions for general conversational chat (no payload).',
                )),
                ('model_name', models.CharField(default='gemini-2.5-flash-lite', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Logistics Agent Configuration',
                'verbose_name_plural': 'Logistics Agent Configurations',
                'app_label': 'core',
            },
        ),
        migrations.CreateModel(
            name='LogisticsAgentGlobalRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rule_text', models.TextField()),
                ('created_by', models.CharField(blank=True, default='admin', max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('priority', models.IntegerField(default=0, help_text='Higher = shown earlier in the prompt.')),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Logistics Agent Global Rule',
                'verbose_name_plural': 'Logistics Agent Global Rules',
                'ordering': ['-priority', '-created_at'],
                'app_label': 'core',
            },
        ),
        migrations.CreateModel(
            name='LogisticsCorrectionRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bad_behavior_description', models.TextField()),
                ('corrected_instruction', models.TextField()),
                ('example_bad_response', models.TextField(blank=True, default='')),
                ('example_good_response', models.TextField(blank=True, default='')),
                ('source_log_id', models.IntegerField(blank=True, null=True)),
                ('created_by', models.CharField(blank=True, default='admin', max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Logistics Correction Rule',
                'verbose_name_plural': 'Logistics Correction Rules',
                'ordering': ['-created_at'],
                'app_label': 'core',
            },
        ),
        migrations.CreateModel(
            name='LogisticsConversationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(blank=True, db_index=True, default='', max_length=100)),
                ('user_identifier', models.CharField(blank=True, default='', max_length=255)),
                ('shop_name', models.CharField(blank=True, default='', max_length=255)),
                ('system_prompt_snapshot', models.TextField()),
                ('user_message', models.TextField()),
                ('ai_response', models.TextField()),
                ('model_used', models.CharField(blank=True, default='', max_length=100)),
                ('tokens_input', models.IntegerField(default=0)),
                ('tokens_output', models.IntegerField(default=0)),
                ('response_time_ms', models.IntegerField(default=0)),
                ('flagged_for_review', models.BooleanField(default=False)),
                ('admin_note', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Logistics Conversation Log',
                'verbose_name_plural': 'Logistics Conversation Logs',
                'ordering': ['-created_at'],
                'app_label': 'core',
            },
        ),
    ]
