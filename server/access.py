import jwt
from flask import redirect, session, url_for, flash, current_app,request,jsonify
from functools import wraps
from utils.models import User

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = session.get('token')
        if not token:
            flash("Session expired : Login is necessary", category="error")
            if request.method not in ['GET','POST']:
                return jsonify({'redirect':'/login'})
            return redirect(url_for('auth.login'))
        try:
            data = jwt.decode(token, current_app.config.get('SECRET_KEY'), 'HS256')
            current_user = User.query.filter_by(name=data['name']).first()
        except jwt.InvalidTokenError:
            flash("Session expired : Login is necessary", category="error")
            if request.method not in ['GET','POST']:
                return jsonify({'redirect':'/login'})
            return redirect(url_for('auth.login'))

        return f(current_user, *args, **kwargs)
    return decorated

#In order to correctly access the token_required_api, you need to insert the token
#previously obtained during login in the Authetication (using the Authentication Baerer).
#Remember to check the result, if the resault is 403, then you should move the user to the
#login page so that he can authenticate again to obtain a new token.
def token_required_api(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify(message="Token is missing."), 403
        try:
            token=token.split()[1]
            data = jwt.decode(token, current_app.config.get('SECRET_KEY'), 'HS256')
            current_user = User.query.filter_by(name=data['name']).first()
        except jwt.ExpiredSignatureError:
            return jsonify(message="Token has expired."), 403
        except jwt.InvalidTokenError:
            return jsonify(message="Invalid token."),403

        return f(current_user, *args, **kwargs)
    return decorated
