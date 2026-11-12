from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def requiere_rol(*roles_permitidos):
    """
    Decorador para restringir el acceso a vistas según el rol del usuario en sesión.
    Ejemplo: @requiere_rol('ADMIN_GERENTE')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if 'usuario_id' not in request.session:
                messages.warning(request, "Debes iniciar sesión para acceder.")
                return redirect('login')
            
            rol_actual = request.session.get('usuario_rol')
            if rol_actual not in roles_permitidos:
                messages.error(request, "No tienes permisos suficientes para acceder a esta sección.")
                return redirect('inicio')
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator