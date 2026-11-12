from django.contrib import admin
from .models import Hotel, Usuario, TipoHabitacion, Habitacion, Huesped, Reserva, Servicio, ServicioReserva, Pago, Factura

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'correo')

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('nombres', 'apellidos', 'correo', 'rol', 'activo')

@admin.register(TipoHabitacion)
class TipoHabitacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'capacidad', 'precio_persona_noche')

@admin.register(Habitacion)
class HabitacionAdmin(admin.ModelAdmin):
    list_display = ('numero', 'piso', 'tipo', 'estado')

@admin.register(Huesped)
class HuespedAdmin(admin.ModelAdmin):
    list_display = ('numero_documento', 'nombres', 'apellidos', 'telefono')

@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ('id', 'huesped', 'habitacion', 'fecha_entrada', 'fecha_salida', 'estado')

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 
                    'precio')
    list_filter = ('categoria',)
    search_fields = ('nombre',) 
    ordering = ('categoria', 'nombre')

@admin.register(ServicioReserva)
class ServicioReservaAdmin(admin.ModelAdmin):
    list_display = ('reserva', 'servicio', 'cantidad', 'precio_unitario', 'subtotal')
    list_filter = ('servicio__categoria',)
    search_fields = ('reserva__id', 'servicio__nombre')
    readonly_fields = ('subtotal',)

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('reserva', 'monto', 'metodo_pago')

@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('numero_dian', 'reserva', 'total')
