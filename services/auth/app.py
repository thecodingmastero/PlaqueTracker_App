from flask import Flask, request, jsonify
import jwt
import datetime

app = Flask(__name__)
SECRET = 'dev-secret-change-me'

# prototype user store
USERS = {
    'alice@example.com': {'password': 'password', 'roles': ['user']},
    'doc@example.com': {'password': 'docpass', 'roles': ['user', 'clinician']}
}


@app.route('/v1/token', methods=['POST'])
def token():
    data = request.get_json(force=True)
    email = data.get('email')
    pwd = data.get('password')
    user = USERS.get(email)
    if not user or user['password'] != pwd:
        return jsonify({'error': 'invalid'}), 401
    payload = {'sub': email, 'roles': user['roles'], 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=4)}
    token = jwt.encode(payload, SECRET, algorithm='HS256')
    return jsonify({'access_token': token})


def requires_role(token, role):
    try:
        p = jwt.decode(token, SECRET, algorithms=['HS256'])
        return role in p.get('roles', [])
    except Exception:
        return False


@app.route('/v1/secure', methods=['GET'])
def secure():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'missing token'}), 401
    token = auth.split(' ', 1)[1]
    if not requires_role(token, 'clinician'):
        return jsonify({'error': 'forbidden'}), 403
    return jsonify({'status': 'ok', 'role': 'clinician'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7070)
