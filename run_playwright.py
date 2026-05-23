from playwright.sync_api import sync_playwright, TimeoutError
import time

def automate_tts_in_chunks(voice, transcript):
    # Cắt kịch bản thành nhiều phần
    chunks = chunk_text(transcript, max_length=2000)
    print(f"Kịch bản đã được chia thành {len(chunks)} phần nhỏ.")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()

        tts_url = "https://aistudio.google.com/generate-speech/" # Cập nhật URL thực tế
        if tts_url not in page.url:
            page.goto(tts_url)

        # Các Selectors (CẦN F12 ĐỂ LẤY CHÍNH XÁC NHƯ ĐÃ HƯỚNG DẪN)
        text_area_selector = 'textarea[placeholder="Enter text..."]' 
        dropdown_selector = 'button[aria-label="Select voice"]'
        generate_btn_selector = 'button:has-text("Generate")'
        download_btn_selector = 'button[aria-label="Download audio"]'

        # Chọn Giọng đọc (Chỉ cần chọn 1 lần ở đầu)
        page.wait_for_selector(dropdown_selector)
        page.click(dropdown_selector)
        page.click(f'text="{voice}"')
        print(f"Đã thiết lập giọng đọc: {voice}")

        # Lặp qua từng phần văn bản
        for index, chunk in enumerate(chunks):
            part_num = index + 1
            print(f"\n--- Đang xử lý Phần {part_num}/{len(chunks)} ---")
            print(f"Độ dài: {len(chunk)} ký tự")

            try:
                # 1. Xóa nội dung cũ và nhập phần mới
                page.fill(text_area_selector, "") # Xóa trắng
                page.fill(text_area_selector, chunk) # Nhập text mới
                
                # Chờ một nhịp nhỏ để UI Google kịp nhận diện text thay đổi
                time.sleep(1) 

                # 2. Bấm Generate
                page.click(generate_btn_selector)
                print("Đang render âm thanh...")

                # 3. Chờ tải file
                with page.expect_download(timeout=180000) as download_info:
                    # Đợi nút Download xuất hiện (có thể mất thời gian tùy độ dài)
                    page.wait_for_selector(download_btn_selector, timeout=180000)
                    page.click(download_btn_selector)

                # 4. Lưu file theo số thứ tự
                download = download_info.value
                file_name = f"podcast_{voice}_part_{part_num:02d}.wav"
                download.save_as(file_name)
                print(f"-> Đã lưu thành công: {file_name}")

            except TimeoutError:
                print(f"Lỗi timeout ở Phần {part_num}. Có thể do server phản hồi chậm.")
            except Exception as e:
                print(f"Lỗi không xác định ở Phần {part_num}: {e}")

        print("\nHOÀN TẤT TOÀN BỘ KỊCH BẢN!")
        browser.disconnect()