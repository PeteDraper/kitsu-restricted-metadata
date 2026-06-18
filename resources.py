from flask import jsonify
from flask_restful import Resource
from flask_jwt_extended import jwt_required
from zou.app.services import persons_service

class HealthResource(Resource):
    @jwt_required()
    def get(self):
        persons_service.check_admin_permissions()
        return jsonify({
            "status": "ok",
            "plugin": "restricted-metadata"
        })

routes = [
    ("/health", HealthResource),
]
