import base64

def encode_file(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

for file in ["credentials.json", "token.json"]:
    print(f"\n{file} (base64 encoded):\n")
    print(encode_file(file))
