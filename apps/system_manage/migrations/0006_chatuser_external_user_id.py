from django.db import migrations, models


class Migration(migrations.Migration):
    """矩阵租户：ChatUser 关联外部统一用户ID（sub2api，同源贯穿所有产品）"""

    dependencies = [
        ("system_manage", "0005_resourcemapping"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatuser",
            name="external_user_id",
            field=models.CharField(blank=True, max_length=128, null=True, unique=True, verbose_name="外部统一用户ID"),
        ),
    ]
