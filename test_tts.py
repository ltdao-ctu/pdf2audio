import re
from playwright.sync_api import sync_playwright, TimeoutError
import time

def parse_scenario(file_path):
    """Đọc file kịch bản và trả về dictionary các thông số"""
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # SỬA Ở ĐÂY: Thêm chữ 'r' vào trước chuỗi regex
    def get_val(key):
        match = re.search(fr"{key}:\s*(.*)", text)
        return match.group(1).strip() if match else ""

    # SỬA Ở ĐÂY: Thêm chữ 'r' vào trước chuỗi regex
    transcript_match = re.search(r"TTS_TRANSCRIPT:\s*(.*)", text, re.DOTALL)
    transcript = transcript_match.group(1).strip() if transcript_match else ""

    
    return {
        "scene": get_val("TTS_SCENE"),
        "context": get_val("TTS_CONTEXT"),
        "profile": get_val("AUDIO_PROFILE"),
        "voice": get_val("TTS_VOICE"),
        "style": get_val("DIRECTOR_STYLE"),
        "pace": get_val("DIRECTOR_PACE"),
        "accent": get_val("DIRECTOR_ACCENT"),
        "transcript": transcript
    }

def select_dropdown1(page, label, value):
    """Hàm chọn dropdown đa năng"""
    try:
        # Click mở dropdown
        page.locator(f'div:has-text("{label}")').locator('div[role="combobox"]').first.click()
        time.sleep(0.5)
        # Chọn giá trị
        page.get_by_role("option", name=value, exact=True).first.click()
        print(f"✔ Đã chọn {label}: {value}")
    except:
        print(f"⚠ Không tìm thấy hoặc không thể chọn {label}: {value}")


def select_dropdown(page, label, value):
    """Hàm chọn dropdown bằng cách tìm nhãn và click danh sách hiện ra"""
    try:
        # 1. Tìm cái nút (hoặc thẻ div) có chứa chữ label (ví dụ: Style, Pace, Accent) và click để mở menu
        # Chúng ta dùng locator chứa label rồi tìm phần tử 'mat-select' hoặc thẻ có vai trò dropdown
        print(f"Đang tìm dropdown cho: {label}...")
        
        # Tìm container chứa label đó rồi click vào phần tử tương tác (div/button) bên cạnh
        dropdown_container = page.locator(f'//div[contains(text(), "{label}")]/following-sibling::*').first
        dropdown_container.click()
        time.sleep(1) # Đợi menu xổ xuống
        
        # 2. Tìm giá trị trong menu (ví dụ: Empathetic, Natural, Neutral)
        # Click trực tiếp vào phần tử có text đó
        page.get_by_text(value, exact=True).first.click()
        print(f"✔ Đã chọn {label}: {value}")
        
    except Exception as e:
        print(f"⚠ Lỗi khi chọn {label}: {value}. Chi tiết: {e}")


def run_tts_automation(config):
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = browser.contexts[0].pages[0]
        
        print("Đang truy cập AI Studio...")
        page.goto("https://aistudio.google.com/generate-speech", wait_until="networkidle")
        time.sleep(3)

        # 1. Click vào "The Master Storyteller" để vào giao diện chính
        print("Đang vào dự án 'The Master Storyteller'...")
        try:
            # Tìm thẻ có chứa chữ "The Master Storyteller" và click vào
            page.get_by_text("The Master Storyteller").first.click()
            time.sleep(3) # Chờ giao diện chính load xong
        except Exception:
            print("⚠ Không thấy hoặc đã vào rồi, tiếp tục...")

        # 2. Điền các thông số từ config
        print("Đang điền thông tin kịch bản...")
        page.locator('textarea[aria-label="Scene"]').fill(config["scene"])
        page.locator('textarea[aria-label*="ample"]').fill(config["context"])

        # 3. Mở bảng Speaker Settings (giữ nguyên logic cũ)
        page.locator('button', has_text="Speaker").first.click()
        time.sleep(1)

        # Cấu hình Style, Pace, Accent
        select_dropdown(page, "Style", config["style"])
        select_dropdown(page, "Pace", config["pace"])
        select_dropdown(page, "Accent", config["accent"])
        
        # Audio Profile
        page.locator('textarea').first.fill(config["profile"])
        
        # Chọn giọng
        page.get_by_role("textbox", name="Search voices").fill(config["voice"])
        page.get_by_text(config["voice"], exact=True).first.click()
        
        # Đóng bảng
        page.locator('button[aria-label*="Close"]').first.click()
        time.sleep(1)

        # 4. Nhập kịch bản và Run
        page.locator('textarea').last.fill(config["transcript"])
        page.locator('button', has_text="Run").first.click()

        # 5. Download
        with page.expect_download(timeout=180000) as download_info:
            page.locator('button[aria-label="Download audio"]').wait_for(state="visible")
            page.locator('button[aria-label="Download audio"]').click()
        
        download_info.value.save_as(f"podcast_{config['voice']}.wav")
        print("🎉 Xong! Đã lưu file.")
        browser.disconnect()

if __name__ == "__main__":
    # Chỉ cần thay đổi tên file ở đây để chạy kịch bản mới
    my_config = parse_scenario("kich_ban.txt")
    run_tts_automation(my_config)