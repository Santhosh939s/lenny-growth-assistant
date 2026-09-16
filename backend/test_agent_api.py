import httpx
import json

base_url = "http://127.0.0.1:8000/api/sessions"

def test_agent():
    print("1. Creating session...")
    res = httpx.post(f"{base_url}/", json={"title": "Agent Test"})
    if res.status_code != 201:
        print(f"Failed to create session: {res.text}")
        return
        
    session_id = res.json()["id"]
    print(f"Session created: {session_id}")
    
    print("\n2. Sending grounded question...")
    payload = {"role": "user", "content": "What is product market fit according to Lenny?"}
    res = httpx.post(f"{base_url}/{session_id}/messages", json=payload, timeout=300.0)
    
    if res.status_code == 200:
        data = res.json()
        print(f"\nResponse from {data.get('provider')}:")
        print(data["message"]["content"])
        
        print("\nSources:")
        for src in data.get("sources", []):
            print(f"- {src['title']} (Guest: {src['guest']}) - Sim: {src['similarity']:.4f}")
    else:
        print(f"Failed to send message: {res.text}")

if __name__ == "__main__":
    test_agent()
