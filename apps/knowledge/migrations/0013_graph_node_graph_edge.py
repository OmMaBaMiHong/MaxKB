from django.db import migrations, models
import django.db.models.deletion
import uuid_utils.compat as uuid


class Migration(migrations.Migration):
    """M3：知识图谱 PG 邻接表（GraphNode/GraphEdge，矩阵租户隔离）"""

    dependencies = [
        ("knowledge", "0012_knowledge_owner_user_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="GraphNode",
            fields=[
                ("create_time", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="修改时间")),
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False, verbose_name="主键id")),
                ("workspace_id", models.CharField(db_index=True, default="default", max_length=64, verbose_name="产品id")),
                ("name", models.CharField(db_index=True, max_length=150, verbose_name="实体名")),
                ("type", models.CharField(db_index=True, default="概念", max_length=32, verbose_name="实体类型")),
                ("description", models.CharField(default="", max_length=2048, verbose_name="实体描述")),
                ("mention_count", models.IntegerField(default=0, verbose_name="提及次数")),
                ("source_paragraph_ids", models.JSONField(default=list, verbose_name="证据段落id")),
                ("knowledge", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, to="knowledge.knowledge", verbose_name="知识库")),
            ],
            options={
                "db_table": "graph_node",
            },
        ),
        migrations.CreateModel(
            name="GraphEdge",
            fields=[
                ("create_time", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="修改时间")),
                ("id", models.UUIDField(default=uuid.uuid7, editable=False, primary_key=True, serialize=False, verbose_name="主键id")),
                ("workspace_id", models.CharField(db_index=True, default="default", max_length=64, verbose_name="产品id")),
                ("relation", models.CharField(default="相关", max_length=64, verbose_name="关系类型")),
                ("description", models.CharField(default="", max_length=2048, verbose_name="关系描述")),
                ("source_paragraph_ids", models.JSONField(default=list, verbose_name="证据段落id")),
                ("knowledge", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, to="knowledge.knowledge", verbose_name="知识库")),
                ("source_node", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name="out_edges", to="knowledge.graphnode", verbose_name="源节点")),
                ("target_node", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name="in_edges", to="knowledge.graphnode", verbose_name="目标节点")),
            ],
            options={
                "db_table": "graph_edge",
            },
        ),
        migrations.AlterUniqueTogether(
            name="graphnode",
            unique_together={("knowledge", "name")},
        ),
        migrations.AlterUniqueTogether(
            name="graphedge",
            unique_together={("knowledge", "source_node", "target_node", "relation")},
        ),
        migrations.AddIndex(
            model_name="graphnode",
            index=models.Index(fields=["workspace_id", "type"], name="graph_node_ws_type_idx"),
        ),
        migrations.AddIndex(
            model_name="graphedge",
            index=models.Index(fields=["workspace_id", "relation"], name="graph_edge_ws_rel_idx"),
        ),
    ]
