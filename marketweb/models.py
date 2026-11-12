from django.db import models
from decimal import Decimal
from datetime import datetime, time, date

# 1. Tabla: hotel
class Hotel(models.Model):
    nombre = models.CharField(max_length=100, default="Hotel Walena S.A.S.")
    direccion = models.CharField(max_length=200, default="Calle 15 # 14B - 205, Riohacha, La Guajira")
    telefono = models.CharField(max_length=20, default="+57 312 833 5638")
    correo = models.EmailField(default="reservashotelwalena@gmail.com")
    horario_checkin = models.TimeField(default="14:00")
    horario_checkout = models.TimeField(default="12:00")

    class Meta:
        db_table = 'hotel'

    def __str__(self):
        return self.nombre


# 2. Tabla: usuario
class Usuario(models.Model):
    ROLES = [
        ('ADMIN_GERENTE', 'Admin-Gerente'),
        ('RECEPCIONISTA', 'Recepcionista'),
        ('CLIENTE', 'Cliente'),
    ]
    nombres = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=80)
    correo = models.EmailField(unique=True)
    contrasena = models.CharField(max_length=255)
    rol = models.CharField(max_length=20, choices=ROLES, default='RECEPCIONISTA')
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return f"{self.nombres} {self.apellidos} ({self.rol})"


# 3. Tabla: tipo_habitacion
class TipoHabitacion(models.Model):
    nombre = models.CharField(max_length=50) # Suite Sencilla, Doble, Triple, Cuádruple
    capacidad = models.IntegerField(default=4)
    precio_persona_noche = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('160650.00'))
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'tipo_habitacion'

    def __str__(self):
        return f"{self.nombre} (Capacidad: {self.capacidad} personas)"


# 4. Tabla: habitacion
class Habitacion(models.Model):
    ESTADOS = [
        ('DISPONIBLE', 'Disponible'),
        ('OCUPADA', 'Ocupada'),
        ('EN_ASEO', 'En Aseo / Mantenimiento'),
    ]
    numero = models.CharField(max_length=10, unique=True)
    piso = models.IntegerField(default=1)
    tipo = models.ForeignKey(TipoHabitacion, on_delete=models.CASCADE, related_name='habitaciones')
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='habitaciones')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='DISPONIBLE')
    codigo_color = models.CharField(max_length=10, default='#FFFFFF') # Blanco (#FFFFFF), Azul (#1E88E5), Anaranjado (#FFB74D)

    class Meta:
        db_table = 'habitacion'

    def save(self, *args, **kwargs):
        # Asignación automática de códigos de color institucionales
        if self.estado == 'DISPONIBLE':
            self.codigo_color = '#FFFFFF'
        elif self.estado == 'OCUPADA':
            self.codigo_color = '#1E88E5'
        elif self.estado == 'EN_ASEO':
            self.codigo_color = '#FFB74D'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Habitación {self.numero} (Piso {self.piso})"


# 5. Tabla: huesped
class Huesped(models.Model):
    TIPOS_DOC = [
        ('CC', 'Cédula de Ciudadanía'),
        ('CE', 'Cédula de Extranjería'),
        ('PASAPORTE', 'Pasaporte'),
        ('TI', 'Tarjeta de Identidad'),
    ]
    tipo_documento = models.CharField(max_length=20, choices=TIPOS_DOC, default='CC')
    numero_documento = models.CharField(max_length=30, unique=True)
    nombres = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=80)
    telefono = models.CharField(max_length=20)
    correo = models.EmailField()
    nacionalidad = models.CharField(max_length=50, default='Colombiana')
    es_extranjero = models.BooleanField(default=False)

    class Meta:
        db_table = 'huesped'

    def __str__(self):
        return f"{self.nombres} {self.apellidos} - {self.numero_documento}"


# 6. Tabla: reserva
class Reserva(models.Model):
    ESTADOS_RESERVA = [
        ('PENDIENTE', 'Pendiente Pago'),
        ('CONFIRMADA', 'Confirmada'),
        ('CHECKIN', 'Huésped en Casa'),
        ('CHECKOUT', 'Completada / Check-out'),
        ('CANCELADA', 'Cancelada'),
    ]
    CANALES = [
        ('DIRECTA', 'Directa / WhatsApp'),
        ('WEB', 'Sitio Web Walena'),
        ('BOOKING', 'Booking.com'),
        ('EXPEDIA', 'Expedia'),
        ('PRESENCIAL', 'Presencial'),
    ]
    huesped = models.ForeignKey(Huesped, on_delete=models.PROTECT, related_name='reservas')
    habitacion = models.ForeignKey(Habitacion, on_delete=models.PROTECT, related_name='reservas')
    fecha_entrada = models.DateField()
    fecha_salida = models.DateField()
    num_huespedes = models.IntegerField(default=1)
    canal_reserva = models.CharField(max_length=20, choices=CANALES, default='PRESENCIAL')
    estado = models.CharField(max_length=20, choices=ESTADOS_RESERVA, default='PENDIENTE')
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    cargo_tardio = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reserva'

    def calcular_noches(self):
        noches = (self.fecha_salida - self.fecha_entrada).days
        return noches if noches > 0 else 1

    def calcular_alojamiento(self):
        # Regla: $160.650 por persona por noche
        tarifa_persona = Decimal('160650.00')
        return Decimal(self.calcular_noches()) * Decimal(self.num_huespedes) * tarifa_persona

    def __str__(self): 
        return f"Reserva #{self.id} - Hab: {self.habitacion.numero} ({self.huesped.nombres})"


# 7. Tabla: servicio (Catálogo de minibar y lavandería)
class Servicio(models.Model):
    CATEGORIAS = [
        ('LAVANDERIA', 'Servicio de Lavandería'),
        ('MINIBAR', 'Consumo de Minibar'),
    ]
    nombre = models.CharField(max_length=100)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='MINIBAR')
    precio = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'servicio'

    def __str__(self):
        return f"{self.nombre} (${self.precio})"


# 8. Tabla: servicio_reserva
class ServicioReserva(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='servicios')
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(self.cantidad) * Decimal(self.precio_unitario)
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'servicio_reserva'


# 9. Tabla: pago
class Pago(models.Model):
    METODOS = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('DATAFONO', 'Datáfono'),
        ('LINK_PAGO', 'Link de Pago'),
    ]
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='pagos')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODOS)
    fecha_pago = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pago'


# 10. Tabla: factura (Ajustado exactamente al Diccionario de Datos del Documento de Diseño)
class Factura(models.Model):
    reserva = models.OneToOneField(Reserva, on_delete=models.CASCADE, related_name='factura')
    numero_dian = models.CharField(max_length=30, null=True, blank=True)
    fecha_emision = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    exento_iva = models.BooleanField(default=False) # Exención para huéspedes extranjeros (RN17)

    class Meta:
        db_table = 'factura'

    def __str__(self):
        return f"Factura DIAN {self.numero_dian} - Reserva #{self.reserva.id}"