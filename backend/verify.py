import httpx

client = httpx.Client(base_url="http://127.0.0.1:8000/api/sessions")

# Create Session A and Session B
s1 = client.post("/", json={"title": "Session A"}).json()
s2 = client.post("/", json={"title": "Session B"}).json()

# Add messages
client.post(f"/{s1['id']}/messages", json={"role": "user", "content": "Hello from A"})
client.post(f"/{s2['id']}/messages", json={"role": "user", "content": "Hello from B"})

# Verify Isolation
resp1 = client.get(f"/{s1['id']}").json()
resp2 = client.get(f"/{s2['id']}").json()

a_isolated = (len(resp1["messages"]) == 1 and resp1["messages"][0]["content"] == "Hello from A")
b_isolated = (len(resp2["messages"]) == 1 and resp2["messages"][0]["content"] == "Hello from B")

print(f"Session A Isolated: {a_isolated}")
print(f"Session B Isolated: {b_isolated}")

# Delete Session A
client.delete(f"/{s1['id']}")

# Verify Deletion
del_resp = client.get(f"/{s1['id']}")
print(f"Session A Deleted (404 expected): {del_resp.status_code == 404}")
