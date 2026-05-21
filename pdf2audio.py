import mimetypes
import os
import re
import struct
import time
from google import genai
from google.genai import types

# Tự động nạp cấu hình API Key từ file .env bí mật của bạn
from dotenv import load_dotenv
load_dotenv()

def save_binary_file(file_name, data):
    """Lưu dữ liệu âm thanh dạng binary ra file kết quả."""
    with open(file_name, "wb") as f:
        f.write(data)
    print(f"-> Đã tạo xong phân đoạn âm thanh: {file_name}")

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Xử lý định dạng mã hóa và tạo header tiêu chuẩn cho file WAV."""
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16, 1,
        num_channels, sample_rate, byte_rate, block_align,
        bits_per_sample, b"data", data_size
    )
    return header + audio_data

def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
    """Phân tích các thông số kỹ thuật âm thanh đầu ra từ API."""
    bits_per_sample = 16
    rate = 24000
    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try: rate = int(param.split("=", 1)[1])
            except (ValueError, IndexError): pass
        elif param.startswith("audio/L"):
            try: bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError): pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}

def pipeline_generate_podcast():
    """Luồng xử lý chính: Đọc PDF -> Biên kịch kịch bản -> Chuyển đổi TTS thành Audiobook."""
    # Khởi tạo kết nối với Google GenAI (Tự nhặt biến GEMINI_API_KEY từ file .env)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Lỗi: Không tìm thấy GEMINI_API_KEY trong file .env hoặc hệ thống!")
        
    client = genai.Client(api_key=api_key)
    
    # Định nghĩa file sách PDF đầu vào của bạn
    pdf_file_path = "book_input.pdf"
    
    if not os.path.exists(pdf_file_path):
        raise FileNotFoundError(
            f"Lỗi: Không tìm thấy file '{pdf_file_path}' trong thư mục dự án.\n"
            f"Vui lòng chạy lệnh copy file sách của bạn vào đây trước khi chạy script."
        )

    # =========================================================================
    # BƯỚC 1: TẢI FILE PDF LÊN GOOGLE FILE API
    # =========================================================================
    print(f"1. Đang tải file PDF '{pdf_file_path}' lên máy chủ đám mây của Google...")
    uploaded_file = client.files.upload(file=pdf_file_path)
    print(f"-> Tải lên thành công! ID file tạm thời: {uploaded_file.name}")
    
    # Chờ Google xử lý cấu trúc và text hóa file PDF
    print("-> Đang chờ hệ thống Google phân tích dữ liệu PDF...")
    while uploaded_file.state.name == "PROCESSING":
        time.sleep(2)
        uploaded_file = client.files.get(name=uploaded_file.name)
        
    if uploaded_file.state.name == "FAILED":
        raise Exception("Lỗi nghiêm trọng: Google xử lý file PDF này thất bại!")
        
    print("-> Sách PDF đã được xử lý xong và sẵn sàng để phân tích.")

    # =========================================================================
    # BƯỚC 2: DÙNG GEMINI 1.5 PRO ĐỌC HIỂU SÁCH VÀ BIÊN KỊCH PODCAST
    # =========================================================================
    prompt_viet_kich_ban = """
    Bạn là một chuyên gia biên kịch kịch bản kiêm kỹ sư tối ưu hóa dữ liệu đầu vào cho hệ thống AI Voice (TTS). Nhiệm vụ của bạn là dựa vào tài liệu/sách PDF được đính kèm để viết một kịch bản kịch tính hoàn chỉnh.

    Hãy thực hiện quy trình theo các bước sau và xuất ra văn bản thuần, không định dạng markdown (không dùng dấu sao, không bọc trong khung code block):

    1. TỰ PHÂN TÍCH THỂ LOẠI & THIẾT LẬP THÔNG SỐ:
    Hãy tự đọc tài liệu PDF đính kèm để xác định thể loại sách, sau đó sinh ra các thông số cấu hình bằng tiếng Anh theo cấu trúc chính xác sau (giữ nguyên các từ khóa bằng tiếng Anh):

    AUDIO_PROFILE: [Mô tả giọng đọc phù hợp]
    DIRECTOR_STYLE: [Chọn: Whisper hoặc Normal hoặc Dramatic]
    DIRECTOR_PACE: [Chọn: The Drift hoặc Normal hoặc Fluent]
    DIRECTOR_ACCENT: [Chọn: British (GB) hoặc American (US)]
    TTS_SCENE: [Mô tả bối cảnh không gian bằng 1 câu tiếng Anh]
    TTS_CONTEXT: [Mô tả phong cách đọc bằng tiếng Anh]

    2. VIẾT KỊCH BẢN (Bắt đầu bằng từ khóa TTS_TRANSCRIPT):
    TTS_TRANSCRIPT:
    [Viết nội dung kịch bản phát thanh tại đây dựa theo nội dung sách PDF. Tỷ lệ 75% tóm tắt cốt lõi, 25% đan xen nhận xét/review cá nhân của bạn dưới góc xưng "Tôi" và "Các bạn". Tự động chèn các thẻ cảm xúc trong ngoặc vuông như [description], [sensory], [mystery], [tension], [emotional]... vào trước các câu văn tương ứng. Tuyệt đối KHÔNG chèn ký hiệu trích dẫn nguồn hoặc số trang như "PDF+4", "[1]"].
    """
    
    print("2. Đang yêu cầu Gemini 1.5 Pro đọc hiểu toàn bộ cuốn sách và dựng kịch bản...")
    script_response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=[uploaded_file, prompt_viet_kich_ban]
    )
    
    generated_script = script_response.text
    print("--- KỊCH BẢN ĐÃ ĐƯỢC AI DỰNG XONG ---")
    
    # Ghi lại file nháp để bạn có thể mở ra đọc nội dung chữ chữ nếu muốn
    with open("generated_script_debug.txt", "w", encoding="utf-8") as f:
        f.write(generated_script)
    print("-> Đã lưu bản nháp kịch bản chữ tại: generated_script_debug.txt")

    # Dọn dẹp: Xóa file PDF khỏi bộ nhớ tạm của Google sau khi đã khai thác xong dữ liệu
    client.files.delete(name=uploaded_file.name)

    # =========================================================================
    # BƯỚC 3: TỰ ĐỘNG BÓC TÁCH (PARSE) KỊCH BẢN VÀ THIẾT LẬP GIỌNG ĐỌC AI VOICE
    # =========================================================================
    data = {}
    keywords = {
        "audio_profile": r"AUDIO_PROFILE:\s*(.*)",
        "style": r"DIRECTOR_STYLE:\s*(.*)",
        "pace": r"DIRECTOR_PACE:\s*(.*)",
        "accent": r"DIRECTOR_ACCENT:\s*(.*)",
        "scene": r"TTS_SCENE:\s*(.*)",
        "context": r"TTS_CONTEXT:\s*(.*)",
        "transcript": r"TTS_TRANSCRIPT:\s*([\s\S]*)"
    }
    
    for key, pattern in keywords.items():
        match = re.search(pattern, generated_script)
        if match:
            data[key] = match.group(1).strip()
        else:
            data[key] = ""
            
    if not data["transcript"]:
        print("Lỗi hệ thống: AI phản hồi không đúng cấu trúc kịch bản yêu cầu. Không thể bóc tách văn bản để đọc!")
        return

    # Lắp ghép dữ liệu cấu hình vào prompt xử lý âm thanh đặc chủng cho mô hình Flash-TTS
    prompt_tts = f"""Read the following transcript based on the audio profile and director's note.

# Audio Profile
{data['audio_profile']}

# Director's note
Style: {data['style']}. Pace: {data['pace']}. Accent: {data['accent']}.

## Scene:
{data['scene']}

## Sample Context:
{data['context']}

## Transcript:
{data['transcript']}"""

    # =========================================================================
    # BƯỚC 4: STREAM DỮ LIỆU ÂM THANH VÀ XUẤT RA FILE AUDIO BOOK
    # =========================================================================
    print("3. Đang chuyển giao kịch bản sang mô hình Gemini Flash TTS để chuyển thành giọng nói...")
    
    contents_tts = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt_tts)],
        ),
    ]
    
    generate_content_config = types.GenerateContentConfig(
        temperature=0.5,
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
            )
        ),
    )

    file_index = 0
    # Chạy cơ chế Stream nhận dữ liệu âm thanh trả về từng đợt để tối ưu bộ nhớ cho điện thoại
    for chunk in client.models.generate_content_stream(
        model="gemini-3.1-flash-tts-preview", 
        contents=contents_tts, 
        config=generate_content_config,
    ):
        if chunk.parts is None:
            continue
        if chunk.parts[0].inline_data and chunk.parts[0].inline_data.data:
            file_name = f"podcast_pdf_part_{file_index}"
            file_index += 1
            inline_data = chunk.parts[0].inline_data
            data_buffer = inline_data.data
            file_extension = mimetypes.guess_extension(inline_data.mime_type)
            
            if file_extension is None:
                file_extension = ".wav"
                data_buffer = convert_to_wav(inline_data.data, inline_data.mime_type)
            
            save_binary_file(f"{file_name}{file_extension}", data_buffer)
            
    print("\n🎉 XIN CHÚC MỪNG! Quy trình chuyển đổi toàn bộ sách PDF thành Audiobook đã hoàn thành xuất sắc!")

if __name__ == "__main__":
    pipeline_generate_podcast()

