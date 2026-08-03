import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0182_courierinvoiceline_anomaly_category_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatRoom',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('room_id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True, default='')),
                ('icon', models.ImageField(blank=True, null=True, upload_to='chat_room_icons/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_chat_rooms', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_rooms', to='core.shopcredentials')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ChatRoomSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allow_member_messages', models.BooleanField(default=True)),
                ('announcement_mode', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('room', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='settings', to='core.chatroom')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_chat_room_settings', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ChatRoomMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('owner', 'Owner'), ('admin', 'Admin'), ('member', 'Member')], default='member', max_length=30)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('added_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='added_chat_room_members', to=settings.AUTH_USER_MODEL)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='core.chatroom')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_room_memberships', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='edited_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='reply_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='replies', to='core.chatmessage'),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='room',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='core.chatroom'),
        ),
        migrations.CreateModel(
            name='ChatMessageMention',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('mentioned_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_mentions', to=settings.AUTH_USER_MODEL)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentions', to='core.chatmessage')),
            ],
        ),
        migrations.CreateModel(
            name='ChatMessageReaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reaction', models.CharField(choices=[('thumbs_up', 'Thumbs Up'), ('heart', 'Heart'), ('laugh', 'Laugh'), ('party', 'Party'), ('fire', 'Fire'), ('clap', 'Clap')], max_length=30)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reactions', to='core.chatmessage')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_message_reactions', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ChatPinnedMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pin_entries', to='core.chatmessage')),
                ('pinned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pinned_chat_messages', to=settings.AUTH_USER_MODEL)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pinned_messages', to='core.chatroom')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='chatroom',
            index=models.Index(fields=['organization', 'is_deleted'], name='chatroom_org_deleted_idx'),
        ),
        migrations.AddIndex(
            model_name='chatroom',
            index=models.Index(fields=['room_id'], name='chatroom_roomid_idx'),
        ),
        migrations.AddIndex(
            model_name='chatroommember',
            index=models.Index(fields=['room', 'role'], name='chatroommem_room_role_idx'),
        ),
        migrations.AddIndex(
            model_name='chatroommember',
            index=models.Index(fields=['user', 'role'], name='chatroommem_user_role_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='chatroommember',
            unique_together={('room', 'user')},
        ),
        migrations.AddIndex(
            model_name='chatmessage',
            index=models.Index(fields=['room', 'created_at'], name='chatmsg_room_created_idx'),
        ),
        migrations.AddIndex(
            model_name='chatmessagemention',
            index=models.Index(fields=['mentioned_user', 'created_at'], name='chatmention_user_created_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='chatmessagemention',
            unique_together={('message', 'mentioned_user')},
        ),
        migrations.AddIndex(
            model_name='chatmessagereaction',
            index=models.Index(fields=['message', 'reaction'], name='chatreact_msg_react_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='chatmessagereaction',
            unique_together={('message', 'user', 'reaction')},
        ),
        migrations.AddIndex(
            model_name='chatpinnedmessage',
            index=models.Index(fields=['room', 'created_at'], name='chatpin_room_created_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='chatpinnedmessage',
            unique_together={('room', 'message')},
        ),
    ]
