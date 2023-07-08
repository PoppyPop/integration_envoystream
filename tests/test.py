import jwt

print(
    jwt.decode(
        "eyJraWQiOiI3ZDEwMDA1ZC03ODk5LTRkMGQtYmNiNC0yNDRmOThlZTE1NmIiLCJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9.eyJhdWQiOiIxMjIxMjUwOTczMzEiLCJpc3MiOiJFbnRyZXoiLCJlbnBoYXNlVXNlciI6Im93bmVyIiwiZXhwIjoxNzIwMzg4NzI5LCJpYXQiOjE2ODg4NTI3MjksImp0aSI6ImYxYmVkY2EzLWEzYTgtNDA3YS05MGRjLWY4YjY1OTUzNDU5NyIsInVzZXJuYW1lIjoic2t5dGVwQGdtYWlsLmNvbSJ9.ipq0ig2W3edW8u3Sq4PuJH3kx1HMLrC879yOwUrUnZKAry7sW_U13unjvfzhu0-wQEC7NpUOcXkAF4Fx3q2_cQ",
        options={"verify_signature": False},
    )["exp"]
)
