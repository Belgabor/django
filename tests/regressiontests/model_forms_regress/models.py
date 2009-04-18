import os
from django.db import models

class Person(models.Model):
    name = models.CharField(max_length=100)

class Triple(models.Model):
    left = models.IntegerField()
    middle = models.IntegerField()
    right = models.IntegerField()

    class Meta:
        unique_together = (('left', 'middle'), ('middle', 'right'))

class FilePathModel(models.Model):
    path = models.FilePathField(path=os.path.dirname(__file__), match=".*\.py$", blank=True)
