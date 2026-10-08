from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0003_alter_event_options_event_activity_type_event_course_and_more")]
    operations = [migrations.AddField(
        model_name="event",
        name="location",
        field=models.CharField(default="", max_length=255, verbose_name="lugar"),
    )]
