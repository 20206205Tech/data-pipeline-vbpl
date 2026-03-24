import requests

import env


def main():
    payload = {}
    headers = {"accept": "application/json"}

    response = requests.request(
        "POST", env.WEBHOOK_OLLAMA_URL, headers=headers, data=payload
    )

    print(response.text)


if __name__ == "__main__":
    main()
