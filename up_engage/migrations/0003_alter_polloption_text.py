from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("up_engage", "0002_event_qa_enabled"),
    ]

    operations = [
        migrations.AlterField(
            model_name="polloption",
            name="text",
            field=models.CharField(max_length=512),
        ),
    ]