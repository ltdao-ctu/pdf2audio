import os
from google import genai
from dotenv import load_dotenv

# 1. Load các biến môi trường từ file .env
load_dotenv()

# 2. Khởi tạo client (Nó sẽ tự động tìm os.environ["GEMINI_API_KEY"])
client = genai.Client()

print("--- Danh sách các model Gemini khả dụng: ---")
try:
    for m in client.models.list():
        print(f"Name: {m.name}")
except Exception as e:
    print(f"Đã xảy ra lỗi: {e}")
    print("Vui lòng kiểm tra lại file .env hoặc API key của bạn.")

