from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app.models.user import User

def role_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            username = get_jwt_identity()
            user = User.query.filter_by(username=username).first()
            if not user or user.role not in allowed_roles:
                return jsonify({
                    "error": "FORBIDDEN",
                    "message": f"User does not have required permissions: {allowed_roles}"
                }), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
