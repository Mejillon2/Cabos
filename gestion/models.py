from django.db import models

class Persona(models.Model):
    id_persona = models.IntegerField(primary_key=True, db_column='ID_PERSONA')
    nombre = models.CharField(max_length=100, db_column='NOMBRE')
    rol = models.CharField(max_length=20, db_column='ROL')
    es_admin = models.IntegerField(db_column='ES_ADMIN')
    
class Meta:
    managed = False
    db_table = 'PERSONAS'
# Create your models here.
