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
        # Make sure there is a user
        u = User.query.first()
        if not u:
            u = User(name="Test", email="test@test.com")
            u.set_password("password")
            db.session.add(u)
            db.session.commit()
        user_id = u.id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.post("/settings/add-profile", data={
        "platform": "youtube",
        "profile_url": "https://www.youtube.com/@mkbhd",
    }, headers={"X-Requested-With": "XMLHttpRequest"})
    
    print(response.status_code)
    try:
        print(response.get_json())
    except:
        print(response.data.decode("utf-8"))
