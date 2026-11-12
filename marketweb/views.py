from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Q, Case, When, Value, IntegerField
from decimal import Decimal
from datetime import datetime, time, date, timedelta
from .models import Habitacion, Reserva, Huesped, Servicio, ServicioReserva, Pago, Factura, Usuario
from .decorators import requiere_rol



# ----------------------------------------------------
# 1. MÓDULO LOG IN (Iniciar Sesión)
# ----------------------------------------------------
def iniciar_sesion(request):
    if 'usuario_id' in request.session:
        return redirect('inicio')
    if request.method == 'POST':
        identificador = request.POST.get('identificador', '').strip()
        clave_input = request.POST.get('contrasena', '').strip()
        usuario = Usuario.objects.filter(
            Q(correo__iexact=identificador) | 
            Q(nombres__iexact=identificador),
            activo=True
        ).first()
        if usuario and (check_password(clave_input, usuario.contrasena) or usuario.contrasena == clave_input):
            if usuario.contrasena == clave_input:
                usuario.contrasena = make_password(clave_input)
                usuario.save()
            request.session['usuario_id'] = usuario.id
            request.session['usuario_nombre'] = f"{usuario.nombres} {usuario.apellidos}"
            request.session['usuario_rol'] = usuario.rol
            return redirect('inicio')
        else:
            messages.error(request, "Credenciales incorrectas.")
    return render(request, 'login.html')


# ----------------------------------------------------
# 2. MÓDULO LOG OUT (Cerrar Sesión)
# ----------------------------------------------------
def cerrar_sesion(request):
    # Limpia cualquier mensaje acumulado antes de cerrar sesión
    list(messages.get_messages(request)) 
    
    # Destruye la sesión
    request.session.flush()
    
    # Agrega el único mensaje que debe mostrarse en el login
    messages.info(request, "Has cerrado sesión correctamente.")
    return redirect('login')



# ----------------------------------------------------
# 3. MÓDULO INICIO (Panel del Recepcionista)
# ----------------------------------------------------
def inicio(request):
    if 'usuario_id' not in request.session:
        return redirect('login')

    # Orden personalizado: 1. DISPONIBLE, 2. OCUPADA, 3. EN_ASEO (y luego por piso/número)
    habitaciones = Habitacion.objects.annotate(
        orden_estado=Case(
            When(estado='DISPONIBLE', then=Value(1)),
            When(estado='OCUPADA', then=Value(2)),
            When(estado='EN_ASEO', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    ).order_by('orden_estado', 'piso', 'numero')

    # Vincular la reserva activa a cada habitación ocupada
    for hab in habitaciones:
        if hab.estado == 'OCUPADA':
            hab.reserva_activa = Reserva.objects.filter(
                habitacion=hab, 
                estado__in=['CONFIRMADA', 'CHECKIN']
            ).order_by('-id').first()

    contexto = {
        'habitaciones': habitaciones,
        'total_habitaciones': habitaciones.count(),
        'disponibles': habitaciones.filter(estado='DISPONIBLE').count(),
        'ocupadas': habitaciones.filter(estado='OCUPADA').count(),
        'en_aseo': habitaciones.filter(estado='EN_ASEO').count(),
        'usuario_nombre': request.session.get('usuario_nombre'),
        'usuario_rol': request.session.get('usuario_rol'),
    }
    return render(request, 'inicio.html', contexto)


# ----------------------------------------------------
# CONSULTA DE DISPONIBILIDAD (Filtrado exacto por huéspedes)
# ----------------------------------------------------
def consulta_disponibilidad(request):
    hoy = date.today()
    mañana = hoy + timedelta(days=1)

    # 1. Si no se especifican fechas en la URL, asignar HOY y MAÑANA por defecto
    f_entrada = request.GET.get('fecha_entrada') or hoy.strftime('%Y-%m-%d')
    f_salida = request.GET.get('fecha_salida') or mañana.strftime('%Y-%m-%d')
    num_huespedes = request.GET.get('num_huespedes', '1')

    # 2. Filtro base: Solo habitaciones en estado DISPONIBLE
    habitaciones_disponibles = Habitacion.objects.filter(estado='DISPONIBLE')

    # 3. Filtrar por capacidad exacta según el número de huéspedes
    if num_huespedes and num_huespedes.isdigit():
        num_huespedes_int = int(num_huespedes)
        habitaciones_disponibles = habitaciones_disponibles.filter(tipo__capacidad=num_huespedes_int)

    # 4. Filtrar traslape de fechas con reservas activas
    try:
        entrada = datetime.strptime(f_entrada, '%Y-%m-%d').date()
        salida = datetime.strptime(f_salida, '%Y-%m-%d').date() 

        reservas_solapadas = Reserva.objects.filter(
            estado__in=['CONFIRMADA', 'CHECKIN'],
            fecha_entrada__lt=salida,
            fecha_salida__gt=entrada
        ).values_list('habitacion_id', flat=True)

        habitaciones_disponibles = habitaciones_disponibles.exclude(id__in=reservas_solapadas)
    except ValueError:
        pass

    return render(request, 'disponibilidad.html', {
        'habitaciones': habitaciones_disponibles,
        'f_entrada': f_entrada,
        'f_salida': f_salida,
        'num_huespedes': num_huespedes
    })






# ----------------------------------------------------
# CREAR RESERVA (Con Cálculo Completo de Estancia)
# ----------------------------------------------------
def crear_reserva(request, habitacion_id):
    if 'usuario_id' not in request.session:
        return redirect('login')

    habitacion = get_object_or_404(Habitacion, pk=habitacion_id)
    hoy = date.today()

    # 1. Obtener fechas y número de huéspedes enviados por GET o POST
    f_entrada = request.GET.get('fecha_entrada') or request.POST.get('fecha_entrada')
    f_salida = request.GET.get('fecha_salida') or request.POST.get('fecha_salida')
    num_huespedes_raw = request.GET.get('num_huespedes') or request.POST.get('num_huespedes', '1')

    # Protección de seguridad si las fechas vienen vacías
    if not f_entrada or f_entrada == 'None':
        f_entrada = hoy.strftime('%Y-%m-%d')
    if not f_salida or f_salida == 'None':
        f_salida = (hoy + timedelta(days=1)).strftime('%Y-%m-%d')

    try:
        num_huespedes = int(num_huespedes_raw)
    except (ValueError, TypeError):
        num_huespedes = 1

    # 2. Calcular la cantidad de noches reales
    try:
        d_entrada = datetime.strptime(f_entrada, '%Y-%m-%d').date()
        d_salida = datetime.strptime(f_salida, '%Y-%m-%d').date()
        cant_noches = (d_salida - d_entrada).days
        if cant_noches <= 0:
            cant_noches = 1
    except ValueError:
        cant_noches = 1

    # 3. Calcular Total Estancia (Noches * Huéspedes * Tarifa Persona/Noche)
    tarifa_persona = habitacion.tipo.precio_persona_noche
    total_estancia = Decimal(cant_noches) * Decimal(num_huespedes) * tarifa_persona

    if request.method == 'POST':
        tipo_doc = request.POST.get('tipo_documento')
        num_doc = request.POST.get('numero_documento', '').strip()
        nombres = request.POST.get('nombres', '').strip()
        apellidos = request.POST.get('apellidos', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        correo = request.POST.get('correo', '').strip()
        nacionalidad = request.POST.get('nacionalidad', 'Colombiana').strip()
        es_extranjero = request.POST.get('es_extranjero') == 'on'
        num_huespedes_post = int(request.POST.get('num_huespedes', 1))
        canal = request.POST.get('canal_reserva', 'PRESENCIAL')

        # Guardar / Actualizar Huésped
        huesped, _ = Huesped.objects.update_or_create(
            numero_documento=num_doc,
            defaults={
                'tipo_documento': tipo_doc,
                'nombres': nombres,
                'apellidos': apellidos,
                'telefono': telefono,
                'correo': correo,
                'nacionalidad': nacionalidad,
                'es_extranjero': es_extranjero
            }
        )

        entrada = datetime.strptime(f_entrada, '%Y-%m-%d').date()
        salida = datetime.strptime(f_salida, '%Y-%m-%d').date()

        reserva = Reserva(
            huesped=huesped,
            habitacion=habitacion,
            fecha_entrada=entrada,
            fecha_salida=salida,
            num_huespedes=num_huespedes_post,
            canal_reserva=canal,
            estado='CONFIRMADA'
        )
        reserva.valor_total = reserva.calcular_alojamiento()
        reserva.save()

        habitacion.estado = 'OCUPADA'
        habitacion.save()

        messages.success(request, f"¡Reserva #{reserva.id} creada exitosamente!")
        return redirect('inicio')

    contexto = {
        'habitacion': habitacion,
        'f_entrada': f_entrada,
        'f_salida': f_salida,
        'num_huespedes': num_huespedes,
        'cant_noches': cant_noches,
        'total_estancia': total_estancia
    }
    return render(request, 'crear_reserva.html', contexto)



# ----------------------------------------------------
# REGISTRO Y PROCESAMIENTO DE CHECK-IN COMPLETO
# ----------------------------------------------------
def registrar_checkin(request, reserva_id):
    if 'usuario_id' not in request.session:
        return redirect('login')

    reserva = get_object_or_404(Reserva, pk=reserva_id)
    huesped = reserva.huesped

    # Solo se puede hacer check-in si la reserva está en estado CONFIRMADA
    if reserva.estado != 'CONFIRMADA':
        messages.warning(request, f"La reserva #{reserva.id} no está en estado 'CONFIRMADA'.")
        return redirect('listar_reservas')

    if request.method == 'POST':
        # 1. Actualizar y verificar datos del huésped principal
        huesped.tipo_documento = request.POST.get('tipo_documento')
        huesped.numero_documento = request.POST.get('numero_documento', '').strip()
        huesped.nombres = request.POST.get('nombres', '').strip()
        huesped.apellidos = request.POST.get('apellidos', '').strip()
        huesped.telefono = request.POST.get('telefono', '').strip()
        huesped.correo = request.POST.get('correo', '').strip()
        huesped.nacionalidad = request.POST.get('nacionalidad', 'Colombiana').strip()
        
        # Marcado clave para exención de IVA en facturación DIAN
        huesped.es_extranjero = request.POST.get('es_extranjero') == 'on'
        huesped.save()

        # 2. Actualizar acompañantes/huéspedes reales y recalcular tarifa total
        num_huespedes = request.POST.get('num_huespedes')
        if num_huespedes and num_huespedes.isdigit():
            reserva.num_huespedes = int(num_huespedes)
            reserva.valor_total = reserva.calcular_alojamiento()

        # 3. Registrar abono o anticipo inicial (se remueve 'concepto' no existente)
        monto_anticipo = request.POST.get('monto_anticipo', '0').strip()
        metodo_pago = request.POST.get('metodo_pago', 'EFECTIVO')
        
        if monto_anticipo and Decimal(monto_anticipo) > 0:
            Pago.objects.create(
                reserva=reserva,
                monto=Decimal(monto_anticipo),
                metodo_pago=metodo_pago
            )

        # 4. Transición formal de estados
        reserva.estado = 'CHECKIN'
        reserva.save()

        habitacion = reserva.habitacion
        habitacion.estado = 'OCUPADA'
        habitacion.save()

        messages.success(request, f"Check-in completado exitosamente para la reserva #{reserva.id}. Habitación {habitacion.numero} ahora en casa (OCUPADA).")
        return redirect('inicio')

    # Ajustado a 'checkin/form_checkin.html' (asegúrate de renombrar la carpeta en VS Code a 'checkin')
    return render(request, 'checkin/form_checkin.html', {
        'reserva': reserva,
        'huesped': huesped,
        'habitacion': reserva.habitacion
    })










# ----------------------------------------------------
# CAMBIAR ESTADO DE HABITACIÓN (Liberar de Aseo)
# ----------------------------------------------------
def cambiar_estado_habitacion(request, habitacion_id):
    if 'usuario_id' not in request.session:
        return redirect('login')

    habitacion = get_object_or_404(Habitacion, pk=habitacion_id)
    
    # Si la habitación está en aseo, la cambiamos a disponible
    if habitacion.estado == 'EN_ASEO':
        habitacion.estado = 'DISPONIBLE'
        habitacion.save()  # Asigna automáticamente el color blanco (#FFFFFF)
        messages.success(request, f"La Habitación {habitacion.numero} ha sido aseada y ahora está DISPONIBLE.")
    else:
        messages.warning(request, f"La Habitación {habitacion.numero} no está en estado 'En Aseo'.")

    return redirect('inicio')


# ----------------------------------------------------
# PROCESAMIENTO Y REGISTRO DE CHECK-OUT COMPLETO
# ----------------------------------------------------
def registrar_checkout(request, reserva_id):
    if 'usuario_id' not in request.session:
        return redirect('login')

    reserva = get_object_or_404(Reserva, pk=reserva_id)

    # Solo se puede hacer check-out si el huésped está en casa (CHECKIN)
    if reserva.estado != 'CHECKIN':
        messages.warning(request, f"La reserva #{reserva.id} no se encuentra en estado 'CHECKIN'.")
        return redirect('listar_reservas')

    servicios = ServicioReserva.objects.filter(reserva=reserva)
    pagos = Pago.objects.filter(reserva=reserva)

    total_servicios = sum(s.subtotal for s in servicios)
    total_pagos = sum(p.monto for p in pagos)
    total_alojamiento = reserva.calcular_alojamiento()

    # Cálculo automático del cargo tardío de salida (Late Check-out)
    hora_actual = datetime.now().time()
    cargo_tardio = Decimal('0.00')

    if hora_actual > time(12, 0) and hora_actual <= time(12, 30):
        cargo_tardio = Decimal('30000.00')
    elif hora_actual > time(12, 30) and hora_actual <= time(13, 0):
        cargo_tardio = Decimal('60000.00')
    elif hora_actual > time(13, 0):
        cargo_tardio = Decimal('160650.00') * Decimal(reserva.num_huespedes)

    reserva.cargo_tardio = cargo_tardio
    reserva.valor_total = total_alojamiento + total_servicios + cargo_tardio
    reserva.save()

    saldo_pendiente = reserva.valor_total - total_pagos

    if request.method == 'POST':
        # 1. Registrar pago del saldo pendiente si se ingresó monto
        monto_pago = request.POST.get('monto_pago', '0').strip()
        metodo_pago = request.POST.get('metodo_pago', 'EFECTIVO')

        if monto_pago and Decimal(monto_pago) > 0:
            Pago.objects.create(
                reserva=reserva,
                monto=Decimal(monto_pago),
                metodo_pago=metodo_pago
            )

        # 2. Transición del estado de la Reserva
        reserva.estado = 'CHECKOUT'
        reserva.save()

        # 3. Transición del estado de la Habitación a EN_ASEO
        habitacion = reserva.habitacion
        habitacion.estado = 'EN_ASEO'
        habitacion.save()

        messages.success(request, f"Check-out completado. La Habitación {habitacion.numero} ha pasado a estado EN ASEO.")
        
        # Redirigir a la vista de Factura DIAN
        return redirect('factura_dian', reserva_id=reserva.id)

    return render(request, 'checkout.html', {
        'reserva': reserva,
        'servicios': servicios,
        'pagos': pagos,
        'total_alojamiento': total_alojamiento,
        'total_servicios': total_servicios,
        'cargo_tardio': cargo_tardio,
        'total_general': reserva.valor_total,
        'total_pagos': total_pagos,
        'saldo_pendiente': max(Decimal('0.00'), saldo_pendiente)
    })




# --------------------------------------------------
# LISTADO GENERAL DE RESERVAS (Filtros Check-in / Check-out)
# ----------------------------------------------------
def listar_reservas(request):
    if 'usuario_id' not in request.session:
        return redirect('login')

    estado_filtro = request.GET.get('estado', '')
    busqueda = request.GET.get('q', '').strip()

    reservas = Reserva.objects.all().select_related('huesped', 'habitacion').order_by('-id')

    if estado_filtro:
        reservas = reservas.filter(estado=estado_filtro)

    if busqueda:
        reservas = reservas.filter(
            Q(huesped__nombres__icontains=busqueda) |
            Q(huesped__apellidos__icontains=busqueda) |
            Q(huesped__numero_documento__icontains=busqueda) |
            Q(habitacion__numero__icontains=busqueda)
        )

    return render(request, 'reservas.html', {
        'reservas': reservas,
        'estado_filtro': estado_filtro,
        'busqueda': busqueda
    })





# -
# ---------------------------------------------------
# DIRECTORIO DE HUÉSPEDES
# ----------------------------------------------------
def listar_huespedes(request):
    if 'usuario_id' not in request.session:
        return redirect('login')

    busqueda = request.GET.get('q', '').strip()
    huespedes = Huesped.objects.all().order_by('apellidos', 'nombres')

    if busqueda:
        huespedes = huespedes.filter(
            Q(nombres__icontains=busqueda) |
            Q(apellidos__icontains=busqueda) |
            Q(numero_documento__icontains=busqueda) |
            Q(correo__icontains=busqueda)
        )

    return render(request, 'huespedes.html', {
        'huespedes': huespedes,
        'busqueda': busqueda
    })






def generar_factura_dian(request, reserva_id):
    reserva = get_object_or_404(Reserva, pk=reserva_id)
    huesped = reserva.huesped

    # Lógica de IVA
    exento = huesped.es_extranjero
    subtotal = reserva.valor_total / Decimal('1.19') if not exento else reserva.valor_total
    iva = reserva.valor_total - subtotal if not exento else Decimal('0.00')

    num_dian_generado = f"SETT-{reserva.id:06d}"

    factura, created = Factura.objects.get_or_create(
        reserva=reserva,
        defaults={
            'numero_dian': num_dian_generado,
            'subtotal': subtotal,
            'iva': iva,
            'total': reserva.valor_total,
            'exento_iva': exento
        }
    )

    return render(request, 'marketweb/factura.html', {'factura': factura, 'reserva': reserva})

# ----------------------------------------------------
# MÓDULO HUÉSPEDES (CRUD COMPLETO)
# ----------------------------------------------------

def crear_huesped(request):
    if 'usuario_id' not in request.session:
        return redirect('login')

    if request.method == 'POST':
        num_doc = request.POST.get('numero_documento', '').strip()
        
        # Verificar si el documento ya existe
        if Huesped.objects.filter(numero_documento=num_doc).exists():
            messages.error(request, f"Ya existe un huésped registrado con el documento N° {num_doc}.")
            return render(request, 'form_huesped.html', {'huesped': request.POST})

        Huesped.objects.create(
            tipo_documento=request.POST.get('tipo_documento'),
            numero_documento=num_doc,
            nombres=request.POST.get('nombres', '').strip(),
            apellidos=request.POST.get('apellidos', '').strip(),
            telefono=request.POST.get('telefono', '').strip(),
            correo=request.POST.get('correo', '').strip(),
            nacionalidad=request.POST.get('nacionalidad', 'Colombiana').strip(),
            es_extranjero=request.POST.get('es_extranjero') == 'on'
        )
        messages.success(request, "Huésped registrado correctamente.")
        return redirect('listar_huespedes')

    return render(request, 'form_huesped.html')


def editar_huesped(request, huesped_id):
    if 'usuario_id' not in request.session:
        return redirect('login')

    huesped = get_object_or_404(Huesped, pk=huesped_id)

    if request.method == 'POST':
        num_doc = request.POST.get('numero_documento', '').strip()
        
        # Validar duplicados si cambia de documento
        if Huesped.objects.filter(numero_documento=num_doc).exclude(id=huesped.id).exists():
            messages.error(request, f"El documento N° {num_doc} pertenece a otro huésped.")
            return render(request, 'form_huesped.html', {'huesped': huesped})

        huesped.tipo_documento = request.POST.get('tipo_documento')
        huesped.numero_documento = num_doc
        huesped.nombres = request.POST.get('nombres', '').strip()
        huesped.apellidos = request.POST.get('apellidos', '').strip()
        huesped.telefono = request.POST.get('telefono', '').strip()
        huesped.correo = request.POST.get('correo', '').strip()
        huesped.nacionalidad = request.POST.get('nacionalidad', 'Colombiana').strip()
        huesped.es_extranjero = request.POST.get('es_extranjero') == 'on'
        huesped.save()

        messages.success(request, f"Información del huésped {huesped.nombres} actualizada exitosamente.")
        return redirect('listar_huespedes')

    return render(request, 'form_huesped.html', {'huesped': huesped})


def detalle_huesped(request, huesped_id):
    if 'usuario_id' not in request.session:
        return redirect('login')

    huesped = get_object_or_404(Huesped, pk=huesped_id)
    reservas = Reserva.objects.filter(huesped=huesped).select_related('habitacion').order_by('-id')

    return render(request, 'detalle_huesped.html', {
        'huesped': huesped,
        'reservas': reservas
    })


def agregar_servicio_reserva(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    
    if request.method == 'POST':
        servicio_id = request.POST.get('servicio_id')
        cantidad = int(request.POST.get('cantidad', 1))
        
        if servicio_id and cantidad > 0:
            servicio = get_object_or_404(Servicio, id=servicio_id)
            
            # Crea el registro del consumo asociado a la reserva
            ServicioReserva.objects.create(
                reserva=reserva,
                servicio=servicio,
                cantidad=cantidad,
                precio_unitario=servicio.precio # Toma el precio actual del catálogo
            )
            messages.success(request, f"Se agregó {cantidad}x {servicio.nombre} a la reserva #{reserva.id}.")
        else:
            messages.error(request, "Por favor selecciona un servicio y una cantidad válida.")
            
        # Redirige de vuelta a la página de inicio
        return redirect('inicio')

    # Si es GET, pasamos la lista de servicios disponibles al template
    servicios_disponibles = Servicio.objects.all().order_by('categoria', 'nombre')
    return render(request, 'reservas/agregar_servicio.html', {
        'reserva': reserva,
        'servicios': servicios_disponibles

        
    })













# ----------------------------------------------------
# MÓDULO DE USUARIOS, ROLES Y PERMISOS (CRUD COMPLETO)
# ----------------------------------------------------

@requiere_rol('ADMIN_GERENTE')
def listar_usuarios(request):
    busqueda = request.GET.get('q', '').strip()
    usuarios = Usuario.objects.all().order_by('-activo', 'apellidos')

    if busqueda:
        usuarios = usuarios.filter(
            Q(nombres__icontains=busqueda) |
            Q(apellidos__icontains=busqueda) |
            Q(correo__icontains=busqueda) |
            Q(rol__icontains=busqueda)
        )

    return render(request, 'usuarios.html', {
        'usuarios': usuarios,
        'busqueda': busqueda
    })


@requiere_rol('ADMIN_GERENTE')
def crear_usuario(request):
    if request.method == 'POST':
        correo = request.POST.get('correo', '').strip().lower()
        
        if Usuario.objects.filter(correo__iexact=correo).exists():
            messages.error(request, f"El correo {correo} ya se encuentra registrado.")
            return render(request, 'form_usuario.html', {'datos': request.POST})

        clave_plana = request.POST.get('contrasena', '').strip()
        
        Usuario.objects.create(
            nombres=request.POST.get('nombres', '').strip(),
            apellidos=request.POST.get('apellidos', '').strip(),
            correo=correo,
            contrasena=make_password(clave_plana),
            rol=request.POST.get('rol', 'RECEPCIONISTA'),
            activo=request.POST.get('activo') == 'on'
        )
        messages.success(request, "Usuario y credenciales creados exitosamente.")
        return redirect('listar_usuarios')

    return render(request, 'form_usuario.html')


@requiere_rol('ADMIN_GERENTE')
def editar_usuario(request, usuario_id):
    usuario_item = get_object_or_404(Usuario, pk=usuario_id)

    if request.method == 'POST':
        correo = request.POST.get('correo', '').strip().lower()
        
        if Usuario.objects.filter(correo__iexact=correo).exclude(id=usuario_item.id).exists():
            messages.error(request, f"El correo {correo} ya está asignado a otro usuario.")
            return render(request, 'form_usuario.html', {'usuario_item': usuario_item})

        usuario_item.nombres = request.POST.get('nombres', '').strip()
        usuario_item.apellidos = request.POST.get('apellidos', '').strip()
        usuario_item.correo = correo
        usuario_item.rol = request.POST.get('rol', 'RECEPCIONISTA')
        usuario_item.activo = request.POST.get('activo') == 'on'

        nueva_clave = request.POST.get('contrasena', '').strip()
        if nueva_clave:
            usuario_item.contrasena = make_password(nueva_clave)

        usuario_item.save()
        messages.success(request, f"Usuario {usuario_item.nombres} actualizado correctamente.")
        return redirect('listar_usuarios')

    return render(request, 'form_usuario.html', {'usuario_item': usuario_item})


@requiere_rol('ADMIN_GERENTE')
def cambiar_estado_usuario(request, usuario_id):
    usuario_item = get_object_or_404(Usuario, pk=usuario_id)
    
    # Evitar deshabilitarse a sí mismo
    if usuario_item.id == request.session.get('usuario_id'):
        messages.error(request, "No puedes desactivar tu propia cuenta mientras estás en sesión.")
        return redirect('listar_usuarios')

    usuario_item.activo = not usuario_item.activo
    usuario_item.save()
    
    estado_txt = "activado" if usuario_item.activo else "desactivado"
    messages.info(request, f"El usuario {usuario_item.nombres} ha sido {estado_txt}.")
    return redirect('listar_usuarios')