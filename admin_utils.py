from functools import wraps
from flask import session, redirect, url_for, flash

def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if 'logueado' in session and session.get('id_rol') == 1:
            # El usuario está autenticado como administrador
            return view_func(*args, **kwargs)
        else:
            flash('Acceso denegado. Debes iniciar sesión como administrador.', 'error')
            return redirect(url_for('login'))
    return wrapped

