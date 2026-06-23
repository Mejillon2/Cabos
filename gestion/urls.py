from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login_view'),
    path('logout/', views.logout_view, name='logout_view'),
    path('terapeutas/', views.lista_terapeutas, name='lista_terapeutas'),
    path('pacientes/', views.lista_pacientes, name='lista_pacientes'),
    path('caballos/', views.lista_caballos, name='lista_caballos'),
    path('caballos/editar/<int:id_caballo>/', views.editar_caballo, name='editar_caballo'),
    path('caballos/eliminar/<int:id_caballo>/', views.eliminar_caballo, name='eliminar_caballo'),
    path('padres/', views.lista_padres, name='lista_padres'),
    path('agendar/', views.agendar_cita, name='agendar'),
    path('reportes/', views.lista_reportes, name='reportes'),
]