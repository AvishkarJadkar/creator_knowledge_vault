import os
import sys
from app import app
from extensions import db
from models import User

os.environ["FLASK_ENV"] = "testing"
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False

with app.test_client() as client:
    with app.app_context():
        u = User.query.first()
        if not u:
            u = User(name="Test", email="test@test.com")
            u.set_password("password")
            db.session.add(u)
            db.session.commit()
        user_id = u.id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    # Test GET settings page where 500 might occur
    print("Fetching /settings...")
    response = client.get("/settings")
    print("Status:", response.status_code)
    if response.status_code == 500:
        print("500 ERROR CAUSE:")
        print(response.data.decode("utf-8"))
