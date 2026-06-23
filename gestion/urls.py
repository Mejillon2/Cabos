from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login_view'),
    path('logout/', views.logout_view, name='logout_view'),
    path('terapeutas/', views.lista_terapeutas, name='lista_terapeutas'),
    path('terapeutas/editar/<int:id_persona>/', views.editar_terapeuta, name='editar_terapeuta'),
    path('terapeutas/eliminar/<int:id_persona>/', views.eliminar_terapeuta, name='eliminar_terapeuta'),
    path('pacientes/', views.lista_pacientes, name='lista_pacientes'),
    path('pacientes/editar/<int:id_persona>/', views.editar_paciente, name='editar_paciente'),
    path('pacientes/eliminar/<int:id_persona>/', views.eliminar_paciente, name='eliminar_paciente'),
    path('caballos/', views.lista_caballos, name='lista_caballos'),
    path('caballos/editar/<int:id_caballo>/', views.editar_caballo, name='editar_caballo'),
    path('caballos/eliminar/<int:id_caballo>/', views.eliminar_caballo, name='eliminar_caballo'),
    path('padres/', views.lista_padres, name='lista_padres'),
    path('padres/editar/<int:id_persona>/', views.editar_padres, name='editar_padres'),
    path('padres/eliminar/<int:id_persona>/', views.eliminar_padres, name='eliminar_padres'),
    path('agendar/', views.agendar_cita, name='agendar'),
    path('sesiones/editar/<int:id_sesion>/', views.editar_cita, name='editar_cita'),
    path('sesiones/eliminar/<int:id_sesion>/', views.eliminar_cita, name='eliminar_cita'),
    path('reportes/', views.lista_reportes, name='reportes'),
]