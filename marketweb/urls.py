from django.contrib import admin
from django.urls import path
from marketweb import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.iniciar_sesion, name='login'),
    path('logout/', views.cerrar_sesion, name='logout'),
    path('', views.inicio, name='inicio'),
    
    path('disponibilidad/', views.consulta_disponibilidad, name='disponibilidad'),
    path('reserva/crear/<int:habitacion_id>/', views.crear_reserva, name='crear_reserva'),
    
    # Rutas para el bloque Operaciones Rápidas
    path('reservas/', views.listar_reservas, name='listar_reservas'),
    path('huespedes/', views.listar_huespedes, name='listar_huespedes'),
    
    # Procesos individuales
    path('checkin/<int:reserva_id>/', views.registrar_checkin, name='checkin'),
    path('checkout/<int:reserva_id>/', views.registrar_checkout, name='checkout'),
    path('habitacion/liberar/<int:habitacion_id>/', views.cambiar_estado_habitacion, name='liberar_habitacion'),

    # Módulo CRUD Huéspedes
    path('huespedes/', views.listar_huespedes, name='listar_huespedes'),
    path('huesped/crear/', views.crear_huesped, name='crear_huesped'),
    path('huesped/editar/<int:huesped_id>/', views.editar_huesped, name='editar_huesped'),
    path('huesped/detalle/<int:huesped_id>/', views.detalle_huesped, name='detalle_huesped'),
    # ... tus otras urls ...
    path('reservas/<int:reserva_id>/agregar_servicio/', views.agregar_servicio_reserva, name='agregar_servicio_reserva'),

    path('usuarios/', views.listar_usuarios, name='listar_usuarios'),
    path('usuarios/crear/', views.crear_usuario, name='crear_usuario'),
    path('usuarios/editar/<int:usuario_id>/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/estado/<int:usuario_id>/', views.cambiar_estado_usuario, name='cambiar_estado_usuario'),

    
]