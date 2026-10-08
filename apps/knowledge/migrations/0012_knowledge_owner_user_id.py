from django.db import migrations, models


class Migration(migrations.Migration):
    """矩阵租户：Knowledge 增加属主维度（workspace=产品 × owner_user_id=用户）"""

    dependencies = [
        ("knowledge", "0011_knowledgeworkflow_default_model_setting_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="knowledge",
            name="owner_user_id",
            field=models.CharField(db_index=True, default="", max_length=128, verbose_name="属主外部用户ID"),
        ),
        migrations.AddIndex(
            model_name="knowledge",
            index=models.Index(fields=["workspace_id", "owner_user_id"], name="knowledge_ws_owner_idx"),
        ),
    ]
