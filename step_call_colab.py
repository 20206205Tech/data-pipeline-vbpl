import sys

import requests

import env


def main():
    payload = {}
    headers = {"accept": "application/json"}

    print(f"Đang gửi request tới: {env.WEBHOOK_OLLAMA_URL}")

    try:
        response = requests.request(
            "POST", env.WEBHOOK_OLLAMA_URL, headers=headers, data=payload
        )

        # Nếu status code >= 400 (ví dụ: 404, 500, 530...), response.ok sẽ là False
        if not response.ok:
            print(f"❌ Lỗi kết nối Webhook! Mã lỗi HTTP: {response.status_code}")
            print(f"Chi tiết phản hồi: {response.text}")
            # Báo cho GitHub Actions biết script đã thất bại và dừng chạy
            sys.exit(1)

        # Nếu thành công (status code 2xx)
        print("✅ Request thành công!")
        print(response.text)

    except requests.exceptions.RequestException as e:
        # Bắt các lỗi mạng nghiêm trọng khác (timeout, không thể phân giải tên miền...)
        print(f"❌ Lỗi mạng khi gọi Webhook: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
