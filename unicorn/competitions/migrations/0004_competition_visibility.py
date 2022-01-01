# Generated by Django 3.2.9 on 2022-01-01 15:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0003_alter_genre_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='competition',
            name='visibility',
            field=models.CharField(choices=[('public', 'Public'), ('crew', 'Crew'), ('hidden', 'Hidden')], default='public', max_length=16, verbose_name='Visibility'),
        ),
    ]
