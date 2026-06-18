from stockquant.persistence.repository import delete_chat_messages, list_chat_sessions
from stockquant.persistence.models import _default_db_url

db_url = _default_db_url()
print(f"DB URL: {db_url}")

sessions = list_chat_sessions(db_url)
print(f"Found {len(sessions)} sessions")

for sess in sessions:
    sess_id = sess["id"]
    print(f"Deleting session: {sess_id}")
    delete_chat_messages(db_url, sess_id)

print("Done!")
