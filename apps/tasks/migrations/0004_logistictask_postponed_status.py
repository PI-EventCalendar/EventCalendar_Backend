from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tasks", "0003_alter_logistictask_status")]

    operations = [
        migrations.AlterField(
            model_name="logistictask",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pendiente"),
                    ("in_progress", "En Progreso"),
                    ("completed", "Completada"),
                    ("postponed", "Pospuesta"),
                    ("cancelled", "Cancelada"),
                ],
                default="pending",
                max_length=20,
                verbose_name="estado",
            ),
        )
    ]
