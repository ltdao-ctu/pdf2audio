import re
from playwright.sync_api import sync_playwright, TimeoutError
import time
import os

def find_download_button(page):
    selector_candidates = [
        'button.download-button[aria-label*="Download" i]',
        'button[aria-label="Download"]',
        'button[mattooltip*="Download" i]',
        'button:has-text("download")',
        'button:has-text("Download")',
        'button[aria-label*="download" i]',
        'button[title*="download" i]',
        'button[aria-label*="tải xuống" i]',
        'button[title*="tải xuống" i]',
    ]

    for selector in selector_candidates:
        locator = page.locator(selector).first
        try:
            if locator.count() > 0 and locator.is_visible():
                return locator
        except Exception:
            continue

    try:
        locator = page.locator('button').filter(has_text='download').first
        if locator.count() > 0 and locator.is_visible():
            return locator
    except Exception:
        pass

    return None


def wait_for_download_button(page, timeout=30000):
    start = time.time()
    while time.time() - start < timeout / 1000:
        locator = find_download_button(page)
        if locator is not None:
            return locator
        time.sleep(0.5)

    raise TimeoutError("Không tìm thấy nút download bằng các selector chuẩn")


def wait_for_download_button_with_status(page, timeout=180000):
    print("Đang chờ UI hiển thị nút download...")
    start = time.time()
    last_status = 0

    while time.time() - start < timeout / 1000:
        locator = find_download_button(page)
        if locator is not None:
            return locator

        elapsed = int(time.time() - start)
        if elapsed - last_status >= 5:
            print(f"Đang tạo âm thanh... đã chờ {elapsed}s")
            last_status = elapsed

        time.sleep(1)

    raise TimeoutError("Hết thời gian chờ nút download")


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
    print(f"Đang tìm dropdown cho: {label}...")
    
    strategies = [
        
        # Strategy 1: Tìm bằng aria-label
        lambda: (
            page.locator(f'[aria-label*="{label}"]').first.click(),
            time.sleep(0.5),
            page.get_by_text(value, exact=True).first.click()
        ),
        
        # Strategy 2: Tìm label và click phần tử sibling
        lambda: (
            page.locator(f'//div[contains(text(), "{label}")]/following-sibling::*[contains(@role, "combobox") or contains(@class, "mat-select")]').first.click(),
            page.get_by_role("option", name=value, exact=True).first.click()
        ),
        
        # Strategy 3: Tìm label và click trên button/div gần đó
        lambda: (
            page.locator(f'//label[contains(text(), "{label}")]/following-sibling::*[contains(@role, "button")]').first.click(),
            time.sleep(0.5),
            page.get_by_text(value, exact=True).first.click()
        ),
        
        
        
        # Strategy 4: Tìm bằng placeholder hoặc title
        lambda: (
            page.locator(f'//div[contains(text(), "{label}")]/preceding-sibling::input | //div[contains(text(), "{label}")]/following-sibling::input').first.click(),
            time.sleep(0.5),
            page.get_by_text(value, exact=True).first.click()
        ),
        
        # Strategy 5: Click vào mat-select-value
        lambda: (
            page.locator(f'//span[contains(text(), "{label}")]/ancestor::mat-form-field//mat-select').first.click(),
            time.sleep(0.5),
            page.get_by_text(value, exact=True).first.click()
        ),
    ]
    
    for i, strategy in enumerate(strategies, 1):
        try:
            strategy()
            print(f"✔ Đã chọn {label}: {value} (Strategy {i})")
            return
        except Exception as e:
            print(f"  Strategy {i} thất bại: {str(e)[:60]}")
    
    print(f"⚠ Không thể chọn {label}: {value} sau khi thử {len(strategies)} cách")


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

        # 3. Mở bảng Speaker Settings
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
        print("Đang gửi yêu cầu tạo âm thanh...")
        page.locator('button', has_text="Run").first.click()
        
        # --- THÊM LOGIC CHỜ Ở ĐÂY ---
        print("Đã click Run, đang đợi hệ thống xử lý...")
        stop_button = page.locator('button', has_text="Stop").first
        
        try:
            # Chờ 5s để đảm bảo UI kịp cập nhật từ Run sang Stop
            stop_button.wait_for(state="visible", timeout=5000)
        except Exception:
            pass # Bỏ qua nếu mạng nhanh, xử lý xong trước cả khi thấy nút Stop
            
        print("Đang tạo âm thanh (Chờ nút Stop chuyển thành Run)...")
        # Ép Playwright chờ tối đa 3 phút (180000ms) cho đến khi nút Stop biến mất
        stop_button.wait_for(state="hidden", timeout=180000)
        print("Đã tạo xong! Trạng thái đã chuyển về Run.")
        # ----------------------------


        # 5. Download
        download_button = wait_for_download_button_with_status(page)
        print("Tìm thấy nút download, đang bắt đầu tải file...")
        with page.expect_download(timeout=180000) as download_info:
            download_button.scroll_into_view_if_needed()
            download_button.click(force=True)

        # --- SỬA Ở ĐÂY ---
        # Lấy tên file gốc (bỏ đuôi .txt) để làm tên file âm thanh
        script_filename = os.path.basename(config["script_path"]) 
        script_name_without_ext = os.path.splitext(script_filename)[0]
        
        # Lưu file với tên kịch bản
        output_filename = f"{script_name_without_ext}.wav"
        download_info.value.save_as(output_filename)
        
        print(f"🎉 Xong! Đã lưu file: {output_filename}")
        browser.close()

if __name__ == "__main__":
    # Khai báo tên file kịch bản
    script_path = "kich_ban.txt" 
    
    my_config = parse_scenario(script_path)
    # Lưu lại đường dẫn file vào config để dùng lúc lưu file
    my_config["script_path"] = script_path 
    
    run_tts_automation(my_config)

